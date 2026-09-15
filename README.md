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
6. visualizar contagens separadas para `QAs` e `clinical_protocols`;
7. visualizar o relatório de curadoria automática, com registros aceitos, rejeitados e motivos por fonte.

O fluxo principal funciona assim:

- o usuário acessa a interface web no frontend;
- a tela envia uma requisição ao backend para iniciar o processamento;
- o backend cria um registro no MongoDB e inicia a tarefa em background;
- o processamento baixa ou consulta os datasets, extrai texto dos PDFs dos protocolos clínicos (FHEMIG e PCDT) e gera os arquivos de saída;
- a etapa de extração aplica critérios de curadoria versionados e gera `curation_report.json`, associado ao `preprocess_id` no MongoDB;
- o frontend faz polling do estado da execução até a conclusão e permite gerar e consultar a base RAG.

## Como a aplicação funciona

O fluxo completo acontece em etapas encadeadas:

1. O avaliador acessa o frontend em `http://localhost:8080` e inicia o processamento dos datasets.
2. O frontend envia a solicitação ao backend, que registra a execução no MongoDB e processa os dados em background. O status pode ser consultado até a tarefa terminar.
3. O backend organiza QAs, laudos e protocolos clínicos, gera os arquivos estruturados e cria a base RAG para buscas por similaridade.
4. No chat, o agente valida se a pergunta é médica, aplica guardrails de segurança, identifica se há referência a um paciente (Jornada 2 com busca e anonimização de prontuário e laudos), sumariza o contexto caso exceda a janela de 3K tokens do SFT e consulta a base RAG antes de chamar o modelo fine-tunado.
5. O agente devolve a resposta com fontes, disclaimer e indicação de validação humana, enquanto registra a interação para auditoria no MongoDB. Quando a pergunta menciona exames, laudos ou resultados, ele prioriza o contexto clínico estruturado disponível e bloqueia respostas quando o dado não existe em datasets confiáveis.

O modelo fine-tunado utilizado pelo agente está disponível publicamente no [Hugging Face](https://huggingface.co/fiap-hospital-helper/hospital-helper-qwen2.5-1.5b) (tag oficial `v2.0`). O endpoint de inferência pode ser o [Space do projeto](https://huggingface.co/spaces/fiap-hospital-helper/hospital-helper) (com alocação ZeroGPU) ou uma URL FastAPI exposta via ngrok.

## Tela do Assistente Médico

O frontend possui a tela `Assistente Médico`, disponível como último item do menu lateral. Ela suporta duas jornadas clínicas principais:
- **Jornada 1 — Dúvida clínica pontual:** Pergunta clínica geral sem identificação de paciente, respondida com busca RAG sobre protocolos e literatura médica.
- **Jornada 2 — Consulta contextualizada por paciente:** Ao preencher o campo opcional *Nome do paciente*, o assistente consulta o prontuário e os laudos médicos do paciente no backend, extrai dados clínicos anonimizados (diagnósticos, alergias, medicações em uso, sinais vitais e resumo de exames/laudos), cruza esse contexto com a busca RAG e gera uma recomendação contextualizada com badges visuais (`🏥 Prontuário consultado`, `🧾 Laudos consultados` e `⚡ Contexto resumido`).

Para usar a tela:

1. Suba o backend, o agente, o MongoDB e o frontend com o Docker Compose.
2. Garanta que o agente esteja configurado com uma URL de inferência da LLM em `LLM_ENDPOINT_URL` (e opcionalmente `GROQ_API_KEY` para sumarização avançada).
3. Acesse `http://localhost:8080` e selecione `Assistente Médico`.
4. Digite uma pergunta. Para a Jornada 2, preencha o campo *Nome do paciente* (ex.: "João da Silva"). Se necessário, informe um `preprocess_id` para limitar a consulta a uma execução RAG específica.

A tela chama `POST http://localhost:8001/agent/chat`. A resposta apresenta o texto do assistente, badges de status, fontes consultadas e detalhes clínicos utilizados. Solicitações bloqueadas pelos guardrails exibem o motivo de segurança. As respostas do agente incluem disclaimer e indicação de validação humana, conforme descrito em [agent/README.md](agent/README.md).

Em desenvolvimento local, a URL do agente no frontend pode ser ajustada pela variável `VITE_AGENT_URL`, cujo padrão é `http://localhost:8001`.

## Quick Start para Avaliadores

No terminal Bash, a partir da raiz do repositório:

```bash
# 1. Configure o endpoint de inferência do modelo
#export LLM_ENDPOINT_URL=https://huggingface.co/spaces/fiap-hospital-helper/hospital-helper

# 2. Suba frontend, backend, agente e MongoDB
#docker compose -f app-docker-compose.yaml up --build -d

# 3. Confirme que backend e agente estão disponíveis
#curl http://localhost:3000/health && curl http://localhost:8001/health

# 4. Envie uma pergunta médica geral (Jornada 1)
#curl -X POST http://localhost:8001/agent/chat \
#	-H "Content-Type: application/json" \
#	-d '{"query":"Quais são os sintomas da tuberculose?"}'

# 5. Envie uma consulta contextualizada por paciente (Jornada 2)
curl.exe -X POST http://localhost:8001/agent/chat    -H "Content-Type: application/json"   --data-binary @- <<'JSON'
{"patient_name":"Ana Souza Ferreira","query":"Quais cuidados prescrever para o quadro clínico deste paciente?"}
JSON

# 6. Envie uma consulta contextualizada por paciente com laudos (Jornada 2)
curl.exe -X POST http://localhost:8001/agent/chat    -H "Content-Type: application/json"   --data-binary @- <<'JSON'
{"patient_name":"Maria Santos Almeida","query":"Quais foram os últimos exames e resultados realizados pela paciente?"}
JSON


```

Depois, abra http://localhost:8080 para usar a interface web. A documentação interativa da API fica em http://localhost:3000/docs (backend) e http://localhost:8001/docs (agente). O primeiro build e o primeiro processamento dos datasets podem demorar; acompanhe a inicialização com `docker compose -f app-docker-compose.yaml logs -f`.

## Documentação Técnica e Arquitetura

Para detalhes aprofundados sobre a arquitetura e decisões de projeto:

- **Jornadas do Usuário (J1, J2 e J3):** [docs/jornadas_agente_medico.md](docs/jornadas_agente_medico.md)
- **Walkthrough do Agente Médico:** [docs/agent-walkthrough.md](docs/agent-walkthrough.md)
- **Arquitetura Geral & C4 Models:** [docs/architecture/README.md](docs/architecture/README.md)
- **Decisões de Arquitetura (ADRs):** [docs/architecture/adr/README.md](docs/architecture/adr/README.md)
- **Relatório de Avaliação do Modelo (ROUGE/BLEU):** [docs/avaliacao-modelo.md](docs/avaliacao-modelo.md)
- **Notebooks de Treinamento e Avaliação:** [backend/src/notebooks/README.md](backend/src/notebooks/README.md)
- **Agente Médico (LangGraph):** [agent/README.md](agent/README.md)
- **Backend API & RAG:** [backend/README.md](backend/README.md)
- **Datasets:** [backend/datasets/README.md](backend/datasets/README.md)
- **Curadoria e rastreabilidade:** [backend/README.md#estrategias-de-curadoria](backend/README.md#estrategias-de-curadoria)
- **Frontend:** [frontend/README.md](frontend/README.md)

## Subindo tudo com Docker Compose

O arquivo [app-docker-compose.yaml](app-docker-compose.yaml) sobe a aplicação completa.

### Comando

### Comando (Modo GPU - Nvidia CUDA)

```bash
docker compose -f app-docker-compose.yaml up --build -d
```

### Comando (Modo CPU - Sem necessidade de GPU Nvidia)

Para rodar em máquinas sem placa Nvidia ou sem o NVIDIA Container Toolkit configurado:

```bash
./start-app-cpu.sh
```

Ou diretamente via Docker Compose:

```bash
docker compose -f app-docker-compose.cpu.yaml up --build -d
```

Para atualizar somente o backend ou frontend pós correção, use:

```bash
docker compose -f app-docker-compose.yaml up --build -d backend
docker compose -f app-docker-compose.yaml up --build -d frontend
# Ou para o modo CPU:
docker compose -f app-docker-compose.cpu.yaml up --build -d backend
```

Observação: o build com GPU Nvidia baixa dependências CUDA adicionais. Já o build em modo CPU utiliza imagem otimizada `python:3.10-slim` com PyTorch CPU, sendo consideravelmente mais leve e rápido de baixar.

Depois de subir a aplicação, acompanhe os logs em tempo real com `docker compose logs -f` ou, usando o arquivo deste projeto:

```bash
docker compose -f app-docker-compose.yaml logs -f
# Ignorando o mongodb, use:
docker compose -f app-docker-compose.yaml logs -f backend agent frontend
# Ou em modo CPU:
docker compose -f app-docker-compose.cpu.yaml logs -f
```

### Acesso

- Frontend: http://localhost:8080
- Backend/API: http://localhost:3000
- Documentação Swagger: http://localhost:3000/docs
- MongoDB: localhost:27017

### Parar os containers

```bash
# Modo GPU
docker compose -f app-docker-compose.yaml down
# ou ./stop-app.sh

# Modo CPU
./stop-app-cpu.sh
# ou docker compose -f app-docker-compose.cpu.yaml down
```

## Scripts de automação

- **Modo GPU (padrão):**
  - Iniciar: `./start-app.sh`
  - Parar: `./stop-app.sh`
  - Reiniciar: `./restart-app.sh`
- **Modo CPU (sem GPU):**
  - Iniciar: `./start-app-cpu.sh`
  - Parar: `./stop-app-cpu.sh`
  - Reiniciar: `./restart-app-cpu.sh`


## Observações importantes

- O backend depende do MongoDB para subir corretamente.
- O processamento de datasets é feito em background, então a API responde rapidamente e o estado pode ser acompanhado depois.
- A tradução usa `Helsinki-NLP/opus-mt-tc-big-en-pt`, em lotes e com fragmentação de textos longos; quando houver uma GPU Nvidia compatível, o backend usa CUDA, caso contrário faz fallback para CPU.
- Uma execução pode terminar com status `error`; em cenários de falha de fallback interno, também pode aparecer `failed`.
- Os datasets são baixados automaticamente na primeira execução, incluindo FHEMIG e PCDT; também podem ser tratados manualmente conforme descrito em [backend/datasets/README.md](backend/datasets/README.md).
- Devido a restrições de hardware, o fine-tuning e a avaliação formal do modelo escolhido foram realizados através de notebooks no Google Colab. Os arquivos e instruções detalhadas estão na pasta [backend/src/notebooks/](backend/src/notebooks/) (incluindo a linhagem dos modelos v1.0 e v2.0 e os notebooks de avaliação com métricas ROUGE/BLEU). O modelo canônico de produção foi disponibilizado publicamente no [HuggingFace](https://huggingface.co/fiap-hospital-helper/hospital-helper-qwen2.5-1.5b) sob a tag `v2.0`, e a análise empírica com calibração de hiperparâmetros está detalhada em [docs/avaliacao-modelo.md](docs/avaliacao-modelo.md).
- **Aviso sobre a Tradução de QAs**: A tradução dos dados de QAs é extremamente demorada e não roda em todos os hardwares que temos. Por isso, foi implementada a opção de pular essa etapa e utilizar o dataset já traduzido que está fixado na pasta `backend/datasets/preprocessed/fixed/qas`.
