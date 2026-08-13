# FIAP POS IA - Backend

API REST em FastAPI responsavel pelo pre-processamento de datasets medicos e fine tuning de modelos de linguagem. Hoje o fluxo trata duas familias de dados e uma etapa adicional de traducao local:

- QAs, a partir de PubMedQA e MedQuAD;
- protocolos clinicos FHEMIG, com extracao de texto dos PDFs;
- traducao dos QAs para pt-BR com um modelo local de machine translation;
- fine tuning do modelo hospital helper com os dados processados.

O progresso de cada execucao e persistido no MongoDB.

## Sumario

- Visao geral
- Arquitetura
- Pre-requisitos
- Configuracao
- Como subir a aplicacao
- Endpoints da API
- Fluxo de fine tuning
- Fluxo de preprocessamento
- Estrutura do projeto
- Documentacao interativa

## Visao geral

O backend expoe endpoints para:

1. iniciar o pre-processamento dos datasets;
2. consultar o status de uma execucao em andamento ou concluida;
3. iniciar o fine tuning do modelo hospital helper;
4. consultar o status do fine tuning em andamento ou concluido;
5. gerar a base RAG para uso futuro por um agente de IA;
6. consultar o status da geracao da base RAG;
7. verificar a saude da aplicacao.

Na inicializacao, a API testa a conexao com o MongoDB. Se a conexao falhar, a aplicacao nao sobe.

## Arquitetura

```text
src/
|-- main.py              # Ponto de entrada (uvicorn na porta 3000)
|-- server.py            # Factory da aplicacao FastAPI, CORS e lifespan
|-- routers/
|   |-- preprocess.py    # POST /preprocess, GET /preprocess/{id}
|   `-- fine_tunning.py  # POST /fine-tunning, GET /fine-tunning/{id}
|   `-- rag_database.py  # POST /rag-database, GET /rag-database/{id}
|-- services/
|   |-- preprocess_data.py   # Logica de processamento em background
|   |-- fine_tunning.py      # Logica de fine tuning em background
|   `-- rag_database.py      # Logica de geracao da base RAG em background
|   `-- preprocess/
|       `-- step_three_translation.py   # Traducao local dos QAs
`-- infra/
    `-- database/
        |-- mongodb.py           # Conexao singleton com MongoDB
        `-- collections/
            |-- preprocess.py    # CRUD da collection preprocess
            |-- fine_tunning.py  # CRUD da collection fine_tunning
            `-- rag_database.py  # CRUD das collections da base RAG

datasets/
|-- get_datasets.py      # Clone do PubMedQA/MedQuAD e download dos protocolos clinicos
|-- files/               # Datasets baixados em runtime
`-- preprocessed/        # Arquivos JSON gerados em runtime

models/
|-- hospital_helper/     # Modelo fine-tuned gerado
`-- hospital_helper_tokenizer/  # Tokenizer do modelo fine-tuned
```

O processamento pesado roda em background task do FastAPI. O endpoint POST /preprocess retorna imediatamente com o ID da execucao, e o cliente consulta o progresso via GET /preprocess/{id}.

Quando ha uma GPU Nvidia disponivel com driver/runtime configurados, o backend usa CUDA automaticamente para a etapa de traducao. Se nao houver GPU, ele faz fallback para CPU, o que deixa a traducao bem mais lenta.

## Pre-requisitos

| Requisito | Versao minima | Observacao |
|-----------|---------------|------------|
| Python | 3.8+ | 3.9 recomendado |
| uv | - | Gerenciador de dependencias do projeto |
| MongoDB | 4.x+ | Obrigatorio para a API subir |
| Git | - | Necessario para clonar os datasets em runtime |

Para desenvolvimento local, tambem e util ter Docker e Docker Compose.

### Dependencias Python

Definidas em `pyproject.toml`:

| Pacote | Uso |
|--------|-----|
| `fastapi` | Framework web |
| `uvicorn[standard]` | Servidor ASGI |
| `pydantic` | Validacao de request/response |
| `python-dotenv` | Carregamento de variaveis de ambiente |
| `pymongo` | Cliente MongoDB |
| `requests` | Download dos protocolos clinicos |
| `beautifulsoup4` | Parse do HTML com links dos PDFs |
| `pdfplumber` | Extracao de texto dos PDFs |
| `transformers` | Carregamento do modelo local de traducao e fine tuning |
| `torch` | Inferencia e treinamento do modelo com suporte a CPU/GPU |
| `sentencepiece` | Tokenizacao usada pelo modelo de traducao |
| `sacremoses` | Pre e pos-processamento de texto para traducao |
| `peft` | LoRA para fine tuning eficiente |
| `trl` | SFTTrainer para fine tuning |
| `datasets` | Manipulacao de datasets para treinamento |
| `bitsandbytes` | Quantizacao 4-bit (quando disponivel) |

Dependencias de desenvolvimento: `pytest`, `black`, `mypy`.

## Configuracao

Copie o arquivo de exemplo e ajuste conforme seu ambiente:

```bash
cp .env.example .env
```

| Variavel | Descricao | Padrao |
|----------|-----------|--------|
| `PYTHONPATH` | Diretorio raiz dos modulos Python | `src` |
| `MONGODB_USER` | Usuario do MongoDB | `db_user` |
| `MONGODB_PASSWORD` | Senha do MongoDB | `db_pass` |
| `MONGODB_HOST` | Host do MongoDB | `localhost` |
| `MONGODB_PORT` | Porta do MongoDB | `27017` |
| `DB_NAME` | Nome do banco de dados | `fiap_pos_ia_fase3` |
| `FINE_TUNING_BASE_MODEL` | Modelo base para fine tuning | `Qwen/Qwen2.5-1.5B-Instruct` |
| `RAG_EMBEDDING_MODEL` | Modelo de embeddings para a base RAG | `hkunlp/instructor-base` |

> Com Docker Compose, o host do MongoDB deve ser `mongodb`, nao `localhost`.

## Como subir a aplicacao

### Opcao 1 - Docker Compose

```bash
docker compose -f app-docker-compose.yaml up --build -d
```

O primeiro build pode demorar bastante porque a imagem do backend instala dependencias grandes de IA e, em ambientes Linux com GPU Nvidia, baixa tambem bibliotecas CUDA.

Para reiniciar os containers:

```bash
./restart-app.sh
```

### Opcao 2 - Apenas infraestrutura via Docker

```bash
docker compose -f infra-docker-compose.yaml up -d
```

Configure o `.env` com `MONGODB_HOST=localhost`.

### Opcao 3 - Desenvolvimento local

1. Suba o MongoDB localmente ou via Docker.
2. Instale as dependencias:

   ```bash
   cd backend
   uv sync
   ```

3. Execute a aplicacao:

   ```bash
   uv run python src/main.py
   ```

4. Verifique a API:

   ```bash
   curl http://localhost:3000/health
   ```

## Endpoints da API

### `GET /health`

Health check da aplicacao.

**Resposta:**

```json
{
  "app_name": "FIAP POS IA Backend",
  "timestamp": "2026-07-31T10:00:00.000000",
  "status": "UP"
}
```

### `POST /preprocess`

Inicia o pre-processamento dos datasets. O processamento roda em background; a resposta traz o documento criado no MongoDB.

**Body:**

| Campo | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| `rag_percent` | `float` | Nao | Percentual destinado ao conjunto RAG (0.0 a 1.0). E aplicado tanto ao MedQuAD quanto aos protocolos clinicos. |

**Exemplo:**

```bash
curl -X POST http://localhost:3000/preprocess/ \
  -H "Content-Type: application/json" \
  -d '{"rag_percent": 0.5}'
```

**Resposta:**

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "rag_percent": 0.5,
  "steps": {
    "one_download_datasets": { "status": "pending", "error_message": null },
    "step_two_data_extraction": { "status": "pending", "error_message": null }
  },
  "results": {
    "QAs": { "train_data": 0, "rag_data": 0 },
    "clinical_protocols": { "train_data": 0, "rag_data": 0 }
  },
  "status": "created",
  "updated_date": "2026-07-31T10:00:00.000000+00:00",
  "completion_percentage": 0
}
```

Em caso de falha, o documento pode incluir `error_message` e o status pode mudar para `error` ou `failed`.

### `GET /preprocess/{doc_id}`

Consulta o status de uma execucao pelo ID.

**Resposta de exemplo:**

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "rag_percent": 0.5,
  "steps": {
    "one_download_datasets": { "status": "completed" },
    "step_two_data_extraction": { "status": "completed" }
  },
  "results": {
    "QAs": { "train_data": 15234, "rag_data": 8765 },
    "clinical_protocols": { "train_data": 120, "rag_data": 40 }
  },
  "status": "completed",
  "updated_date": "2026-07-31T10:05:00.000000+00:00",
  "completion_percentage": 100
}
```

### `POST /fine-tunning`

Inicia o fine tuning do modelo `hospital_helper` a partir de um `preprocess_id` ja concluido. O treinamento roda em background e a resposta retorna imediatamente com o documento criado.

**Regras principais:**

1. o `preprocess_id` deve existir no MongoDB;
2. o preprocess precisa estar com status `completed`;
3. se nao existir, a API retorna `404`;
4. se existir mas nao estiver concluido, a API retorna `422`;
5. o treino usa GPU quando disponivel e CPU como fallback;
6. o progresso e atualizado periodicamente no MongoDB.

**Body:**

| Campo | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| `preprocess_id` | `str` | Sim | ID do preprocessamento anterior |
| `base_model_name` | `str` | Nao | Override opcional do modelo base |
| `include_clinical_protocols` | `bool` | Nao | Inclui protocolos clinicos no treino (padrao: true) |
| `use_4bit` | `bool` | Nao | Habilita 4-bit quando o ambiente suportar (padrao: false) |
| `max_seq_length` | `int` | Nao | Tamanho maximo da sequencia (padrao: 2048) |
| `num_train_epochs` | `float` | Nao | Numero de epocas (padrao: 1.0) |
| `per_device_train_batch_size` | `int` | Nao | Batch size por dispositivo (padrao: 1) |
| `gradient_accumulation_steps` | `int` | Nao | Passos de acumulacao de gradiente (padrao: 4) |
| `learning_rate` | `float` | Nao | Taxa de aprendizado (padrao: 2e-4) |
| `warmup_ratio` | `float` | Nao | Razao de warmup (padrao: 0.03) |
| `logging_steps` | `int` | Nao | Passos de logging (padrao: 5) |
| `seed` | `int` | Nao | Semente aleatoria (padrao: 3407) |

**Exemplo:**

```bash
curl -X POST http://localhost:3000/fine-tunning/ \
  -H "Content-Type: application/json" \
  -d '{"preprocess_id":"<id>", "use_4bit": false}'
```

**Resposta (documento criado):**

```json
{
  "_id": "550e8400-e29b-41d4-a716-446655440000",
  "preprocess_id": "<id>",
  "preprocess_snapshot": {
    "_id": "<id>",
    "status": "completed",
    "rag_percent": 0.5,
    "updated_date": "2026-08-04T10:00:00.000000+00:00"
  },
  "base_model_name": "Qwen/Qwen2.5-1.5B-Instruct",
  "status": "pendding",
  "completion_percentage": 0,
  "error_message": null,
  "created_date": "2026-08-04T10:05:00.000000+00:00",
  "updated_date": "2026-08-04T10:05:00.000000+00:00",
  "started_date": null,
  "finished_date": null,
  "device": null,
  "dataset_size": 0,
  "qas_examples": 0,
  "clinical_protocol_examples": 0,
  "estimated_total_steps": 0,
  "current_step": 0,
  "current_epoch": null,
  "current_loss": null,
  "loss_history": [],
  "training_metrics": {}
}
```

### `GET /fine-tunning/{doc_id}`

Consulta o status de um fine tuning em andamento ou concluido pelo ID.

**Resposta de exemplo (durante o treinamento):**

```json
{
  "_id": "550e8400-e29b-41d4-a716-446655440000",
  "preprocess_id": "<id>",
  "base_model_name": "Qwen/Qwen2.5-1.5B-Instruct",
  "status": "in_progress",
  "completion_percentage": 45.5,
  "error_message": null,
  "created_date": "2026-08-04T10:05:00.000000+00:00",
  "updated_date": "2026-08-04T10:15:00.000000+00:00",
  "started_date": "2026-08-04T10:05:05.000000+00:00",
  "finished_date": null,
  "device": "cuda",
  "dataset_size": 15000,
  "qas_examples": 15000,
  "clinical_protocol_examples": 120,
  "estimated_total_steps": 15000,
  "current_step": 6825,
  "current_epoch": 0.45,
  "current_loss": 0.234,
  "loss_history": [
    {
      "step": 0,
      "epoch": 0.0,
      "loss": 2.5,
      "timestamp": "2026-08-04T10:05:10.000000+00:00"
    },
    {
      "step": 100,
      "epoch": 0.01,
      "loss": 1.8,
      "timestamp": "2026-08-04T10:06:00.000000+00:00"
    }
  ],
  "training_metrics": {}
}
```

**Resposta de exemplo (concluido):**

```json
{
  "_id": "550e8400-e29b-41d4-a716-446655440000",
  "preprocess_id": "<id>",
  "base_model_name": "Qwen/Qwen2.5-1.5B-Instruct",
  "status": "completed",
  "completion_percentage": 100,
  "error_message": null,
  "created_date": "2026-08-04T10:05:00.000000+00:00",
  "updated_date": "2026-08-04T10:30:00.000000+00:00",
  "started_date": "2026-08-04T10:05:05.000000+00:00",
  "finished_date": "2026-08-04T10:30:00.000000+00:00",
  "device": "cuda",
  "dataset_size": 15000,
  "qas_examples": 15000,
  "clinical_protocol_examples": 120,
  "estimated_total_steps": 15000,
  "current_step": 15000,
  "current_epoch": 1.0,
  "current_loss": 0.12,
  "loss_history": [...],
  "training_metrics": {
    "train_loss": 0.12,
    "train_runtime": 1500.5,
    "train_samples_per_second": 10.0,
    "train_steps_per_second": 10.0
  }
}
```

### `POST /rag-database`

Gera e persiste a base RAG a partir dos arquivos preprocessados existentes. O processo roda em background e a resposta retorna imediatamente com o documento de controle criado.

**Regras principais:**

1. o `preprocess_id` deve existir no MongoDB;
2. o preprocess precisa estar com status `completed`;
3. se nao existir, a API retorna `404`;
4. se existir mas nao estiver concluido, a API retorna `422`;
5. os documentos da base sao persistidos em `rag_documents`;
6. cada documento inclui `metadatas.source` para rastreabilidade de origem.

**Body:**

| Campo | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| `preprocess_id` | `str` | Sim | ID do preprocessamento concluido |

**Exemplo:**

```bash
curl -X POST http://localhost:3000/rag-database/ \
  -H "Content-Type: application/json" \
  -d '{"preprocess_id":"<id>"}'
```

**Resposta (documento criado):**

```json
{
  "_id": "3c3efdbb-4f8e-4d1c-8f4a-0c8d5a8b5e0d",
  "batch_id": "3c3efdbb-4f8e-4d1c-8f4a-0c8d5a8b5e0d",
  "preprocess_id": "<id>",
  "preprocess_snapshot": {
    "_id": "<id>",
    "status": "completed",
    "rag_percent": 0.5,
    "updated_date": "2026-08-13T10:00:00+00:00"
  },
  "qas_rag_path": "backend/datasets/preprocessed/qas/rag_pt_br.json",
  "clinical_protocols_rag_path": "backend/datasets/preprocessed/clinical_protocols/rag.json",
  "embedding_model": "hkunlp/instructor-base",
  "splitter_name": "RecursiveCharacterTextSplitter",
  "splitter_chunk_size": 2400,
  "splitter_chunk_overlap": 200,
  "status": "pendding",
  "completion_percentage": 0,
  "error_message": null,
  "current_step": 0,
  "estimated_total_steps": 2,
  "qas_documents": 0,
  "clinical_protocol_documents": 0,
  "total_documents": 0
}
```

### `GET /rag-database/{doc_id}`

Consulta o status da geracao da base RAG pelo ID.

**Resposta de exemplo (concluido):**

```json
{
  "_id": "3c3efdbb-4f8e-4d1c-8f4a-0c8d5a8b5e0d",
  "batch_id": "3c3efdbb-4f8e-4d1c-8f4a-0c8d5a8b5e0d",
  "preprocess_id": "<id>",
  "preprocess_snapshot": {
    "_id": "<id>",
    "status": "completed",
    "rag_percent": 0.5,
    "updated_date": "2026-08-13T10:00:00+00:00"
  },
  "status": "completed",
  "completion_percentage": 100,
  "error_message": null,
  "current_step": 2,
  "estimated_total_steps": 2,
  "qas_documents": 8703,
  "clinical_protocol_documents": 42,
  "total_documents": 8745
}
```

### Estrutura do corpus RAG

Os documentos gravados em `rag_documents` seguem uma estrutura pensada para recuperacao e citacao:

- `content`: texto normalizado usado na indexacao;
- `dataset` / `source_type`: identifica se o documento veio de `qas` ou `clinical_protocols`;
- `embedding`: vetor gerado para recuperar o documento no futuro;
- `metadatas.source`: guarda a origem que o agente pode exibir ao responder.

Para `qas`, `metadatas.source` replica o objeto `metadata` do dataset original. Para `clinical_protocols`, `metadatas.source` contem `name`, `url` e `source`.

**Resposta de exemplo (erro):**

```json
{
  "_id": "550e8400-e29b-41d4-a716-446655440000",
  "preprocess_id": "<id>",
  "base_model_name": "Qwen/Qwen2.5-1.5B-Instruct",
  "status": "error",
  "completion_percentage": 23.5,
  "error_message": "CUDA out of memory",
  "created_date": "2026-08-04T10:05:00.000000+00:00",
  "updated_date": "2026-08-04T10:10:00.000000+00:00",
  "started_date": "2026-08-04T10:05:05.000000+00:00",
  "finished_date": "2026-08-04T10:10:00.000000+00:00"
}
```

## Fluxo de fine tuning

O fluxo de fine tuning segue estes passos:

1. **Validacao**: Verifica se o `preprocess_id` existe e esta com status `completed`
2. **Criacao do documento**: Cria um documento na collection `fine_tunning` com status `pendding`
3. **Retorno imediato**: Retorna o documento criado com ID para o cliente
4. **Treinamento em background**: Inicia o treinamento em background task
5. **Atualizacao de progresso**: Callback do Trainer atualiza status, completion_percentage e loss_history a cada 5 segundos
6. **Conclusao**: Ao finalizar, marca como `completed` com 100% e salva metricas finais
7. **Erro**: Em caso de falha, marca como `error` com `error_message` preenchido

```mermaid
flowchart TD
    A[POST /fine-tunning] --> B[Valida preprocess_id]
    B --> C[Cria documento fine_tunning]
    C --> D[Retorna ID imediatamente]
    C --> E[Background task]
    E --> F[Carrega dados preprocessados]
    F --> G[Carrega modelo base]
    G --> H[Aplica LoRA]
    H --> I[Inicia treinamento]
    I --> J[Callback atualiza progresso]
    J --> K[Treinamento concluido?]
    K -->|Nao| J
    K -->|Sim| L[Salva modelo e tokenizer]
    L --> M[Atualiza MongoDB com metricas]
    M --> N[Status: completed]
    J --> O[Erro?]
    O -->|Sim| P[Atualiza MongoDB com erro]
    P --> Q[Status: error]
```

**Campos de progresso monitorados:**

- `status`: `pendding` → `in_progress` → `completed` ou `error`
- `completion_percentage`: 0 a 100, calculado baseado em `current_step / estimated_total_steps`
- `current_loss`: Loss atual do treinamento
- `loss_history`: Array com historico de loss por step/epoch para acompanhar eficiencia
- `training_metrics`: Metricas finais do treinamento (train_loss, train_runtime, etc.)
- `error_message`: Mensagem de erro em caso de falha

## Fluxo de preprocessamento

Quando `POST /preprocess` e chamado, a sequencia em background e:

```mermaid
flowchart TD
    A[POST /preprocess] --> B[Cria documento no MongoDB]
    B --> C[Retorna ID imediatamente]
    B --> D[Background task]
    D --> E[Download PubMedQA e MedQuAD]
    E --> F[Baixa protocolos clinicos FHEMIG]
    F --> G[Processa PubMedQA e MedQuAD]
    G --> H[Extrai texto dos PDFs dos protocolos]
    H --> I[Divide train e RAG]
    I --> J[Traduz os QAs com o modelo local]
    J --> K[Salva JSONs em datasets/preprocessed/]
    K --> L[Atualiza MongoDB]
```

### Regras de divisao dos dados

- PubMedQA vai 100% para `train.json`.
- MedQuAD e protocolos clinicos sao divididos conforme `rag_percent`.
- Os resultados sao salvos separadamente em:
  - `datasets/preprocessed/qas/`
  - `datasets/preprocessed/clinical_protocols/`

### Step 3 - traducao local

A etapa de traducao usa localmente o modelo `Helsinki-NLP/opus-mt-tc-big-en-pt`, carregado por `transformers` e executado com `torch`.

- Se o backend encontrar uma GPU Nvidia disponivel, a inferencia roda em CUDA.
- Se nao encontrar GPU, o modelo roda em CPU, o que aumenta bastante o tempo de execucao.
- Os arquivos traduzidos sao gerados com sufixo `_pt_br.json`.

## Estrutura do projeto

```text
backend/
|-- Dockerfile
|-- pyproject.toml
|-- uv.lock
|-- src/
`-- datasets/
    |-- get_datasets.py
    |-- files/
    `-- preprocessed/
```

## Documentacao interativa

Com a API rodando:

| URL | Descricao |
|-----|-----------|
| http://localhost:3000/docs | Swagger UI |
| http://localhost:3000/redoc | ReDoc |
