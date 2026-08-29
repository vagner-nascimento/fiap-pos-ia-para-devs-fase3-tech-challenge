FROM python:3.11-slim

WORKDIR /app

# Instalar dependências básicas do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalar uv (gerenciador de pacotes rápido)
RUN pip install --no-cache-dir uv

# Copiar arquivos de dependências (pyproject.toml + lock file para build reproduzível)
COPY pyproject.toml uv.lock ./

# Instalar dependências via uv sync (usa o lock file — rápido e determinístico)
RUN uv sync --frozen --no-dev

# Copiar código fonte
COPY src/ ./src/

# Definir PYTHONPATH
ENV PYTHONPATH=src

# Expor porta do agente
EXPOSE 8001

# Executar o serviço
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
