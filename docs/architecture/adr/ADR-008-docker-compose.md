# ADR-008 — Orquestração local via Docker Compose

**Status:** Aceito  
**Data:** 2026-08-18  
**Contexto:** Projeto FIAP POS IA Fase 3 — Empacotamento e execução do ambiente completo  
**Decisores:** Equipe do projeto  

---

## Contexto

O projeto é composto por três serviços interdependentes: Frontend (React/Nginx), Backend (FastAPI/Uvicorn) e MongoDB. Para facilitar o setup local, a entrega do trabalho e a execução em diferentes máquinas, é necessário uma estratégia de empacotamento e orquestração.

Requisitos:
- Subir todos os serviços com **um único comando**;
- Garantir dependências entre serviços (backend só sobe após MongoDB estar pronto);
- Suporte a GPU Nvidia para o backend (quando disponível);
- Persistência de dados do MongoDB entre reinicializações;
- Isolamento de rede entre os serviços (frontend não acessa MongoDB diretamente).

## Decisão

Utilizamos **Docker Compose** para orquestrar os três serviços do projeto, com dois arquivos de composição:

| Arquivo | Propósito |
|---|---|
| `infra-docker-compose.yaml` | Sobe apenas a infra (MongoDB) para desenvolvimento local |
| `app-docker-compose.yaml` | Sobe a stack completa (Frontend + Backend + MongoDB) |

### Topologia de rede

```
fiap-network (bridge)
├── frontend  :8080 (host) → :80 (container)
├── backend   :3000 (host) → :3000 (container)
└── mongodb   :27017 (host) → :27017 (container)
```

### Suporte a GPU

```yaml
backend:
  runtime: nvidia
  environment:
    NVIDIA_VISIBLE_DEVICES: all
    NVIDIA_DRIVER_CAPABILITIES: compute,utility
  deploy:
    resources:
      reservations:
        devices:
          - capabilities: ["gpu"]
```

### Persistência

```yaml
mongodb:
  volumes:
    - mongodb_data:/data/db

volumes:
  mongodb_data:
```

## Justificativa

| Critério | Docker Compose | Kubernetes | Scripts shell | Processos manuais |
|---|---|---|---|---|
| Complexidade | Baixa | Alta | Média | Baixa |
| Reprodutibilidade | Alta | Alta | Média | Baixa |
| Suporte a GPU | ✅ (nvidia runtime) | ✅ (device plugin) | Depende | Depende |
| Curva de aprendizado | Baixa | Alta | Baixa | N/A |
| Adequado para projeto acadêmico | ✅ | ❌ | ✅ | ❌ |

Kubernetes seria uma escolha excessiva para um projeto local de escopo acadêmico, adicionando complexidade sem benefícios práticos neste contexto.

## Alternativas consideradas

| Alternativa | Razão para não escolher |
|---|---|
| Kubernetes (k8s / k3s) | Overengineering; complexidade de configuração não justificada |
| Scripts shell | Menos portável; sem garantia de isolamento de rede |
| Apenas processos locais (sem Docker) | Dificulta reprodutibilidade em diferentes sistemas operacionais |
| Podman Compose | Menor adoção na comunidade; compatibilidade com nvidia runtime menor |

## Consequências

**Positivas:**
- Setup completo em um único comando: `docker compose -f app-docker-compose.yaml up --build`;
- Separação de arquivo para infra permite desenvolvimento local sem subir frontend/backend;
- Rede bridge isola os serviços sem expor MongoDB diretamente à internet;
- Volume nomeado garante persistência dos dados entre reinicializações.

**Negativas:**
- O `runtime: nvidia` no docker-compose exige que o `nvidia-container-toolkit` esteja instalado no host;
- Sem orchestrador avançado, não há auto-healing ou rolling updates automáticos;
- Em máquinas sem GPU, a configuração `runtime: nvidia` pode causar erro (requer `docker-compose.override.yaml` para contornar).

**Neutras:**
- O script `restart-app.sh` na raiz do projeto automatiza o fluxo de rebuild + restart para facilitar o desenvolvimento.
