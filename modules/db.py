import os
import pandas as pd
import openpyxl
from openpyxl import Workbook, load_workbook
from pathlib import Path
from datetime import datetime

# DATA_DIR pode ser sobrescrito por variável de ambiente (volume persistente no deploy).
_DATA_DIR = os.environ.get("DATA_DIR")
if _DATA_DIR:
    DB_PATH = Path(_DATA_DIR) / "financeiro.xlsx"
else:
    DB_PATH = Path(__file__).parent.parent / "data" / "financeiro.xlsx"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# ── Backend de dados ──────────────────────────────────────────────────────────
# Se DATABASE_URL estiver definida (ex.: Supabase Postgres no deploy), usa Postgres.
# Caso contrário, usa o Excel local. Toda a aplicação passa por load_sheet/save_sheet,
# então a troca de backend é transparente para o restante do código.
_DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
USE_POSTGRES = bool(_DATABASE_URL)
_engine = None

def _normalize_pg_url(url: str) -> str:
    """Normaliza a URL do Postgres e codifica a senha (caracteres como @ na senha
    quebram o parse). Aceita senha crua ou já codificada."""
    from urllib.parse import quote, unquote
    url = url.strip()
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if "://" not in url or "@" not in url:
        return url
    scheme, rest = url.split("://", 1)
    userinfo, host = rest.rsplit("@", 1)
    if ":" in userinfo:
        user, pwd = userinfo.split(":", 1)
        userinfo = f"{user}:{quote(unquote(pwd), safe='')}"
    return f"{scheme}://{userinfo}@{host}"


if USE_POSTGRES:
    from sqlalchemy import create_engine, inspect as _sa_inspect
    _engine = create_engine(_normalize_pg_url(_DATABASE_URL), pool_pre_ping=True)

# Colunas de cada tabela (usadas para criar tabelas vazias no Postgres)
_SCHEMA = {
    "lancamentos": ["id", "mes_ano", "cartao", "dono", "valor", "descricao",
                    "categoria", "valor_thais", "pessoa_thais", "tipo_parcela",
                    "parcela_atual", "total_parcelas", "id_grupo", "subtipo_cartao",
                    "data_lancamento"],
    "meses": ["mes_ano", "salario_kelvin", "salario_thais", "fechado"],
    "fixos": ["id", "cartao", "descricao", "categoria", "valor_estimado",
              "pessoa_thais", "valor_thais", "ativo"],
    "grupos_parcelamento": ["id", "descricao", "cartao", "subtipo_cartao", "categoria",
                            "valor_parcela", "total_parcelas", "mes_inicio",
                            "pessoa_thais", "valor_thais", "cancelado"],
    "config": ["chave", "valor"],
    "orcamentos": ["mes_ano", "categoria", "valor_planejado"],
}

SHEETS = ["lancamentos", "meses", "fixos", "config"]

CATEGORIAS = ["Essencial", "Não essencial", "Estudos", "Lazer", "Viagem", "Reforma", "Negócios", "Metinha", "Livre"]
CARTOES = ["Santander", "Itaú", "C6"]
SUBTIPOS_SANTANDER = ["Regular", "Físico"]
TIPOS = ["única", "FIXO", "ULTIMA"]

CORES_CARTAO = {
    "Itaú":      {"bg": "#FF6B00", "text": "#FFFFFF"},
    "Santander": {"bg": "#EC0000", "text": "#FFFFFF"},
    "C6":        {"bg": "#242424", "text": "#F7C15F"},
    "Santander Físico": {"bg": "#A80000", "text": "#FFFFFF"},
}


def db_exists():
    if USE_POSTGRES:
        return _sa_inspect(_engine).has_table("lancamentos")
    return DB_PATH.exists()


_CONFIG_PADRAO = [
    {"chave": "divisao_kelvin", "valor": "80"},
    {"chave": "divisao_thais", "valor": "20"},
    {"chave": "nome_kelvin", "valor": "Kelvin"},
    {"chave": "nome_thais", "valor": "Thais"},
]


def init_db():
    if USE_POSTGRES:
        # Cria tabelas vazias com as colunas corretas e popula config padrão.
        for nome, cols in _SCHEMA.items():
            if nome == "config":
                continue
            save_sheet(nome, pd.DataFrame(columns=cols))
        save_sheet("config", pd.DataFrame(_CONFIG_PADRAO))
        return

    wb = Workbook()
    wb.remove(wb.active)
    for nome, cols in _SCHEMA.items():
        ws = wb.create_sheet(nome)
        ws.append(cols)
        if nome == "config":
            for c in _CONFIG_PADRAO:
                ws.append([c["chave"], c["valor"]])
    wb.save(DB_PATH)


def load_sheet(sheet_name: str) -> pd.DataFrame:
    if USE_POSTGRES:
        try:
            return pd.read_sql_table(sheet_name, _engine)
        except Exception:
            return pd.DataFrame()
    if not db_exists():
        return pd.DataFrame()
    try:
        return pd.read_excel(DB_PATH, sheet_name=sheet_name, engine="openpyxl")
    except ValueError:
        return pd.DataFrame()


def save_sheet(sheet_name: str, df: pd.DataFrame):
    if USE_POSTGRES:
        df.to_sql(sheet_name, _engine, if_exists="replace", index=False)
        return
    wb = load_workbook(DB_PATH)
    if sheet_name in wb.sheetnames:
        del wb[sheet_name]
    ws = wb.create_sheet(sheet_name)
    ws.append(list(df.columns))
    for row in df.itertuples(index=False):
        ws.append(list(row))
    wb.save(DB_PATH)


def get_config() -> dict:
    df = load_sheet("config")
    if df.empty:
        return {}
    return dict(zip(df["chave"], df["valor"]))


def set_config(chave: str, valor):
    df = load_sheet("config")
    if chave in df["chave"].values:
        df.loc[df["chave"] == chave, "valor"] = str(valor)
    else:
        df = pd.concat([df, pd.DataFrame([{"chave": chave, "valor": str(valor)}])], ignore_index=True)
    save_sheet("config", df)


def get_meses() -> list[str]:
    df = load_sheet("meses")
    if df.empty:
        return []
    return sorted(df["mes_ano"].tolist())


def get_mes(mes_ano: str) -> dict:
    df = load_sheet("meses")
    row = df[df["mes_ano"] == mes_ano]
    if row.empty:
        return {"mes_ano": mes_ano, "salario_kelvin": 0.0, "salario_thais": 0.0, "fechado": False}
    return row.iloc[0].to_dict()


def upsert_mes(mes_ano: str, salario_kelvin: float, salario_thais: float, fechado: bool = False):
    df = load_sheet("meses")
    if mes_ano in df["mes_ano"].values:
        df.loc[df["mes_ano"] == mes_ano, "salario_kelvin"] = salario_kelvin
        df.loc[df["mes_ano"] == mes_ano, "salario_thais"] = salario_thais
        df.loc[df["mes_ano"] == mes_ano, "fechado"] = fechado
    else:
        novo = pd.DataFrame([{"mes_ano": mes_ano, "salario_kelvin": salario_kelvin,
                               "salario_thais": salario_thais, "fechado": fechado}])
        df = pd.concat([df, novo], ignore_index=True)
    save_sheet("meses", df)


def get_lancamentos(mes_ano: str) -> pd.DataFrame:
    df = load_sheet("lancamentos")
    if df.empty:
        return df
    return df[df["mes_ano"] == mes_ano].copy()


def add_lancamento(mes_ano, cartao, dono, valor, descricao, categoria,
                   valor_thais=None, pessoa_thais=None, tipo_parcela="única",
                   parcela_atual=None, total_parcelas=None, id_grupo=None,
                   subtipo_cartao=None, data_lancamento=None):
    from datetime import date as _date
    df = load_sheet("lancamentos")
    if "subtipo_cartao" not in df.columns:
        df["subtipo_cartao"] = None
    if "data_lancamento" not in df.columns:
        df["data_lancamento"] = None
    if data_lancamento is None:
        data_lancamento = _date.today().isoformat()
    novo_id = int(df["id"].max() + 1) if not df.empty and not pd.isna(df["id"].max()) else 1
    novo = {
        "id": novo_id, "mes_ano": mes_ano, "cartao": cartao, "dono": dono,
        "valor": valor, "descricao": descricao, "categoria": categoria,
        "valor_thais": valor_thais, "pessoa_thais": pessoa_thais,
        "tipo_parcela": tipo_parcela, "parcela_atual": parcela_atual,
        "total_parcelas": total_parcelas, "id_grupo": id_grupo,
        "subtipo_cartao": subtipo_cartao, "data_lancamento": data_lancamento,
    }
    df = pd.concat([df, pd.DataFrame([novo])], ignore_index=True)
    save_sheet("lancamentos", df)
    return novo_id


def aplicar_fixos_ao_mes(mes_ano: str) -> int:
    """Sprint 2: cria lançamentos pendentes (valor=0) para cada fixo ativo no mês."""
    fixos = get_fixos(apenas_ativos=True)
    if fixos.empty:
        return 0
    lanc_existentes = get_lancamentos(mes_ano)
    descs_existentes = set(lanc_existentes["descricao"].str.strip().str.lower()) if not lanc_existentes.empty else set()
    adicionados = 0
    for _, fixo in fixos.iterrows():
        desc = str(fixo["descricao"]).strip()
        if desc.lower() in descs_existentes:
            continue
        add_lancamento(
            mes_ano=mes_ano, cartao=str(fixo["cartao"]), dono="Kelvin",
            valor=float(fixo.get("valor_estimado") or 0) or 0.0,
            descricao=desc, categoria=str(fixo["categoria"]),
            valor_thais=float(fixo["valor_thais"]) if fixo.get("valor_thais") and not pd.isna(fixo["valor_thais"]) else None,
            pessoa_thais=str(fixo["pessoa_thais"]) if fixo.get("pessoa_thais") and not pd.isna(fixo["pessoa_thais"]) else None,
            tipo_parcela="FIXO",
        )
        adicionados += 1
    return adicionados


def _proximo_mes(mes_ano: str, n: int) -> str:
    """Retorna mes_ano + n meses no formato YYYY-MM."""
    from datetime import date
    ano, mes = int(mes_ano[:4]), int(mes_ano[5:7])
    total = (mes - 1) + n
    return f"{ano + total // 12}-{(total % 12) + 1:02d}"


def criar_grupo_parcelamento(
    descricao, cartao, subtipo_cartao, categoria, valor_parcela, total_parcelas,
    mes_inicio, pessoa_thais=None, valor_thais=None,
) -> int:
    """Cria o grupo e todos os lançamentos mensais. Retorna o id do grupo."""
    df_g = load_sheet("grupos_parcelamento")
    if df_g.empty or "id" not in df_g.columns:
        df_g = pd.DataFrame(columns=["id", "descricao", "cartao", "subtipo_cartao",
                                      "categoria", "valor_parcela", "total_parcelas",
                                      "mes_inicio", "pessoa_thais", "valor_thais", "cancelado"])
    novo_gid = int(df_g["id"].max() + 1) if not df_g.empty and not pd.isna(df_g["id"].max()) else 1
    novo_g = {
        "id": novo_gid, "descricao": descricao, "cartao": cartao,
        "subtipo_cartao": subtipo_cartao, "categoria": categoria,
        "valor_parcela": valor_parcela, "total_parcelas": total_parcelas,
        "mes_inicio": mes_inicio, "pessoa_thais": pessoa_thais,
        "valor_thais": valor_thais, "cancelado": False,
    }
    df_g = pd.concat([df_g, pd.DataFrame([novo_g])], ignore_index=True)
    save_sheet("grupos_parcelamento", df_g)

    for i in range(total_parcelas):
        mes = _proximo_mes(mes_inicio, i)
        # "Faltam" = parcelas restantes APÓS a atual (ex.: 4x → mês 1 mostra 3)
        faltam = total_parcelas - i - 1
        tipo = "ULTIMA" if faltam == 0 else "parcelado"
        # garante que o mês existe
        dados_mes = get_mes(mes)
        if not dados_mes.get("salario_kelvin"):
            upsert_mes(mes, 0.0, 0.0)
        add_lancamento(
            mes_ano=mes, cartao=cartao, dono="Kelvin",
            valor=valor_parcela, descricao=descricao, categoria=categoria,
            valor_thais=valor_thais, pessoa_thais=pessoa_thais,
            tipo_parcela=tipo, parcela_atual=i + 1,
            total_parcelas=faltam, id_grupo=novo_gid,
            subtipo_cartao=subtipo_cartao,
        )
    return novo_gid


def get_grupos_ativos() -> pd.DataFrame:
    """Retorna grupos com pelo menos uma parcela futura não cancelada."""
    df_g = load_sheet("grupos_parcelamento")
    if df_g.empty:
        return pd.DataFrame()
    df_l = load_sheet("lancamentos")
    if df_l.empty:
        return df_g
    # Para cada grupo, calcula parcelas restantes
    rows = []
    for _, g in df_g.iterrows():
        if g.get("cancelado"):
            continue
        lgs = df_l[df_l["id_grupo"] == g["id"]]
        total = int(g["total_parcelas"])
        pagas = len(lgs[lgs["tipo_parcela"].isin(["ULTIMA"])]) + len(
            lgs[(lgs["tipo_parcela"] == "parcelado") & (lgs["mes_ano"] < _mes_atual())]
        )
        restantes = total - pagas
        rows.append({**g.to_dict(), "pagas": pagas, "restantes": max(0, restantes)})
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _mes_atual() -> str:
    from datetime import date
    d = date.today()
    return f"{d.year}-{d.month:02d}"


def cancelar_parcelas_restantes(grupo_id: int, mes_atual: str):
    """Remove lançamentos futuros de um grupo (antecipa quitação)."""
    df = load_sheet("lancamentos")
    df = df[~((df["id_grupo"] == grupo_id) & (df["mes_ano"] > mes_atual))]
    save_sheet("lancamentos", df)
    df_g = load_sheet("grupos_parcelamento")
    df_g.loc[df_g["id"] == grupo_id, "cancelado"] = True
    save_sheet("grupos_parcelamento", df_g)


def update_lancamento(lancamento_id: int, **campos):
    df = load_sheet("lancamentos")
    for col, val in campos.items():
        if col in df.columns:
            df.loc[df["id"] == lancamento_id, col] = val
    save_sheet("lancamentos", df)


def delete_lancamento(lancamento_id: int):
    df = load_sheet("lancamentos")
    df = df[df["id"] != lancamento_id]
    save_sheet("lancamentos", df)


def get_fixos(apenas_ativos: bool = True) -> pd.DataFrame:
    df = load_sheet("fixos")
    if df.empty:
        return df
    if apenas_ativos:
        return df[df["ativo"] == True].copy()
    return df.copy()


def update_fixo(fixo_id: int, **campos):
    df = load_sheet("fixos")
    for col, val in campos.items():
        if col in df.columns:
            df.loc[df["id"] == fixo_id, col] = val
    save_sheet("fixos", df)


def delete_fixo(fixo_id: int):
    df = load_sheet("fixos")
    df = df[df["id"] != fixo_id]
    save_sheet("fixos", df)


def resumo_mes(mes_ano: str) -> dict:
    lanc = get_lancamentos(mes_ano)
    mes = get_mes(mes_ano)
    if lanc.empty:
        total = 0.0
        por_categoria = {}
    else:
        total = float(lanc["valor"].sum())
        por_categoria = lanc.groupby("categoria")["valor"].sum().to_dict()
    sal_k = float(mes.get("salario_kelvin") or 0)
    sal_t = float(mes.get("salario_thais") or 0)
    return {
        "total_gasto": total,
        "salario_kelvin": sal_k,
        "salario_thais": sal_t,
        "saldo": (sal_k + sal_t) - total,
        "por_categoria": por_categoria,
    }


def fazer_backup(manter=7) -> str:
    """Copia o banco para data/backups/. Retorna o caminho do backup criado.
    No Postgres (Supabase), o backup é gerenciado pela própria plataforma — no-op."""
    if USE_POSTGRES:
        return ""
    import shutil
    from datetime import datetime as _dt
    if not db_exists():
        return ""
    backup_dir = DB_PATH.parent / "backups"
    backup_dir.mkdir(exist_ok=True)
    ts = _dt.now().strftime("%Y%m%d_%H%M%S")
    dest = backup_dir / f"financeiro_{ts}.xlsx"
    shutil.copy2(DB_PATH, dest)
    # Remove backups antigos, mantém os N mais recentes
    backups = sorted(backup_dir.glob("financeiro_*.xlsx"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in backups[manter:]:
        old.unlink()
    return str(dest)


def listar_backups() -> list:
    if USE_POSTGRES:
        return []
    backup_dir = DB_PATH.parent / "backups"
    if not backup_dir.exists():
        return []
    return sorted(backup_dir.glob("financeiro_*.xlsx"), key=lambda p: p.stat().st_mtime, reverse=True)


def get_orcamentos(mes_ano: str) -> dict:
    """Retorna {categoria: valor_planejado} para o mês."""
    df = load_sheet("orcamentos")
    if df.empty or "mes_ano" not in df.columns:
        return {}
    df = df[df["mes_ano"] == mes_ano]
    if df.empty:
        return {}
    return dict(zip(df["categoria"], df["valor_planejado"].astype(float)))


def set_orcamento(mes_ano: str, categoria: str, valor_planejado: float):
    df = load_sheet("orcamentos")
    if df.empty or "mes_ano" not in df.columns:
        df = pd.DataFrame(columns=["mes_ano", "categoria", "valor_planejado"])
    mask = (df["mes_ano"] == mes_ano) & (df["categoria"] == categoria)
    if mask.any():
        df.loc[mask, "valor_planejado"] = valor_planejado
    else:
        df = pd.concat([df, pd.DataFrame([{"mes_ano": mes_ano, "categoria": categoria,
                                            "valor_planejado": valor_planejado}])], ignore_index=True)
    save_sheet("orcamentos", df)


def delete_orcamento(mes_ano: str, categoria: str):
    df = load_sheet("orcamentos")
    if df.empty:
        return
    df = df[~((df["mes_ano"] == mes_ano) & (df["categoria"] == categoria))]
    save_sheet("orcamentos", df)


def calcular_divisao_mes(mes_ano: str, pct_k: float, pct_t: float) -> dict:
    """
    Retorna quanto cada um deve pagar no mês.

    Regra: se o lançamento tem valor_thais + pessoa_thais preenchidos,
    esse valor é responsabilidade de Pessoa (ex: Thais paga direto).
    O restante é dividido pct_k/pct_t entre Kelvin e a outra pessoa.
    """
    lanc = get_lancamentos(mes_ano)
    if lanc.empty:
        return {"total": 0.0, "kelvin": 0.0, "thais": 0.0, "thais_direto": 0.0,
                "saldo_kelvin": 0.0, "saldo_thais": 0.0}

    total = float(lanc["valor"].sum())

    # Valor direto de Pessoa (ex: Thais deve pagar de volta para Kelvin)
    mask_pessoa = lanc["pessoa_thais"].notna() & (lanc["valor_thais"].notna())
    thais_direto = float(lanc.loc[mask_pessoa, "valor_thais"].sum()) if mask_pessoa.any() else 0.0

    # Valor compartilhado = total menos itens que são 100% de Kelvin sem divisão
    # A divisão pct_k/pct_t é sobre o total gasto no cartão
    kelvin_paga = round(total * pct_k / 100, 2)
    thais_paga_proporcional = round(total * pct_t / 100, 2)

    return {
        "total": total,
        "kelvin": kelvin_paga,
        "thais_proporcional": thais_paga_proporcional,
        "thais_direto": thais_direto,
    }
