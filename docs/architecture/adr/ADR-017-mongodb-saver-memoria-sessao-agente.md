# ADR-017 — MongoDBSaver para memória de sessão do agente médico

**Status:** Aceito  
**Data:** 2026-09-08  
**Contexto:** Projeto FIAP POS IA Fase 3 — Persistência de estado conversacional do agente médico  
**Decisores:** Equipe do projeto  

---

## Contexto

O endpoint `/agent/chat` já recebia e registrava um `session_id` nos logs de auditoria, mas cada execução do agente criava um estado LangGraph novo. Assim, chamadas posteriores da mesma sessão não recuperavam o estado de interações anteriores.

O requisito do edital solicita contextualizar as respostas com informações atualizadas do paciente. O agente já possui RAG e auditoria, porém precisava de persistência nativa do estado do grafo entre invocações e reinícios do processo.

A coleção `agent_audit_logs` é destinada à auditoria e contém documentos com formato próprio. Ela não deve ser usada como armazenamento de checkpoints do LangGraph.

## Decisão

Adicionar a dependência `langgraph-checkpoint-mongodb` e compilar o `StateGraph` do agente médico com um `MongoDBSaver` síncrono.

A integração:

- reutiliza o `MongoClient` singleton já existente na infraestrutura do agente;
- usa `DB_NAME` para selecionar o banco MongoDB;
- mantém o saver em singleton durante o processo;
- armazena checkpoints nas collections `agent_checkpoints` e `agent_checkpoint_writes`;
- usa o `session_id` recebido pela API como `configurable.thread_id`;
- usa o namespace estável `medical_agent` para os checkpoints do grafo;
- mantém `agent_audit_logs` separado para auditoria de cada interação.

A dependência é limitada à série `0.4.x` (`>=0.4.0,<0.5.0`) para preservar o suporte declarado a Python `>=3.10`.

## Justificativa

O `MongoDBSaver` é a implementação nativa do contrato de checkpointer do LangGraph e permite recuperar o estado por thread sem criar uma camada paralela de histórico textual. O uso do mesmo `session_id` como `thread_id` preserva a identidade de sessão já exposta pela API e evita a introdução de outro identificador.

A separação das collections evita misturar o schema operacional do LangGraph com o schema de compliance dos logs. O MongoDB já é uma dependência obrigatória dos serviços e possui volume persistente no Docker Compose, reduzindo a infraestrutura adicional necessária.

## Alternativas consideradas

| Alternativa | Razão para não escolher |
|---|---|
| Consultar `agent_audit_logs` e montar histórico manual no prompt | Duplica estado, exige serialização própria e acopla memória conversacional ao schema de auditoria. |
| `MemorySaver` em memória do processo | Perde o histórico em reinícios e não funciona de forma consistente entre réplicas. |
| Redis ou outro armazenamento adicional | Introduz outro serviço persistente sem necessidade, já que MongoDB está disponível. |
| Criar um histórico textual separado | Não preserva o estado completo do grafo e exige definir manualmente quais campos entram no prompt. |

## Consequências

**Positivas:**

- Interações da mesma sessão reutilizam o thread persistido pelo LangGraph;
- o estado pode sobreviver ao reinício do processo enquanto o volume MongoDB existir;
- o `session_id` continua sendo a identidade pública e auditável da conversa;
- auditoria e checkpoints possuem responsabilidades e collections distintas;
- o saver singleton evita criar conexões e índices a cada requisição.

**Negativas:**

- O estado persistido pode conter query, contexto RAG e resposta clínica, exigindo controles de acesso, retenção e descarte compatíveis com dados de saúde;
- cada execução grava checkpoints adicionais e aumenta o armazenamento no MongoDB;
- a disponibilidade do MongoDB passa a ser necessária para inicializar e executar o grafo com persistência;
- mudanças incompatíveis no schema do `AgentState` podem exigir estratégia de versionamento ou limpeza dos checkpoints.

**Neutras:**

- O `audit_logger` continua registrando uma auditoria por interação, independentemente do checkpoint;
- os testes unitários usam um checkpointer em memória ou desabilitado para não depender de MongoDB real.

## Verificação

- Confirmar `uv lock --check` e a resolução de `langgraph-checkpoint-mongodb` na série compatível com Python 3.10;
- testar que o grafo é compilado com `checkpointer` e que cada chamada envia `configurable.thread_id=session_id`;
- executar duas chamadas com o mesmo `session_id` e confirmar o mesmo thread no MongoDB;
- executar chamadas com `session_id` diferentes e confirmar o isolamento dos checkpoints;
- verificar que os checkpoints usam `agent_checkpoints`/`agent_checkpoint_writes` e não `agent_audit_logs`.

## Referências

- [ADR-004](ADR-004-mongodb-estado.md) — MongoDB como banco de estado do processamento
- [ADR-011](ADR-011-langgraph-medical-agent.md) — LangGraph como orquestrador do agente médico
- [agent/src/infra/database/checkpointer.py](../../../agent/src/infra/database/checkpointer.py) — criação do `MongoDBSaver`
- [agent/src/services/medical_agent.py](../../../agent/src/services/medical_agent.py) — compilação e invocação do grafo
