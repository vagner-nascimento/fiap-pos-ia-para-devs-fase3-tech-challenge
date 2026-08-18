# Documentação de Arquitetura — FIAP POS IA Fase 3

> **Tech Challenge — Pré-processamento de Datasets Médicos e Fine-tuning de LLM**

Este documento descreve a arquitetura do sistema desenvolvido para o Tech Challenge da Fase 3 da Pós-graduação FIAP em IA para Devs. O objetivo é prover uma visão técnica abrangente — do contexto de alto nível até os componentes internos — para facilitar a compreensão, manutenção e evolução da solução.

---

## Índice

1. [Visão Geral](#visão-geral)
2. [C4 Level 1 — Diagrama de Contexto](#c4-level-1--diagrama-de-contexto)
3. [C4 Level 2 — Diagrama de Container](#c4-level-2--diagrama-de-container)
4. [C4 Level 3 — Diagrama de Componentes](#c4-level-3--diagrama-de-componentes)
5. [Diagrama de Deployment](#diagrama-de-deployment)
6. [Diagrama de Sequência — Pipeline de Pré-processamento](#diagrama-de-sequência--pipeline-de-pré-processamento)
7. [Diagrama de Sequência — Fine-tuning Local](#diagrama-de-sequência--fine-tuning-local)
8. [Decisões de Arquitetura (ADRs)](#decisões-de-arquitetura-adrs)

---

## Visão Geral

A solução é uma aplicação **full-stack** composta por três camadas principais:

| Camada | Tecnologia | Responsabilidade |
|---|---|---|
| **Frontend** | React + TypeScript + Vite | Interface web para iniciar e monitorar o processamento |
| **Backend** | Python + FastAPI | API REST, orquestração das pipelines de dados e fine-tuning |
| **Banco de dados** | MongoDB | Persistência do estado das execuções |

O fluxo central da aplicação é:

1. O usuário acessa o frontend e inicia o pré-processamento configurando o parâmetro `rag_percent`.
2. O backend recebe a requisição, cria um documento de rastreamento no MongoDB e dispara a pipeline em background.
3. A pipeline baixa os datasets (PubMedQA, MedQuAD, protocolos FHEMIG), extrai os dados, os separa entre conjuntos de treino e RAG, e os traduz para português.
4. O usuário pode acompanhar o progresso em tempo real via polling do frontend.
5. Com os dados pré-processados, é possível iniciar o fine-tuning do modelo Qwen2.5-1.5B-Instruct diretamente pela aplicação (com GPU) ou via Jupyter Notebooks no Google Colab.

> **Nota sobre fine-tuning:** Devido a restrições de hardware local, o fine-tuning do modelo foi executado no Google Colab. O modelo treinado está disponível como repositório privado no HuggingFace. Para servir o modelo em produção, utiliza-se HuggingFace Spaces com ZeroGPU.

---

## C4 Level 1 — Diagrama de Contexto

Visão de mais alto nível: quem usa o sistema e com quais sistemas externos ele se integra.

```mermaid
C4Context
    title Diagrama de Contexto — FIAP POS IA Fase 3

    Person(usuario, "Usuário / Pesquisador", "Acessa a interface web para disparar e monitorar o pré-processamento e o fine-tuning")

    System(sistema, "FIAP POS IA — Sistema de Processamento", "Pré-processa datasets médicos e realiza fine-tuning de LLM para o domínio de saúde")

    System_Ext(pubmedqa, "PubMedQA", "Dataset público de Q&A médico baseado em artigos do PubMed")
    System_Ext(medquad, "MedQuAD", "Dataset de Q&A médico derivado de fontes do NIH")
    System_Ext(fhemig, "FHEMIG (protocolos clínicos)", "PDFs de protocolos clínicos públicos da FHEMIG/MG")
    System_Ext(huggingface, "HuggingFace Hub", "Hospeda o modelo base (Qwen2.5) e o modelo fine-tunado")
    System_Ext(colab, "Google Colab", "Plataforma de execução do fine-tuning com GPU gratuita")

    Rel(usuario, sistema, "Usa", "HTTPS / interface web")
    Rel(sistema, pubmedqa, "Baixa dataset", "HTTP/HuggingFace datasets lib")
    Rel(sistema, medquad, "Baixa dataset", "HTTP/HuggingFace datasets lib")
    Rel(sistema, fhemig, "Baixa PDFs e extrai texto", "HTTP + pdfplumber")
    Rel(sistema, huggingface, "Baixa modelo base e publica modelo treinado", "HuggingFace Hub API")
    Rel(colab, huggingface, "Publica modelo fine-tunado", "HuggingFace Hub API")
    Rel(usuario, colab, "Executa notebooks de fine-tuning", "Google Colab UI")
```

---

## C4 Level 2 — Diagrama de Container

Detalha os containers (processos/serviços) que compõem o sistema e como se comunicam.

```mermaid
C4Container
    title Diagrama de Container — FIAP POS IA Fase 3

    Person(usuario, "Usuário", "Acessa via navegador")

    Container_Boundary(sistema, "FIAP POS IA System") {
        Container(frontend, "Frontend", "React + TypeScript + Vite\nNginx (produção)", "Interface web para iniciar e monitorar processamento e fine-tuning")
        Container(backend, "Backend API", "Python 3.11 + FastAPI + Uvicorn", "REST API: orquestra pré-processamento, fine-tuning e rastreamento de estado")
        ContainerDb(mongodb, "MongoDB", "MongoDB (Docker)", "Armazena documentos de rastreamento de preprocess e fine-tuning")
        Container(datasets_fs, "Sistema de Arquivos / Datasets", "Volume Docker", "Armazena datasets brutos, pré-processados e modelos treinados")
    }

    Container_Ext(huggingface, "HuggingFace Hub", "SaaS", "Modelo base e repositório do modelo fine-tunado")
    Container_Ext(colab, "Google Colab", "SaaS", "Notebooks de fine-tuning com GPU A100/T4")

    Rel(usuario, frontend, "Acessa", "HTTPS :8080")
    Rel(frontend, backend, "REST API calls", "HTTP :3000")
    Rel(backend, mongodb, "Lê / Grava estado", "MongoDB Wire Protocol :27017")
    Rel(backend, datasets_fs, "Lê/Grava datasets e modelos", "I/O local")
    Rel(backend, huggingface, "Baixa modelo base", "HTTPS / datasets lib")
    Rel(colab, huggingface, "Publica modelo fine-tunado", "HTTPS / HuggingFace Hub API")
    Rel(usuario, colab, "Executa fine-tuning", "HTTPS")
```

---

## C4 Level 3 — Diagrama de Componentes

Detalha os componentes internos do **Backend**, que é o núcleo da lógica de negócio.

```mermaid
C4Component
    title Diagrama de Componentes — Backend FastAPI

    Container_Boundary(backend, "Backend API") {
        Component(server, "server.py", "FastAPI Application Factory", "Cria a app, configura CORS, lifespan e carrega routers dinamicamente")

        Component(router_preprocess, "routers/preprocess.py", "APIRouter", "POST /preprocess — inicia pipeline\nGET /preprocess/{id} — consulta status")
        Component(router_finetuning, "routers/fine_tunning.py", "APIRouter", "POST /fine-tunning — inicia treinamento\nGET /fine-tunning/{id} — consulta status")

        Component(svc_preprocess, "services/preprocess_data.py", "Service", "Orquestra a pipeline de 3 steps em background")
        Component(svc_finetuning, "services/fine_tunning.py", "Service", "Carrega modelo, aplica LoRA, executa SFTTrainer em background")

        Component(step1, "services/preprocess/step_one_download_datasets.py", "Step", "Baixa PubMedQA, MedQuAD e PDFs FHEMIG")
        Component(step2, "services/preprocess/step_two_data_extraction.py", "Step", "Extrai e divide dados em train/RAG por rag_percent")
        Component(step3, "services/preprocess/step_three_translation.py", "Step", "Traduz dados QA para pt-BR")

        Component(infra_db, "infra/database/mongodb.py", "Infrastructure", "Gerencia conexão com MongoDB (pymongo)")
        Component(col_preprocess, "infra/database/collections/preprocess.py", "Repository", "CRUD da collection preprocess")
        Component(col_finetuning, "infra/database/collections/fine_tunning.py", "Repository", "CRUD da collection fine_tunning")
    }

    ContainerDb(mongodb, "MongoDB", "MongoDB")

    Rel(server, router_preprocess, "Registra router")
    Rel(server, router_finetuning, "Registra router")
    Rel(router_preprocess, svc_preprocess, "Chama")
    Rel(router_finetuning, svc_finetuning, "Chama")
    Rel(svc_preprocess, step1, "Executa Step 1")
    Rel(svc_preprocess, step2, "Executa Step 2")
    Rel(svc_preprocess, step3, "Executa Step 3")
    Rel(svc_preprocess, col_preprocess, "Lê/Grava estado")
    Rel(svc_finetuning, col_finetuning, "Lê/Grava estado")
    Rel(svc_finetuning, col_preprocess, "Valida preprocess_id")
    Rel(col_preprocess, infra_db, "Usa conexão")
    Rel(col_finetuning, infra_db, "Usa conexão")
    Rel(infra_db, mongodb, "Conecta", "pymongo :27017")
```

---

## Diagrama de Deployment

Representa a topologia de execução em ambiente local via Docker Compose.

```mermaid
graph TB
    subgraph Host["🖥️ Host — Máquina Local"]
        subgraph DockerCompose["Docker Compose (fiap-network)"]
            subgraph FE["Container: fiap-pos-ia-frontend"]
                nginx["Nginx :80\n(serve build React)"]
            end

            subgraph BE["Container: fiap-pos-ia-backend"]
                uvicorn["Uvicorn :3000\nFastAPI App"]
                gpu_detect["Detecção GPU/CPU\n(runtime: nvidia)"]
                datasets_vol["📁 /datasets\n(raw + preprocessed)"]
                models_vol["📁 /models\n(fine-tuned model)"]
            end

            subgraph DB["Container: mongodb"]
                mongo_proc["MongoDB :27017"]
                mongo_vol[("📦 Volume\nmongodb_data")]
            end
        end

        port_fe["→ :8080 (host)"]
        port_be["→ :3000 (host)"]
        port_db["→ :27017 (host)"]
    end

    subgraph Externos["☁️ Externos"]
        hf["HuggingFace Hub\n(modelo base)"]
        fhemig_ext["FHEMIG / PubMedQA\n/ MedQuAD"]
    end

    port_fe -->|":8080 → :80"| nginx
    port_be -->|":3000 → :3000"| uvicorn
    port_db -->|":27017 → :27017"| mongo_proc

    nginx -->|"API calls"| uvicorn
    uvicorn --> gpu_detect
    uvicorn --> datasets_vol
    uvicorn --> models_vol
    uvicorn -->|"pymongo"| mongo_proc
    mongo_proc --> mongo_vol
    uvicorn -->|"HTTPS"| hf
    uvicorn -->|"HTTPS download"| fhemig_ext

    style Host fill:#1e2130,stroke:#4a5568,color:#e2e8f0
    style DockerCompose fill:#2d3748,stroke:#63b3ed,color:#e2e8f0
    style FE fill:#2c5282,stroke:#63b3ed,color:#e2e8f0
    style BE fill:#276749,stroke:#68d391,color:#e2e8f0
    style DB fill:#744210,stroke:#f6ad55,color:#e2e8f0
    style Externos fill:#322659,stroke:#b794f4,color:#e2e8f0
```

---

## Diagrama de Sequência — Pipeline de Pré-processamento

Fluxo completo desde a requisição do usuário até a conclusão da pipeline de 3 steps.

```mermaid
sequenceDiagram
    actor U as Usuário
    participant FE as Frontend (React)
    participant API as Backend API (FastAPI)
    participant BG as Background Task
    participant S1 as Step 1: Download
    participant S2 as Step 2: Extração
    participant S3 as Step 3: Tradução
    participant DB as MongoDB

    U->>FE: Clica em "Iniciar Processamento"\n(informa rag_percent)
    FE->>API: POST /preprocess\n{ rag_percent: 0.5 }
    API->>DB: create_preprocess_document()
    DB-->>API: { _id, status: "pending", ... }
    API->>BG: background_tasks.add_task(preprocess_data_background)
    API-->>FE: 200 OK — { _id, status: "pending" }
    FE-->>U: Exibe card com status inicial

    loop Polling a cada N segundos
        FE->>API: GET /preprocess/{id}
        API->>DB: get_preprocess_document(id)
        DB-->>API: documento atual
        API-->>FE: status + completion_percentage
        FE-->>U: Atualiza progresso na tela
    end

    Note over BG,DB: Execução em background

    BG->>DB: update_step_status("one_download_datasets", "in_progress")
    BG->>S1: download_datasets(doc_id)
    S1-->>BG: { qas_paths, clinical_protocols_paths }
    BG->>DB: update_step_status("one_download_datasets", "completed")

    BG->>DB: update_step_status("two_data_extraction", "in_progress")
    BG->>S2: extract_data(doc_id, qas_paths, clinical_protocols_paths, rag_percent)
    S2-->>BG: train_qa_path, rag_qa_path, train_clinical_path, rag_clinical_path
    BG->>DB: update_step_status("two_data_extraction", "completed")

    BG->>DB: update_step_status("three_translating", "in_progress")
    BG->>S3: translate(doc_id, (train_qa_path, rag_qa_path))
    S3-->>BG: translated_train_path, translated_rag_path
    BG->>DB: update_step_status("three_translating", "completed")

    BG->>DB: update_preprocess_document(doc_id, results, 100%)
    FE->>API: GET /preprocess/{id}
    API-->>FE: status: "completed", completion_percentage: 100
    FE-->>U: Exibe resultados finais (contagens QAs e clinical_protocols)
```

---

## Diagrama de Sequência — Fine-tuning Local

Fluxo do fine-tuning executado localmente via API (requer GPU).

```mermaid
sequenceDiagram
    actor U as Usuário
    participant FE as Frontend (React)
    participant API as Backend API (FastAPI)
    participant BG as Background Task
    participant SVC as FineTunning Service
    participant DB as MongoDB
    participant FS as Sistema de Arquivos
    participant HF as HuggingFace Hub

    U->>FE: Clica em "Iniciar Fine-tuning"\n(informa preprocess_id)
    FE->>API: POST /fine-tunning\n{ preprocess_id, ... params }
    API->>DB: Valida preprocess_id (status == "completed")
    DB-->>API: preprocess document OK
    API->>DB: create_fine_tunning_document(payload)
    DB-->>API: { _id, status: "pending" }
    API->>BG: background_tasks.add_task(_training_job, doc_id)
    API-->>FE: 200 OK — { _id, status: "pending" }

    Note over BG,FS: Execução em background (pode levar horas)

    BG->>SVC: _training_job(doc_id)
    SVC->>FS: Lê train_pt_br.json e train.json (clinical_protocols)
    SVC->>SVC: _build_training_texts() — formata exemplos para SFTTrainer
    SVC->>HF: AutoModelForCausalLM.from_pretrained("Qwen/Qwen2.5-1.5B-Instruct")
    HF-->>SVC: Modelo base carregado
    SVC->>SVC: _apply_lora() — configura LoRA (r=16, alpha=16)
    SVC->>DB: Atualiza device, dataset_size, estimated_total_steps

    loop A cada logging_step (padrão: 5 steps)
        SVC->>DB: FineTunningProgressCallback._persist()\n(status, completion%, loss, epoch)
    end

    SVC->>FS: model.save_pretrained(model_output_dir)
    SVC->>FS: tokenizer.save_pretrained(tokenizer_output_dir)
    SVC->>FS: Salva training_summary.json
    SVC->>DB: mark_fine_tunning_document_completed()
    FE->>API: GET /fine-tunning/{id}
    API-->>FE: status: "completed", training_metrics
    FE-->>U: Exibe métricas finais (loss, epochs, steps)
```

---

## Decisões de Arquitetura (ADRs)

As decisões técnicas que moldaram esta arquitetura estão documentadas como **ADRs (Architecture Decision Records)** no formato MADR:

| # | Título | Status |
|---|---|---|
| [ADR-001](adr/ADR-001-modelo-base-qwen.md) | Escolha do modelo base Qwen2.5-1.5B-Instruct | ✅ Aceito |
| [ADR-002](adr/ADR-002-lora-peft-finetuning.md) | Uso de LoRA/PEFT para fine-tuning eficiente | ✅ Aceito |
| [ADR-003](adr/ADR-003-qlora-4bit-fallback-cpu.md) | QLoRA (quantização 4-bit) com fallback para CPU | ✅ Aceito |
| [ADR-004](adr/ADR-004-mongodb-estado.md) | MongoDB como banco de estado do processamento | ✅ Aceito |
| [ADR-005](adr/ADR-005-background-tasks-fastapi.md) | Processamento assíncrono via FastAPI BackgroundTasks | ✅ Aceito |
| [ADR-006](adr/ADR-006-finetuning-google-colab.md) | Fine-tuning executado no Google Colab | ✅ Aceito |
| [ADR-007](adr/ADR-007-split-train-rag.md) | Split train/RAG configurável via rag_percent | ✅ Aceito |
| [ADR-008](adr/ADR-008-docker-compose.md) | Orquestração local via Docker Compose | ✅ Aceito |
| [ADR-009](adr/ADR-009-deteccao-gpu-cpu.md) | Detecção automática GPU/CPU no backend | ✅ Aceito |
| [ADR-010](adr/ADR-010-colab-ngrok-zerогpu.md) | Colab + ngrok e HuggingFace ZeroGPU para servir o modelo | ✅ Aceito |
