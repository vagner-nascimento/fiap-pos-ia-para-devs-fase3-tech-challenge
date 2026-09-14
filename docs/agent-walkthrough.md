# Walkthrough — Agente Médico com LangChain/LangGraph

## ✅ Implementação Completa
 
### Resultado dos Testes
```
64 passed, 1 warning in 0.94s
```

| Suite | Testes | Status |
|---|---|---|
| `test_topic_validator.py` | 15 | ✅ 15/15 |
| `test_safety_guard.py` | 12 | ✅ 12/12 |
| `test_patient_context_retriever.py` | 14 | ✅ 14/14 |
| `test_context_summarizer.py` | 16 | ✅ 16/16 |
| `test_audit_logger.py` | 3 | ✅ 3/3 |
| `test_medical_agent.py` | 4 | ✅ 4/4 |

---

## Arquivos Criados / Modificados

### Serviço Isolado `agent/`

| Arquivo | Descrição |
|---|---|
| `agent/Dockerfile` | Container Python 3.11, porta 8001 |
| `agent/pyproject.toml` | Dependências: langgraph, langchain, pymongo, fastapi, httpx... |
| `agent/.env.example` | Template de variáveis de ambiente (`LLM_MAX_CONTEXT_TOKENS=3000`, Groq configs) |
| `agent/src/main.py` | Entrypoint Uvicorn |
| `agent/src/server.py` | App factory FastAPI (mesmo padrão do backend) |

### Infra / Database

| Arquivo | Descrição |
|---|---|
| `agent/src/infra/database/mongodb.py` | Conexão MongoDB singleton |
| `agent/src/infra/database/collections/agent_audit_logs.py` | Collection de auditoria detalhada com suporte a Jornada 2 |

### Serviços LangGraph (8 Nós)

| Arquivo | Responsabilidade |
|---|---|
| `agent/src/services/llm_client.py` | HuggingFaceEndpoint + fallback HTTP direto |
| `agent/src/services/medical_agent.py` | **StateGraph LangGraph** — orquestrador dos 8 nós com checkpoints |
| `agent/src/services/nodes/topic_validator.py` | Nó 1: Valida domínio médico (keywords + regex + normalização Unicode) |
| `agent/src/services/nodes/safety_guard.py` | Nó 2: Guardrails de segurança (bloqueia prescrição imperativa/dosagens) |
| `agent/src/services/nodes/patient_context_retriever.py` | Nó 3: Busca prontuário estruturado (`GET /medical-record`) e anonimiza dados LGPD |
| `agent/src/services/nodes/rag_retriever.py` | Nó 4: RAG via HTTP → `/rag-database/query` enriquecido com diagnóstico do paciente |
| `agent/src/services/nodes/context_summarizer.py` | Nó 5: Gerenciador da janela SFT de 3.000 tokens (Groq `compound-mini` / fallback Python) |
| `agent/src/services/nodes/llm_generator.py` | Nó 6: Prompt SFT estruturado e inferência no modelo fine-tunado |
| `agent/src/services/nodes/response_formatter.py` | Nó 7: Formata fontes inline + disclaimer obrigatório |
| `agent/src/services/nodes/audit_logger.py` | Nó 8: Persiste auditoria completa no MongoDB |
| `agent/src/routers/agent.py` | `POST /agent/chat`, `GET /agent/audit/{session_id}` |

---

## Grafo LangGraph (fluxo de execução dos 8 nós)

```
[START] → topic_validator
              │
     ┌────────┴───────────┐
 (inválido)            (válido)
     │                    │
     ▼                    ▼
audit_logger         safety_guard
                          │
                ┌─────────┴──────────┐
            (bloqueado)           (seguro)
                │                    │
                ▼                    ▼
          audit_logger    patient_context_retriever
                                     │
                                     ▼
                               rag_retriever
                                     │
                                     ▼
                             context_summarizer
                                     │
                                     ▼
                               llm_generator
                                     │
                                     ▼
                             response_formatter
                                     │
                                     ▼
                               audit_logger → [END]
```

---

## Como Usar

### 1. Configurar variáveis de ambiente
```bash
cp agent/.env.example agent/.env
# Edite LLM_ENDPOINT_URL com a URL do ngrok (Colab) ou ZeroGPU
```

### 2. Subir o serviço
```bash
# Com Docker Compose (recomendado)
LLM_ENDPOINT_URL=https://seu-ngrok.ngrok-free.app \
LLM_API_TOKEN=hf_seu_token \
docker compose -f app-docker-compose.yaml up agent --build

# Local (para desenvolvimento)
cd agent
PYTHONPATH=src LLM_ENDPOINT_URL=https://... uvicorn main:app --port 8001 --reload
```

### 3. Testar o agente

```bash
# Jornada 1 — Consulta médica geral (RAG sobre protocolos FHEMIG / PubMedQA)
curl -X POST http://localhost:8001/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "sess-001", "query": "Quais são as diretrizes para manejo de sepse em UTI?"}'

# Jornada 2 — Consulta contextualizada por paciente (Prontuário + RAG + Sumarizador)
curl -X POST http://localhost:8001/agent/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess-002",
    "patient_name": "Carlos Eduardo Oliveira",
    "query": "O paciente possui contraindicações nos protocolos para uso de anticoagulantes considerando seu quadro?"
  }'

# Consulta off-topic (bloqueada pelo topic_validator)
curl -X POST http://localhost:8001/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "sess-003", "query": "Como fazer bolo de cenoura com chocolate?"}'

# Prescrição imperativa (bloqueada pelo safety_guard)
curl -X POST http://localhost:8001/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "sess-004", "query": "Me prescreva amoxicilina 500mg de 8 em 8 horas?"}'

# Histórico de auditoria da sessão
curl http://localhost:8001/agent/audit/sess-002

# Swagger UI interativo
open http://localhost:8001/docs
```

### 4. Rodar testes
```bash
cd agent
PYTHONPATH=src uv run --with pytest pytest tests/ -v
```

---

## Decisões Técnicas Importantes

### Roteamento Determinístico via `patient_name` (Jornada 1 vs Jornada 2)
Em vez de depender de expressões regulares frágeis ou tentar extrair nomes de pessoas livres no texto da pergunta (com risco de falsos positivos em nomes de medicamentos, doenças ou autores de protocolos), a diferenciação entre Jornada 1 e Jornada 2 é **determinística**:
- Se `patient_name` é fornecido no payload (`POST /agent/chat`), o fluxo executa a **Jornada 2**: consulta a base estruturada (`GET /medical-record`), anonimiza dados clínicos e cruza prontuário com RAG.
- Se `patient_name` estiver ausente ou vazio, executa a **Jornada 1**: consulta puramente informativa de protocolos institucionais.

### Controle Estrito da Janela SFT de 3.000 Tokens (`context_summarizer`)
O modelo customizado `hospital-helper-qwen2.5-1.5b` foi submetido a fine-tuning com sequência máxima de 3.000 tokens.
Quando o pacote completo (pergunta + prontuário clínico + documentos RAG) se aproxima de 3.000 tokens (`LLM_MAX_CONTEXT_TOKENS=3000`), o nó `context_summarizer` atua antes da inferência:
- Invoca a LLM de alta velocidade `groq/compound-mini` (70.000 TPM, sem limite diário de tokens) para condensar os pontos críticos em menos de 800 tokens.
- Se a API da Groq estiver indisponível ou offline, entra em ação o fallback determinístico em Python puro, truncando o contexto por ordem de prioridade clínica (`avaliação` > `plano/prescrição` > `alergias` > `vitais` > `RAG`).

### Correção de Normalização Unicode (`Mn`) no Validador de Tópico
A categoria padrão para diacríticos em `unicodedata` é `"Mn"` (titlecase). A versão inicial continha `"MN"`, impedindo a remoção adequada de acentos em palavras portuguesas com caracteres combinados. Além disso, keywords ambíguas como `"receita"` foram substituídas por termos estritamente clínicos (`"receituario"`, `"prescrever"`, etc.) para evitar falsos positivos culinários.

### Early-exit eficiente
Queries off-topic e violações de guardrail não chegam ao RAG retriever, prontuário nem à LLM. O grafo LangGraph faz short-circuit direto para o `audit_logger`, economizando latência, requisições de rede e custo de inferência.

### `requires_human_validation: true` — Invariante do sistema
Sempre `true` em toda resposta, independentemente do conteúdo. Garante que nenhuma integração trate o assistente como substituto de validação médica profissional.

### LLM Endpoint flexível
O `llm_client.py` tenta usar `HuggingFaceEndpoint` do LangChain. Se não disponível, faz fallback para chamada HTTP direta. A URL é configurável via `LLM_ENDPOINT_URL`, suportando ngrok (Colab dev) e ZeroGPU (produção) sem alterar código.

---

## Segurança — 4 Camadas

| Camada | Mecanismo | Onde |
|---|---|---|
| 1 — Validação de tópico | Keywords médicas PT/EN + padrões contextuais | `topic_validator.py` |
| 2 — Guardrails de regex | Lista negra: prescrição com dose, diagnóstico definitivo | `safety_guard.py` |
| 3 — System prompt | Instruções de limite de atuação para a LLM | `llm_generator.py` |
| 4 — Disclaimer obrigatório | Appended em toda resposta + campo `requires_human_validation` | `response_formatter.py` |

---

## Schema da Collection `agent_audit_logs`

```json
{
  "_id": "uuid-v4",
  "session_id": "string",
  "query": "string",
  "topic_valid": true,
  "safety_triggered": false,
  "safety_reason": null,
  "patient_name": "Carlos Eduardo Oliveira | null",
  "patient_record_used": true,
  "patient_fields_used": ["avaliacao", "alergias", "prescricao_atual", "sinais_vitais"],
  "context_summarized": true,
  "context_summarizer_mode": "groq",
  "rag_documents_used": [
    {
      "id": "doc-id",
      "dataset": "qas",
      "source_type": "qas",
      "similarity_score": 0.87,
      "content_preview": "primeiros 200 chars..."
    }
  ],
  "rag_documents_count": 5,
  "llm_response_raw": "string",
  "final_response": "string (com fontes + disclaimer)",
  "sources_cited": ["PubMedQA/MedQuAD", "FHEMIG (Protocolos Clínicos)", "Prontuário do Paciente (Carlos Eduardo Oliveira)"],
  "has_disclaimer": true,
  "preprocess_id": "string | null",
  "duration_ms": 1234,
  "created_date": "ISO8601"
}
```
