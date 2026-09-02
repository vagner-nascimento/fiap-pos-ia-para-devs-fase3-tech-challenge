# FIAP POS IA - Challenge Fase 3

Este repositório reúne uma aplicação full-stack para pré-processar datasets médicos, servir um agente médico inteligente com RAG e LangGraph, e acompanhar a execução em uma interface web. A solução está organizada em quatro partes:

- **Backend** em FastAPI para pré-processamento de datasets, base RAG e persistência de estado em MongoDB (porta 3000);
- **Agente Médico** em FastAPI + LangGraph para orquestração de assistente clínico com RAG híbrido, guardrails determinísticos e auditoria (porta 8001);
- **Frontend** em React + TypeScript para iniciar e acompanhar o processamento (porta 8080);
- **Stack completa** via Docker Compose para subir tudo com um comando.

## Visão geral

A aplicação permite:

1. iniciar o pré-processamento dos datasets PubMedQA, MedQuAD, protocolos clínicos FHEMIG e protocolos PCDT;
2. gerar e consultar a base RAG vetorial/híbrida sobre os dados médicos;
3. interagir com o agente médico inteligente via chat contextualizado com citações de fontes e avisos legais;
4. acompanhar o progresso das tarefas em tempo real;
5. consultar os arquivos gerados em formato estruturado para fine-tuning, RAG e recuperação;
6. visualizar contagens separadas para `QAs` e `clinical_protocols`.

O fluxo principal funciona assim:

- o usuário acessa a interface web no frontend;
- a tela envia uma requisição ao backend para iniciar o processamento;
- o backend cria um registro no MongoDB e inicia a tarefa em background;
- o processamento baixa ou consulta os datasets, extrai texto dos PDFs dos protocolos clínicos (FHEMIG e PCDT) e gera os arquivos de saída;
- o frontend faz polling do estado da execução até a conclusão e permite gerar e consultar a base RAG.

## Como a aplicação funciona

## Documentação Técnica e Arquitetura

Para detalhes aprofundados sobre a arquitetura e decisões de projeto:

- **Arquitetura Geral & C4 Models:** [docs/architecture/README.md](docs/architecture/README.md)
- **Decisões de Arquitetura (ADRs):** [docs/architecture/adr/README.md](docs/architecture/adr/README.md)
- **Agente Médico (LangGraph):** [agent/README.md](agent/README.md)
- **Backend API & RAG:** [backend/README.md](backend/README.md)
- **Datasets:** [backend/datasets/README.md](backend/datasets/README.md)
- **Frontend:** [frontend/README.md](frontend/README.md)

## Subindo tudo com Docker Compose

O arquivo [app-docker-compose.yaml](app-docker-compose.yaml) sobe a aplicação completa.

### Comando

```bash
docker compose -f app-docker-compose.yaml up --build -d
```

Para atualizar somente o backend ou frontend pós correção, use:

```bash
docker compose -f app-docker-compose.yaml up --build -d backend
docker compose -f app-docker-compose.yaml up --build -d frontend
```

Observação: o primeiro build pode demorar bastante, principalmente por causa do backend, que baixa dependências grandes de IA e pacotes de suporte à execução em GPU Nvidia.

Depois de subir a aplicação, acompanhe os logs em tempo real com `docker compose logs -f` ou, usando o arquivo deste projeto, `docker compose -f app-docker-compose.yaml logs -f`:

```bash
docker compose -f app-docker-compose.yaml logs -f
```

### Acesso

- Frontend: http://localhost:8080
- Backend/API: http://localhost:3000
- Documentação Swagger: http://localhost:3000/docs
- MongoDB: localhost:27017

### Parar os containers

```bash
docker compose -f app-docker-compose.yaml down
```

## Script de reinicialização

O script [restart-app.sh](restart-app.sh) facilita a reinicialização completa da aplicação.

```bash
./restart-app.sh
```

## Observações importantes

- O backend depende do MongoDB para subir corretamente.
- O processamento de datasets é feito em background, então a API responde rapidamente e o estado pode ser acompanhado depois.
- A tradução usa `Helsinki-NLP/opus-mt-tc-big-en-pt`, em lotes e com fragmentação de textos longos; quando houver uma GPU Nvidia compatível, o backend usa CUDA, caso contrário faz fallback para CPU.
- Uma execução pode terminar com status `error`; em cenários de falha de fallback interno, também pode aparecer `failed`.
- Os datasets são baixados automaticamente na primeira execução, incluindo FHEMIG e PCDT; também podem ser tratados manualmente conforme descrito em [backend/datasets/README.md](backend/datasets/README.md).
- Devido a restrições de hardware, o finetunning do modelo escolhido foi feito através de notebook no Google Colab. Os arquivos relacionados ao processo estão na pasta [backend/notebooks/](backend/notebooks/) e o modelo treinado foi disponibilizado como private no [HuggingFace](fiap-hospital-helper/hospital-helper-qwen2.5-1.5b).
- **Aviso sobre a Tradução de QAs**: A tradução dos dados de QAs é extremamente demorada e não roda em todos os hardwares que temos. Por isso, foi implementada a opção de pular essa etapa e utilizar o dataset já traduzido que está fixado na pasta `backend/datasets/preprocessed/fixed/qas`.
