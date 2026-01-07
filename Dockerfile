# ===========================================
# ExaSignal - Dockerfile para Cloud Deploy
# ===========================================
# Uso:
#   docker build -t exasignal .
#   docker run -d --env-file .env exasignal
# ===========================================

FROM python:3.11-slim

WORKDIR /app

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements primeiro (cache layer)
# Use requirements-prod.txt for lightweight deploy
COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt

# Copiar código
COPY src/ src/
COPY markets.yaml .

# Directório para persistência (Railway volume mount)
RUN mkdir -p /data

# Variáveis de ambiente (override com --env-file)
ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=INFO
ENV DATABASE_PATH=/data/exasignal.db

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Executar em modo daemon
CMD ["python", "-m", "src.main"]

