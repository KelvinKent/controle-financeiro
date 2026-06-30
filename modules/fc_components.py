"""
fc_components.py — Componentes HTML do Controle Financeiro (Design System)
==========================================================================

REDESIGN "Fintech Elevated" — visual mais moderno: mais espaçamento,
tipografia maior, cards com profundidade (gradiente + sombra), números em
destaque e linhas de lançamento como **cards expansíveis** (`<details>`,
CSS puro — sem JavaScript, compatível com `st.html()`).

Tudo é drop-in: as assinaturas continuam compatíveis com o `app.py`
(parâmetros novos são opcionais). Funções puras (str -> str).

Uso típico
----------
    import streamlit as st
    from fc_components import inject_base_css, hero_saldo, lancamento_row

    inject_base_css()                       # 1x por página (classes fc-*)
    st.html(hero_saldo(1240, trend="▲ 12% vs mês passado"))
    st.html(lancamento_row("Spotify", "Santander", 21.90,
                           categoria="Assinaturas", tipo="FIXO",
                           conferido=True, pessoa="Thais", valor_pessoa=10.95,
                           data="05/06"))

As linhas usam `<details>`: o cabeçalho é a linha densa; ao clicar, expande
um grid com Categoria · Parcela · Faltam · Divisão · Status. Os botões
✏️/🗑 continuam sendo `st.button` reais na coluna ao lado (ver row_actions_css).
"""

from __future__ import annotations
from typing import Optional, Sequence, Tuple

# ──────────────────────────────────────────────────────────────────────────────
# Paleta (espelha tokens/colors.css). Literais para o iframe do Streamlit.
# ──────────────────────────────────────────────────────────────────────────────
BANCO = {
    "Itaú":             {"bg": "#FF6B00", "fg": "#fff", "label": "Itaú"},
    "Santander":        {"bg": "#EC0000", "fg": "#fff", "label": "Santander"},
    "Santander Físico": {"bg": "#A80000", "fg": "#fff", "label": "Santander Físico"},
    "C6":               {"bg": "#000000", "fg": "#fff", "label": "C6"},
}

# Bandeiras Itaú. Mastercard usa o gradiente oficial vermelho→laranja→amarelo.
BANDEIRA = {
    "Visa":       "#1A1F71",
    "Mastercard": "linear-gradient(100deg,#EB001B 0%,#FF5F00 52%,#F79E1B 100%)",
    "LATAM Pass": "#00128C",
}

# Cor SÓLIDA de fundo do card por cartão (banco + subtipo). Mantida para
# compatibilidade — app.py importa CARTAO_COR.
CARTAO_COR = {
    ("Itaú", "Visa"):            "#1A1F71",
    ("Itaú", "Mastercard"):      "linear-gradient(100deg,#EB001B 0%,#FF5F00 52%,#F79E1B 100%)",
    ("Itaú", "LATAM Pass"):      "#00128C",
    ("Itaú", None):              "#FF6B00",
    ("Santander", "Físico"):     "#A80000",
    ("Santander", None):         "#EC0000",
    ("C6", None):                "#000000",
}

# REDESIGN: versão com GRADIENTE (profundidade) para os cards de total.
CARTAO_GRAD = {
    ("Itaú", "Visa"):        "linear-gradient(150deg,#2a3290,#12153f)",
    ("Itaú", "Mastercard"):  "linear-gradient(90deg,#EB001B 0%,#EB001B 30%,#FF5F00 55%,#F79E1B 100%)",
    ("Itaú", "LATAM Pass"):  "linear-gradient(150deg,#1b2db0,#00104f)",
    ("Itaú", None):          "linear-gradient(150deg,#ff8a33,#e85d00)",
    ("Santander", None):     "linear-gradient(150deg,#ff3b3b,#c20000)",
    ("C6", None):            "linear-gradient(150deg,#2c2c2c,#0a0a0a)",
    ("Outros", None):        "linear-gradient(150deg,#4b5563,#1f2937)",
}

# Cor do texto por cartão (padrão #fff; Itaú usa azul corporativo no laranja)
_CARTAO_FG = {
    ("Itaú", None): "#003D7B",
}

CHIP = {
    "única":     ("#1a2a3a", "#60a5fa", "única"),
    "FIXO":      ("#1a3a2a", "#4ade80", "FIXO"),
    "ULTIMA":    ("#3a1a1a", "#f87171", "ÚLTIMA"),
    "parcelado": ("#2a2a1a", "#facc15", "parcelado"),
}

SALARIO_COR = {"kelvin": "#2f6fd1", "thais": "#1e9e5a"}

VERDE, VERMELHO, VERDE_CLARO = "#21c354", "#ff5b5b", "#4ade80"

# Paleta harmônica para o quadradinho de categoria (cor estável por nome).
_CAT_PALETTE = ["#60a5fa", "#4ade80", "#facc15", "#f472b6",
                "#a78bfa", "#fb923c", "#22d3ee", "#f87171"]


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────
def _br(v: float, casas: int = 2) -> str:
    """Formata moeda BR: 1234.5 -> 'R$ 1.234,50'. casas=0 omite centavos."""
    fmt = f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {fmt}"


def _cat_cor(categoria: str) -> str:
    """Cor estável (mesma categoria → mesma cor) a partir da paleta harmônica."""
    if not categoria:
        return "#7a8190"
    h = sum(ord(c) for c in str(categoria))
    return _CAT_PALETTE[h % len(_CAT_PALETTE)]


def _rgba(hexcol: str, a: float) -> str:
    """'#60a5fa', .14 -> 'rgba(96,165,250,0.14)'. Útil para tints translúcidos."""
    h = hexcol.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{a})"


# ──────────────────────────────────────────────────────────────────────────────
# CSS base. Chame inject_base_css() uma vez por página.
#   - fc-box / fc-hdr / fc-grid : painel-resumo (inalterado).
#   - fc-lanc*                  : NOVO — card de lançamento expansível (<details>).
# ──────────────────────────────────────────────────────────────────────────────
def base_css() -> str:
    return """
<style>
  /* ── Painel-resumo (inalterado) ─────────────────────────────────────── */
  .fc-box { border:1px solid rgba(255,255,255,.12); border-radius:8px; overflow:hidden; margin-bottom:12px; }
  .fc-hdr { background:#1a1a2e; color:#fff; padding:6px 12px; font-size:12px; font-weight:700;
            text-align:center; text-transform:uppercase; letter-spacing:.5px; }
  .fc-grid { display:flex; flex-wrap:wrap; gap:12px; font-family:inherit; }
  .fc-grid > .fc-box { flex:1; min-width:280px; }

  /* ── REDESIGN: linha de lançamento como card expansível ─────────────── */
  .fc-lanc { border:1px solid rgba(255,255,255,0.06); border-radius:14px;
             background:rgba(255,255,255,0.02); overflow:hidden; margin-bottom:10px;
             font-family:inherit; color:#fafafa;
             transition:border-color .16s ease, background .16s ease; }
  .fc-lanc[open] { border-color:rgba(255,255,255,0.14); background:rgba(255,255,255,0.035); }
  .fc-lanc.is-conferido { box-shadow:inset 3px 0 0 #21c354; }
  .fc-lanc > summary { list-style:none; cursor:pointer; display:flex; align-items:center;
                       gap:14px; padding:14px 16px; }
  .fc-lanc > summary::-webkit-details-marker { display:none; }
  .fc-lanc > summary::marker { content:""; }
  .fc-lanc > summary:hover { background:rgba(255,255,255,0.03); }
  .fc-lanc-ic { flex:0 0 auto; width:40px; height:40px; border-radius:11px; display:flex;
                align-items:center; justify-content:center; font-size:15px; font-weight:800; }
  .fc-lanc-main { flex:1; min-width:0; }
  .fc-lanc-title { display:flex; align-items:center; gap:8px; font-size:15px; font-weight:600;
                   color:#f2f2f5; }
  .fc-lanc-desc { white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .fc-lanc-badges { display:flex; align-items:center; gap:7px; margin-top:5px; flex-wrap:wrap; }
  .fc-lanc-right { flex:0 0 auto; text-align:right; }
  .fc-lanc-val { font-size:18px; font-weight:700; letter-spacing:-.3px;
                 font-variant-numeric:tabular-nums; }
  .fc-lanc-date { font-size:11px; color:#6c707b; margin-top:3px; }
  .fc-caret { flex:0 0 auto; color:#5a5e68; font-size:13px; transition:transform .18s ease; }
  .fc-lanc[open] .fc-caret { transform:rotate(180deg); }
  .fc-lanc-detail { padding:4px 16px 16px 70px; }
  .fc-lanc-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:14px 10px;
                  padding-top:14px; border-top:1px solid rgba(255,255,255,0.06); }
  .fc-lanc-k { font-size:10px; letter-spacing:.6px; text-transform:uppercase; color:#6c707b;
               margin-bottom:3px; }
  .fc-lanc-v { font-size:13px; color:#d6d6dd; font-weight:600; }
</style>
"""


def inject_base_css() -> None:
    """Injeta o CSS base no Streamlit (chame 1x por página)."""
    import streamlit as st
    st.html(base_css())


# ──────────────────────────────────────────────────────────────────────────────
# 1. Badge de banco (+ bandeira) — modernizado (raio 5px, peso 700, sombra sutil)
# ──────────────────────────────────────────────────────────────────────────────
def bank_badge(cartao: str, subtipo: Optional[str] = None) -> str:
    """Etiqueta colorida do banco; Itaú ganha 2ª etiqueta com a cor da bandeira."""
    key = cartao
    if cartao == "Santander" and subtipo == "Físico":
        key = "Santander Físico"
    b = BANCO.get(key, BANCO["Santander"])
    ts = "" if cartao == "C6" else ";text-shadow:0 1px 1px rgba(0,0,0,.3)"
    s = (f"background:{b['bg']};color:{b['fg']};padding:2px 8px;border-radius:5px;"
         f"font-size:11px;font-weight:700;display:inline-block;white-space:nowrap{ts}")
    html = f'<span style="{s}">{b["label"]}</span>'
    if cartao == "Itaú" and subtipo in BANDEIRA:
        sombra = ""
        if subtipo == "Mastercard":
            sombra = ";text-shadow:0 1px 1px rgba(0,0,0,.35)"
        elif subtipo == "Visa":
            sombra = ";box-shadow:inset 0 -2px 0 #F7B600"   # acento dourado da Visa
        fs = (f"background:{BANDEIRA[subtipo]};color:#fff;padding:2px 8px;border-radius:5px;"
              f"font-size:11px;font-weight:700;display:inline-block;white-space:nowrap;"
              f"margin-left:5px{sombra}")
        html += f'<span style="{fs}">{subtipo}</span>'
    return html


# ──────────────────────────────────────────────────────────────────────────────
# 2. Chip de tipo de parcela — modernizado (raio 5px, padding maior)
# ──────────────────────────────────────────────────────────────────────────────
def tipo_chip(tipo: str, label_override: Optional[str] = None) -> str:
    bg, fg, label = CHIP.get(tipo, ("#2a2a2a", "#aaa", str(tipo)))
    if label_override:
        label = label_override
    return (f'<span style="background:{bg};color:{fg};padding:2px 8px;border-radius:5px;'
            f'font-size:11px;font-weight:600;white-space:nowrap">{label}</span>')


# ──────────────────────────────────────────────────────────────────────────────
# 3. Hero de saldo — REDESIGN "Fintech Elevated"
#    gradiente + barra com glow + halo + número grande + chip de tendência
# ──────────────────────────────────────────────────────────────────────────────
def hero_saldo(saldo: float, label: str = "Saldo combinado do mês",
               trend: Optional[str] = None) -> str:
    """`trend` (opcional): texto curto no chip (ex.: '▲ 12% vs mês passado')."""
    neg = saldo < 0
    cor = VERMELHO if neg else VERDE_CLARO
    bar = ("linear-gradient(180deg,#ff5b5b,#c0392b)" if neg
           else "linear-gradient(180deg,#21c354,#1e9e5a)")
    glow = "rgba(255,91,91,0.5)" if neg else "rgba(33,195,84,0.55)"
    halo = ("radial-gradient(circle,rgba(255,91,91,0.16),transparent 70%)" if neg
            else "radial-gradient(circle,rgba(33,195,84,0.18),transparent 70%)")
    nota = f'{"⚠️ faltam" if neg else "✅ sobram"} {_br(abs(saldo), 0)} no mês'
    trend_chip = ""
    if trend:
        tcor = "#f87171" if neg else "#4ade80"
        tbg = "rgba(255,91,91,0.14)" if neg else "rgba(33,195,84,0.14)"
        trend_chip = (f'<span style="display:inline-flex;align-items:center;gap:5px;'
                      f'background:{tbg};color:{tcor};font-size:12px;font-weight:700;'
                      f'padding:5px 11px;border-radius:999px">{trend}</span>')
    return (
        f'<div style="position:relative;overflow:hidden;border-radius:18px;padding:24px 26px;'
        f'background:linear-gradient(150deg,#1b2233 0%,#12141d 100%);'
        f'border:1px solid rgba(255,255,255,0.07);box-shadow:0 10px 30px rgba(0,0,0,0.35);'
        f'font-family:inherit;color:#fafafa;margin-bottom:18px">'
        f'<div style="position:absolute;left:0;top:0;bottom:0;width:5px;background:{bar};'
        f'box-shadow:0 0 24px 2px {glow}"></div>'
        f'<div style="position:absolute;right:-40px;top:-40px;width:180px;height:180px;'
        f'border-radius:50%;background:{halo};pointer-events:none"></div>'
        f'<div style="display:flex;align-items:center;justify-content:space-between;position:relative">'
        f'<div style="font-size:12px;font-weight:600;letter-spacing:1.2px;text-transform:uppercase;'
        f'color:#9aa0ad">{label}</div>{trend_chip}</div>'
        f'<div style="font-size:3.4rem;font-weight:800;line-height:1;letter-spacing:-1.5px;'
        f'color:#fff;margin-top:12px;position:relative;font-variant-numeric:tabular-nums">{_br(saldo, 0)}</div>'
        f'<div style="font-size:14px;font-weight:600;margin-top:12px;color:{cor};position:relative">{nota}</div>'
        f'</div>'
    )


# ──────────────────────────────────────────────────────────────────────────────
# 4. Card de total por cartão — REDESIGN (gradiente + sombra + número grande)
#    clicabilidade = st.button por cima (como antes).
# ──────────────────────────────────────────────────────────────────────────────
def card_cartao(cartao: str, total: float, subtipo: Optional[str] = None,
                ativo: bool = False, qtd: Optional[str] = None) -> str:
    """`qtd` (opcional): legenda menor (ex.: '3 lançamentos')."""
    grad = (CARTAO_GRAD.get((cartao, subtipo))
            or CARTAO_GRAD.get((cartao, None)) or "#444")
    # Itaú sem subtipo: label azul, valor branco. Demais: tudo branco.
    fg_label = "#003D7B" if (cartao == "Itaú" and subtipo is None) else "#fff"
    fg_value = "#fff"
    label = f"{cartao} {subtipo}" if subtipo else cartao
    sombras = ["0 0 0 2px rgba(255,255,255,0.9) inset, 0 12px 26px rgba(0,0,0,0.4)"] if ativo \
        else ["0 8px 20px rgba(0,0,0,0.35)"]
    if subtipo == "Visa":
        sombras.append("inset 0 -4px 0 #F7B600")
    ts = "text-shadow:0 1px 2px rgba(0,0,0,.35);" if subtipo == "Mastercard" else ""
    sub = (f'<span style="font-size:11px;opacity:.7;margin-top:2px;color:{fg_value}">{qtd}</span>'
           if qtd else "")
    return (
        f'<div style="background:{grad};border-radius:16px;padding:16px 18px;'
        f'width:100%;box-sizing:border-box;font-family:inherit;box-shadow:{", ".join(sombras)};{ts}'
        f'display:flex;flex-direction:column;gap:4px">'
        f'<span style="font-size:12px;font-weight:600;opacity:.9;color:{fg_label}">{label}</span>'
        f'<span style="font-size:1.75rem;font-weight:800;letter-spacing:-.5px;color:{fg_value}">{_br(total, 0)}</span>'
        f'{sub}</div>'
    )


# ──────────────────────────────────────────────────────────────────────────────
# 5. Painel-resumo (caixa de métricas estilo planilha) — INALTERADO
# ──────────────────────────────────────────────────────────────────────────────
_PAINEL_CSS = (
    "<style>"
    ".fc-box{border:1px solid rgba(255,255,255,.12);border-radius:8px;overflow:hidden;margin-bottom:12px}"
    ".fc-hdr{background:#1a1a2e;color:#fff;padding:6px 12px;font-size:12px;font-weight:700;"
    "text-align:center;text-transform:uppercase;letter-spacing:.5px}"
    ".fc-grid{display:flex;flex-wrap:wrap;gap:12px;font-family:inherit}"
    ".fc-grid>.fc-box{flex:1;min-width:280px}"
    "</style>"
)


def painel_resumo(titulo: str,
                  linhas: Sequence[Tuple[str, float, Optional[str]]],
                  cents: bool = False, neg_red: bool = True) -> str:
    casas = 2 if cents else 0
    trs = []
    for label, valor, destaque in linhas:
        if destaque in SALARIO_COR:
            cor = SALARIO_COR[destaque]
            trs.append(
                f'<tr style="border-bottom:1px solid rgba(255,255,255,.06)">'
                f'<td style="padding:6px 12px;background:{cor};color:#fff;font-size:13px;font-weight:600">{label}</td>'
                f'<td style="padding:6px 12px;background:{cor};color:#fff;text-align:right;font-weight:700">{_br(valor, casas)}</td>'
                f'</tr>'
            )
        else:
            cv = f";color:{VERMELHO}" if (neg_red and valor < 0) else ""
            trs.append(
                f'<tr style="border-bottom:1px solid rgba(255,255,255,.06)">'
                f'<td style="padding:6px 12px;font-size:13px;color:#fafafa">{label}</td>'
                f'<td style="padding:6px 12px;text-align:right;font-weight:600;color:#fafafa{cv}">{_br(valor, casas)}</td>'
                f'</tr>'
            )
    return (
        _PAINEL_CSS
        + f'<div class="fc-box" style="font-family:inherit;color:#fafafa">'
        + f'<div class="fc-hdr">{titulo}</div>'
        + f'<table style="width:100%;border-collapse:collapse">{"".join(trs)}</table>'
        + f'</div>'
    )


def painel_grid(*caixas_html: str) -> str:
    """Envolve várias caixas de painel_resumo() num grid flex responsivo."""
    return _PAINEL_CSS + f'<div class="fc-grid">{"".join(caixas_html)}</div>'


# ──────────────────────────────────────────────────────────────────────────────
# 6. Linha de lançamento — REDESIGN: card expansível (<details>, CSS puro)
#    O cabeçalho (<summary>) é a linha densa; o corpo é o grid de detalhe.
#    Os botões ✏️/🗑 continuam sendo st.button na coluna ao lado.
# ──────────────────────────────────────────────────────────────────────────────
_LANC_CSS = """
<style>
  .fc-lanc{border:1px solid rgba(255,255,255,0.06);border-radius:14px;
    background:rgba(255,255,255,0.02);overflow:hidden;margin-bottom:10px;
    font-family:inherit;color:#fafafa;
    transition:border-color .16s ease,background .16s ease}
  .fc-lanc[open]{border-color:rgba(255,255,255,0.14);background:rgba(255,255,255,0.035)}
  .fc-lanc.is-conferido{box-shadow:inset 3px 0 0 #21c354}
  .fc-lanc>summary{list-style:none;cursor:pointer;display:flex;align-items:center;
    gap:14px;padding:14px 16px}
  .fc-lanc>summary::-webkit-details-marker{display:none}
  .fc-lanc>summary::marker{content:""}
  .fc-lanc>summary:hover{background:rgba(255,255,255,0.03)}
  .fc-lanc-ic{flex:0 0 auto;width:40px;height:40px;border-radius:11px;display:flex;
    align-items:center;justify-content:center;font-size:15px;font-weight:800}
  .fc-lanc-main{flex:1;min-width:0}
  .fc-lanc-title{display:flex;align-items:center;gap:8px;font-size:15px;font-weight:600;color:#f2f2f5}
  .fc-lanc-desc{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .fc-lanc-badges{display:flex;align-items:center;gap:7px;margin-top:5px;flex-wrap:wrap}
  .fc-lanc-right{flex:0 0 auto;text-align:right}
  .fc-lanc-val{font-size:18px;font-weight:700;letter-spacing:-.3px;font-variant-numeric:tabular-nums}
  .fc-lanc-date{font-size:11px;color:#6c707b;margin-top:3px}
  .fc-caret{flex:0 0 auto;color:#5a5e68;font-size:13px;transition:transform .18s ease}
  .fc-lanc[open] .fc-caret{transform:rotate(180deg)}
  .fc-lanc-detail{padding:4px 16px 16px 70px}
  .fc-lanc-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px 10px;
    padding-top:14px;border-top:1px solid rgba(255,255,255,0.06)}
  .fc-lanc-k{font-size:10px;letter-spacing:.6px;text-transform:uppercase;color:#6c707b;margin-bottom:3px}
  .fc-lanc-v{font-size:13px;color:#d6d6dd;font-weight:600}
</style>
"""
_LANC_CSS_INJECTED = False


def _tipo_chip_or_empty(tipo: str, parcela_atual: Optional[int], total_parcelas: Optional[int]) -> str:
    """Renderiza o chip de tipo; para parcelado/ULTIMA usa label com parcelas.
    Se não houver label significativo (única parcela, dados ausentes), oculta o chip."""
    if tipo in ("parcelado", "ULTIMA"):
        label = _parc_label(tipo, parcela_atual, total_parcelas)
        if label is None:
            return ""
        return tipo_chip(tipo, label)
    if tipo == "única":
        return ""  # não exibe chip para lançamentos únicos
    return tipo_chip(tipo)


def _parc_label(tipo: str, parcela_atual: Optional[int], total_parcelas: Optional[int]) -> Optional[str]:
    """Retorna '2 de 5' para parcelado, 'ÚLTIMA' para ULTIMA, None para ocultar.
    total_parcelas no banco = parcelas restantes (sem a atual); total real = pa + tp."""
    if tipo == "ULTIMA":
        return "ÚLTIMA"
    if tipo == "parcelado":
        pa = int(parcela_atual) if parcela_atual is not None else None
        tp = int(total_parcelas) if total_parcelas is not None else None
        if pa is not None and tp is not None:
            total_real = pa + tp
            if total_real <= 1:
                return None  # única parcela, não exibe
            return f"{pa} de {total_real}"
        if tp is not None and tp > 0:
            return f"? de {tp}"
    return None


def lancamento_row(descricao: str, cartao: str, valor: float, categoria: str = "",
                   tipo: str = "única", faltam: str = "—",
                   subtipo: Optional[str] = None, conferido: bool = False,
                   pessoa: Optional[str] = None, valor_pessoa: Optional[float] = None,
                   data: str = "", parcela: Optional[str] = None,
                   parcela_atual: Optional[int] = None, total_parcelas: Optional[int] = None,
                   aberto: bool = False) -> str:
    """`data` e `parcela` (opcionais) aparecem no detalhe expandido.
    `aberto=True` renderiza o card já expandido."""
    global _LANC_CSS_INJECTED
    css_block = ""
    if not _LANC_CSS_INJECTED:
        css_block = _LANC_CSS
        _LANC_CSS_INJECTED = True

    cat_cor = _cat_cor(categoria)
    inicial = (str(categoria).strip()[:1].upper() if categoria else "•")
    check = '<span style="font-size:12px;color:#4ade80">✓</span>' if conferido else ""
    cor_val = VERDE_CLARO if valor < 0 else "#f2f2f5"

    parcela_fmt = parcela if parcela else "—"
    faltam_fmt = faltam if (faltam and faltam != "—") else "—"
    if pessoa:
        vp = f" · {_br(valor_pessoa)}" if valor_pessoa is not None else ""
        divisao = f"👤 {pessoa}{vp}"
    else:
        divisao = "Sem divisão"
    status = ("✅ Conferido", "#4ade80") if conferido else ("⚠️ Pendente", "#f59e0b")

    def _cel(k, v, cor="#d6d6dd"):
        return (f'<div><div class="fc-lanc-k">{k}</div>'
                f'<div class="fc-lanc-v" style="color:{cor}">{v}</div></div>')

    detalhe = (
        '<div class="fc-lanc-detail"><div class="fc-lanc-grid">'
        + _cel("Categoria", categoria or "—")
        + _cel("Parcela", parcela_fmt)
        + _cel("Faltam", faltam_fmt)
        + _cel("Divisão", divisao)
        + _cel("Status", status[0], status[1])
        + '</div></div>'
    )

    cls = "fc-lanc" + (" is-conferido" if conferido else "")
    open_attr = " open" if aberto else ""
    return (
        css_block
        + f'<details class="{cls}"{open_attr}>'
        + f'<summary>'
        + f'<div class="fc-lanc-ic" style="background:{_rgba(cat_cor, 0.14)};color:{cat_cor}">{inicial}</div>'
        + f'<div class="fc-lanc-main">'
        + f'<div class="fc-lanc-title"><span class="fc-lanc-desc">{descricao}</span>{check}</div>'
        + f'<div class="fc-lanc-badges">{bank_badge(cartao, subtipo)}{_tipo_chip_or_empty(tipo, parcela_atual, total_parcelas)}</div>'
        + f'</div>'
        + f'<div class="fc-lanc-right">'
        + f'<div class="fc-lanc-val" style="color:{cor_val}">{_br(valor)}</div>'
        + f'<div class="fc-lanc-date">{data or "—"}</div>'
        + f'</div>'
        + f'<div class="fc-caret">⌄</div>'
        + f'</summary>'
        + detalhe
        + f'</details>'
    )


def lancamento_header() -> str:
    """No layout em cards o cabeçalho de colunas não é necessário.
    Mantido por compatibilidade com app.py — retorna vazio."""
    return ""


# ──────────────────────────────────────────────────────────────────────────────
# 7. Ações por linha — st.button reais. Injete este CSS 1x para deixá-los
#    quadrados/discretos e use os rótulos "✏️" e "🗑".
# ──────────────────────────────────────────────────────────────────────────────
def row_actions_css() -> str:
    return """
<style>
  div[data-testid="stHorizontalBlock"] button[kind="secondary"]{
    width:34px;height:34px;padding:0;line-height:1;
    background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,.12);
    border-radius:9px;color:#aaa;
  }
  div[data-testid="stHorizontalBlock"] button[kind="secondary"]:hover{
    background:rgba(255,255,255,0.09);color:#fafafa;border-color:rgba(255,255,255,.2);
  }
</style>
"""
