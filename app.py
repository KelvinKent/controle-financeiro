import streamlit as st
import pandas as pd
import plotly.express as px
import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).parent))

from modules.db import (
    db_exists, get_meses, get_mes, upsert_mes, get_lancamentos,
    add_lancamento, update_lancamento, delete_lancamento, get_config, set_config,
    resumo_mes, CATEGORIAS, CARTOES, SUBTIPOS_SANTANDER, CORES_CARTAO,
    get_fixos, load_sheet, save_sheet, aplicar_fixos_ao_mes,
    criar_grupo_parcelamento, get_grupos_ativos, cancelar_parcelas_restantes,
    _proximo_mes, get_orcamentos, set_orcamento, delete_orcamento, calcular_divisao_mes,
    fazer_backup, listar_backups,
)

MES_LABELS = {
    "2026-07": "Julho/2026", "2026-08": "Agosto/2026", "2026-09": "Setembro/2026",
    "2026-10": "Outubro/2026", "2026-11": "Novembro/2026", "2026-12": "Dezembro/2026",
}


def badge_cartao(cartao: str, subtipo: str = None) -> str:
    if cartao == "Itaú":
        bg, fg, label = "#FF6B00", "#ffffff", "Itaú"
    elif cartao == "C6":
        bg, fg, label = "#000000", "#ffffff", "C6"
    elif cartao == "Santander" and subtipo == "Físico":
        bg, fg, label = "#A80000", "#ffffff", "Santander Físico"
    else:
        bg, fg, label = "#EC0000", "#ffffff", "Santander"
    s = (f"background:{bg};color:{fg};padding:2px 8px;border-radius:4px;"
         f"font-size:12px;font-weight:600;display:inline-block;white-space:nowrap")
    return f'<span style="{s}">{label}</span>'


def _fmt_desc(desc) -> str:
    """Normaliza a exibição da descrição: se estiver toda em maiúsculas
    (ex.: vindo de print de fatura), converte para formato Título.
    Não altera descrições já com capitalização própria."""
    s = str(desc) if desc is not None else ""
    letras = [c for c in s if c.isalpha()]
    if letras and all(c.isupper() for c in letras):
        return s.title()
    return s


def _mes_padrao(meses: list) -> str:
    hoje = date.today()
    prox = f"{hoje.year+1}-01" if hoje.month == 12 else f"{hoje.year}-{hoje.month+1:02d}"
    return prox if prox in meses else (meses[0] if meses else "2026-07")


st.set_page_config(
    page_title="Controle Financeiro",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _check_password() -> bool:
    """Gate de autenticação. Ativo apenas quando APP_PASSWORD está definida
    (variável de ambiente ou st.secrets). Em ambiente local sem senha, libera."""
    import os as _os
    senha_correta = _os.environ.get("APP_PASSWORD", "")
    if not senha_correta:
        try:
            senha_correta = st.secrets["APP_PASSWORD"]
        except Exception:
            senha_correta = ""
    # Sem senha configurada → acesso livre (uso local)
    if not senha_correta:
        return True
    if st.session_state.get("_autenticado"):
        return True

    st.markdown("<div style='max-width:380px;margin:8vh auto 0'>", unsafe_allow_html=True)
    st.markdown("### 🔒 Controle Financeiro")
    st.caption("Acesso restrito. Informe a senha para continuar.")
    senha = st.text_input("Senha", type="password", label_visibility="collapsed",
                          placeholder="Senha de acesso")
    if senha:
        if senha == senha_correta:
            st.session_state["_autenticado"] = True
            st.rerun()
        else:
            st.error("Senha incorreta.")
    st.markdown("</div>", unsafe_allow_html=True)
    return False


if not _check_password():
    st.stop()

if not db_exists():
    st.title("Configuração inicial")
    st.info("Banco de dados não encontrado. Executando migração da planilha original...")
    with st.spinner("Importando dados de Julho-26 a Dezembro-26..."):
        try:
            from modules.migration import migrar
            total = migrar()
            st.success(f"Migração concluída! {total} lançamentos importados.")
            st.rerun()
        except Exception as e:
            st.error(f"Erro na migração: {e}")
            st.stop()

meses_disponiveis = get_meses()

# Backup automático diário — uma vez por sessão
if db_exists() and not st.session_state.get("_backup_feito"):
    from datetime import datetime as _dt
    backups = listar_backups()
    _hoje = _dt.now().strftime("%Y%m%d")
    _backup_hoje = any(_hoje in b.name for b in backups)
    if not _backup_hoje:
        fazer_backup()
    st.session_state["_backup_feito"] = True

if "mes_selecionado" not in st.session_state:
    st.session_state.mes_selecionado = _mes_padrao(meses_disponiveis)

with st.sidebar:
    st.markdown("### 💰 Controle Financeiro")
    st.divider()
    labels = [MES_LABELS.get(m, m) for m in meses_disponiveis]
    idx = meses_disponiveis.index(st.session_state.mes_selecionado) if st.session_state.mes_selecionado in meses_disponiveis else 0
    escolha = st.selectbox("Mês", options=labels, index=idx)
    st.session_state.mes_selecionado = meses_disponiveis[labels.index(escolha)]
    st.divider()
    pagina = st.radio("Navegação", ["Dashboard", "Histórico", "Lançamentos", "Parcelamentos", "Fixos", "Importar", "Configurações"], label_visibility="collapsed")
    if st.session_state.get("_autenticado"):
        st.divider()
        if st.button("🚪 Sair", use_container_width=True):
            st.session_state["_autenticado"] = False
            st.rerun()

mes = st.session_state.mes_selecionado
mes_label = MES_LABELS.get(mes, mes)
cfg = get_config()


# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
if pagina == "Dashboard":
    st.title(f"Dashboard — {mes_label}")

    dados_mes = get_mes(mes)
    sal_k = float(dados_mes.get("salario_kelvin") or 15500)
    sal_t = float(dados_mes.get("salario_thais") or 6000)

    st.markdown("#### Salários do mês")
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        novo_sal_k = st.number_input(f"Salário {cfg.get('nome_kelvin','Kelvin')} (R$)",
            value=sal_k, min_value=0.0, step=100.0, format="%.2f", key="sal_k")
    with col2:
        novo_sal_t = st.number_input(f"Salário {cfg.get('nome_thais','Thais')} (R$)",
            value=sal_t, min_value=0.0, step=100.0, format="%.2f", key="sal_t")
    with col3:
        st.write(""); st.write("")
        if st.button("💾 Salvar salários"):
            upsert_mes(mes, novo_sal_k, novo_sal_t)
            st.success("Salários atualizados!")
            st.rerun()

    sal_k, sal_t = novo_sal_k, novo_sal_t
    st.divider()

    res = resumo_mes(mes)
    total = res["total_gasto"]
    saldo = (sal_k + sal_t) - total

    def _card(label, value, nota=None, vermelho=False):
        cor = "#ff4b4b" if vermelho else "#21c354"
        nota_html = f'<div style="font-size:12px;color:{cor};margin-top:4px">{nota}</div>' if nota else ""
        return (f'<div style="padding:6px 0">'
                f'<div style="font-size:13px;color:#aaa;margin-bottom:4px">{label}</div>'
                f'<div style="font-size:1.4rem;font-weight:700">{value}</div>'
                f'{nota_html}</div>')

    c1, c2, c3, c4 = st.columns(4)
    c1.html(_card(f"Salário {cfg.get('nome_kelvin','Kelvin')}", f"R$ {sal_k:,.0f}"))
    c2.html(_card(f"Salário {cfg.get('nome_thais','Thais')}", f"R$ {sal_t:,.0f}"))
    c3.html(_card("Total gasto", f"R$ {total:,.0f}"))
    c4.html(_card("Saldo combinado", f"R$ {saldo:,.0f}",
                   nota=f"{'↑ sobra' if saldo >= 0 else '↑ falta'}", vermelho=(saldo < 0)))

    st.divider()

    lanc = get_lancamentos(mes)
    if lanc.empty:
        st.info("Nenhum lançamento neste mês ainda.")
    else:
        por_cat = lanc.groupby("categoria")["valor"].sum().sort_values(ascending=False)
        div_k = int(cfg.get("divisao_kelvin", 80))
        div_t = int(cfg.get("divisao_thais", 20))

        st.markdown(f"#### Gastos por categoria — divisão {div_k}/{div_t}")
        col_bar, col_div = st.columns([2, 1])
        with col_bar:
            df_cat = por_cat.reset_index()
            df_cat.columns = ["Categoria", "Total (R$)"]
            df_cat["Total (R$)"] = df_cat["Total (R$)"].round(2)
            fig = px.bar(df_cat, x="Categoria", y="Total (R$)",
                text=df_cat["Total (R$)"].apply(lambda v: f"R$ {v:,.0f}"),
                color="Categoria", color_discrete_sequence=px.colors.qualitative.Set2)
            fig.update_layout(showlegend=False, margin=dict(t=10, b=10), height=280)
            fig.update_traces(textposition="outside")
            st.plotly_chart(fig, use_container_width=True)
        with col_div:
            st.markdown(f"**{cfg.get('nome_kelvin','Kelvin')}** ({div_k}%)")
            total_k = total * div_k / 100
            st.metric("Responsabilidade", f"R$ {total_k:,.0f}")
            saldo_k = sal_k - total_k
            st.metric("Saldo", f"R$ {saldo_k:,.0f}", delta_color="normal" if saldo_k >= 0 else "inverse")
            st.markdown(f"**{cfg.get('nome_thais','Thais')}** ({div_t}%)")
            total_t = total * div_t / 100
            st.metric("Responsabilidade", f"R$ {total_t:,.0f}")
            saldo_t = sal_t - total_t
            st.metric("Saldo", f"R$ {saldo_t:,.0f}", delta_color="normal" if saldo_t >= 0 else "inverse")

        st.divider()
        col_top, col_export = st.columns([3, 1])
        col_top.markdown("#### Top 10 maiores gastos variáveis")
        with col_export:
            st.write("")
            if st.button("📥 Exportar Excel", use_container_width=True, help="Baixar lançamentos do mês como .xlsx"):
                import io
                from openpyxl import Workbook as _WB
                exp = lanc.copy()
                exp = exp.drop(columns=["data_lancamento"], errors="ignore")
                wb_exp = _WB()
                ws_exp = wb_exp.active
                ws_exp.title = mes_label.replace("/", "-")
                ws_exp.append(list(exp.columns))
                for r in exp.itertuples(index=False):
                    ws_exp.append(list(r))
                buf = io.BytesIO()
                wb_exp.save(buf)
                buf.seek(0)
                st.download_button("⬇️ Baixar", data=buf,
                    file_name=f"lancamentos_{mes}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        variaveis = lanc[~lanc["tipo_parcela"].isin(["FIXO"])]
        if not variaveis.empty:
            top10 = variaveis.nlargest(10, "valor")[["descricao", "categoria", "cartao", "valor"]].copy()
            top10["valor"] = top10["valor"].apply(lambda x: f"R$ {x:,.2f}")
            top10.columns = ["Descrição", "Categoria", "Cartão", "Valor"]
            st.dataframe(top10, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum lançamento variável neste mês.")

        # ── Sprint 5: Painel de divisão ───────────────────────────────────────
        st.divider()
        st.markdown("#### Divisão do mês")
        div_k = int(cfg.get("divisao_kelvin", 80))
        div_t = int(cfg.get("divisao_thais", 20))
        nome_k = cfg.get("nome_kelvin", "Kelvin")
        nome_t = cfg.get("nome_thais", "Thais")
        divisao = calcular_divisao_mes(mes, div_k, div_t)

        total_div = divisao["total"]
        k_paga = divisao["kelvin"]
        t_proporcional = divisao["thais_proporcional"]
        t_direto = divisao["thais_direto"]

        dk1, dk2, dk3, dk4 = st.columns(4)
        dk1.html(_card("Total fatura", f"R$ {total_div:,.2f}"))
        dk2.html(_card(f"{nome_k} paga ({div_k}%)", f"R$ {k_paga:,.2f}"))
        dk3.html(_card(f"{nome_t} — cota ({div_t}%)", f"R$ {t_proporcional:,.2f}"))
        dk4.html(_card(f"{nome_t} deve (direto)", f"R$ {t_direto:,.2f}",
                       nota="valor a ser ressarcido" if t_direto > 0 else None))

        if t_direto > 0:
            st.info(
                f"💡 **{nome_t}** tem R$ {t_direto:,.2f} em lançamentos marcados como dela — "
                f"valor a ressarcir para {nome_k}."
            )

        # Detalhamento dos lançamentos com Pessoa preenchida
        mask_p = lanc["pessoa_thais"].notna() & (lanc["valor_thais"].notna())
        if mask_p.any():
            df_pessoa = lanc[mask_p][["descricao", "categoria", "pessoa_thais", "valor_thais", "valor"]].copy()
            df_pessoa.columns = ["Descrição", "Categoria", "Pessoa", "Valor (Pessoa)", "Valor Total"]
            df_pessoa["Valor (Pessoa)"] = df_pessoa["Valor (Pessoa)"].apply(lambda x: f"R$ {float(x):,.2f}")
            df_pessoa["Valor Total"] = df_pessoa["Valor Total"].apply(lambda x: f"R$ {float(x):,.2f}")
            with st.expander(f"Ver detalhes dos {mask_p.sum()} lançamentos divididos"):
                st.dataframe(df_pessoa, use_container_width=True, hide_index=True)

        # ── Sprint 5: Orçamento por categoria ────────────────────────────────
        st.divider()
        st.markdown("#### Orçamento por categoria")
        orcamentos = get_orcamentos(mes)
        por_cat_real = lanc.groupby("categoria")["valor"].sum().to_dict()

        # Configurar orçamentos (expander)
        with st.expander("⚙️ Configurar orçamentos do mês"):
            st.caption("Defina um teto de gastos para cada categoria. Deixe 0 para não monitorar.")
            orc_cols = st.columns(3)
            novos_orcs = {}
            for i, cat in enumerate(CATEGORIAS):
                col = orc_cols[i % 3]
                atual = float(orcamentos.get(cat, 0))
                novo = col.number_input(cat, min_value=0.0, step=50.0, value=atual,
                                        format="%.0f", key=f"orc_{cat}")
                novos_orcs[cat] = novo
            if st.button("💾 Salvar orçamentos", use_container_width=True):
                for cat, val in novos_orcs.items():
                    if val > 0:
                        set_orcamento(mes, cat, val)
                    else:
                        delete_orcamento(mes, cat)
                st.success("Orçamentos atualizados!")
                st.rerun()

        # Barras de progresso por categoria
        cats_monitoradas = {c: v for c, v in orcamentos.items() if float(v) > 0}
        cats_sem_orcamento = [c for c in por_cat_real if c not in cats_monitoradas and float(por_cat_real[c]) > 0]

        if cats_monitoradas:
            prog_rows = ""
            for cat, limite in sorted(cats_monitoradas.items()):
                gasto = float(por_cat_real.get(cat, 0))
                limite = float(limite)
                pct = min(gasto / limite * 100, 100) if limite > 0 else 0
                over = gasto > limite
                bar_color = "#ef4444" if over else ("#f59e0b" if pct > 80 else "#4ade80")
                alerta = "⚠️" if over else ("🔶" if pct > 80 else "✅")
                prog_rows += f"""
                <tr style="border-bottom:1px solid rgba(255,255,255,0.06)">
                  <td style="padding:10px 14px;font-size:13px;width:160px">{alerta} {cat}</td>
                  <td style="padding:10px 14px;width:60%">
                    <div style="background:rgba(255,255,255,0.07);border-radius:4px;height:10px;overflow:hidden">
                      <div style="background:{bar_color};width:{pct:.1f}%;height:100%;border-radius:4px;transition:width .3s"></div>
                    </div>
                  </td>
                  <td style="padding:10px 14px;text-align:right;font-size:12px;color:#aaa;white-space:nowrap">
                    R$ {gasto:,.0f} / R$ {limite:,.0f}
                  </td>
                  <td style="padding:10px 14px;text-align:right;font-size:12px;font-weight:600;white-space:nowrap;color:{bar_color}">
                    {pct:.0f}%{'  (+R$ ' + f'{gasto-limite:,.0f})' if over else ''}
                  </td>
                </tr>"""
            st.html(f"""
            <table style="width:100%;border-collapse:collapse;font-family:inherit">
              <thead>
                <tr style="border-bottom:2px solid rgba(255,255,255,0.12)">
                  <th style="padding:8px 14px;text-align:left;font-size:11px;color:#666;text-transform:uppercase;letter-spacing:.6px">Categoria</th>
                  <th style="padding:8px 14px;text-align:left;font-size:11px;color:#666;text-transform:uppercase;letter-spacing:.6px">Progresso</th>
                  <th style="padding:8px 14px;text-align:right;font-size:11px;color:#666;text-transform:uppercase;letter-spacing:.6px">Gasto / Limite</th>
                  <th style="padding:8px 14px;text-align:right;font-size:11px;color:#666;text-transform:uppercase;letter-spacing:.6px">%</th>
                </tr>
              </thead>
              <tbody>{prog_rows}</tbody>
            </table>""")

            n_over = sum(1 for cat, lim in cats_monitoradas.items()
                         if float(por_cat_real.get(cat, 0)) > float(lim))
            if n_over:
                st.warning(f"⚠️ {n_over} categoria(s) acima do orçamento este mês.")
        else:
            st.caption("Nenhum orçamento configurado. Use o painel acima para definir limites por categoria.")

        if cats_sem_orcamento:
            nomes = ", ".join(cats_sem_orcamento)
            st.caption(f"Categorias sem orçamento com gastos: **{nomes}**")


# ══════════════════════════════════════════════════════════════════════════════
# HISTÓRICO
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "Histórico":
    st.title("Histórico")
    st.caption("Evolução de gastos ao longo dos meses disponíveis.")

    todos_meses = get_meses()
    if len(todos_meses) < 1:
        st.info("Nenhum mês com dados disponível.")
    else:
        labels_all = [MES_LABELS.get(m, m) for m in todos_meses]

        # Filtros de período
        fc1, fc2, fc3, fc4 = st.columns(4)
        idx_ini_def = 0
        idx_fim_def = len(todos_meses) - 1
        sel_ini = fc1.selectbox("De", labels_all, index=idx_ini_def, key="hist_ini")
        sel_fim = fc2.selectbox("Até", labels_all, index=idx_fim_def, key="hist_fim")
        filtro_cat_hist = fc3.multiselect("Categorias", CATEGORIAS, key="hist_cat")
        filtro_cartao_hist = fc4.multiselect("Cartão", CARTOES, key="hist_cart")

        idx_ini = labels_all.index(sel_ini)
        idx_fim = labels_all.index(sel_fim)
        if idx_ini > idx_fim:
            idx_ini, idx_fim = idx_fim, idx_ini
        meses_range = todos_meses[idx_ini: idx_fim + 1]

        # Carrega todos os lançamentos do período
        frames = []
        for m in meses_range:
            df_m = get_lancamentos(m)
            if not df_m.empty:
                df_m = df_m.copy()
                df_m["_mes"] = m
                frames.append(df_m)

        if not frames:
            st.info("Nenhum lançamento no período selecionado.")
        else:
            df_hist = pd.concat(frames, ignore_index=True)
            if filtro_cat_hist:
                df_hist = df_hist[df_hist["categoria"].isin(filtro_cat_hist)]
            if filtro_cartao_hist:
                df_hist = df_hist[df_hist["cartao"].isin(filtro_cartao_hist)]

            df_hist["Mês"] = df_hist["_mes"].map(lambda x: MES_LABELS.get(x, x))

            # ── Gráfico de linha: evolução do total mensal ────────────────────
            st.markdown("#### Evolução dos gastos totais")
            totais = df_hist.groupby(["_mes", "Mês"], sort=False)["valor"].sum().reset_index()
            totais = totais.sort_values("_mes")
            fig_line = px.line(totais, x="Mês", y="valor", markers=True,
                labels={"valor": "Total (R$)"},
                color_discrete_sequence=["#4C9BE8"])
            fig_line.update_traces(line_width=2.5, marker_size=8,
                text=totais["valor"].apply(lambda v: f"R$ {v:,.0f}"),
                textposition="top center")
            fig_line.update_layout(height=300, margin=dict(t=20, b=20),
                yaxis_title="Total (R$)", xaxis_title="")
            st.plotly_chart(fig_line, use_container_width=True)

            # ── Gráfico de barras empilhadas: categorias por mês ─────────────
            st.markdown("#### Gastos por categoria por mês")
            cat_mes = df_hist.groupby(["_mes", "Mês", "categoria"], sort=False)["valor"].sum().reset_index()
            cat_mes = cat_mes.sort_values("_mes")
            fig_stack = px.bar(cat_mes, x="Mês", y="valor", color="categoria",
                barmode="stack", labels={"valor": "Total (R$)", "categoria": "Categoria"},
                color_discrete_sequence=px.colors.qualitative.Set2)
            fig_stack.update_layout(height=350, margin=dict(t=20, b=20),
                yaxis_title="Total (R$)", xaxis_title="", legend_title="Categoria")
            st.plotly_chart(fig_stack, use_container_width=True)

            st.divider()
            col_l, col_r = st.columns(2)

            # ── Top 10 maiores gastos do período ──────────────────────────────
            with col_l:
                st.markdown("#### Top 10 maiores gastos (variáveis)")
                var_hist = df_hist[~df_hist["tipo_parcela"].isin(["FIXO"])]
                if not var_hist.empty:
                    top10 = var_hist.nlargest(10, "valor")[["descricao", "Mês", "categoria", "valor"]].copy()
                    top10["valor"] = top10["valor"].apply(lambda x: f"R$ {x:,.2f}")
                    top10.columns = ["Descrição", "Mês", "Categoria", "Valor"]
                    st.dataframe(top10, use_container_width=True, hide_index=True)
                else:
                    st.info("Nenhum gasto variável no período.")

            # ── Comparativo por categoria ─────────────────────────────────────
            with col_r:
                st.markdown("#### Comparativo por categoria")
                comp = df_hist.groupby("categoria")["valor"].agg(["sum", "mean", "count"]).reset_index()
                comp.columns = ["Categoria", "Total (R$)", "Média/mês (R$)", "Lançamentos"]
                comp["Total (R$)"] = comp["Total (R$)"].round(2)
                comp["Média/mês (R$)"] = comp["Média/mês (R$)"].round(2)
                comp = comp.sort_values("Total (R$)", ascending=False)
                st.dataframe(comp, use_container_width=True, hide_index=True)

            # ── Resumo do período ─────────────────────────────────────────────
            st.divider()
            st.markdown("#### Resumo do período")
            total_periodo = df_hist["valor"].sum()
            media_mensal = total_periodo / len(meses_range) if meses_range else 0
            mes_maior = totais.loc[totais["valor"].idxmax(), "Mês"] if not totais.empty else "—"
            mes_menor = totais.loc[totais["valor"].idxmin(), "Mês"] if not totais.empty else "—"

            def _card(label, value, nota=None, vermelho=False):
                cor = "#ff4b4b" if vermelho else "#21c354"
                nota_html = f'<div style="font-size:12px;color:{cor};margin-top:4px">{nota}</div>' if nota else ""
                return (f'<div style="padding:6px 0">'
                        f'<div style="font-size:13px;color:#aaa;margin-bottom:4px">{label}</div>'
                        f'<div style="font-size:1.4rem;font-weight:700">{value}</div>'
                        f'{nota_html}</div>')

            rs1, rs2, rs3, rs4 = st.columns(4)
            rs1.html(_card("Total no período", f"R$ {total_periodo:,.0f}"))
            rs2.html(_card("Média mensal", f"R$ {media_mensal:,.0f}"))
            rs3.html(_card("Mês mais caro", mes_maior))
            rs4.html(_card("Mês mais barato", mes_menor))


# ══════════════════════════════════════════════════════════════════════════════
# LANÇAMENTOS
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "Lançamentos":
    col_title, col_fixos = st.columns([3, 1])
    col_title.title(f"Lançamentos — {mes_label}")
    with col_fixos:
        st.write("")
        if st.button("📌 Aplicar fixos do mês", use_container_width=True):
            n = aplicar_fixos_ao_mes(mes)
            st.success(f"{n} fixo(s) adicionado(s)!" if n > 0 else "Todos os fixos já estão neste mês.")
            st.rerun()

    if "editando_id" not in st.session_state:
        st.session_state.editando_id = None
    if "form_novo_ver" not in st.session_state:
        st.session_state.form_novo_ver = 0

    def form_lancamento(prefixo, dados=None):
        """Renderiza campos do formulário. Funciona fora de st.form para reatividade."""
        d = dados or {}
        fc1, fc2 = st.columns(2)
        cartao_atual = d.get("cartao", "Santander")
        cartao_idx = CARTOES.index(cartao_atual) if cartao_atual in CARTOES else 0
        cartao = fc1.selectbox("Cartão", CARTOES, index=cartao_idx, key=f"{prefixo}_cartao")
        valor = fc2.number_input("Valor total (R$)", min_value=0.01, step=0.01, format="%.2f",
            value=float(d.get("valor") or 0.01), key=f"{prefixo}_valor")

        subtipo = None
        if cartao == "Santander":
            sub_atual = d.get("subtipo_cartao") or "Regular"
            sub_idx = SUBTIPOS_SANTANDER.index(sub_atual) if sub_atual in SUBTIPOS_SANTANDER else 0
            subtipo = st.radio("Tipo Santander", SUBTIPOS_SANTANDER, index=sub_idx,
                horizontal=True, key=f"{prefixo}_subtipo")

        descricao = st.text_input("Descrição", value=d.get("descricao", ""), key=f"{prefixo}_desc")
        fc3, fc4 = st.columns(2)
        cat_idx = CATEGORIAS.index(d["categoria"]) if d.get("categoria") in CATEGORIAS else 0
        categoria = fc3.selectbox("Categoria", CATEGORIAS, index=cat_idx, key=f"{prefixo}_cat")
        tipos = ["única", "FIXO", "ULTIMA", "parcelado"]
        tipo_idx = tipos.index(d["tipo_parcela"]) if d.get("tipo_parcela") in tipos else 0
        tipo = fc4.selectbox("Tipo", tipos, index=tipo_idx, key=f"{prefixo}_tipo")

        # Dividir — checkbox reativo (sem st.form)
        tem_pessoa = bool(d.get("pessoa_thais") and not pd.isna(d.get("pessoa_thais", "")))
        dividir = st.checkbox("Dividir", value=tem_pessoa, key=f"{prefixo}_dividir")

        pessoa = None
        val_pessoa = None
        if dividir:
            col_p1, col_p2 = st.columns(2)
            pessoa_default = d.get("pessoa_thais") or "Thais"
            if pd.isna(pessoa_default):
                pessoa_default = "Thais"
            pessoa = col_p1.text_input("Pessoa", value=str(pessoa_default), key=f"{prefixo}_pessoa")

            val_key = f"{prefixo}_valpessoa"
            auto_key = f"{prefixo}_valpessoa_auto"
            div_t = int(get_config().get("divisao_thais", 20))

            if str(pessoa).strip().lower() == "thais":
                new_auto = round(valor * div_t / 100, 2)
                prev_auto = st.session_state.get(auto_key)
                curr_val = st.session_state.get(val_key)
                # Atualiza automaticamente se: primeira vez ou usuário não mudou manualmente
                if curr_val is None or curr_val == prev_auto:
                    st.session_state[val_key] = new_auto
                st.session_state[auto_key] = new_auto
                vp_default = st.session_state.get(val_key, new_auto)
            else:
                st.session_state.pop(auto_key, None)
                vp_default = float(d.get("valor_thais") or 0.0)
                if pd.isna(vp_default):
                    vp_default = 0.0

            val_pessoa = col_p2.number_input("Valor (R$)", min_value=0.0, step=0.01,
                format="%.2f", value=vp_default, key=val_key)

        total_parc = None
        mes_inicio_parc = mes
        if tipo == "parcelado":
            pp1, pp2 = st.columns(2)
            total_parc = pp1.number_input("Total de parcelas", min_value=2, max_value=48,
                value=int(d.get("total_parcelas") or 2), step=1, key=f"{prefixo}_parc")
            meses_disp = get_meses()
            idx_mes = meses_disp.index(mes) if mes in meses_disp else 0
            labels_m = [MES_LABELS.get(m, m) for m in meses_disp]
            escolha_m = pp2.selectbox("Mês da 1ª parcela", labels_m, index=idx_mes, key=f"{prefixo}_mesinicio")
            mes_inicio_parc = meses_disp[labels_m.index(escolha_m)]

        return {
            "cartao": cartao, "subtipo": subtipo, "valor": valor, "descricao": descricao,
            "categoria": categoria, "tipo": tipo,
            "pessoa": pessoa.strip() if pessoa and str(pessoa).strip() else None,
            "val_pessoa": val_pessoa if dividir and val_pessoa else None,
            "total_parc": total_parc,
            "mes_inicio_parc": mes_inicio_parc,
        }

    def salvar_campos(campos):
        if not campos["descricao"]:
            st.error("Preencha a descrição.")
            return False
        if campos["tipo"] == "parcelado" and campos["total_parc"]:
            gid = criar_grupo_parcelamento(
                descricao=campos["descricao"], cartao=campos["cartao"],
                subtipo_cartao=campos["subtipo"], categoria=campos["categoria"],
                valor_parcela=campos["valor"], total_parcelas=campos["total_parc"],
                mes_inicio=campos["mes_inicio_parc"],
                pessoa_thais=campos["pessoa"], valor_thais=campos["val_pessoa"],
            )
            ultimo = _proximo_mes(campos["mes_inicio_parc"], campos["total_parc"] - 1)
            st.success(f"'{campos['descricao']}' criado em {campos['total_parc']}x até {ultimo}!")
        else:
            add_lancamento(
                mes_ano=mes, cartao=campos["cartao"], dono="Kelvin",
                valor=campos["valor"], descricao=campos["descricao"],
                categoria=campos["categoria"],
                valor_thais=campos["val_pessoa"], pessoa_thais=campos["pessoa"],
                tipo_parcela=campos["tipo"], total_parcelas=campos["total_parc"],
                subtipo_cartao=campos["subtipo"],
            )
            st.success(f"Lançamento '{campos['descricao']}' salvo!")
        return True

    # ── Novo lançamento (sem st.form → checkbox reativo) ──────────────────────
    ver = st.session_state.form_novo_ver
    with st.expander("➕ Novo lançamento", expanded=False):
        campos = form_lancamento(f"novo_{ver}")
        if st.button("💾 Salvar lançamento", use_container_width=True, key=f"btn_novo_{ver}"):
            if salvar_campos(campos):
                st.session_state.form_novo_ver = ver + 1
                st.rerun()

    # ── Filtros ───────────────────────────────────────────────────────────────
    st.markdown("#### Filtrar")
    fc1, fc2, fc3, fc4, fc5 = st.columns([2, 2, 1.5, 1.5, 1.5])
    filtro_cat = fc1.multiselect("Categoria", CATEGORIAS)
    filtro_tipo = fc2.multiselect("Tipo", ["única", "FIXO", "ULTIMA", "parcelado"])
    filtro_cartao = fc3.multiselect("Cartão", CARTOES)
    filtro_subtipo = fc4.multiselect("Santander", SUBTIPOS_SANTANDER)
    filtro_ordem = fc5.selectbox("Ordenar por", ["Mais recentes", "Mais antigos"])
    busca = st.text_input("Buscar descrição", placeholder="Ex: Spotify, Uber...")

    lanc = get_lancamentos(mes)
    if "subtipo_cartao" not in lanc.columns:
        lanc["subtipo_cartao"] = None

    if not lanc.empty:
        if filtro_cat:
            lanc = lanc[lanc["categoria"].isin(filtro_cat)]
        if filtro_tipo:
            lanc = lanc[lanc["tipo_parcela"].isin(filtro_tipo)]
        if filtro_cartao:
            lanc = lanc[lanc["cartao"].isin(filtro_cartao)]
        if filtro_subtipo:
            lanc = lanc[(lanc["cartao"] != "Santander") | lanc["subtipo_cartao"].isin(filtro_subtipo)]
        if busca:
            lanc = lanc[lanc["descricao"].str.contains(busca, case=False, na=False)]

    # Ordenação por data
    if not lanc.empty:
        if "data_lancamento" in lanc.columns:
            lanc["data_lancamento"] = pd.to_datetime(lanc["data_lancamento"], errors="coerce")
            lanc = lanc.sort_values("data_lancamento", ascending=(filtro_ordem == "Mais antigos"), na_position="last")
        else:
            lanc = lanc.sort_values("id", ascending=(filtro_ordem == "Mais antigos"))

    # ── Tabela de lançamentos ─────────────────────────────────────────────────
    if lanc.empty:
        st.info("Nenhum lançamento encontrado para os filtros selecionados.")
    else:
        st.markdown(f"<small style='color:#888'>{len(lanc)} lançamentos · Total: <b>R$ {lanc['valor'].sum():,.2f}</b></small>", unsafe_allow_html=True)

        # Monta HTML da tabela completa
        tipo_chip = {
            "FIXO":      ("#1a3a2a", "#4ade80", "FIXO"),
            "ULTIMA":    ("#3a1a1a", "#f87171", "ÚLTIMA"),
            "única":     ("#1a2a3a", "#60a5fa", "única"),
            "parcelado": ("#2a2a1a", "#facc15", "parcelado"),
        }
        rows_html = ""
        for i, (_, row) in enumerate(lanc.iterrows()):
            subtipo_val = row.get("subtipo_cartao")
            subtipo_str = str(subtipo_val) if subtipo_val and not pd.isna(subtipo_val) else None
            badge = badge_cartao(row["cartao"], subtipo_str)

            pessoa_val = row.get("pessoa_thais")
            valor_p = row.get("valor_thais")
            nome_p = str(pessoa_val) if pessoa_val and not pd.isna(pessoa_val) else ""
            val_p_fmt = f" · R$ {float(valor_p):,.2f}" if valor_p and not pd.isna(valor_p) else ""
            pessoa_line = (f'<div style="font-size:10px;color:#666;margin-top:1px">👤 {nome_p}{val_p_fmt}</div>'
                           if nome_p else "")

            tipo_raw = str(row["tipo_parcela"])
            tc = tipo_chip.get(tipo_raw, ("#2a2a2a", "#aaa", tipo_raw))
            chip = (f'<span style="background:{tc[0]};color:{tc[1]};padding:1px 7px;'
                    f'border-radius:3px;font-size:11px;white-space:nowrap">{tc[2]}</span>')

            parc_rest = row.get("total_parcelas")
            faltam = str(int(parc_rest)) if parc_rest and not pd.isna(parc_rest) else "—"

            valor = float(row["valor"])
            cat = str(row.get("categoria", ""))
            bg = "rgba(255,255,255,0.02)" if i % 2 == 0 else "transparent"

            rows_html += f"""
            <tr style="background:{bg};border-bottom:1px solid rgba(255,255,255,0.06)">
              <td style="padding:9px 14px;min-width:220px">
                <span style="font-weight:500;font-size:13px">{_fmt_desc(row['descricao'])}</span>&nbsp;{badge}{pessoa_line}
              </td>
              <td style="padding:9px 14px;font-size:12px;color:#aaa;white-space:nowrap">{cat}</td>
              <td style="padding:9px 14px">{chip}</td>
              <td style="padding:9px 14px;text-align:center;color:#888;font-size:13px">{faltam}</td>
              <td style="padding:9px 14px;text-align:right;font-size:13px;font-weight:600;white-space:nowrap;color:{'#4ade80' if valor < 0 else 'inherit'}">R$ {valor:,.2f}</td>
              <td style="padding:9px 14px;text-align:center;color:#444;font-size:11px">{int(row['id'])}</td>
            </tr>"""

        table_html = f"""
        <table style="width:100%;border-collapse:collapse;font-family:inherit;font-size:13px">
          <thead>
            <tr style="border-bottom:2px solid rgba(255,255,255,0.12)">
              <th style="padding:10px 14px;text-align:left;font-weight:500;color:#666;font-size:11px;text-transform:uppercase;letter-spacing:.6px">Descrição</th>
              <th style="padding:10px 14px;text-align:left;font-weight:500;color:#666;font-size:11px;text-transform:uppercase;letter-spacing:.6px">Categoria</th>
              <th style="padding:10px 14px;text-align:left;font-weight:500;color:#666;font-size:11px;text-transform:uppercase;letter-spacing:.6px">Tipo</th>
              <th style="padding:10px 14px;text-align:center;font-weight:500;color:#666;font-size:11px;text-transform:uppercase;letter-spacing:.6px">Faltam</th>
              <th style="padding:10px 14px;text-align:right;font-weight:500;color:#666;font-size:11px;text-transform:uppercase;letter-spacing:.6px">Valor</th>
              <th style="padding:10px 14px;text-align:center;font-weight:500;color:#444;font-size:10px">#</th>
            </tr>
          </thead>
          <tbody>{rows_html}</tbody>
        </table>"""
        st.html(table_html)

        # ── Painel de ações ───────────────────────────────────────────────────
        st.divider()
        if st.session_state.editando_id:
            row_ed = lanc[lanc["id"] == st.session_state.editando_id]
            if not row_ed.empty:
                row_ed = row_ed.iloc[0]
                st.markdown(f"##### ✏️ Editando: *{row_ed['descricao']}*")
                edit_ver = st.session_state.get(f"edit_ver_{st.session_state.editando_id}", 0)
                campos_ed = form_lancamento(f"edit_{st.session_state.editando_id}_{edit_ver}", dados=row_ed.to_dict())
                ce1, ce2 = st.columns(2)
                if ce1.button("💾 Salvar alterações", use_container_width=True, key="btn_salvar_ed"):
                    update_lancamento(st.session_state.editando_id,
                        cartao=campos_ed["cartao"], valor=campos_ed["valor"],
                        descricao=campos_ed["descricao"], categoria=campos_ed["categoria"],
                        tipo_parcela=campos_ed["tipo"],
                        pessoa_thais=campos_ed["pessoa"], valor_thais=campos_ed["val_pessoa"],
                        total_parcelas=campos_ed["total_parc"],
                        subtipo_cartao=campos_ed["subtipo"],
                    )
                    st.session_state.editando_id = None
                    st.rerun()
                if ce2.button("✕ Cancelar", use_container_width=True, key="btn_cancel_ed"):
                    st.session_state.editando_id = None
                    st.rerun()
            else:
                st.session_state.editando_id = None
        else:
            opcoes_ids = [int(r["id"]) for _, r in lanc.iterrows()]
            opcoes_labels = {int(r["id"]): f"#{int(r['id'])} — {r['descricao']} (R$ {float(r['valor']):,.2f})"
                             for _, r in lanc.iterrows()}
            ca1, ca2, ca3 = st.columns([4, 1, 1])
            sel_id = ca1.selectbox("Selecionar lançamento", opcoes_ids,
                                   format_func=lambda x: opcoes_labels[x], label_visibility="collapsed",
                                   placeholder="Selecione um lançamento para editar ou excluir...")
            if ca2.button("✏️ Editar", use_container_width=True):
                st.session_state.editando_id = sel_id
                st.rerun()
            if ca3.button("🗑 Excluir", use_container_width=True, type="primary"):
                delete_lancamento(sel_id)
                st.rerun()

        # ── Resumo por categoria ──────────────────────────────────────────────
        st.divider()
        st.markdown("#### Resumo por categoria")
        por_cat = lanc.groupby("categoria")["valor"].agg(["sum", "count"]).reset_index()
        por_cat.columns = ["Categoria", "Total (R$)", "Qtd"]
        por_cat["Total (R$)"] = por_cat["Total (R$)"].round(2)
        st.dataframe(por_cat.sort_values("Total (R$)", ascending=False), use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# PARCELAMENTOS
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "Parcelamentos":
    st.title("Parcelamentos em aberto")
    st.caption("Compras parceladas criadas pelo sistema. Parcelas futuras são geradas automaticamente.")

    grupos = get_grupos_ativos()
    df_lanc_all = load_sheet("lancamentos")
    if "subtipo_cartao" not in df_lanc_all.columns:
        df_lanc_all["subtipo_cartao"] = None

    if grupos.empty:
        st.info("Nenhum parcelamento ativo. Crie um lançamento do tipo 'parcelado' na aba Lançamentos.")
    else:
        ativos = grupos[grupos.get("restantes", 0) > 0] if "restantes" in grupos.columns else grupos
        st.markdown(f"**{len(ativos)} grupo(s) ativo(s)**")
        st.divider()

        MES_SHORT = {
            "2026-07": "Jul/26", "2026-08": "Ago/26", "2026-09": "Set/26",
            "2026-10": "Out/26", "2026-11": "Nov/26", "2026-12": "Dez/26",
        }

        for _, g in ativos.iterrows():
            gid = int(g["id"])
            total = int(g["total_parcelas"])
            pagas = int(g.get("pagas", 0))
            restantes = int(g.get("restantes", total - pagas))
            pct = int(pagas / total * 100) if total > 0 else 0
            valor_parc = float(g["valor_parcela"])

            sub = g.get("subtipo_cartao")
            sub_str = str(sub) if sub and not pd.isna(sub) else None
            badge = badge_cartao(str(g["cartao"]), sub_str)

            col_info, col_prog, col_acao = st.columns([2.5, 2, 1])
            with col_info:
                st.html(
                    f'<div style="padding:4px 0">'
                    f'<span style="font-weight:600;font-size:15px">{g["descricao"]}</span> {badge}'
                    f'<br><span style="font-size:12px;color:#888">{g["categoria"]} · '
                    f'R$ {valor_parc:,.2f}/mês · total R$ {valor_parc*total:,.2f}</span></div>'
                )
            with col_prog:
                st.markdown(f"**{pagas}/{total}** parcelas pagas &nbsp; `{pct}%`")
                st.progress(pct / 100)
                prox_mes = _proximo_mes(str(g["mes_inicio"]), pagas)
                prox_label = MES_SHORT.get(prox_mes, prox_mes)
                if restantes == 1:
                    st.markdown(f"🔔 **Última parcela:** {prox_label}")
                elif restantes > 0:
                    st.markdown(f"Próxima: **{prox_label}** · faltam R$ {valor_parc*restantes:,.2f}")
            with col_acao:
                st.write("")
                if restantes > 0:
                    if st.button("✅ Quitar antecipado", key=f"quit_{gid}"):
                        cancelar_parcelas_restantes(gid, mes)
                        st.success("Parcelas futuras removidas!")
                        st.rerun()
            st.divider()

    st.markdown("#### Projeção de comprometimento por mês")
    df_parc = df_lanc_all[df_lanc_all["tipo_parcela"].isin(["parcelado", "ULTIMA"])]
    if not df_parc.empty and "id_grupo" in df_parc.columns:
        df_pg = df_parc[df_parc["id_grupo"].notna()]
        if not df_pg.empty:
            proj = df_pg.groupby("mes_ano")["valor"].sum().reset_index()
            proj.columns = ["Mês", "Total parcelas (R$)"]
            proj["Total parcelas (R$)"] = proj["Total parcelas (R$)"].round(2)
            proj["Mês"] = proj["Mês"].map(lambda x: MES_LABELS.get(x, x))
            st.dataframe(proj.sort_values("Mês"), use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum parcelamento criado via sistema ainda.")
    else:
        st.info("Nenhum parcelamento criado via sistema ainda.")


# ══════════════════════════════════════════════════════════════════════════════
# FIXOS
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "Fixos":
    st.title("Gastos Fixos")
    st.caption("Lançamentos que se repetem todo mês. Edite os valores estimados aqui.")

    fixos = get_fixos(apenas_ativos=False)

    with st.expander("➕ Novo fixo", expanded=False):
        with st.form("form_fixo", clear_on_submit=True):
            ff1, ff2 = st.columns(2)
            f_cartao = ff1.selectbox("Cartão", CARTOES, key="f_cartao")
            f_desc = ff2.text_input("Descrição", key="f_desc")
            ff3, ff4 = st.columns(2)
            f_cat = ff3.selectbox("Categoria", CATEGORIAS, key="f_cat")
            f_val = ff4.number_input("Valor estimado (R$)", min_value=0.0, step=0.01, format="%.2f", key="f_val")
            ff5, ff6, ff7 = st.columns(3)
            f_divide = ff5.checkbox("Dividir?", key="f_divide")
            f_pessoa = ff6.text_input("Pessoa", value="Thais", key="f_pessoa")
            f_vt = ff7.number_input("Valor (R$)", min_value=0.0, step=0.01, format="%.2f", key="f_vt")
            if st.form_submit_button("Salvar fixo", use_container_width=True):
                df_fixos = load_sheet("fixos")
                novo_id = int(df_fixos["id"].max() + 1) if not df_fixos.empty else 1
                novo = {
                    "id": novo_id, "cartao": f_cartao, "descricao": f_desc,
                    "categoria": f_cat, "valor_estimado": f_val,
                    "pessoa_thais": f_pessoa if f_divide else None,
                    "valor_thais": f_vt if f_divide else None,
                    "ativo": True,
                }
                df_fixos = pd.concat([df_fixos, pd.DataFrame([novo])], ignore_index=True)
                save_sheet("fixos", df_fixos)
                st.success(f"Fixo '{f_desc}' adicionado!")
                st.rerun()

    if fixos.empty:
        st.info("Nenhum fixo cadastrado ainda.")
    else:
        ativos_df = fixos[fixos["ativo"] == True]
        st.markdown(f"<small style='color:#888'>{len(ativos_df)} ativos · estimativa mensal: <b>R$ {float(ativos_df['valor_estimado'].sum()):,.2f}</b></small>", unsafe_allow_html=True)

        rows_fx = ""
        for i, (_, row) in enumerate(fixos.iterrows()):
            ativo = bool(row.get("ativo", True))
            subtipo_val = row.get("subtipo_cartao")
            subtipo_str = str(subtipo_val) if subtipo_val and not pd.isna(subtipo_val) else None
            badge = badge_cartao(str(row["cartao"]), subtipo_str)
            cat = str(row.get("categoria", ""))
            val_est = float(row.get("valor_estimado") or 0)
            pt = row.get("pessoa_thais")
            vt = row.get("valor_thais")
            pessoa_info = ""
            if pt and not pd.isna(pt):
                vt_fmt = f" · R$ {float(vt):,.2f}" if vt and not pd.isna(vt) else ""
                pessoa_info = f'<div style="font-size:10px;color:#666;margin-top:1px">👤 {pt}{vt_fmt}</div>'

            status_dot = ('<span style="color:#4ade80;font-size:10px">● ativo</span>'
                          if ativo else
                          '<span style="color:#555;font-size:10px">● pausado</span>')
            bg = "rgba(255,255,255,0.02)" if i % 2 == 0 else "transparent"
            opacity = "1" if ativo else "0.45"
            rows_fx += f"""
            <tr style="background:{bg};border-bottom:1px solid rgba(255,255,255,0.06);opacity:{opacity}">
              <td style="padding:9px 14px;min-width:200px">
                <span style="font-weight:500;font-size:13px">{_fmt_desc(row['descricao'])}</span>&nbsp;{badge}{pessoa_info}
              </td>
              <td style="padding:9px 14px;font-size:12px;color:#aaa">{cat}</td>
              <td style="padding:9px 14px;text-align:right;font-size:13px;font-weight:600;white-space:nowrap">R$ {val_est:,.2f}</td>
              <td style="padding:9px 14px;text-align:center">{status_dot}</td>
              <td style="padding:9px 14px;text-align:center;color:#444;font-size:11px">{int(row['id'])}</td>
            </tr>"""

        fixos_table_html = f"""
        <table style="width:100%;border-collapse:collapse;font-family:inherit;font-size:13px">
          <thead>
            <tr style="border-bottom:2px solid rgba(255,255,255,0.12)">
              <th style="padding:10px 14px;text-align:left;font-weight:500;color:#666;font-size:11px;text-transform:uppercase;letter-spacing:.6px">Descrição</th>
              <th style="padding:10px 14px;text-align:left;font-weight:500;color:#666;font-size:11px;text-transform:uppercase;letter-spacing:.6px">Categoria</th>
              <th style="padding:10px 14px;text-align:right;font-weight:500;color:#666;font-size:11px;text-transform:uppercase;letter-spacing:.6px">Valor Est.</th>
              <th style="padding:10px 14px;text-align:center;font-weight:500;color:#666;font-size:11px;text-transform:uppercase;letter-spacing:.6px">Status</th>
              <th style="padding:10px 14px;text-align:center;font-weight:500;color:#444;font-size:10px">#</th>
            </tr>
          </thead>
          <tbody>{rows_fx}</tbody>
        </table>"""
        st.html(fixos_table_html)

        # Painel de ações
        st.divider()
        df_fixos_full = load_sheet("fixos")
        opcoes_fx = [int(r["id"]) for _, r in fixos.iterrows()]
        opcoes_fx_labels = {int(r["id"]): f"#{int(r['id'])} — {r['descricao']} ({'ativo' if bool(r.get('ativo', True)) else 'pausado'})"
                            for _, r in fixos.iterrows()}
        fa1, fa2 = st.columns([5, 1])
        sel_fx = fa1.selectbox("Selecionar fixo", opcoes_fx,
                               format_func=lambda x: opcoes_fx_labels[x], label_visibility="collapsed")
        sel_row = fixos[fixos["id"] == sel_fx].iloc[0] if sel_fx else None
        if sel_row is not None:
            esta_ativo = bool(sel_row.get("ativo", True))
            btn_label = "⏸ Pausar" if esta_ativo else "▶ Ativar"
            if fa2.button(btn_label, use_container_width=True):
                df_fixos_full.loc[df_fixos_full["id"] == sel_fx, "ativo"] = not esta_ativo
                save_sheet("fixos", df_fixos_full)
                st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# IMPORTAR
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "Importar":
    st.title("Importar via print de fatura")
    st.caption("Envie um print da sua fatura. A IA identifica o banco, extrai os lançamentos com valores e parcelas, e você revisa antes de salvar.")

    import os, base64, json as _json

    # Chave da API — prioridade: variável de ambiente > session_state
    _SECRETS_FILE = Path(__file__).parent / ".streamlit" / "secrets.toml"

    def _load_saved_key() -> str:
        if _SECRETS_FILE.exists():
            for line in _SECRETS_FILE.read_text(encoding="utf-8").splitlines():
                if line.startswith("ANTHROPIC_API_KEY"):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
        return ""

    def _outras_linhas() -> list:
        """Linhas do secrets.toml que NÃO são ANTHROPIC_API_KEY (ex.: APP_PASSWORD)."""
        if not _SECRETS_FILE.exists():
            return []
        return [ln for ln in _SECRETS_FILE.read_text(encoding="utf-8").splitlines()
                if ln.strip() and not ln.lstrip().startswith("ANTHROPIC_API_KEY")]

    def _save_key(key: str):
        _SECRETS_FILE.parent.mkdir(parents=True, exist_ok=True)
        linhas = _outras_linhas() + [f'ANTHROPIC_API_KEY = "{key}"']
        _SECRETS_FILE.write_text("\n".join(linhas) + "\n", encoding="utf-8")

    def _delete_key():
        # Remove apenas a chave da API, preservando o resto (APP_PASSWORD etc.)
        linhas = _outras_linhas()
        if linhas:
            _SECRETS_FILE.write_text("\n".join(linhas) + "\n", encoding="utf-8")
        elif _SECRETS_FILE.exists():
            _SECRETS_FILE.unlink()

    # Prioridade: variável de ambiente > arquivo salvo > session_state
    # Sempre tenta carregar do arquivo (não bloqueia por session_state vazio)
    _persisted = os.environ.get("ANTHROPIC_API_KEY", "") or _load_saved_key()
    if _persisted:
        st.session_state["_imp_api_key"] = _persisted

    _trocar = st.session_state.get("_imp_trocar", False)
    api_key = st.session_state.get("_imp_api_key", "")

    if not api_key or _trocar:
        st.session_state["_imp_trocar"] = False
        _typed = st.text_input("Chave da API Anthropic (ANTHROPIC_API_KEY)", type="password",
                               help="Cole sua chave e pressione Enter. Fica salva localmente para próximas sessões.")
        if _typed:
            _save_key(_typed)
            st.session_state["_imp_api_key"] = _typed
            api_key = _typed
            st.success("✅ Chave salva!")
    else:
        st.success("✅ Chave da API configurada e salva localmente.")
        if st.button("🔑 Trocar chave", key="trocar_chave"):
            _delete_key()
            st.session_state["_imp_api_key"] = ""
            st.session_state["_imp_trocar"] = True
            st.rerun()

    uploaded_files = st.file_uploader(
        "Prints da fatura (até 5 imagens)",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )
    if uploaded_files and len(uploaded_files) > 5:
        st.warning("Máximo de 5 imagens por vez. Apenas as 5 primeiras serão analisadas.")
        uploaded_files = uploaded_files[:5]

    col_up1, col_up2 = st.columns(2)
    mes_imp = col_up1.selectbox("Mês de destino", meses_disponiveis,
                                 index=meses_disponiveis.index(mes) if mes in meses_disponiveis else 0,
                                 format_func=lambda x: MES_LABELS.get(x, x))
    col_up2.selectbox("Cartão (será substituído pelo detectado)", CARTOES, key="imp_cartao")

    if uploaded_files:
        # Lê bytes uma vez e armazena para preview + análise
        _imgs = [{"name": f.name, "bytes": f.read(),
                  "ext": f.name.rsplit(".", 1)[-1].lower()} for f in uploaded_files]
        ncols = min(len(_imgs), 5)
        cols_prev = st.columns(ncols + [1] * (5 - ncols) if ncols < 5 else ncols)
        for col, img in zip(cols_prev, _imgs):
            col.image(img["bytes"], caption=img["name"], width=160)
    else:
        _imgs = []

    st.divider()
    _btn_disabled = not api_key or not _imgs
    _btn_tip = ("Configure a chave da API primeiro." if not api_key
                else "Envie ao menos uma imagem." if not _imgs else "")
    if _btn_tip and _btn_disabled:
        st.caption(f"⚠️ {_btn_tip}")

    if st.button("🔍 Analisar com IA", use_container_width=True, type="primary",
                 disabled=_btn_disabled):
        if True:
            import anthropic as _anthropic
            client = _anthropic.Anthropic(api_key=api_key)

            _prompt = """Analise este print de fatura de cartão de crédito e extraia TODOS os lançamentos visíveis.

Retorne APENAS um JSON válido com esta estrutura (sem texto extra, sem markdown):
{
  "banco": "Santander|Itaú|C6",
  "subtipo": "Regular|Físico|null",
  "lancamentos": [
    {
      "descricao": "nome do lançamento",
      "valor": 0.00,
      "parcela_atual": 1,
      "total_parcelas": 1,
      "categoria_sugerida": "Essencial|Não essencial|Estudos|Lazer|Viagem|Reforma|Negócios|Metinha|Livre"
    }
  ]
}

Regras:
- valor deve ser positivo (número float, sem R$)
- Se não houver parcelamento, parcela_atual=1 e total_parcelas=1
- Se aparecer "2/5" ou "Parc 2 de 5", parcela_atual=2 e total_parcelas=5
- total_parcelas representa as parcelas RESTANTES incluindo a atual
- banco: identifique pelo visual, cores ou nome visível (Santander=vermelho, Itaú=laranja, C6=preto)
- subtipo: "Físico" se for cartão físico Santander, "Regular" para virtual/padrão, null para outros bancos
- categoria_sugerida: escolha a mais adequada pelo nome do estabelecimento"""

            todos_lancamentos = []
            banco_det = None
            subtipo_det = None
            erros = []

            prog = st.progress(0, text="Analisando imagens...")
            for idx, f in enumerate(_imgs):
                prog.progress(idx / len(_imgs), text=f"Analisando {f['name']}…")
                try:
                    img_bytes = f["bytes"]
                    ext = f["ext"]
                    mime = {"png": "image/png", "jpg": "image/jpeg",
                            "jpeg": "image/jpeg", "webp": "image/webp"}.get(ext, "image/png")
                    img_b64 = base64.standard_b64encode(img_bytes).decode()
                    resp = client.messages.create(
                        model="claude-sonnet-4-6",
                        max_tokens=2000,
                        messages=[{"role": "user", "content": [
                            {"type": "image", "source": {"type": "base64", "media_type": mime, "data": img_b64}},
                            {"type": "text", "text": _prompt},
                        ]}],
                    )
                    raw = resp.content[0].text.strip()
                    if raw.startswith("```"):
                        raw = raw.split("```")[1]
                        if raw.startswith("json"):
                            raw = raw[4:]
                    dados = _json.loads(raw)
                    if not banco_det:
                        banco_det = dados.get("banco")
                        subtipo_det = dados.get("subtipo") or None
                    todos_lancamentos.extend(dados.get("lancamentos", []))
                except Exception as e:
                    erros.append(f"{f.name}: {e}")

            prog.progress(1.0, text="Concluído!")

            if erros:
                for err in erros:
                    st.error(f"Erro em {err}")
            if todos_lancamentos:
                st.session_state["imp_dados"] = {"banco": banco_det, "subtipo": subtipo_det,
                                                   "lancamentos": todos_lancamentos}
                st.session_state["imp_mes"] = mes_imp
                st.rerun()

    # ── Tabela de revisão ─────────────────────────────────────────────────────
    if "imp_dados" in st.session_state and st.session_state["imp_dados"]:
        dados = st.session_state["imp_dados"]
        lancamentos_ia = dados.get("lancamentos", [])
        banco_det = dados.get("banco") or st.session_state.get("imp_cartao", "Santander")
        subtipo_det = dados.get("subtipo") or None

        st.divider()
        badge_det = badge_cartao(banco_det, subtipo_det)
        st.html(f'<div style="font-size:14px;margin-bottom:8px">Banco detectado: {badge_det}&nbsp;&nbsp;<span style="color:#888;font-size:12px">{len(lancamentos_ia)} lançamento(s) encontrado(s)</span></div>')

        # Carrega lançamentos existentes para deduplicação
        from difflib import SequenceMatcher
        lanc_existentes = get_lancamentos(st.session_state.get("imp_mes", mes_imp))

        def _dup_check(desc: str, valor: float):
            """Retorna (é_dup, motivo) comparando valor exato e similaridade de descrição."""
            if lanc_existentes.empty:
                return False, ""
            desc_norm = desc.strip().lower()
            for _, ex in lanc_existentes.iterrows():
                ex_desc = str(ex["descricao"]).strip().lower()
                ex_val = float(ex["valor"])
                valor_igual = abs(ex_val - valor) < 0.01
                similaridade = SequenceMatcher(None, desc_norm, ex_desc).ratio()
                if valor_igual and similaridade >= 0.85:
                    return True, f"idêntico a '{ex['descricao']}' (R$ {ex_val:,.2f})"
                if valor_igual:
                    return True, f"mesmo valor que '{ex['descricao']}' (R$ {ex_val:,.2f})"
                if similaridade >= 0.85:
                    return True, f"descrição similar a '{ex['descricao']}' (R$ {ex_val:,.2f})"
            return False, ""

        # Inicializa estado editável
        if "imp_rows" not in st.session_state or st.session_state.get("imp_rows_src") != id(lancamentos_ia):
            rows_init = []
            for l in lancamentos_ia:
                is_dup, motivo = _dup_check(l["descricao"], float(l["valor"]))
                rows_init.append({**l, "_ativo": not is_dup, "_dup": is_dup, "_dup_motivo": motivo})
            st.session_state["imp_rows"] = rows_init
            st.session_state["imp_rows_src"] = id(lancamentos_ia)

        rows = st.session_state["imp_rows"]

        # Cabeçalho
        hc = st.columns([0.4, 2.5, 1.5, 0.8, 0.8, 0.8, 1.5])
        for col, label in zip(hc, ["✓", "Descrição", "Categoria", "Valor", "Parc.", "Total", "Tipo"]):
            col.markdown(f"<small style='color:#666;text-transform:uppercase;letter-spacing:.5px;font-size:11px'>{label}</small>", unsafe_allow_html=True)

        st.divider()
        for i, row in enumerate(rows):
            is_dup = row.get("_dup", False)
            rc = st.columns([0.4, 2.5, 1.5, 0.8, 0.8, 0.8, 1.5])
            row["_ativo"] = rc[0].checkbox("", value=row["_ativo"], key=f"imp_ck_{i}", label_visibility="collapsed")
            dup_tip = f"⚠️ Possível duplicata: {row.get('_dup_motivo','já existe')}" if is_dup else ""
            row["descricao"] = rc[1].text_input("", value=row["descricao"], key=f"imp_desc_{i}",
                                                  label_visibility="collapsed", help=dup_tip)
            cats_idx = CATEGORIAS.index(row["categoria_sugerida"]) if row.get("categoria_sugerida") in CATEGORIAS else 0
            row["categoria_sugerida"] = rc[2].selectbox("", CATEGORIAS, index=cats_idx,
                                                          key=f"imp_cat_{i}", label_visibility="collapsed")
            row["valor"] = rc[3].number_input("", value=float(row["valor"]), min_value=0.0,
                                               step=0.01, format="%.2f", key=f"imp_val_{i}",
                                               label_visibility="collapsed")
            row["parcela_atual"] = rc[4].number_input("", value=int(row.get("parcela_atual", 1)),
                                                        min_value=1, step=1, key=f"imp_parc_{i}",
                                                        label_visibility="collapsed")
            row["total_parcelas"] = rc[5].number_input("", value=int(row.get("total_parcelas", 1)),
                                                         min_value=1, step=1, key=f"imp_tot_{i}",
                                                         label_visibility="collapsed")
            tot = int(row["total_parcelas"])
            parc = int(row["parcela_atual"])
            restantes = tot - parc + 1
            tipo = "FIXO" if tot > 90 else ("ULTIMA" if restantes == 1 else ("única" if tot == 1 else "parcelado"))
            rc[6].markdown(f"`{tipo}`" + (" ⚠️ dup" if is_dup else ""), unsafe_allow_html=True)

        n_ativos = sum(1 for r in rows if r["_ativo"])
        n_dup = sum(1 for r in rows if r["_dup"] and r["_ativo"])

        st.divider()
        si1, si2 = st.columns([3, 1])
        si1.markdown(f"**{n_ativos}** selecionado(s)" + (f" · ⚠️ {n_dup} possível(is) duplicata(s)" if n_dup else ""))

        if si2.button("💾 Importar selecionados", use_container_width=True, type="primary", disabled=n_ativos == 0):
            mes_dest = st.session_state.get("imp_mes", mes_imp)
            banco_final = banco_det
            subtipo_final = subtipo_det
            importados = 0
            for row in rows:
                if not row["_ativo"]:
                    continue
                tot = int(row["total_parcelas"])
                parc = int(row["parcela_atual"])
                restantes = tot - parc + 1
                tipo = "FIXO" if tot > 90 else ("ULTIMA" if restantes == 1 else ("única" if tot == 1 else "parcelado"))

                if tipo == "parcelado" and restantes > 1:
                    # Cria grupo de parcelamento a partir do mês destino
                    criar_grupo_parcelamento(
                        descricao=row["descricao"],
                        cartao=banco_final,
                        subtipo_cartao=subtipo_final,
                        categoria=row["categoria_sugerida"],
                        valor_parcela=float(row["valor"]),
                        total_parcelas=restantes,
                        mes_inicio=mes_dest,
                    )
                else:
                    add_lancamento(
                        mes_ano=mes_dest,
                        cartao=banco_final,
                        dono="Kelvin",
                        valor=float(row["valor"]),
                        descricao=row["descricao"],
                        categoria=row["categoria_sugerida"],
                        tipo_parcela=tipo,
                        parcela_atual=parc,
                        total_parcelas=restantes,
                        subtipo_cartao=subtipo_final,
                    )
                importados += 1

            del st.session_state["imp_dados"]
            del st.session_state["imp_rows"]
            st.success(f"✅ {importados} lançamento(s) importado(s) para {MES_LABELS.get(mes_dest, mes_dest)}!")
            st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURAÇÕES
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "Configurações":
    st.title("Configurações")
    cfg = get_config()

    # ── Nomes e divisão ───────────────────────────────────────────────────────
    st.markdown("#### Perfil")
    cn1, cn2 = st.columns(2)
    nome_k = cn1.text_input("Seu nome", value=cfg.get("nome_kelvin", "Kelvin"))
    nome_t = cn2.text_input("Nome do(a) parceiro(a)", value=cfg.get("nome_thais", "Thais"))

    st.markdown("#### Divisão de despesas compartilhadas")
    cd1, cd2 = st.columns(2)
    div_k = cd1.number_input(f"% de {nome_k}", min_value=0, max_value=100,
                              value=int(cfg.get("divisao_kelvin", 80)), step=1)
    div_t = cd2.number_input(f"% de {nome_t}", min_value=0, max_value=100,
                              value=int(cfg.get("divisao_thais", 20)), step=1)

    if div_k + div_t != 100:
        st.warning(f"A soma deve ser 100%. Atualmente: {div_k + div_t}%")

    if st.button("💾 Salvar configurações", disabled=(div_k + div_t != 100)):
        set_config("nome_kelvin", nome_k)
        set_config("nome_thais", nome_t)
        set_config("divisao_kelvin", div_k)
        set_config("divisao_thais", div_t)
        st.success("Configurações salvas!")
        st.rerun()

    # ── Exportação completa ───────────────────────────────────────────────────
    st.divider()
    st.markdown("#### Exportar todos os meses")
    st.caption("Gera um arquivo Excel com uma aba por mês contendo todos os lançamentos.")

    if st.button("📥 Gerar exportação completa", use_container_width=False):
        import io
        from openpyxl import Workbook as _WB
        from openpyxl.styles import Font as _Font, PatternFill as _Fill, Alignment as _Align
        wb_full = _WB()
        wb_full.remove(wb_full.active)
        todos_meses = get_meses()
        for m in todos_meses:
            df_m = get_lancamentos(m)
            label_m = MES_LABELS.get(m, m).replace("/", "-")
            ws = wb_full.create_sheet(label_m)
            cols_exp = ["descricao", "categoria", "cartao", "subtipo_cartao",
                        "valor", "tipo_parcela", "total_parcelas", "pessoa_thais", "valor_thais"]
            headers = ["Descrição", "Categoria", "Cartão", "Subtipo", "Valor",
                       "Tipo", "Faltam", "Pessoa", "Valor Pessoa"]
            ws.append(headers)
            for cell in ws[1]:
                cell.font = _Font(bold=True, color="FFFFFF")
                cell.fill = _Fill("solid", start_color="1A1A2E")
                cell.alignment = _Align(horizontal="center")
            if not df_m.empty:
                for _, row in df_m.iterrows():
                    ws.append([row.get(c, "") for c in cols_exp])
            for col in ws.columns:
                ws.column_dimensions[col[0].column_letter].width = 18
        buf = io.BytesIO()
        wb_full.save(buf)
        buf.seek(0)
        st.download_button("⬇️ Baixar Excel completo", data=buf,
            file_name="controle_financeiro_completo.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=False)

    # ── Backup ────────────────────────────────────────────────────────────────
    st.divider()
    st.markdown("#### Backup do banco de dados")

    from modules.db import DB_PATH, USE_POSTGRES
    from datetime import datetime as _dt

    if USE_POSTGRES:
        st.info("🗄️ Backend: **Postgres (Supabase)**. Os backups são gerenciados "
                "automaticamente pela plataforma. Use a exportação acima para uma cópia em Excel.")

    backups = listar_backups()
    bc1, bc2 = st.columns([3, 1])
    bc1.caption("Local: Supabase Postgres" if USE_POSTGRES else f"Local: `{DB_PATH}`")
    if not USE_POSTGRES:
        if bc2.button("💾 Fazer backup agora", use_container_width=True):
            caminho = fazer_backup()
            st.success(f"Backup salvo: `{Path(caminho).name}`")
            st.rerun()

    if backups:
        rows_bk = ""
        for i, b in enumerate(backups):
            ts_str = b.stem.replace("financeiro_", "")
            try:
                ts_fmt = _dt.strptime(ts_str, "%Y%m%d_%H%M%S").strftime("%d/%m/%Y %H:%M:%S")
            except Exception:
                ts_fmt = ts_str
            size_kb = b.stat().st_size / 1024
            bg = "rgba(255,255,255,0.02)" if i % 2 == 0 else "transparent"
            tag = ' <span style="background:#1a3a2a;color:#4ade80;padding:1px 6px;border-radius:3px;font-size:10px">mais recente</span>' if i == 0 else ""
            rows_bk += f'<tr style="background:{bg};border-bottom:1px solid rgba(255,255,255,0.06)"><td style="padding:8px 14px;font-size:13px">{ts_fmt}{tag}</td><td style="padding:8px 14px;text-align:right;font-size:12px;color:#888">{size_kb:.1f} KB</td></tr>'
        st.html(f"""<table style="width:100%;border-collapse:collapse;font-family:inherit">
          <thead><tr style="border-bottom:2px solid rgba(255,255,255,0.12)">
            <th style="padding:8px 14px;text-align:left;font-size:11px;color:#666;text-transform:uppercase;letter-spacing:.6px">Data</th>
            <th style="padding:8px 14px;text-align:right;font-size:11px;color:#666;text-transform:uppercase;letter-spacing:.6px">Tamanho</th>
          </tr></thead><tbody>{rows_bk}</tbody></table>""")
        st.caption(f"Últimos {len(backups)} backup(s) mantidos automaticamente (máx. 7).")
    elif not USE_POSTGRES:
        st.caption("Nenhum backup encontrado.")
