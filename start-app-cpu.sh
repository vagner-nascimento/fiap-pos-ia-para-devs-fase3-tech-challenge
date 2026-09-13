#!/bin/bash

# Script para iniciar os containers em modo 100% CPU (sem necessidade de GPU Nvidia/CUDA)

if docker compose version >/dev/null 2>&1; then
    DOCKER_COMPOSE="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    DOCKER_COMPOSE="docker-compose"
else
    echo "Erro: Nem 'docker compose' nem 'docker-compose' foram encontrados no sistema."
    exit 1
fi

echo "Iniciando containers em modo CPU usando $DOCKER_COMPOSE..."
$DOCKER_COMPOSE -f app-docker-compose.cpu.yaml up --build -d

echo "Containers em modo CPU iniciados com sucesso!"
