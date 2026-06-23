# 💰 Controle Financeiro

Aplicativo web pessoal para controle de gastos, faturas, parcelamentos e divisão de despesas — substituindo a planilha `CONTAS.xlsx`. Construído em **Streamlit** com banco de dados em **Excel (.xlsx)**.

## Funcionalidades

- **Dashboard** — salários, total gasto, saldo, gastos por categoria, divisão 80/20, top 10 gastos, orçamento por categoria com alertas
- **Histórico** — evolução de gastos mês a mês, comparativos por categoria/cartão
- **Lançamentos** — tabela estilo Excel com badges por banco, edição e exclusão
- **Parcelamentos** — projeção automática de parcelas nos meses futuros
- **Fixos** — despesas recorrentes aplicadas automaticamente a cada mês
- **Importar** — upload de até 5 prints de fatura; a IA (Claude) reconhece banco, valores e parcelas, com deduplicação antes de salvar
- **Configurações** — nomes, divisão, exportação Excel completa, backup automático

---

## Rodando localmente (Windows)

```bash
# 1. Criar ambiente virtual
python -m venv venv

# 2. Instalar dependências
venv\Scripts\python.exe -m pip install -r requirements.txt

# 3. Iniciar (ou dar duplo-clique em iniciar.bat)
venv\Scripts\python.exe -m streamlit run app.py
```

Acesse **http://localhost:8501**.

Na primeira execução, o sistema migra automaticamente os dados de Jul-26 a Dez-26 da planilha original.

---

## Deploy online — GRATUITO (Streamlit Community Cloud + Supabase)

Hospedagem 100% gratuita com persistência real: o **Streamlit Community Cloud** roda o
app e o **Supabase** (Postgres free) guarda os dados. O app detecta `DATABASE_URL` e usa
Postgres automaticamente; sem ela, continua no Excel local.

### Variáveis de ambiente / secrets

| Variável | Obrigatória | Descrição |
|----------|-------------|-----------|
| `DATABASE_URL` | Sim (deploy) | String de conexão Postgres do Supabase (Session pooler). |
| `APP_PASSWORD` | Recomendada | Senha de acesso. Sem ela, o app fica **aberto**. |
| `ANTHROPIC_API_KEY` | Opcional | Chave da API para a aba Importar. |

### Passo a passo

**1. Criar o banco no Supabase (grátis)**
- Crie conta em [supabase.com](https://supabase.com) → **New project**.
- Defina uma senha forte para o banco (guarde-a).
- Em **Project Settings → Database → Connection string → Session pooler**, copie a URI
  (formato `postgresql://postgres.xxxx:SENHA@aws-0-regiao.pooler.supabase.com:5432/postgres`).

**2. Carregar seus dados atuais no Supabase (uma vez, local)**
```bash
venv\Scripts\python.exe seed_supabase.py "POSTGRESQL_URL_AQUI"
```
Isso copia todas as abas do seu Excel local para o Postgres.

**3. Publicar no Streamlit Community Cloud**
- Suba o código para um repositório no GitHub (segredos já protegidos pelo `.gitignore`).
- Em [share.streamlit.io](https://share.streamlit.io) → **New app** → selecione o repo,
  branch e `app.py`.
- Em **Advanced settings → Secrets**, cole:
  ```toml
  DATABASE_URL = "postgresql://postgres.xxxx:SENHA@aws-0-regiao.pooler.supabase.com:5432/postgres"
  APP_PASSWORD = "sua-senha-de-acesso"
  ANTHROPIC_API_KEY = "sk-ant-..."   # opcional
  ```
- **Deploy**. Em ~2 min você recebe uma URL pública `https://<app>.streamlit.app`.

**4. Acessar**
- Abra a URL em qualquer dispositivo → tela de senha (`APP_PASSWORD`) → app.
- Todos os dados ficam no Supabase e **persistem** entre reinícios e redeploys.

### Segurança

- Acesso protegido por senha (`APP_PASSWORD`), com botão **Sair** na barra lateral.
- Segredos **nunca** vão para o repositório (veja [`.gitignore`](.gitignore)); ficam só
  nos Secrets da plataforma.
- Tráfego HTTPS por padrão; conexão ao Supabase via SSL.

---

## Deploy alternativo (Docker — Railway/Render, com disco)

Também há `Dockerfile`, [`render.yaml`](render.yaml) e [`railway.json`](railway.json) prontos
para deploy via container usando volume persistente (`DATA_DIR=/data`) com o backend Excel.
Essas plataformas exigem **plano pago** para disco persistente — use a opção gratuita acima
quando possível.

---

## Backups

- Backup automático **diário** ao abrir o app (mantém os 7 mais recentes em `data/backups/`).
- Backup manual e histórico disponíveis na aba **Configurações**.
- Exportação completa para Excel (uma aba por mês) também em **Configurações**.

---

## Estrutura

```
financeiro/
├── app.py               # Interface Streamlit (todas as páginas)
├── modules/
│   ├── db.py            # Camada de dados (Excel via openpyxl/pandas)
│   └── migration.py     # Migração da planilha original
├── data/
│   ├── financeiro.xlsx  # Banco de dados (local)
│   └── backups/         # Backups automáticos
├── Dockerfile           # Imagem para deploy
├── render.yaml          # Blueprint do Render
├── railway.json         # Config do Railway
└── requirements.txt
```
