"""
fc_components.py — Componentes HTML do Controle Financeiro (Design System)
==========================================================================

Funções que retornam HTML pronto para `st.html(...)`. Tema dark, sem JavaScript,
cores literais (os tokens CSS não existem dentro do iframe do Streamlit).

Uso típico
----------
    import streamlit as st
    from fc_components import inject_base_css, hero_saldo, painel_resumo, lancamento_row

    inject_base_css()                       # 1x por página (classes fc-*)
    st.html(hero_saldo(1240))
    st.html(painel_resumo("Kelvin", [
        ("Salário", 6500, "kelvin"),
        ("Gastos + Pix", 5260, None),
        ("Diferença", 1240, None),
    ]))

Todas as funções são puras (str -> str) e seguras para reusar nas páginas
Dashboard, Lançamentos, Histórico, etc.
"""

from __future__ import annotations
from typing import Iterable, Optional, Sequence, Tuple

# ──────────────────────────────────────────────────────────────────────────────
# Paleta (espelha tokens/colors.css). Mantida aqui em literais para o Streamlit.
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

# Cor de fundo do card de total por cartão (banco + subtipo).
CARTAO_COR = {
    ("Itaú", "Visa"):            "#1A1F71",
    ("Itaú", "Mastercard"):      "linear-gradient(100deg,#EB001B 0%,#FF5F00 52%,#F79E1B 100%)",
    ("Itaú", "LATAM Pass"):      "#00128C",
    ("Itaú", None):              "#FF6B00",
    ("Santander", "Físico"):     "#A80000",
    ("Santander", None):         "#EC0000",
    ("C6", None):                "#000000",
}

CHIP = {
    "única":     ("#1a2a3a", "#60a5fa", "única"),
    "FIXO":      ("#1a3a2a", "#4ade80", "FIXO"),
    "ULTIMA":    ("#3a1a1a", "#f87171", "ÚLTIMA"),
    "parcelado": ("#2a2a1a", "#facc15", "parcelado"),
}

SALARIO_COR = {"kelvin": "#2f6fd1", "thais": "#1e9e5a"}

VERDE, VERMELHO, VERDE_CLARO = "#21c354", "#ff5b5b", "#4ade80"


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────
def _br(v: float, casas: int = 2) -> str:
    """Formata moeda BR: 1234.5 -> 'R$ 1.234,50'. casas=0 omite centavos."""
    fmt = f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {fmt}"


# ──────────────────────────────────────────────────────────────────────────────
# CSS base (classes reutilizadas). Chame inject_base_css() uma vez por página.
# Equivale ao bloco st.html(<style>…</style>) original do app.
# ──────────────────────────────────────────────────────────────────────────────
def base_css() -> str:
    return """
<style>
  .fc-box { border:1px solid rgba(255,255,255,.12); border-radius:8px; overflow:hidden; margin-bottom:12px; }
  .fc-hdr { background:#1a1a2e; color:#fff; padding:6px 12px; font-size:12px; font-weight:700;
            text-align:center; text-transform:uppercase; letter-spacing:.5px; }
  .fc-hero { border-left:4px solid #21c354; border-radius:10px; background:rgba(255,255,255,0.04);
             padding:18px 22px; margin-bottom:18px; font-family:inherit; color:#fafafa; }
  .fc-hero.is-negative { border-left-color:#ff5b5b; }
  .fc-hero-label { font-size:13px; color:#aaa; text-transform:uppercase; letter-spacing:.5px; margin-bottom:6px; }
  .fc-hero-value { font-size:2.4rem; font-weight:800; line-height:1.1; }
  .fc-hero-nota  { font-size:13px; margin-top:6px; }
  .fc-grid { display:flex; flex-wrap:wrap; gap:12px; font-family:inherit; }
  .fc-grid > .fc-box { flex:1; min-width:280px; }
</style>
"""


def inject_base_css() -> None:
    """Injeta o CSS base no Streamlit (chame 1x por página)."""
    import streamlit as st
    st.html(base_css())


# ──────────────────────────────────────────────────────────────────────────────
# 1. Badge de banco (+ bandeira)
# ──────────────────────────────────────────────────────────────────────────────
def bank_badge(cartao: str, subtipo: Optional[str] = None) -> str:
    """Etiqueta colorida do banco; Itaú ganha 2ª etiqueta com a cor da bandeira."""
    key = cartao
    if cartao == "Santander" and subtipo == "Físico":
        key = "Santander Físico"
    b = BANCO.get(key, BANCO["Santander"])
    s = (f"background:{b['bg']};color:{b['fg']};padding:2px 8px;border-radius:4px;"
         f"font-size:12px;font-weight:600;display:inline-block;white-space:nowrap")
    html = f'<span style="{s}">{b["label"]}</span>'
    if cartao == "Itaú" and subtipo in BANDEIRA:
        sombra = ""
        if subtipo == "Mastercard":
            sombra = ";text-shadow:0 1px 1px rgba(0,0,0,.35)"
        elif subtipo == "Visa":
            sombra = ";box-shadow:inset 0 -2px 0 #F7B600"   # acento dourado da Visa
        fs = (f"background:{BANDEIRA[subtipo]};color:#fff;padding:2px 7px;border-radius:4px;"
              f"font-size:11px;font-weight:700;display:inline-block;white-space:nowrap;"
              f"margin-left:4px{sombra}")
        html += f'<span style="{fs}">{subtipo}</span>'
    return html


# ──────────────────────────────────────────────────────────────────────────────
# 2. Chip de tipo de parcela
# ──────────────────────────────────────────────────────────────────────────────
def tipo_chip(tipo: str) -> str:
    bg, fg, label = CHIP.get(tipo, ("#2a2a2a", "#aaa", str(tipo)))
    return (f'<span style="background:{bg};color:{fg};padding:1px 7px;border-radius:3px;'
            f'font-size:11px;white-space:nowrap">{label}</span>')


# ──────────────────────────────────────────────────────────────────────────────
# 3. Hero de saldo
# ──────────────────────────────────────────────────────────────────────────────
def hero_saldo(saldo: float, label: str = "Saldo combinado do mês") -> str:
    neg = saldo < 0
    cls = " is-negative" if neg else ""
    cor = VERMELHO if neg else VERDE
    nota = f'{"⚠️ faltam" if neg else "✅ sobram"} {_br(abs(saldo), 0)} no mês'
    return (
        f'<div class="fc-hero{cls}">'
        f'<div class="fc-hero-label">{label}</div>'
        f'<div class="fc-hero-value">{_br(saldo, 0)}</div>'
        f'<div class="fc-hero-nota" style="color:{cor}">{nota}</div>'
        f'</div>'
    )


# ──────────────────────────────────────────────────────────────────────────────
# 4. Card de total por cartão (versão estática; clicabilidade = st.button)
# ──────────────────────────────────────────────────────────────────────────────
def card_cartao(cartao: str, total: float, subtipo: Optional[str] = None,
                ativo: bool = False) -> str:
    cor = CARTAO_COR.get((cartao, subtipo), CARTAO_COR.get((cartao, None), "#444"))
    label = f"{cartao} {subtipo}" if subtipo else cartao
    # box-shadow combina anel de seleção (ativo) + barra dourada da Visa.
    sombras = []
    if ativo:
        sombras.append("0 0 0 2px #fff inset")
    if subtipo == "Visa":
        sombras.append("inset 0 -4px 0 #F7B600")   # acento dourado da Visa
    anel = f"box-shadow:{', '.join(sombras)};" if sombras else ""
    sombra = "text-shadow:0 1px 2px rgba(0,0,0,.3);" if subtipo == "Mastercard" else ""
    return (
        f'<div style="background:{cor};color:#fff;border-radius:4px;padding:10px 14px;'
        f'min-width:130px;font-family:inherit;font-weight:700;line-height:1.3;{anel}{sombra}'
        f'display:inline-flex;flex-direction:column;gap:4px">'
        f'<span style="font-size:12px;font-weight:600;opacity:.92">{label}</span>'
        f'<span style="font-size:1.4rem;font-weight:700">{_br(total, 0)}</span>'
        f'</div>'
    )


# ──────────────────────────────────────────────────────────────────────────────
# 5. Painel-resumo (caixa de métricas estilo planilha)
#    linhas: lista de (label, valor, destaque)  — destaque ∈ {"kelvin","thais",None}
# ──────────────────────────────────────────────────────────────────────────────
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
        f'<div class="fc-box" style="font-family:inherit;color:#fafafa">'
        f'<div class="fc-hdr">{titulo}</div>'
        f'<table style="width:100%;border-collapse:collapse">{"".join(trs)}</table>'
        f'</div>'
    )


def painel_grid(*caixas_html: str) -> str:
    """Envolve várias caixas de painel_resumo() num grid flex responsivo."""
    return f'<div class="fc-grid">{"".join(caixas_html)}</div>'


# ──────────────────────────────────────────────────────────────────────────────
# 6. Linha de lançamento (a HTML da linha; os botões ✏️/🗑 são st.button ao lado)
#    Veja row_actions_css() para estilizar os botões.
# ──────────────────────────────────────────────────────────────────────────────
def lancamento_row(descricao: str, cartao: str, valor: float, categoria: str = "",
                   tipo: str = "única", faltam: str = "—",
                   subtipo: Optional[str] = None, conferido: bool = False,
                   pessoa: Optional[str] = None, valor_pessoa: Optional[float] = None) -> str:
    if conferido:
        borda = "border-left:3px solid #21c354;background:rgba(33,195,84,0.06)"
    else:
        borda = "border-left:3px solid transparent"
    badge = bank_badge(cartao, subtipo)
    cor_val = f";color:{VERDE_CLARO}" if valor < 0 else ""
    pessoa_line = ""
    if pessoa:
        vp = f" · {_br(valor_pessoa)}" if valor_pessoa is not None else ""
        pessoa_line = f'<div style="font-size:10px;color:#666;margin-top:1px">👤 {pessoa}{vp}</div>'
    return (
        f'<div style="display:flex;align-items:center;font-family:inherit;padding:4px 6px;{borda};color:#fafafa">'
        f'<div style="flex:3.2;min-width:0">'
        f'<span style="font-weight:500;font-size:13px">{descricao}</span>&nbsp;{badge}{pessoa_line}</div>'
        f'<div style="flex:1.3;font-size:12px;color:#aaa">{categoria}</div>'
        f'<div style="flex:1.1">{tipo_chip(tipo)}</div>'
        f'<div style="flex:0.8;text-align:center;color:#888;font-size:13px">{faltam}</div>'
        f'<div style="flex:1.3;text-align:right;font-size:13px;font-weight:600{cor_val}">{_br(valor)}</div>'
        f'</div>'
    )


def lancamento_header() -> str:
    """Cabeçalho da tabela de lançamentos (combina com lancamento_row)."""
    cols = ('<div style="flex:3.2">Descrição</div><div style="flex:1.3">Categoria</div>'
            '<div style="flex:1.1">Tipo</div><div style="flex:0.8;text-align:center">Faltam</div>'
            '<div style="flex:1.3;text-align:right">Valor</div>')
    return (
        '<div style="display:flex;color:#666;font-size:11px;text-transform:uppercase;'
        'letter-spacing:.6px;font-weight:500;border-bottom:2px solid rgba(255,255,255,0.12);'
        f'padding:6px 6px;font-family:inherit">{cols}</div>'
    )


# ──────────────────────────────────────────────────────────────────────────────
# 7. Ações por linha — no Streamlit são st.button reais. Injete este CSS 1x para
#    deixá-los quadrados/discretos e use os rótulos "✏️" e "🗑".
# ──────────────────────────────────────────────────────────────────────────────
def row_actions_css() -> str:
    return """
<style>
  div[data-testid="stHorizontalBlock"] button[kind="secondary"]{
    width:30px;height:30px;padding:0;line-height:1;
    background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,.12);
    border-radius:4px;color:#aaa;
  }
  div[data-testid="stHorizontalBlock"] button[kind="secondary"]:hover{
    background:rgba(255,255,255,0.07);color:#fafafa;
  }
</style>
"""
