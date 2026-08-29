# FIAP POS IA - Agente Médico

Serviço de assistente médico inteligente construído com **LangChain** e **LangGraph**. Integra a LLM customizada (Qwen2.5 fine-tunado) com busca contextual via RAG sobre datasets médicos (PubMedQA, MedQuAD, FHEMIG), aplicando múltiplas camadas de segurança antes de gerar cada resposta.

O serviço é isolado do backend principal e roda em container próprio na porta **8001**.

## Sumario

- [Visao geral](#visao-geral)
- [Arquitetura](#arquitetura)
- [Pipeline LangGraph](#pipeline-langgraph)
- [Pre-requisitos](#pre-requisitos)
- [Dependencias Python](#dependencias-python)
- [Configuracao](#configuracao)
- [Como subir o servico](#como-subir-o-servico)
- [Endpoints da API](#endpoints-da-api)
- [Seguranca e guardrails](#seguranca-e-guardrails)
- [Auditoria e explainability](#auditoria-e-explainability)
- [Testes](#testes)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Documentacao interativa](#documentacao-interativa)

---

## Visao geral

O agente expoe endpoints para:

1. enviar perguntas ao assistente médico e receber respostas contextualizadas com fontes;
2. consultar o histórico de auditoria de uma sessão de usuário;
3. acessar o detalhe de um log de auditoria específico;
4. verificar a saúde do serviço.

Na inicializacao, o serviço testa a conexão com o MongoDB. Se a conexão falhar, a aplicação não sobe.

O agente nunca prescreve medicamentos com doses nem fornece diagnósticos definitivos. Toda resposta inclui um disclaimer obrigatório e o campo `requires_human_validation: true`.

---

## Arquitetura

```text
agent/
|-- Dockerfile
|-- pyproject.toml
|-- .env.example
`-- src/
    |-- main.py              # Ponto de entrada (uvicorn na porta 8001)
    |-- server.py            # Factory da aplicacao FastAPI, CORS e lifespan
    |-- routers/
    |   `-- agent.py         # POST /agent/chat, GET /agent/audit/{session_id}
    |-- services/
    |   |-- llm_client.py    # Wrapper HuggingFaceEndpoint + fallback HTTP
    |   |-- medical_agent.py # StateGraph LangGraph — orquestrador principal
    |   `-- nodes/
    |       |-- topic_validator.py    # No 1: valida dominio medico
    |       |-- safety_guard.py       # No 2: guardrails de seguranca
    |       |-- rag_retriever.py      # No 3: busca RAG via backend
    |       |-- llm_generator.py      # No 4: chamada ao modelo fine-tunado
    |       |-- response_formatter.py # No 5: formata fontes e disclaimer
    |       `-- audit_logger.py       # No 6: persiste log no MongoDB
    `-- infra/
        `-- database/
            |-- mongodb.py   # Conexao singleton com MongoDB
            `-- collections/
                `-- agent_audit_logs.py  # CRUD da collection de auditoria
```

---

## Pipeline LangGraph

O agente executa um grafo dirigido com **early-exit** nos nós de guardrail:
quando uma violação é detectada, o grafo pula direto para o `audit_logger`
sem chamar RAG nem LLM, economizando latência e custo de inferência.

```
[START] → init → topic_validator
                      |
             (invalido)         (valido)
                 |                  |
                 v                  v
           audit_logger       safety_guard
                              |            |
                        (bloqueado)     (seguro)
                              |            |
                              v            v
                        audit_logger  rag_retriever
                                           |
                                           v
                                     llm_generator
                                           |
                                           v
                                   response_formatter
                                           |
                                           v
                                     audit_logger --> [END]
```

| No                   | Responsabilidade                                                                          |
| -------------------- | ----------------------------------------------------------------------------------------- |
| `topic_validator`    | Rejeita perguntas fora do domínio médico/saúde (keywords PT/EN + regex contextual)        |
| `safety_guard`       | Bloqueia pedidos de prescrição com dose, diagnóstico definitivo ou substituição de médico |
| `rag_retriever`      | Consulta a API `/rag-database/query` do backend e monta o contexto com fontes             |
| `llm_generator`      | Constrói o prompt no formato ChatML e invoca o modelo Qwen2.5 fine-tunado                 |
| `response_formatter` | Adiciona citações de fontes inline e o disclaimer obrigatório                             |
| `audit_logger`       | Persiste o log completo da interação na collection `agent_audit_logs`                     |

---

## Pre-requisitos

| Requisito    | Versao minima | Observacao                                               |
| ------------ | ------------- | -------------------------------------------------------- |
| Python       | 3.10+         | 3.11 recomendado                                         |
| MongoDB      | 4.x+          | Obrigatorio para o servico subir                         |
| Backend API  | —             | Necessario para as consultas RAG (`/rag-database/query`) |
| LLM Endpoint | —             | URL do ngrok (Colab) ou HuggingFace ZeroGPU              |

Para execução completa via Docker, o backend e o MongoDB precisam estar rodando na mesma rede `fiap-network`.

---

## Dependencias Python

Definidas em `pyproject.toml`:

| Pacote                     | Uso                                            |
| -------------------------- | ---------------------------------------------- |
| `fastapi`                  | Framework web                                  |
| `uvicorn[standard]`        | Servidor ASGI                                  |
| `pydantic`                 | Validacao de request/response                  |
| `python-dotenv`            | Carregamento de variaveis de ambiente          |
| `pymongo`                  | Cliente MongoDB                                |
| `langchain`                | Abstrações de cadeia e prompt                  |
| `langchain-community`      | HuggingFaceEndpoint e outros integradores      |
| `langchain-mongodb`        | Integracao LangChain com MongoDB               |
| `langchain-text-splitters` | Chunking de documentos                         |
| `langgraph`                | Orquestracao do pipeline como grafo dirigido   |
| `sentence-transformers`    | Embeddings locais (fallback)                   |
| `InstructorEmbedding`      | Modelo de embeddings hkunlp/instructor-base    |
| `requests`                 | Chamadas HTTP ao backend e ao endpoint LLM     |
| `huggingface-hub`          | Autenticacao e download de modelos HuggingFace |

Dependencias de desenvolvimento: `pytest`, `pytest-asyncio`, `black`, `mypy`.

---

## Configuracao

Copie o arquivo de exemplo e ajuste conforme seu ambiente:

```bash
cp agent/.env.example agent/.env
```

| Variavel                   | Descricao                                           | Padrao                  |
| -------------------------- | --------------------------------------------------- | ----------------------- |
| `PYTHONPATH`               | Diretorio raiz dos modulos Python                   | `src`                   |
| `MONGODB_USER`             | Usuario do MongoDB                                  | `db_user`               |
| `MONGODB_PASSWORD`         | Senha do MongoDB                                    | `db_pass`               |
| `MONGODB_HOST`             | Host do MongoDB                                     | `localhost`             |
| `MONGODB_PORT`             | Porta do MongoDB                                    | `27017`                 |
| `DB_NAME`                  | Nome do banco de dados                              | `fiap_pos_ia_fase3`     |
| `LLM_ENDPOINT_URL`         | URL do endpoint de inferencia do modelo             | —                       |
| `LLM_API_TOKEN`            | Token de autenticacao HuggingFace                   | —                       |
| `BACKEND_API_URL`          | URL interna do backend para consultas RAG           | `http://localhost:3000` |
| `AGENT_MAX_TOKENS`         | Numero maximo de tokens na resposta da LLM          | `512`                   |
| `AGENT_TEMPERATURE`        | Temperatura de amostragem (0 = deterministico)      | `0.1`                   |
| `RAG_TOP_K`                | Quantidade maxima de documentos RAG retornados      | `5`                     |
| `RAG_SIMILARITY_THRESHOLD` | Score minimo de similaridade para incluir documento | `0.25`                  |

> Com Docker Compose, `MONGODB_HOST` deve ser `mongodb` e `BACKEND_API_URL` deve ser `http://fiap-pos-ia-backend:3000`.

### Configurando o endpoint da LLM

O agente suporta dois modos de endpoint:

**Modo desenvolvimento (ngrok + Google Colab):**
Execute o notebook de fine-tuning no Colab com o túnel ngrok ativo e copie a URL gerada:

```env
LLM_ENDPOINT_URL=https://abcd1234.ngrok-free.app
LLM_API_TOKEN=hf_seu_token_aqui
```

**Modo producao (HuggingFace ZeroGPU / Inference Endpoints):**

```env
LLM_ENDPOINT_URL=https://seu-usuario-seu-espaco.hf.space
LLM_API_TOKEN=hf_seu_token_aqui
```

---

## Como subir o servico

### Opcao 1 — Docker Compose (recomendado)

Sobe o agente junto com o backend, MongoDB e frontend:

```bash
# Configure as variaveis do endpoint LLM
export LLM_ENDPOINT_URL=https://sua-url-aqui
export LLM_API_TOKEN=hf_seu_token

docker-compose -f app-docker-compose.yaml up agent --build
```

Para subir toda a stack completa:

```bash
docker-compose -f app-docker-compose.yaml up --build -d
```

### Opcao 2 — Apenas infraestrutura via Docker

Sobe apenas o MongoDB, inicia o backend e o agente localmente:

```bash
# Sobe o MongoDB
docker-compose -f infra-docker-compose.yaml up -d

# Ajuste o .env para apontar para localhost
# MONGODB_HOST=localhost
# BACKEND_API_URL=http://localhost:3000
```

### Opcao 3 — Desenvolvimento local

1. Certifique-se que o MongoDB e o backend estao rodando.

2. Configure o `.env`:

   ```bash
   cp agent/.env.example agent/.env
   # Edite LLM_ENDPOINT_URL, MONGODB_HOST=localhost, BACKEND_API_URL=http://localhost:3000
   ```

3. Crie e ative um ambiente virtual e instale as dependencias:

   ```bash
   cd agent
   python -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev]"
   ```

4. Execute o servico:

   ```bash
   PYTHONPATH=src uvicorn main:app --host 0.0.0.0 --port 8001 --reload
   ```

5. Verifique o health check:

   ```bash
   curl http://localhost:8001/health
   ```

---

## Endpoints da API

### `GET /health`

Health check do servico.

**Resposta:**

```json
{
  "service": "fiap-pos-ia-agent",
  "timestamp": "2026-08-19T12:00:00.000000",
  "status": "UP"
}
```

---

### `POST /agent/chat`

Envia uma pergunta ao assistente medico e recebe a resposta contextualizada. O agente executa o pipeline LangGraph completo: valida o topico, aplica guardrails, busca contexto via RAG, gera a resposta com a LLM e persiste o log de auditoria.

**Body:**

| Campo           | Tipo  | Obrigatorio | Descricao                                                  |
| --------------- | ----- | ----------- | ---------------------------------------------------------- |
| `query`         | `str` | Sim         | Pergunta em linguagem natural (3 a 2000 caracteres)        |
| `session_id`    | `str` | Nao         | Identificador da sessao. Gerado automaticamente se omitido |
| `preprocess_id` | `str` | Nao         | ID do pre-processamento para filtrar a base RAG            |

**Exemplo:**

```bash
curl -X POST http://localhost:8001/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "sess-001", "query": "Quais sao os sintomas da tuberculose?"}'
```

**Resposta:**

```json
{
  "session_id": "sess-001",
  "response": "A tuberculose é uma doença infecciosa causada pelo Mycobacterium tuberculosis. [Fonte: PubMedQA/MedQuAD, score: 0.87]\nOs principais sintomas incluem tosse persistente por mais de 3 semanas, febre, sudorese noturna e perda de peso involuntária.\n\n---\n⚠️ AVISO IMPORTANTE: Este assistente médico fornece informações gerais baseadas em literatura médica e protocolos clínicos. Não substitui a avaliação, diagnóstico ou prescrição de um profissional de saúde habilitado.",
  "sources": [
    {
      "dataset": "qas",
      "source_type": "qas",
      "similarity_score": 0.87,
      "content_preview": "Pergunta: Quais são os sintomas da tuberculose?..."
    }
  ],
  "sources_cited": ["PubMedQA/MedQuAD"],
  "topic_valid": true,
  "safety_triggered": false,
  "safety_reason": null,
  "requires_human_validation": true,
  "audit_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "duration_ms": 1842
}
```

**Resposta quando o topico e invalido (query fora do dominio medico):**

```json
{
  "session_id": "sess-002",
  "response": "❌ Desculpe, sou um assistente especializado exclusivamente no domínio médico e de saúde...",
  "sources": [],
  "sources_cited": [],
  "topic_valid": false,
  "safety_triggered": false,
  "safety_reason": null,
  "requires_human_validation": true,
  "audit_id": "b2c3d4e5-...",
  "duration_ms": 12
}
```

**Resposta quando um guardrail e ativado (ex: pedido de prescricao):**

```json
{
  "session_id": "sess-003",
  "response": "⚠️ Solicitação não permitida. Por razões de segurança, este assistente não pode prescrever medicamentos com doses específicas...",
  "sources": [],
  "sources_cited": [],
  "topic_valid": true,
  "safety_triggered": true,
  "safety_reason": "Instrução de administração com dose ou unidade específica",
  "requires_human_validation": true,
  "audit_id": "c3d4e5f6-...",
  "duration_ms": 8
}
```

---

### `GET /agent/audit/{session_id}`

Retorna o historico de auditoria de uma sessao de usuario, ordenado cronologicamente.

**Exemplo:**

```bash
curl http://localhost:8001/agent/audit/sess-001
```

**Resposta:**

```json
[
  {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "session_id": "sess-001",
    "query": "Quais sao os sintomas da tuberculose?",
    "topic_valid": true,
    "safety_triggered": false,
    "safety_reason": null,
    "rag_documents_count": 5,
    "sources_cited": ["PubMedQA/MedQuAD"],
    "has_disclaimer": true,
    "preprocess_id": null,
    "duration_ms": 1842,
    "created_date": "2026-08-19T12:00:00.000000+00:00",
    "final_response": "A tuberculose é..."
  }
]
```

---

### `GET /agent/audit/log/{audit_id}`

Retorna o detalhe de um log de auditoria especifico pelo ID.

**Exemplo:**

```bash
curl http://localhost:8001/agent/audit/log/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

---

## Seguranca e guardrails

O agente aplica quatro camadas de protecao em sequencia:

### Camada 1 — Validacao de topico

Verifica se a pergunta pertence ao dominio medico/saude antes de qualquer chamada externa. Usa uma lista curada de keywords medicas em portugues e ingles, complementada por padroes de regex contextual.

Queries rejeitadas nao chegam ao RAG nem a LLM.

### Camada 2 — Guardrails de seguranca (lista negra)

Detecta via regex padroes proibidos na pergunta do usuario:

| Padrao proibido                     | Exemplo                            |
| ----------------------------------- | ---------------------------------- |
| Prescricao com dose especifica      | `"me prescreve amoxicilina 500mg"` |
| Instrucao de administracao com dose | `"devo tomar 2 comprimidos de..."` |
| Pedido direto de prescricao         | `"me receita um antibiotico"`      |
| Diagnostico definitivo              | `"confirme que tenho diabetes"`    |

Queries bloqueadas tambem nao chegam ao RAG nem a LLM.

### Camada 3 — System prompt

O prompt de sistema enviado a LLM contem instrucoes explicitas:

- **NUNCA** prescrever medicamentos com doses;
- **NUNCA** fornecer diagnosticos definitivos;
- **NUNCA** substituir orientacao medica profissional;
- citar as fontes RAG inline no formato `[Fonte: <dataset>, score: <X.XX>]`.

### Camada 4 — Response formatter

Pos-processamento da resposta bruta da LLM:

- adiciona o disclaimer obrigatorio caso esteja ausente;
- adiciona rodape de fontes caso a LLM nao tenha citado nenhuma inline;
- remove artefatos residuais do formato ChatML;
- garante `requires_human_validation: true` invariante na resposta.

---

## Auditoria e explainability

Toda interacao — incluindo as bloqueadas pelos guardrails — e persistida na collection MongoDB `agent_audit_logs` com os seguintes campos:

| Campo                 | Descricao                                             |
| --------------------- | ----------------------------------------------------- |
| `session_id`          | Identificador da sessao do usuario                    |
| `query`               | Pergunta original                                     |
| `topic_valid`         | Se passou na validacao de dominio                     |
| `safety_triggered`    | Se um guardrail foi ativado                           |
| `safety_reason`       | Descricao do guardrail violado                        |
| `rag_documents_used`  | Preview dos documentos RAG utilizados (max 200 chars) |
| `rag_documents_count` | Quantidade de documentos RAG consultados              |
| `llm_response_raw`    | Resposta bruta da LLM antes da formatacao             |
| `final_response`      | Resposta final enviada ao usuario                     |
| `sources_cited`       | Lista de datasets citados na resposta                 |
| `has_disclaimer`      | Confirmacao de que o disclaimer esta presente         |
| `preprocess_id`       | ID do pre-processamento usado no RAG                  |
| `duration_ms`         | Tempo total de execucao do pipeline                   |
| `created_date`        | Timestamp da interacao (UTC)                          |

A explainability das fontes e garantida por dois mecanismos:

1. **Citacao inline** no corpo da resposta: `[Fonte: PubMedQA/MedQuAD, score: 0.87]`
2. **Campo estruturado** `sources` na resposta da API com dataset, source_type e score de similaridade.

---

## Testes

Os testes unitarios cobrem os nos criticos do pipeline sem dependencia de banco de dados real ou LLM.

```bash
cd agent

# Com ambiente virtual ativo
PYTHONPATH=src python -m pytest tests/ -v

# Resultado esperado
# tests/test_topic_validator.py  15 passed
# tests/test_safety_guard.py     12 passed
# tests/test_audit_logger.py      3 passed
# ================================ 30 passed ================================
```

Cada suite de testes:

| Suite                     | O que cobre                                                                          |
| ------------------------- | ------------------------------------------------------------------------------------ |
| `test_topic_validator.py` | Queries medicas aceitas, queries off-topic rejeitadas, comportamento do no LangGraph |
| `test_safety_guard.py`    | Padroes de prescricao bloqueados, padroes informativos permitidos, no LangGraph      |
| `test_medical_agent.py`   | Pipeline completo com mocks de LLM, RAG e MongoDB; early-exit nos guardrails         |
| `test_audit_logger.py`    | Criacao de documentos, truncamento de preview, persistencia de safety fields         |

---

## Estrutura do projeto

```text
agent/
|-- .env.example          # Template de variaveis de ambiente
|-- .gitignore
|-- Dockerfile
|-- pyproject.toml
`-- src/
    |-- main.py
    |-- server.py
    |-- routers/
    |   |-- __init__.py   # Carregamento dinamico de routers
    |   `-- agent.py
    |-- services/
    |   |-- __init__.py
    |   |-- llm_client.py
    |   |-- medical_agent.py
    |   `-- nodes/
    |       |-- __init__.py
    |       |-- topic_validator.py
    |       |-- safety_guard.py
    |       |-- rag_retriever.py
    |       |-- llm_generator.py
    |       |-- response_formatter.py
    |       `-- audit_logger.py
    `-- infra/
        |-- __init__.py
        `-- database/
            |-- __init__.py
            |-- mongodb.py
            `-- collections/
                |-- __init__.py
                `-- agent_audit_logs.py

tests/
|-- __init__.py
|-- test_topic_validator.py
|-- test_safety_guard.py
|-- test_medical_agent.py
`-- test_audit_logger.py
```

---

## Documentacao interativa

Com o servico rodando, acesse a documentacao Swagger em:

```
http://localhost:8001/docs
```

Ou o schema OpenAPI em formato JSON:

```
http://localhost:8001/openapi.json
```
