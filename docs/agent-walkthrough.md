# Walkthrough — Agente Médico com LangChain/LangGraph

## ✅ Implementação Completa

### Resultado dos Testes
```
30 passed, 1 warning in 0.35s
```

| Suite | Testes | Status |
|---|---|---|
| `test_topic_validator.py` | 15 | ✅ 15/15 |
| `test_safety_guard.py` | 12 | ✅ 12/12 |
| `test_audit_logger.py` | 3 | ✅ 3/3 |

---

## Arquivos Criados

### Serviço Isolado `agent/`

| Arquivo | Descrição |
|---|---|
| `agent/Dockerfile` | Container Python 3.11, porta 8001 |
| `agent/pyproject.toml` | Dependências: langgraph, langchain, pymongo, fastapi... |
| `agent/.env.example` | Template de variáveis de ambiente |
| `agent/src/main.py` | Entrypoint Uvicorn |
| `agent/src/server.py` | App factory FastAPI (mesmo padrão do backend) |

### Infra / Database

| Arquivo | Descrição |
|---|---|
| `agent/src/infra/database/mongodb.py` | Conexão MongoDB singleton |
| `agent/src/infra/database/collections/agent_audit_logs.py` | Nova collection de auditoria |

### Serviços LangGraph

| Arquivo | Responsabilidade |
|---|---|
| `agent/src/services/llm_client.py` | HuggingFaceEndpoint + fallback HTTP direto |
| `agent/src/services/medical_agent.py` | **StateGraph LangGraph** — orquestrador principal |
| `agent/src/services/nodes/topic_validator.py` | Nó 1: Valida domínio médico (keywords + regex) |
| `agent/src/services/nodes/safety_guard.py` | Nó 2: Guardrails de segurança (lista negra de padrões) |
| `agent/src/services/nodes/rag_retriever.py` | Nó 3: RAG via HTTP → `/rag-database/query` do backend |
| `agent/src/services/nodes/llm_generator.py` | Nó 4: Prompt ChatML + chamada ao modelo fine-tunado |
| `agent/src/services/nodes/response_formatter.py` | Nó 5: Formata fontes inline + disclaimer |
| `agent/src/services/nodes/audit_logger.py` | Nó 6: Persiste auditoria no MongoDB |
| `agent/src/routers/agent.py` | `POST /agent/chat`, `GET /agent/audit/{session_id}` |

### Arquivos Atualizados

| Arquivo | Mudança |
|---|---|
| `app-docker-compose.yaml` | Adicionado container `fiap-pos-ia-agent` porta 8001 |
| `docs/architecture/README.md` | C4 Level 2 + diagrama de sequência do agente |
| `docs/architecture/adr/ADR-011-langgraph-medical-agent.md` | ADR documentando a escolha do LangGraph |

---

## Grafo LangGraph (fluxo de execução)

```
[START] → init → topic_validator
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
                  audit_logger         rag_retriever
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
# Consulta médica normal
curl -X POST http://localhost:8001/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "sess-001", "query": "Quais são os sintomas da tuberculose?"}'

# Consulta off-topic (bloqueada pelo topic_validator)
curl -X POST http://localhost:8001/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "sess-002", "query": "Como fazer bolo de chocolate?"}'

# Prescrição (bloqueada pelo safety_guard)
curl -X POST http://localhost:8001/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "sess-003", "query": "Me prescreve amoxicilina 500mg?"}'

# Histórico de auditoria
curl http://localhost:8001/agent/audit/sess-001

# Swagger UI
open http://localhost:8001/docs
```

### 4. Rodar testes
```bash
cd agent
PYTHONPATH=src python -m pytest tests/ -v
```

---

## Decisões Técnicas Importantes

### Bug Python 3.14+ — Tokenização Unicode
`re.findall(r"\b\w+\b", ...)` em texto com acentos removidos via NFD (unicodedata) quebrava palavras como `"câncer"` → `['ca', 'ncer']`. Corrigido usando `\b[a-z0-9]{2,}\b` e normalizando as keywords antes da comparação.

### Early-exit eficiente
Queries off-topic e violações de guardrail não chegam ao RAG retriever nem à LLM. O grafo LangGraph faz short-circuit direto para o `audit_logger`, economizando latência e custo de inferência.

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
  "sources_cited": ["PubMedQA/MedQuAD", "FHEMIG (Protocolos Clínicos)"],
  "has_disclaimer": true,
  "preprocess_id": "string | null",
  "duration_ms": 1234,
  "created_date": "ISO8601"
}
```
