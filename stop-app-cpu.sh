#!/bin/bash

# Script para parar os containers do app-docker-compose.cpu.yaml

if docker compose version >/dev/null 2>&1; then
    DOCKER_COMPOSE="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    DOCKER_COMPOSE="docker-compose"
else
    echo "Erro: Nem 'docker compose' nem 'docker-compose' foram encontrados no sistema."
    exit 1
fi

echo "Parando containers em modo CPU usando $DOCKER_COMPOSE..."
$DOCKER_COMPOSE -f app-docker-compose.cpu.yaml down

echo "Containers parados com sucesso!"
