# 📦 Estado do Projeto — Controle Financeiro (Handoff completo)

> Documento de transferência para continuar o projeto em outra sessão/chat.
> Resume **tudo**: arquitetura, dados, links, acessos, decisões e pendências.
> Atualizado na Sprint 10 (2026-06-25).

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
- **meses**: `mes_ano, salario_kelvin, salario_thais, fechado` (`fechado` em uso real desde a Sprint 10 — ver §6/§10)
- **fixos**: `id, cartao, descricao, categoria, valor_estimado, pessoa_thais, valor_thais, ativo,
  subtipo_cartao` (coluna adicionada dinamicamente; já existe na tabela viva)
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
- `total_parcelas` na exibição/edição = **"Faltam"** = parcelas restantes APÓS a atual (4x → 3,2,1,ÚLTIMA).
  Pode ser **1** (última antes do ÚLTIMA) — campos de edição usam `min_value=1`, nunca `2` (ver §12).
- `conferido` (bool) = item batido com o app do banco (checkbox verde em Lançamentos).
- `subtipo_cartao`: Santander → `Regular|Físico`; **Itaú → `Visa|Mastercard`** (`SUBTIPOS_ITAU` em
  `db.py`, badge com chip de cor da bandeira — Visa `#1A1F71`, Mastercard `#EB001B`). C6 não tem subtipo.
- `fechado` (tabela `meses`): mês marcado como pago pelo botão "🔒 Fechar mês" no Dashboard. Ao
  abrir o app, o mês padrão exibido é o **primeiro não-fechado** (cronológico) — não mais
  calculado pela data do calendário. `upsert_mes()` só altera `fechado` se passado explicitamente
  (preserva o valor ao salvar só salários).
- **Parcelamento (criação):** o usuário escolhe se o valor digitado é o **total da compra**
  (app divide pelas parcelas, padrão) ou já o **valor de cada parcela** (usa direto, sem dividir)
  — seletor "O valor informado acima é" no formulário, só aparece criando um lançamento novo.
- **Parcelamento (edição):** ao editar uma parcela que já pertence a um grupo (`id_grupo`), o
  campo "Valor" passa a significar o valor **desta parcela**, e salvar propaga esse valor (e
  divisão/categoria) para as parcelas seguintes do mesmo grupo via `propagar_parcela_grupo()`.

**Dados atuais (vivos no Supabase, variam conforme edições):**
~531+ lançamentos · 35 fixos · 6 meses (Jul–Dez/26) · grupos de parcelamento incluindo Insulfilm
(Ago–Nov, 4x R$225) e Presente Zara (Ago–Dez, 5x R$281,86 — corrigido na Sprint 10, ver §10).

---

## 6. Funcionalidades por página

- **Dashboard (Home):** **🔒 Fechar mês / 🔓 Reabrir mês** (canto superior, ver §10); saldo
  combinado em destaque (card "hero"); salários editáveis; **painel-resumo réplica da planilha**
  (ver §7); campos editáveis do painel (Água, lembretes YouTube/Spotify, CDB, Previdência) por
  mês; gráfico de gastos por categoria (margem ajustada p/ não cortar rótulo); divisão 80/20;
  Top 10; export Excel do mês.
- **Histórico:** evolução mês a mês, comparativos por categoria/cartão, filtros de período.
- **Lançamentos:** tabela estilo Excel; **checkbox "Conferido" (1ª coluna, linha fica verde)**;
  **cards "Totais por cartão" clicáveis** (cor da bandeira/banco) que filtram a tabela — clicar
  **substitui** a seleção (não acumula), clicar de novo no card ativo limpa o filtro; editar
  **via popup (`st.dialog`)** em vez de formulário no fim da página; excluir por linha; badges
  coloridas por banco/bandeira (Itaú mostra chip extra Visa/Mastercard); coluna Faltam
  (3,2,1,ÚLTIMA); filtros (Categoria, Tipo, Cartão, Santander, Itaú, ordenação, busca — todos
  com `key` para não perder o estado); **ordenação estável por id** (antigos→novos); botão
  "Novo lançamento" e filtros aparecem **antes** de qualquer ação com `st.rerun()` (ver §12).
- **Parcelamentos:** grupos ativos, progresso, projeção por mês, quitar antecipado.
- **Fixos:** tabela; editar/excluir/pausar **por linha**; formulário "Novo fixo" e edição
  **reativos** (sem `st.form`) — mostram seletor de **bandeira/tipo** (Santander Regular/Físico,
  Itaú Visa/Mastercard) conforme o cartão escolhido.
- **Importar:** upload de até 5 prints (PNG/JPG/WEBP); IA detecta banco, valores e parcelas;
  deduplicação por valor/descrição similar; revisão editável antes de salvar — inclui **seletor
  de banco/bandeira** (corrige se a IA errou), campo **"Pessoa"** editável (padrão Thais, mas
  pode trocar) + coluna de valor por item para a divisão, e checkbox **"Fixo"** por item (se
  marcado, também cadastra em Fixos e redireciona pra lá após importar).
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

### Multi-usuário (Sprint 11) — conta da Mãe
- O app agora suporta **mais de uma conta** no mesmo deploy/banco. Cada conta tem
  senha própria e só vê seus próprios dados (filtro pela coluna `usuario`, aplicado
  centralmente em `load_sheet`/`save_sheet` em `modules/db.py`).
- Contas definidas em `_CONTAS` no topo do `app.py`: `kelvin` (senha em
  `APP_PASSWORD`) e `mae` (senha em `APP_PASSWORD_MAE`).
- **Para cadastrar a senha da Mãe:** no painel do Streamlit Cloud, abrir o app →
  "⋮" → **Settings** → **Secrets**, e adicionar a linha:
  ```
  APP_PASSWORD_MAE = "a-senha-que-ela-vai-usar"
  ```
  (mesma tela onde já está `APP_PASSWORD`/`DATABASE_URL`). Salvar reinicia o app
  automaticamente. Depois disso, a tela de login passa a mostrar um seletor de
  conta (Kelvin/Mãe) antes do campo de senha.
- Dados antigos (tudo criado antes dessa sprint) pertencem à conta `kelvin` —
  migração automática adiciona a coluna `usuario` nas tabelas Postgres existentes
  e marca essas linhas como `kelvin` na primeira leitura após o deploy.
- Para adicionar uma terceira conta no futuro, basta um novo item em `_CONTAS` +
  uma nova variável de senha nos Secrets — não precisa de mudança em `db.py`.

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
10. **Bandeira Itaú (Visa/Mastercard) + UX de filtros/edição + fechar mês + correções de
    parcelamento** — ver detalhes abaixo.
11. **Multi-usuário (conta da Mãe) + importação dos dados dela + cartão LATAM Pass + controles
    paralelos manuais** — ver detalhes abaixo.

### Sprint 10 — detalhes (2026-06-25)
- **Lançamentos:** cards de "Totais por cartão" clicáveis (filtram a tabela, substituindo a
  seleção em vez de acumular); edição movida para popup (`st.dialog`); filtros com `key` +
  reordenados para nunca perder o estado ao salvar/aplicar fixos (ver §12).
- **Bandeira Itaú:** novo subtipo `Visa|Mastercard` (`SUBTIPOS_ITAU`), com badge colorida,
  filtro dedicado e quebra nos cards de totais — espelha o que já existia para Santander.
  Lançamentos de Itaú de **Julho e Agosto/2026** já tiveram a bandeira corrigida manualmente
  direto no Supabase (com backup local antes de cada mudança); itens "Amil" e "Reserva" ficaram
  sem bandeira por não constarem na lista do usuário.
- **Fixos:** formulário "Novo fixo" e edição ganharam o mesmo seletor de bandeira/tipo (estava
  faltando porque o form usava `st.form`, não reativo — convertido para o padrão de Lançamentos).
- **Importar:** seletor de banco/bandeira editável (corrige detecção errada da IA), campo
  "Pessoa" (quem paga a divisão, não só Thais) + valor por item, checkbox "Fixo" por item
  (cadastra em Fixos e redireciona pra lá).
- **Fechar mês:** botão no Dashboard (`set_mes_fechado`/`get_meses_fechados` em `db.py`); mês
  padrão ao abrir o app passa a ser o primeiro não-fechado, não mais calculado pela data real.
- **Correções de bugs:**
  - Crash ao editar lançamento com **valor negativo** (estorno/crédito) ou **parcela com 1
    parcela restante** — `min_value` dos campos de valor/parcelas estava bloqueando.
  - Edição de parcela existente **não propagava** o valor corrigido para os meses seguintes do
    mesmo parcelamento (caso real: "Presente Zara", Ago–Dez/26, corrigido manualmente + função
    `propagar_parcela_grupo()` criada para isso não se repetir).
  - Legenda do parcelamento renderizando como fórmula matemática (dois `R$` sem escape no mesmo
    texto Markdown — Streamlit interpretava como LaTeX).
  - Aviso do Streamlit sobre `session_state` no campo de valor da divisão (Thais).
  - Filtros da página Lançamentos perdendo o valor ao criar lançamento/aplicar fixos (ver §12).
  - Cliques nos cards de cartão acumulando filtros em vez de substituir.

### Decisões/ajustes relevantes do usuário
- Coluna "Thais" → **"Pessoa"** (quem deve ressarcir: Thais, Mãe, amigos…) — também configurável
  na importação (campo "Pessoa" não é mais fixo em "Thais").
- Cores dos bancos: Itaú `#FF6B00` (+ chip Visa `#1A1F71` / Mastercard `#EB001B`), Santander
  `#EC0000`, Santander Físico `#A80000`, C6 preto.
- Santander permite subtipo **Físico/Regular**; Itaú permite bandeira **Visa/Mastercard**.
- Valores negativos em Lançamentos = **crédito** → exibidos em **verde** (e devem ser editáveis
  sem erro — `min_value` não pode bloquear negativo nesses campos).
- Descrições TODO-MAIÚSCULAS exibidas em Título (sem alterar o dado).
- "Faltam": padrão da planilha **3, 2, 1, ÚLTIMA**.
- Checkbox "Conferido" reproduz o "pintar de verde" da planilha.
- "Fechar mês" é controle manual do usuário (não automático por data) — ele decide quando já
  pagou a fatura do mês.

### Sprint 11 — detalhes (2026-06-26): multi-usuário + conta da Mãe
- **Multi-usuário:** cada conta (`kelvin`, `mae`) tem senha própria (`APP_PASSWORD` /
  `APP_PASSWORD_MAE` nos Secrets) e só vê seus dados — coluna `usuario` filtrada centralmente
  em `load_sheet`/`save_sheet` (`modules/db.py`). Ver §9 "Multi-usuário" para onde cadastrar
  senha de uma nova conta. Ids de `lancamentos`/`grupos_parcelamento`/`controles_extra` são
  **globalmente únicos entre contas** (`_next_id`), mesmo cada conta só vendo os seus.
- **Cartão LATAM Pass:** novo subtipo de Itaú (`SUBTIPOS_ITAU = ["Visa","Mastercard","LATAM Pass"]`),
  usado pela Mãe.
- **Controles paralelos da Mãe** (tabela `controles_extra`, genérica nome/valor/nota por mês/tipo):
  - `salario_componente` (Dashboard): itens que somados definem o salário do mês automaticamente.
  - `fixas` (Lançamentos): orçamento mensal livre.
  - `cofrinho` (Dashboard): extrato de poupança; copiado do mês anterior ao criar mês novo.
  - `aluguel` (Lançamentos): mesma lógica de cópia automática.
  Todos os 4 editores só aparecem para `usuario=="mae"` — zero mudança visual para o Kelvin.
- **Importação dos dados históricos da Mãe** (planilha "CONTAS - Mãe.xlsx", Jan–Ago/26): 163
  lançamentos + 28 componentes de salário + 83 fixas + 89 itens de cofrinho + 88 de aluguel.
  Categoria "." → "Livre"; "Faltam"="2x" → parcelado com 1 parcela restante; linhas sem valor
  preenchido na planilha foram ignoradas; reembolsos "Pessoa=Mãe" no Santander do Kelvin foram
  importados **sem** valor de reembolso (campo vazio, conforme decisão do usuário).
- **🔴 Incidente grave durante a importação** (corrigido no mesmo dia): um bug em
  `_load_sheet_raw` (Postgres) engolia qualquer erro de conexão e retornava tabela vazia; como
  `save_sheet` usa essa leitura para preservar as linhas de OUTRAS contas ao regravar a tabela
  inteira, uma falha de conexão transiente (durante um script que fazia ~900 escritas em
  sequência) fez a função "achar" que não havia dados do Kelvin e **apagou toda a tabela
  `lancamentos` dele**. Causa raiz corrigida: agora só retorna vazio quando a tabela realmente
  não existe; qualquer outro erro propaga (`raise`) em vez de ser silenciado. Recuperação:
  restaurado de `data/backups/financeiro_20260625_050353.xlsx` (531 linhas, ids originais
  preservados) + reaplicadas as correções de bandeira Itaú (Jul/Ago) e do grupo "Presente Zara"
  manualmente a partir dos scripts já usados nesta sessão. **Confirmado com o usuário: nenhuma
  edição feita diretamente no app fora desta conversa foi perdida.** Lição: o Supabase Free não
  tem backup nativo (ver §11) — qualquer script que faça muitas escritas em sequência no Postgres
  deve gravar cada tabela **uma única vez** (montar tudo em memória primeiro), não fazer uma
  escrita por item, tanto por performance quanto para reduzir a janela de exposição a esse tipo
  de falha.

---

## 11. Pendências / ideias futuras

- [ ] **Resetar a senha do Supabase** e atualizar `DATABASE_URL` (segurança) — ainda pendente.
- [x] Rótulo "R$ 13.333" no gráfico de categorias sendo cortado — corrigido (margem do eixo
  aumentada para 90px); validado visualmente pelo usuário.
- [ ] (Opcional) importar as 2 linhas sem valor da planilha p/ o painel bater 100%.
- [ ] (Opcional) gerar Jan–Dez/2027 para previsão (via Configurações → Criar meses futuros).
- [ ] Itens "Amil" (R$ 2.149,69) e "Reserva" (R$ 1.000,00) em Agosto/26 ficaram sem bandeira
  Itaú — o usuário disse que vai revisar manualmente.
- [ ] Há um par de lançamentos "Dux" (R$ 46,34 cada) em Agosto/26 marcados como Visa por decisão
  do usuário (ambíguo entre os dois) — ele vai corrigir manualmente qual é Mastercard.
- [ ] **Considerar upgrade do plano Supabase (Pro) para ter backups automáticos/PITR** — o Free
  não tem nenhum backup nativo (ver incidente na Sprint 11 abaixo). Sem isso, qualquer bug de
  escrita no banco é irrecuperável exceto por backups locais manuais.

---

## 12. Gotchas técnicos (importante para quem continuar)

- **Badges/HTML colorido:** usar `st.html()` com **estilos inline** (st.markdown remove styles).
  Tema centralizado em um único `st.html("<style>...</style>")` logo após `st.set_page_config`
  (classes `fc-box`, `fc-hdr`, `fc-card-*`, `fc-hero`) — preferir reusar essas classes a inventar
  estilo inline novo.
- **st.html por linha** em Lançamentos/Fixos: cada linha é um flex; botões de ação ficam em
  `st.columns` ao lado (Streamlit não coloca botões dentro de `st.html`).
- **Botões "card" coloridos sem CSS visível:** truque do `<span class="anchor-N">` + CSS
  `span.anchor-N + div button {...}` (sibling selector) — é como se estiliza um `st.button`
  individualmente sem afetar os outros (usado nos cards de "Totais por cartão").
- **`st.rerun()` ANTES de outro widget ser instanciado no mesmo script run faz o Streamlit
  descartar o `session_state` desse widget** (mesmo tendo `key=`), porque o script aborta antes
  de chegar até ele — na visão do Streamlit, ele "deixou de existir" naquele ciclo. Foi a causa
  de dois bugs reais: filtros de Lançamentos resetando ao salvar/aplicar fixos. **Regra:**
  qualquer widget cujo estado precise sobreviver a um rerun deve ser instanciado **antes**, no
  código, de qualquer botão que chame `st.rerun()` na mesma página. Se o rerun for só para
  "atualizar a tela" (sem widgets pendentes depois dele), considere remover o `st.rerun()` —
  o restante do script já roda com os dados atualizados na mesma execução.
- **`number_input(..., value=X, key=Y)` quando `st.session_state[Y]` já foi definido no mesmo
  run** dispara o aviso "created with a default value but also had its value set via the
  Session State API" — definir o valor só via `session_state[key]` e omitir `value=` quando a
  key já existe.
- **`min_value` em campos de valor/parcelas que editam dados existentes:** nunca assumir que o
  dado salvo está dentro do range "óbvio". Causou 2 crashes reais: valor negativo (crédito) com
  `min_value=0.01`, e parcela com `total_parcelas=1` (última antes do ÚLTIMA) com `min_value=2`.
- **Markdown interpretando `$...$` como LaTeX:** strings com **dois ou mais `R$`** na mesma
  chamada de `st.markdown`/`st.caption` podem ser lidas como abertura/fechamento de fórmula
  matemática, quebrando a formatação. Escapar como `R\$` nesses casos.
- **Ordenação:** sempre por `id` (Postgres não garante ordem sem ORDER BY; data_lancamento ficou
  vazio após re-sync → ordenar por data reembaralhava ao clicar no checkbox).
- **Escrita no Postgres:** `update_lancamento`/`delete_lancamento` usam UPDATE/DELETE direto
  (rápido); criação de muitos itens usa `add_lancamentos_bulk` (1 escrita) — evita reescrever a
  tabela inteira a cada item (causava lentidão e já gerou duplicidade). Mesmo padrão em
  `propagar_parcela_grupo()` (atualiza várias parcelas + a linha do grupo de uma vez).
  `update_fixo`/`update_lancamento` só atualizam colunas que já existem no DataFrame — uma coluna
  nova (ex.: `subtipo_cartao` em `fixos`) precisa existir na tabela real antes (já existe hoje).
- **Senha do Postgres com `@`:** a URL é normalizada/encodada em `_normalize_pg_url` (db.py) e no
  `seed_supabase.py` — não precisa codificar manualmente.
- **NÃO incluir `pillow-heif`** no requirements: quebra o build no Streamlit Cloud (precisa de
  libheif do sistema) e derruba o ambiente inteiro. Conversão HEIC é opcional/lazy.
- **Auth:** gate por `APP_PASSWORD` no topo do `app.py`; sem a variável, acesso é livre (uso local).
- **Edição/correção em massa direto no Supabase** (ex.: bandeira de cartão em lote): sempre
  conectar via script Python lendo a `DATABASE_URL` de `ACESSOS_PRIVADO.md` (nunca colar a
  credencial em linha de comando — vai para o histórico do shell); fazer backup local (JSON) do
  recorte afetado antes de aplicar; mostrar o mapeamento completo (id → mudança) para o usuário
  confirmar antes de gravar.
- **NUNCA fazer uma escrita por item em loop contra o Postgres** (ex.: `for item in lista:
  add_lancamento(...)`) — cada `save_sheet` faz um `to_sql(..., if_exists="replace")` (DROP +
  CREATE + INSERT da tabela inteira). Centenas de escritas em sequência são lentas E aumentam a
  janela de exposição a erros de conexão (já causou perda de dados real, ver Sprint 11). Sempre
  montar a lista completa de linhas em memória e chamar `save_sheet` **uma única vez** por tabela.
- **`_load_sheet_raw` nunca deve engolir exceções silenciosamente no Postgres** — ela alimenta a
  lógica de `save_sheet` que decide quais linhas de outras contas preservar; tratar "erro de
  leitura" como "tabela vazia" faz a próxima escrita apagar dados de quem não está sendo tocado.
  Só retorna vazio quando a tabela genuinamente não existe (`has_table`); qualquer outro erro
  deve propagar.
</content>
