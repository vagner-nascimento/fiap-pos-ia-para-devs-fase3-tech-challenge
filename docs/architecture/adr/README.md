# Índice de ADRs — FIAP POS IA Fase 3

**Architecture Decision Records** documentam as principais decisões técnicas tomadas no projeto, registrando o contexto, a decisão em si e suas consequências.

> **Template utilizado:** [MADR (Markdown ADR)](https://adr.github.io/madr/)

---

## ADRs

| # | Título | Status | Data |
|---|---|---|---|
| [ADR-001](ADR-001-modelo-base-qwen.md) | Escolha do modelo base Qwen2.5-1.5B-Instruct | ✅ Aceito | 2026-08-18 |
| [ADR-002](ADR-002-lora-peft-finetuning.md) | Uso de LoRA/PEFT para fine-tuning eficiente | ✅ Aceito | 2026-08-18 |
| [ADR-003](ADR-003-qlora-4bit-fallback-cpu.md) | QLoRA (quantização 4-bit) com fallback para CPU | ✅ Aceito | 2026-08-18 |
| [ADR-004](ADR-004-mongodb-estado.md) | MongoDB como banco de estado do processamento | ✅ Aceito | 2026-08-18 |
| [ADR-005](ADR-005-background-tasks-fastapi.md) | Processamento assíncrono via FastAPI BackgroundTasks | ✅ Aceito | 2026-08-18 |
| [ADR-006](ADR-006-finetuning-google-colab.md) | Fine-tuning executado no Google Colab | ✅ Aceito | 2026-08-18 |
| [ADR-007](ADR-007-split-train-rag.md) | Split train/RAG configurável via rag_percent (histórico) | ⚠️ Substituído | 2026-08-18 |
| [ADR-008](ADR-008-docker-compose.md) | Orquestração local via Docker Compose | ✅ Aceito | 2026-08-18 |
| [ADR-009](ADR-009-deteccao-gpu-cpu.md) | Detecção automática GPU/CPU no backend | ✅ Aceito | 2026-08-18 |
| [ADR-010](ADR-010-colab-ngrok-zerogpu.md) | Colab + ngrok e HuggingFace ZeroGPU para servir o modelo | ✅ Aceito | 2026-08-18 |
| [ADR-011](ADR-011-langgraph-medical-agent.md) | LangGraph como orquestrador do agente médico | ✅ Aceito | 2026-08-19 |
| [ADR-012](ADR-012-arquitetura-hibrida-inferencia-llm.md) | Arquitetura híbrida de inferência LLM (HF Spaces / ngrok) | ✅ Aceito | 2026-08-29 |
| [ADR-013](ADR-013-desacoplamento-guardrails-template-sft.md) | Desacoplamento de guardrails e preservação do template SFT | ✅ Aceito | 2026-08-29 |
| [ADR-014](ADR-014-skip-preprocess-translation.md) | Opção de pular a tradução no pré-processamento | ✅ Aceito | 2026-08-28 |
| [ADR-015](ADR-015-anonimizacao-laudos-lgpd.md) | Anonimização de laudos médicos antes da RAG | ✅ Aceito | 2026-09-03 |
| [ADR-016](ADR-016-metodologia-avaliacao-e-calibracao-decodificacao-llm.md) | Metodologia de avaliação empírica e calibração de decodificação LLM | ✅ Aceito | 2026-09-07 |
| [ADR-017](ADR-017-mongodb-saver-memoria-sessao-agente.md) | MongoDBSaver para memória de sessão do agente médico | ✅ Aceito | 2026-09-08 |
| [ADR-018](ADR-018-curadoria-rastreabilidade-datasets.md) | Curadoria automática versionada e rastreabilidade dos datasets | ✅ Aceito | 2026-09-10 |
| [ADR-019](ADR-019-compatibilizacao-instructor-embedding-rag.md) | Compatibilização do InstructorEmbedding com Sentence-Transformers modernos e alinhamento de dimensão vetorial no RAG | ✅ Aceito | 2026-09-13 |
| [ADR-020](ADR-020-jornada2-contexto-paciente-sumarizador.md) | Contextualização clínica estruturada por paciente (Jornada 2) e sumarizador para janela SFT de 3K tokens | ✅ Aceito | 2026-09-14 |

---

## Como adicionar um novo ADR

1. Crie um novo arquivo nesta pasta com o padrão: `ADR-NNN-titulo-kebab-case.md`
2. Use o template MADR abaixo:

```markdown
# ADR-NNN — Título

**Status:** Proposto | Aceito | Depreciado | Substituído por [ADR-NNN](...)
**Data:** YYYY-MM-DD
**Contexto:** Projeto / feature / área afetada
**Decisores:** Equipe / pessoa responsável

---

## Contexto

Descreva o problema, as restrições e o por que uma decisão é necessária.

## Decisão

Descreva a decisão tomada de forma clara e direta.

## Justificativa

Explique por que esta alternativa foi escolhida.

## Alternativas consideradas

| Alternativa | Razão para não escolher |
|---|---|
| ... | ... |

## Consequências

**Positivas:**
- ...

**Negativas:**
- ...

**Neutras:**
- ...
```

3. Adicione a entrada na tabela acima com o status inicial **Proposto**;
4. Atualize o status para **Aceito** após aprovação do time.

---

← [Voltar para Arquitetura](../README.md)
