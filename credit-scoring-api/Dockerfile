# Credit Scoring API - Dockerfile
#
# Build:
#   docker build -t credit-scoring-api .
#
# Run (pasando OPENAI_API_KEY desde un .env local):
#   docker run -p 8000:8000 --env-file .env credit-scoring-api
#
# Run (pasando la key explicita):
#   docker run -p 8000:8000 -e OPENAI_API_KEY=sk-... credit-scoring-api
#
# El .env NO se incluye en la imagen (esta en .dockerignore por razones de
# seguridad). Las variables de entorno se pasan en tiempo de ejecucion.

FROM python:3.13-slim

LABEL description="Credit Scoring API - Random Forest (IQR + Yeo-Johnson + RFECV, 107 variables)"

# Working directory
WORKDIR /app

# System dependencies para compilar wheels nativas si las hubiera (lime, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        g++ \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements primero para aprovechar el cache de capas de Docker
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Codigo de la aplicacion y artefactos del modelo
COPY app/ ./app/
COPY artifacts/ ./artifacts/

# Usuario no-root para seguridad
RUN useradd -m -u 1000 apiuser && \
    chown -R apiuser:apiuser /app
USER apiuser

EXPOSE 8000

# Healthcheck usando stdlib (urllib) para evitar agregar la dep `requests`.
# Sale con codigo distinto de 0 si /health no responde 200 OK.
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request, sys; \
sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health', timeout=5).status == 200 else 1)" \
    || exit 1

# Arranque
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
