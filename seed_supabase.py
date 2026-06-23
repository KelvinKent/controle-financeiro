"""
Carrega os dados do Excel local para o Postgres (Supabase). Rode UMA vez,
localmente, depois de criar o projeto no Supabase.

Uso:
    venv\\Scripts\\python.exe seed_supabase.py "postgresql://postgres:SENHA@host:5432/postgres"

Ou defina a variável de ambiente DATABASE_URL e rode sem argumento:
    set DATABASE_URL=postgresql://...
    venv\\Scripts\\python.exe seed_supabase.py
"""
import os
import sys
import pandas as pd
from pathlib import Path
from urllib.parse import quote, unquote
from sqlalchemy import create_engine

XLSX = Path(__file__).parent / "data" / "financeiro.xlsx"


def normalize_pg_url(url: str) -> str:
    """Normaliza a URL do Postgres e codifica a senha (caracteres como @, :, /
    na senha quebram o parse da URL). Aceita senha crua OU já codificada."""
    url = url.strip()
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if "://" not in url or "@" not in url:
        return url
    scheme, rest = url.split("://", 1)
    userinfo, host = rest.rsplit("@", 1)  # último @ separa userinfo do host
    if ":" in userinfo:
        user, pwd = userinfo.split(":", 1)
        pwd = quote(unquote(pwd), safe="")  # re-codifica (evita codificar duas vezes)
        userinfo = f"{user}:{pwd}"
    return f"{scheme}://{userinfo}@{host}"


def main():
    url = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("DATABASE_URL", "")).strip()
    if not url:
        print("ERRO: forneça a DATABASE_URL como argumento ou variável de ambiente.")
        sys.exit(1)
    url = normalize_pg_url(url)
    if not XLSX.exists():
        print(f"ERRO: banco local não encontrado em {XLSX}")
        sys.exit(1)

    engine = create_engine(url, pool_pre_ping=True)
    print(f"Conectando ao Postgres e carregando {XLSX.name}...\n")

    sheets = pd.read_excel(XLSX, sheet_name=None, engine="openpyxl")
    for nome, df in sheets.items():
        df.to_sql(nome, engine, if_exists="replace", index=False)
        print(f"  ✓ {nome}: {len(df)} linha(s)")

    print("\nSeed concluído! O Supabase agora contém todos os seus dados.")


if __name__ == "__main__":
    main()
