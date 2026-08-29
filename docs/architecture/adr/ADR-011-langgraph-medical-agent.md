# ADR-011 — LangGraph como Orquestrador do Agente Médico

**Status:** Aceito  
**Data:** 2026-08-19  
**Contexto:** Projeto FIAP POS IA Fase 3 — Issue #20: Criação de Agente Médico com LangChain  
**Decisores:** Equipe do projeto  

---

## Contexto

O projeto necessita de um assistente médico inteligente que:
- Integre a LLM customizada (Qwen2.5 fine-tunado) com contexto RAG
- Implemente múltiplas camadas de validação e segurança antes de chamar a LLM
- Garanta auditabilidade completa de todas as interações
- Suporte early-exit quando guardrails de segurança são ativados (sem chamar a LLM desnecessariamente)

As opções consideradas foram: LangChain simples (LLMChain/RetrievalQA), LangChain com Agents (ReAct), e LangGraph.

## Decisão

Utilizamos **LangGraph** (`langgraph>=0.1.0`) para orquestrar o pipeline do agente médico como um `StateGraph` compilado com 6 nós.

## Justificativa

| Critério | LLMChain | ReAct Agent | **LangGraph** |
|---|---|---|---|
| Controle de fluxo explícito | ❌ Linear | ⚠️ Loop interno | ✅ Grafo dirigido |
| Early-exit em guardrails | ❌ Não suportado | ❌ Complexo | ✅ Roteamento condicional |
| Estado tipado entre nós | ❌ Dict genérico | ❌ Dict genérico | ✅ TypedDict |
| Testabilidade por nó | ⚠️ Limitada | ❌ Difícil | ✅ Cada nó é função pura |
| Auditoria por etapa | ❌ Requer wrappers | ❌ Requer wrappers | ✅ Estado compartilhado |
| Visualização do fluxo | ❌ | ❌ | ✅ Grafo visualizável |

O LangGraph permite definir **roteamento condicional** explícito: quando o validador de tópico ou o guardrail de segurança detecta uma violação, o grafo faz early-exit direto para o `audit_logger`, **sem invocar a LLM ou o RAG retriever**. Isso reduz latência, custo e risco de vazamento de informação.

## Arquitetura do Grafo

```
[START] → init → topic_validator
                      │
              ┌───────┴────────┐
         (inválido)        (válido)
              │                │
              ▼                ▼
         audit_logger    safety_guard
                              │
                     ┌────────┴──────────┐
                (violação)           (seguro)
                     │                   │
                     ▼                   ▼
               audit_logger       rag_retriever
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

## Padrão de Segurança Adotado

### Camada 1: Validação de Tópico
- Heurística de keywords médicas (PT/EN)
- Padrões contextuais com regex
- Sem custo de LLM

### Camada 2: Guardrails de Segurança (lista negra)
- Regex patterns para prescrição com dose
- Regex patterns para diagnóstico definitivo
- Regex patterns para substituição de médico

### Camada 3: System Prompt de Segurança
- Instruções explícitas de limite de atuação na LLM
- Obrigatoriedade de citar fontes inline

### Camada 4: Response Formatter
- Disclaimer obrigatório em toda resposta
- `requires_human_validation: true` invariante no contrato de API

## Consequências

### Positivas
- Pipeline completamente auditável (todos os campos persistidos no MongoDB)
- Early-exit eficiente: LLM não é invocada para perguntas inválidas
- Cada nó é uma função pura testável isoladamente
- Extensível: novos nós podem ser adicionados sem reescrever o pipeline

### Negativas
- LangGraph adiciona dependência adicional ao projeto
- A compilação do grafo (`graph.compile()`) adiciona ~100ms no primeiro request (singleton mitiga nos seguintes)
- Maior complexidade de setup inicial comparado a uma simples LLMChain

## Alternativas Rejeitadas

- **LLMChain simples**: Sem suporte a early-exit; toda query passaria pela LLM mesmo sendo inválida. Auditoria requereria wrappers adicionais.
- **ReAct Agent**: Loop interno do agente dificulta controle preciso do fluxo e torna os testes de guardrails mais complexos.

## Referências

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [ADR-004](ADR-004-mongodb-estado.md) — MongoDB como banco de estado (base para audit_logs)
- [ADR-007](ADR-007-split-train-rag.md) — Split train/RAG (base de conhecimento do agente)
- [ADR-010](ADR-010-colab-ngrok-zerogpu.md) — Endpoint LLM via ngrok/ZeroGPU
