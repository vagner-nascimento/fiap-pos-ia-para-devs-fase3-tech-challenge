FROM python:3.9-slim

WORKDIR /app

# Instalar git (necessário para clonar datasets)
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# Instalar uv
RUN pip install uv

# Copiar arquivos de dependências
COPY pyproject.toml uv.lock ./

# Instalar dependências usando uv
RUN uv sync --frozen

# Copiar código fonte
COPY src/ ./src/
COPY datasets/ ./datasets/

# Configurar variáveis de ambiente
ENV PYTHONPATH=src
ENV PATH="/app/.venv/bin:$PATH"

# Expor porta
EXPOSE 3000

# Comando para executar a aplicação usando o venv do uv
CMD ["/app/.venv/bin/python", "src/main.py"]