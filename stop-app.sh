#!/bin/bash

# Script para reiniciar os containers do app-docker-compose.yaml

echo "Parando containers..."
docker compose -f app-docker-compose.yaml down

echo "Containers parados com sucesso!"
