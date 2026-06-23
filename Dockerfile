FROM python:3.12-slim

WORKDIR /app

# Dependências do sistema (mínimas)
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Instala dependências Python primeiro (cache de camada)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante do código
COPY . .

# Volume persistente para o banco de dados Excel
ENV DATA_DIR=/data
VOLUME ["/data"]

# Streamlit usa a porta fornecida pela plataforma (Railway/Render injetam $PORT)
ENV PORT=8501
EXPOSE 8501

# Configurações do Streamlit para rodar em container
ENV STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ENABLE_CORS=false \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

CMD streamlit run app.py \
    --server.port=${PORT} \
    --server.address=0.0.0.0
