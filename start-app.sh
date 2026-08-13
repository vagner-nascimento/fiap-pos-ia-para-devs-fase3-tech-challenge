#!/bin/bash

# Script para reiniciar os containers do app-docker-compose.yaml

echo "Iniciando containers..."
docker compose -f app-docker-compose.yaml up --build -d

echo "Containers iniciados com sucesso!"
