FROM nvidia/cuda:12.1.1-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Instalar dependências básicas do sistema e Python
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    ca-certificates \
    curl \
    python3.10 \
    python3.10-venv \
    python3-pip \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/bin/python3.10 /usr/local/bin/python && \
    ln -sf /usr/bin/python3.10 /usr/local/bin/python3 && \
    python -m pip install --upgrade pip && \
    pip install uv

# Copiar arquivos de dependências
COPY pyproject.toml uv.lock ./

# Criar ambiente virtual e instalar dependências
RUN --mount=type=cache,target=/root/.cache/uv \
    uv venv /app/.venv --python /usr/bin/python3.10 && \
    uv sync --frozen --no-dev

# Copiar código fonte
COPY src/ ./src/
COPY datasets/ ./datasets/

# Expor porta
EXPOSE 3000

# Comando para executar a aplicação usando o venv do uv
CMD ["/app/.venv/bin/python", "src/main.py"]
