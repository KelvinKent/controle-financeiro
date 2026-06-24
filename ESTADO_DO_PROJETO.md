# 📦 Estado do Projeto — Controle Financeiro (Handoff completo)

> Documento de transferência para continuar o projeto em outra sessão/chat.
> Resume **tudo**: arquitetura, dados, links, acessos, decisões e pendências.
> Atualizado na Sprint 9.

---

## 1. Visão geral

App web pessoal que **substitui a planilha `CONTAS.xlsx`** para controle de gastos,
faturas de cartão, parcelamentos, fixos, divisão de despesas (80/20) e previsão.
Feito em **Streamlit** (Python). Banco: **Excel local** OU **Postgres (Supabase)** —
seleção automática pela variável `DATABASE_URL`.

- **Usuário:** Kelvin (parceira: Thais). Divisão padrão de despesas compartilhadas: **80% Kelvin / 20% Thais**.
- **Meses migrados:** Julho/2026 a Dezembro/2026 (origem: abas da planilha). Novos meses podem ser criados (Jan/2027+).

---

## 2. Links e acessos

| Item | Valor |
|------|-------|
| **App ao vivo** | https://controle-financeiro-25i6sfkkap9zczf5oyok7k.streamlit.app |
| **Repositório (público)** | https://github.com/KelvinKent/controle-financeiro |
| **Branch** | `main` (deploy automático a cada push) |
| **Hospedagem** | Streamlit Community Cloud (gratuito) |
| **Banco de dados** | Supabase (Postgres, plano free) — projeto "KelvinKent's Project" |
| **Pasta local** | `C:\Users\kelvin.araujo\ClaudeCode\financeiro` |
| **Conta GitHub** | KelvinKent |

### Segredos (NÃO ficam no código — nunca commitar)
Configurados em **Streamlit Cloud → Manage app → Settings → Secrets**:

| Secret | Para que serve |
|--------|----------------|
| `DATABASE_URL` | Conexão Postgres do Supabase (Session pooler, porta 5432). |
| `APP_PASSWORD` | Senha de acesso ao app (tela de login). Alterável nos Secrets. |
| `ANTHROPIC_API_KEY` | Análise de prints na aba Importar (opcional). |

- **Onde alterar a senha do app:** Streamlit Cloud → Settings → Secrets → editar `APP_PASSWORD` → Save.
- **Connection string do Supabase:** painel Supabase → botão **Connect** (topo) → **Session pooler**.
- ⚠️ **Pendência de segurança:** a senha do banco Supabase foi exposta em chat durante o
  desenvolvimento. **Recomenda-se resetá-la** (Supabase → Settings → Database → Reset database
  password) e atualizar `DATABASE_URL` nos Secrets do Streamlit.

---

## 3. Stack e arquitetura

- **Frontend+Backend:** Python 3.12 (deploy) / 3.14 (local) + Streamlit `1.41.1` (pinado; `starlette 0.41.3`).
- **Dados:** camada única em `modules/db.py`. Tudo passa por `load_sheet()` / `save_sheet()`:
  - Se `DATABASE_URL` definido → **Postgres** (SQLAlchemy + psycopg2). Cada "aba" vira uma tabela.
  - Senão → **Excel** local (`data/financeiro.xlsx`, openpyxl/pandas).
- **Gráficos:** Plotly Express (Altair é incompatível com Python 3.14).
- **IA (Importar):** Anthropic API (`claude-sonnet-4-6`) com visão, para ler prints de fatura.

---

## 4. Estrutura de arquivos

```
financeiro/
├── app.py                  # Toda a interface Streamlit (todas as páginas)
├── modules/
│   ├── db.py               # Camada de dados (Excel/Postgres), fórmulas, helpers
│   └── migration.py        # Migração inicial da planilha CONTAS.xlsx
├── data/
│   ├── financeiro.xlsx     # Banco LOCAL (gitignored)
│   └── backups/            # Backups automáticos + pré-resync (gitignored)
├── seed_supabase.py        # Carrega o Excel local → Supabase (rodar 1x na 1ª vez)
├── resync_planilha.py      # Re-sincroniza Jul-Dez/26 da planilha → Supabase (preserva parcelamentos)
├── requirements.txt        # streamlit, pandas, plotly, openpyxl, anthropic, sqlalchemy, psycopg2-binary
├── Dockerfile              # Deploy alternativo via container
├── render.yaml / railway.json   # Configs de deploy alternativo (pagos, c/ disco)
├── .streamlit/
│   ├── config.toml         # Tema dark + server headless
│   └── secrets.toml.example # Modelo de secrets (sem valores reais)
├── iniciar.bat             # Inicia o app local via venv
├── README.md               # Instalação e deploy
└── ESTADO_DO_PROJETO.md    # (este arquivo) handoff completo
```

> **Python 3.14 local exige venv** (`financeiro\venv\`) — o `-m` do 3.14 não acha pacotes
> de usuário. Rodar sempre com `venv\Scripts\python.exe`.

---

## 5. Modelo de dados (tabelas / colunas)

Definido em `_SCHEMA` no `db.py`:

- **lancamentos**: `id, mes_ano, cartao, dono, valor, descricao, categoria, valor_thais,
  pessoa_thais, tipo_parcela, parcela_atual, total_parcelas, id_grupo, subtipo_cartao,
  data_lancamento, conferido`
- **meses**: `mes_ano, salario_kelvin, salario_thais, fechado`
- **fixos**: `id, cartao, descricao, categoria, valor_estimado, pessoa_thais, valor_thais, ativo`
- **grupos_parcelamento**: `id, descricao, cartao, subtipo_cartao, categoria, valor_parcela,
  total_parcelas, mes_inicio, pessoa_thais, valor_thais, cancelado`
- **config**: `chave, valor` (nome_kelvin, nome_thais, divisao_kelvin=80, divisao_thais=20)
- **orcamentos**: `mes_ano, categoria, valor_planejado`
- **painel**: `mes_ano, agua_boleto, youtube_lembrete, spotify_lembrete, cdb_reserva, previdencia`

**Semântica importante:**
- `mes_ano` formato `AAAA-MM` (ex.: `2026-07`). Rótulos formatados por `fmt_mes()` (qualquer ano).
- `dono` = "Kelvin" ou "Thais" (titular do cartão na planilha, col C).
- `valor_thais` + `pessoa_thais` = quanto alguém (Thais/Mãe/etc.) deve ressarcir (col G/H da planilha).
- `tipo_parcela`: `única | FIXO | ULTIMA | parcelado`.
- `total_parcelas` na exibição = **"Faltam"** = parcelas restantes APÓS a atual (4x → 3,2,1,ÚLTIMA).
- `conferido` (bool) = item batido com o app do banco (checkbox verde em Lançamentos).
- **Parcelamento:** usuário informa o **valor TOTAL**; o app divide pelo nº de parcelas.

**Dados atuais (vivos no Supabase, variam conforme edições):**
~531 lançamentos · 34 fixos · 6 meses (Jul–Dez/26) · 1 grupo de parcelamento (Insulfilm, Ago–Nov, 4x R$225).

---

## 6. Funcionalidades por página

- **Dashboard (Home):** salários editáveis; **painel-resumo réplica da planilha** (ver §7);
  campos editáveis do painel (Água, lembretes YouTube/Spotify, CDB, Previdência) por mês;
  cards de saldo; gráfico de gastos por categoria; divisão 80/20; Top 10; export Excel do mês.
- **Histórico:** evolução mês a mês, comparativos por categoria/cartão, filtros de período.
- **Lançamentos:** tabela estilo Excel; **checkbox "Conferido" (1ª coluna, linha fica verde)**;
  totais por cartão no topo; editar/excluir **por linha**; badges coloridas por banco;
  coluna Faltam (3,2,1,ÚLTIMA); filtros; **ordenação estável por id** (antigos→novos).
- **Parcelamentos:** grupos ativos, progresso, projeção por mês, quitar antecipado.
- **Fixos:** tabela; editar/excluir/pausar **por linha**; formulário de edição inline.
- **Importar:** upload de até 5 prints (PNG/JPG/WEBP); IA detecta banco, valores e parcelas;
  deduplicação por valor/descrição similar; revisão editável antes de salvar.
- **Configurações:** nomes, divisão %, **criar meses futuros (previsão, ilimitado)**,
  exportação completa Excel, backup (Postgres = gerenciado pela plataforma).

---

## 7. Fórmulas do painel-resumo (réplica da planilha)

Reproduzidas em `calcular_painel()` no `db.py`:

| Campo | Fórmula |
|-------|---------|
| Cartão Kelvin | `SUMIF(dono="Kelvin", valor)` |
| Cartão Thais | `SUMIF(dono="Thais", valor)` |
| Pagamentos | `-SUM(valor_thais)` (todas as linhas) |
| Água - Boleto | digitação livre (tabela `painel`) |
| Mãe | `-SUMIF(pessoa="Mãe", valor)` |
| **Total Gastos+Pix** | soma dos 5 acima |
| Diferença Kelvin | `salário_kelvin − Total` |
| Gastos Thais (Cartão/Total) | `SUMIF(pessoa="Thais", valor_thais)` |
| Diferença Thais | `salário_thais − Gastos Thais` |
| Investimentos (CDB, Previdência) | digitação livre (tabela `painel`) |
| Lembretes YouTube/Spotify | texto editável (tabela `painel`) |

**Observações de fidelidade (Julho/26):** o painel pode divergir levemente da planilha porque
o app tem o Insulfilm (não está na planilha) e a planilha tem 2 linhas sem valor lançado
(Convênio Itaú s/ valor + divisão avulsa de R$338, ambos "valor apenas para Thais") que não
viram lançamento. Decisão do usuário: **deixar como está**.

---

## 8. Rodar localmente (Windows)

```bash
cd C:\Users\kelvin.araujo\ClaudeCode\financeiro
venv\Scripts\python.exe -m pip install -r requirements.txt   # 1ª vez
venv\Scripts\python.exe -m streamlit run app.py              # ou duplo-clique em iniciar.bat
```
Sem `DATABASE_URL`, usa o Excel local. Acesse http://localhost:8501.

---

## 9. Deploy e atualização

- **Atualizar o app publicado:** `git add`, `git commit`, `git push origin main` →
  Streamlit Cloud redeploya automático (~2 min).
- **1ª publicação (já feita):** Supabase criado → `seed_supabase.py` (carga inicial) →
  Streamlit Cloud apontando para o repo + Secrets preenchidos.
- **Re-sincronizar com a planilha** (quando atualizar `CONTAS.xlsx`):
  ```bash
  set DATABASE_URL=postgresql://...   (Session pooler do Supabase)
  venv\Scripts\python.exe resync_planilha.py
  ```
  Faz backup, reimporta Jul–Dez/26 e **preserva parcelamentos do app**.

---

## 10. Histórico de sprints (todas concluídas)

1. **Fundação + migração** (Jul–Dez/26 da planilha; Excel como banco).
2. **Fixos automáticos** (template + aplicar ao mês).
3. **Parcelamentos** (projeção automática, quitar antecipado).
4. **Dashboard e histórico** (gráficos, Top 10, export).
5. **Divisão 80/20 + orçamento por categoria** (alertas).
6. **Importar via print** (IA Claude, dedupe, revisão).
7. **Polimento, backup, export, README.**
8. **Deploy online** — escolhido **Streamlit Cloud + Supabase** (gratuito, persistente).
9. **Painel-resumo na Home + Conferido + criar meses futuros + re-sync da planilha.**

### Decisões/ajustes relevantes do usuário
- Coluna "Thais" → **"Pessoa"** (quem deve ressarcir: Thais, Mãe, amigos…).
- Cores dos bancos: Itaú `#FF6B00`, Santander `#EC0000`, Santander Físico `#A80000`, C6 preto.
- Santander permite subtipo **Físico/Regular**.
- Valores negativos em Lançamentos = **crédito** → exibidos em **verde**.
- Descrições TODO-MAIÚSCULAS exibidas em Título (sem alterar o dado).
- "Faltam": padrão da planilha **3, 2, 1, ÚLTIMA**.
- Checkbox "Conferido" reproduz o "pintar de verde" da planilha.

---

## 11. Pendências / ideias futuras

- [ ] **Resetar a senha do Supabase** e atualizar `DATABASE_URL` (segurança).
- [ ] Rótulo "R$ 13.333" no gráfico de categorias estava sendo cortado — ajustado
  (margem/headroom do eixo Y); revalidar visualmente.
- [ ] (Opcional) importar as 2 linhas sem valor da planilha p/ o painel bater 100%.
- [ ] (Opcional) gerar Jan–Dez/2027 para previsão (via Configurações → Criar meses futuros).

---

## 12. Gotchas técnicos (importante para quem continuar)

- **Badges/HTML colorido:** usar `st.html()` com **estilos inline** (st.markdown remove styles).
- **st.html por linha** em Lançamentos/Fixos: cada linha é um flex; botões de ação ficam em
  `st.columns` ao lado (Streamlit não coloca botões dentro de `st.html`).
- **Ordenação:** sempre por `id` (Postgres não garante ordem sem ORDER BY; data_lancamento ficou
  vazio após re-sync → ordenar por data reembaralhava ao clicar no checkbox).
- **Escrita no Postgres:** `update_lancamento`/`delete_lancamento` usam UPDATE/DELETE direto
  (rápido); criação de muitos itens usa `add_lancamentos_bulk` (1 escrita) — evita reescrever a
  tabela inteira a cada item (causava lentidão e já gerou duplicidade).
- **Senha do Postgres com `@`:** a URL é normalizada/encodada em `_normalize_pg_url` (db.py) e no
  `seed_supabase.py` — não precisa codificar manualmente.
- **NÃO incluir `pillow-heif`** no requirements: quebra o build no Streamlit Cloud (precisa de
  libheif do sistema) e derruba o ambiente inteiro. Conversão HEIC é opcional/lazy.
- **Auth:** gate por `APP_PASSWORD` no topo do `app.py`; sem a variável, acesso é livre (uso local).
</content>
