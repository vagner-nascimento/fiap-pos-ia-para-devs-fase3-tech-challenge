# Gaps e Melhorias — Tech Challenge Fase 3

> Análise comparativa entre os **requisitos do edital** e o **estado atual do repositório**.
> Data de análise: 2026-09-03 | **Revisão: 2026-09-04** (issues sincronizados às 08:26 BRT)

---

## Resumo Executivo

O projeto está bem estruturado e atende à maioria dos requisitos do edital. Desde a análise anterior (2026-09-03), **5 gaps foram totalmente resolvidos** (M01, M02, M06, M07, M08, G04) e os issues do GitHub foram sincronizados para refletir o estado atual.

A arquitetura modular (backend, agent, frontend, MongoDB), o pipeline LangGraph com 6 nós, os guardrails de segurança, o logging de auditoria e os notebooks de fine-tuning cobrem os pilares principais da entrega. Permanecem **3 gaps críticos** (G01, G02, G03) e melhorias que podem elevar a qualidade da apresentação final.

---

## 🔴 Gaps Críticos (Requisitos do Edital Não Atendidos ou Parcialmente Atendidos)

### G01 — Relatório Técnico Detalhado ausente

**Requisito do edital:**
> "Relatório técnico detalhado com: explicação do processo de fine-tuning; descrição do assistente médico criado; diagrama do fluxo LangChain; avaliação do modelo e análise dos resultados."

**Situação atual:**
- `docs/architecture/README.md`: contém arquitetura técnica (C4, ADRs, diagramas de sequência). ✅
- `docs/agent-walkthrough.md`: walkthrough de implementação do agente. ✅
- **Faltam:** um relatório técnico consolidado e voltado à entrega acadêmica que contenha:
  - Explicação narrativa do processo de fine-tuning (decisões, hiperparâmetros, curvas de loss);
  - Avaliação quantitativa do modelo (métricas como BLEU, ROUGE, perplexidade ou avaliação qualitativa por amostra);
  - Análise dos resultados (o modelo melhorou? Em quê? Exemplos concretos de pergunta/resposta antes e depois do fine-tuning).

**Ação recomendada:** Criar `docs/relatorio-tecnico.md` consolidando os pontos acima de forma narrativa, com exemplos de I/O do modelo e métricas de avaliação extraídas dos notebooks.

**Issue GitHub:** [#32 [G01] Relatório técnico detalhado](https://github.com/vagner-nascimento/fiap-pos-ia-para-devs-fase3-tech-challenge/issues/32) — **aberto**

---

### G02 — Avaliação do Modelo Fine-tunado sem métricas formais

**Requisito do edital:**
> "Avaliação do modelo e análise dos resultados."

**Situação atual:**
- Há um notebook `FIAP_PosTech_IA4Devs_Fase3_TechChallenge_TestesValidacoes.ipynb` (**3.8 KB — muito pequeno, possivelmente incompleto**).
- Não há no repositório principal nenhum arquivo com métricas de avaliação formais (BLEU, ROUGE, eval loss, perplexidade).
- A comparação "antes vs. depois do fine-tuning" não está documentada de forma acessível.

**Ação recomendada:**
- Expandir o notebook de validação com avaliação quantitativa no conjunto de teste;
- Exportar as métricas como artefato (ex.: `backend/datasets/evaluation/metrics.json` ou tabela no relatório técnico);
- Incluir 3–5 exemplos de respostas do modelo base versus o modelo fine-tunado sobre perguntas médicas reais.

**Issue GitHub:** [#33 [G02] Avaliação do modelo fine-tunado](https://github.com/vagner-nascimento/fiap-pos-ia-para-devs-fase3-tech-challenge/issues/33) — **aberto**

---

### G03 — Diagrama do Fluxo LangChain/LangGraph ausente no formato visual

**Requisito do edital:**
> "Diagrama do fluxo LangChain."

**Situação atual:**
- O grafo LangGraph está documentado como diagrama ASCII no `docs/agent-walkthrough.md` e como diagramas Mermaid no `docs/architecture/README.md`.
- Os diagramas existentes são tecnicamente corretos, mas em formato textual (ASCII art + Mermaid).
- O edital sugere um diagrama visual mais formal, que possa ser exibido em apresentação/vídeo.

**Ação recomendada:** Adicionar uma imagem exportada (PNG/SVG) do diagrama LangGraph em `docs/architecture/` ou no relatório técnico para facilitar referência no vídeo e na entrega.

**Issue GitHub:** [#34 [G03] Diagrama LangGraph ausente como imagem](https://github.com/vagner-nascimento/fiap-pos-ia-para-devs-fase3-tech-challenge/issues/34) — **aberto**

---

### ~~G04~~ — ~~Dataset anonimizado ou sintético não explicitado no repositório raiz~~ ✅ Resolvido

**Situação atual (fechado no GitHub em 2026-09-04):**
- Os datasets PubMedQA e MedQuAD são datasets públicos já anonimizados por natureza. ✅
- O papel do `generate_medical_reports.py` foi documentado. ✅
- Issue #35 foi fechado pela equipe.

**Pendente ainda:** Incluir seção "Dataset" no relatório técnico (G01) descrevendo fontes, volumes e estratégia de curadoria.

**Issue GitHub:** [#35 [G04] Estratégia de dataset/anonimização](https://github.com/vagner-nascimento/fiap-pos-ia-para-devs-fase3-tech-challenge/issues/35) — **fechado** ✅

---

### ~~G05~~ — ~~Fine-tuning executado via Colab sem integração demonstrável no repositório~~ ✅ Resolvido

**Situação atual:**
- O modelo está **público** no HuggingFace: [`fiap-hospital-helper/hospital-helper-qwen2.5-1.5b`](https://huggingface.co/fiap-hospital-helper/hospital-helper-qwen2.5-1.5b). ✅
- O `README.md` raiz possui link clicável e navegável para o modelo. ✅
- O `agent/.env.example` documenta claramente as 3 opções de configuração (`LLM_API_TOKEN` documentado para cada modo). ✅
- Os notebooks de fine-tuning estão em `backend/src/notebooks/` (v1 a v4 + RuntimeModelo).

**Pendente ainda:**
- Documentar no relatório técnico (G01) o link direto para os notebooks do Colab e o link do modelo.

---

### G06 — Agente stateless — sem memória de conversa por sessão

**Requisito do edital:**
> "Contextualizar as respostas da LLM com informações atualizadas do paciente."

**Situação atual:**
- O `session_id` é registrado nos logs de auditoria, mas **não há memória de conversa** — cada chamada ao `/agent/chat` é stateless.
- O agente não "lembra" de interações anteriores da sessão, o que limita a capacidade de contextualizar respostas com o histórico clínico do paciente.
- Verificado em `medical_agent.py`: `initial_state` é criado do zero a cada invocação sem recuperar histórico do MongoDB.

**Ação recomendada:**
- Implementar memória de sessão usando a coleção `agent_audit_logs` existente: ao receber uma query, recuperar as últimas N interações da mesma `session_id` e injetá-las como contexto adicional no prompt;
- Alternativamente, usar `LangGraph Checkpointer` (ex.: `MongoDBSaver`) para persistência nativa de estado entre invocações.

**Issue GitHub:** [#36 [G06] Agente stateless — sem memória de sessão](https://github.com/vagner-nascimento/fiap-pos-ia-para-devs-fase3-tech-challenge/issues/36) — **aberto**

---

## 🟡 Melhorias Importantes (Qualidade, Robustez e Apresentação)

### ~~M01~~ — ~~Página de Chat com o Agente Médico ausente no Frontend~~ ✅ Resolvido

**Situação atual (atualizada em 2026-09-04):**
- `frontend/src/pages/AgentPage.tsx` implementado com interface de chat completa. ✅
- Integrado ao `App.tsx` como view `"agent"` (view padrão ao abrir o frontend). ✅
- Exibe resposta do assistente, fontes consultadas expansíveis com score de similaridade e preview de conteúdo, alerta de segurança quando guardrail é ativado. ✅
- README documenta a tela e os passos para uso. ✅

**Issue GitHub:** [#37 [M01] Página de chat com o agente](https://github.com/vagner-nascimento/fiap-pos-ia-para-devs-fase3-tech-challenge/issues/37) — **deve ser fechado**

---

### ~~M02~~ — ~~Página de Fine-tuning incompleta no Frontend~~ ✅ Resolvido

**Situação atual (fechado no GitHub em 2026-09-04):**
- Issue #38 foi fechado pela equipe.

**Issue GitHub:** [#38 [M02] Página de fine-tuning no frontend](https://github.com/vagner-nascimento/fiap-pos-ia-para-devs-fase3-tech-challenge/issues/38) — **fechado** ✅

---

### M03 — Guardrails baseados apenas em regex — ausência de validação semântica

**Situação atual:**
- O `topic_validator.py` e o `safety_guard.py` usam exclusivamente regex e listas de keywords.
- Regex pode ter falsos positivos (bloquear consultas legítimas) e falsos negativos (deixar passar consultas perigosas mal formuladas).

**Ação recomendada:**
- Adicionar como segunda camada de validação uma chamada leve à LLM para classificar a intenção da query (ex.: zero-shot: *"Esta query solicita prescrição direta? Responda sim/não."*);
- Documentar a decisão de usar regex por desempenho/latência (já existe ADR-013, expandir para mencionar a limitação conhecida).

**Issue GitHub:** [#42 [M03] Guardrails baseados apenas em regex](https://github.com/vagner-nascimento/fiap-pos-ia-para-devs-fase3-tech-challenge/issues/42) — **aberto**

---

### M04 — Ausência de testes de integração end-to-end

**Situação atual:**
- Os testes do `agent/` cobrem os nós individualmente com mocks.
- Os testes do `backend/` cobrem preprocessing, RAG e datasets.
- **Faltam** testes de integração que testem o fluxo completo: frontend → backend → agent → MongoDB.

**Ação recomendada:**
- Adicionar ao menos um teste de integração que suba o Docker Compose e execute um fluxo real de ponta a ponta;
- Ou adicionar testes de contrato de API (ex.: verificar que `/agent/chat` retorna o schema correto com dados reais).

**Issue GitHub:** [#43 [M04] Ausência de testes de integração](https://github.com/vagner-nascimento/fiap-pos-ia-para-devs-fase3-tech-challenge/issues/43) — **aberto**

---

### M05 — Curadoria dos dados não documentada

**Requisito do edital:**
> "Preparar os dados com técnicas de preprocessing, anonimização e **curadoria**."

**Situação atual:**
- O preprocessing automático (limpeza, chunking, tradução) está bem implementado.
- **Curadoria** implica revisão da qualidade das amostras — não há evidência documentada de critérios de aceite/rejeição.

**Ação recomendada:**
- Documentar no relatório técnico os critérios de curadoria aplicados (mínimo de caracteres por QA, filtragem de respostas vazias, validação manual de amostras);
- Incluir estatísticas: quantos registros foram descartados e por quê.

**Issue GitHub:** [#44 [M05] Curadoria dos dados não documentada](https://github.com/vagner-nascimento/fiap-pos-ia-para-devs-fase3-tech-challenge/issues/44) — **aberto**

---

### ~~M06~~ — ~~Explainability limitada a citação de fontes~~ ✅ Resolvido

**Requisito do edital:**
> "Garantir explainability das respostas da LLM (exemplo: indicar a fonte da informação utilizada)."

**Situação atual (fechado no GitHub em 2026-09-04):**
- As fontes são indicadas no `response_formatter.py` via rodapé ou inline. ✅
- A `AgentPage.tsx` exibe `content_preview` e `similarity_score` como "Fontes consultadas" expansíveis por `<details>`. ✅
- Quando um guardrail é ativado, o `safety_reason` é exibido em linguagem natural no frontend. ✅
- Issue #41 foi fechado pela equipe.

**Issue GitHub:** [#41 [M06] Explainability limitada a citação de fontes](https://github.com/vagner-nascimento/fiap-pos-ia-para-devs-fase3-tech-challenge/issues/41) — **fechado** ✅

---

### ~~M07~~ — ~~README principal incompleto~~ ✅ Resolvido

**Situação atual (atualizada em 2026-09-04):**
- A seção `"Como a aplicação funciona"` está preenchida com o fluxo completo em 5 etapas. ✅
- Adicionada seção `"Quick Start para Avaliadores"` com os 4 comandos mínimos para subir e testar. ✅
- Adicionada seção `"Tela do Assistente Médico"` com instruções de uso. ✅
- Link direto para o modelo no HuggingFace presente. ✅

**Issue GitHub:** [#39 [M07] README raiz incompleto](https://github.com/vagner-nascimento/fiap-pos-ia-para-devs-fase3-tech-challenge/issues/39) — **deve ser fechado**

---

### ~~M08~~ — ~~Instrução de configuração do HF_TOKEN ausente no .env.example~~ ✅ Resolvido

**Situação atual (atualizada em 2026-09-04):**
- O `agent/.env.example` documenta os 3 modos de uso com comentários explicativos claros:
  - Opção 1 — HF Spaces ZeroGPU (gratuito, sem token);
  - Opção 2 — Colab/ngrok (sem token);
  - Opção 3 — HuggingFace Inference API (requer token com créditos).
- O README raiz menciona as opções de endpoint. ✅

**Issue GitHub:** [#45 [M08] HF_TOKEN e modos de inferência](https://github.com/vagner-nascimento/fiap-pos-ia-para-devs-fase3-tech-challenge/issues/45) — **deve ser fechado**

---

### M09 — Ausência de CI/CD pipeline

**Situação atual:**
- Não há arquivo `.github/workflows/` ou equivalente (diretório `.github/` inexistente).
- Testes são executados manualmente.

**Ação recomendada (opcional para a nota, mas agrega valor):**
- Adicionar um workflow GitHub Actions que rode `pytest` nos módulos `agent/` e `backend/` a cada push;
- Adicionar verificação de lint (`ruff` ou `flake8`).

**Issue GitHub:** [#46 [M09] Ausência de CI/CD pipeline](https://github.com/vagner-nascimento/fiap-pos-ia-para-devs-fase3-tech-challenge/issues/46) — **aberto**

---

### M10 — Documentação dos notebooks de fine-tuning fragmentada

**Situação atual:**
- Os notebooks `v1, v2, v3, v4` e o notebook de runtime estão em `backend/src/notebooks/`, mas **não há um `README.md`** na pasta explicando a sequência de uso e o que cada versão faz.
- A referência no `README.md` raiz menciona os notebooks mas não distingue qual usar.

**Ação recomendada:**
- Criar `backend/src/notebooks/README.md` documentando qual notebook usar, em que ordem, diferenças entre as versões e como rodar no Colab;
- Marcar o notebook mais atual (v4) como canônico.

**Issue GitHub:** [#40 [M10] Documentação dos notebooks](https://github.com/vagner-nascimento/fiap-pos-ia-para-devs-fase3-tech-challenge/issues/40) — **aberto**

---

## 🟢 Pontos Positivos (Edital bem atendido)

| Requisito do Edital | Status | Evidência |
|---|---|---|
| Fine-tuning de LLM com dados médicos | ✅ Atendido | Notebooks v1–v4, `fine_tunning.py`, modelo no HF |
| Uso de LangChain/LangGraph | ✅ Atendido | `medical_agent.py`, StateGraph com 6 nós |
| Pipeline integrado com LLM customizada | ✅ Atendido | `llm_client.py` com suporte a HF Space e FastAPI |
| Consultas à base RAG | ✅ Atendido | `rag_retriever.py`, `rag_database.py`, busca híbrida |
| Limites de atuação (sem prescrição direta) | ✅ Atendido | `safety_guard.py`, `topic_validator.py` |
| Logging detalhado para auditoria | ✅ Atendido | `audit_logger.py`, collection MongoDB `agent_audit_logs` |
| Explainability (fontes + scores RAG) | ✅ Atendido | `response_formatter.py` + `AgentPage.tsx` com fontes expansíveis e similarity_score |
| Disclaimer obrigatório | ✅ Atendido | Invariante em toda resposta (`requires_human_validation: True`) |
| Projeto modularizado em Python | ✅ Atendido | Módulos separados: `agent/`, `backend/`, com `pyproject.toml` |
| Frontend com chat do agente | ✅ Atendido | `AgentPage.tsx` integrado, view padrão ao abrir o app |
| Instruções no README | ✅ Atendido | README completo com fluxo, Quick Start e seção do assistente |
| Modelo HuggingFace público | ✅ Atendido | Modelo público em `fiap-hospital-helper/hospital-helper-qwen2.5-1.5b` |
| HF_TOKEN documentado | ✅ Atendido | `agent/.env.example` com 3 modos documentados |
| Dataset anonimizado / sintético | ⚠️ Parcial | Datasets públicos; curadoria não documentada explicitamente |
| Relatório técnico | ❌ Ausente | Arquitetura documentada, mas falta relatório narrativo com métricas do modelo |
| Avaliação do modelo | ❌ Ausente | Notebook de validação incompleto (3.8 KB), sem métricas formais |
| Diagrama formal do fluxo | ⚠️ Parcial | Existe como ASCII art e Mermaid, mas não como imagem exportada |

---

## 📋 Backlog Priorizado de Ações

| Prioridade | ID | Título | Esforço Estimado | Status |
|---|---|---|---|---|
| 🔴 Alta | G01 | Criar relatório técnico detalhado | 4–6h | ⏳ Pendente (#32) |
| 🔴 Alta | G02 | Adicionar métricas de avaliação do modelo | 3–4h | ⏳ Pendente (#33) |
| ~~🔴 Alta~~ | ~~M01~~ | ~~Criar página de Chat com o agente no Frontend~~ | ~~4–6h~~ | ✅ Resolvido (#37) |
| ~~🔴 Alta~~ | ~~G05~~ | ~~Documentar pipeline Colab + instruções do HF_TOKEN~~ | ~~0.5h~~ | ✅ Resolvido |
| ~~🟡 Média~~ | ~~G04~~ | ~~Documentar estratégia de dataset/anonimização~~ | ~~1–2h~~ | ✅ Resolvido (#35) |
| 🟡 Média | G03 | Exportar diagrama LangGraph como imagem | 1h | ⏳ Pendente (#34) |
| ~~🟡 Média~~ | ~~M07~~ | ~~Completar README raiz (seção vazia + quickstart)~~ | ~~1–2h~~ | ✅ Resolvido (#39) |
| ~~🟡 Média~~ | ~~M02~~ | ~~Criar página de Fine-tuning no Frontend~~ | ~~3–4h~~ | ✅ Resolvido (#38) |
| 🟡 Média | G06 | Implementar memória de sessão no agente | 3–5h | ⏳ Pendente (#36) |
| 🟡 Média | M10 | Criar README nos notebooks de fine-tuning | 1h | ⏳ Pendente (#40) |
| ~~🟢 Baixa~~ | ~~M06~~ | ~~Enriquecer explainability com scores RAG no frontend~~ | ~~2–3h~~ | ✅ Resolvido (#41) |
| 🟢 Baixa | M03 | Adicionar validação semântica nos guardrails | 3–4h | ⏳ Pendente (#42) |
| 🟢 Baixa | M04 | Testes de integração end-to-end | 4–6h | ⏳ Pendente (#43) |
| 🟢 Baixa | M05 | Documentar curadoria dos dados | 1h | ⏳ Pendente (#44) |
| ~~🟢 Baixa~~ | ~~M08~~ | ~~Documentar HF_TOKEN no .env.example~~ | ~~0.5h~~ | ✅ Resolvido (#45) |
| 🟢 Baixa | M09 | Adicionar CI/CD com GitHub Actions | 2–3h | ⏳ Pendente (#46) |

---

## 🔄 Issues do GitHub — Status de Sincronização

> Sincronizado em: 2026-09-04 às 08:26 BRT

| Issue | Título | Estado no GitHub |
|---|---|---|
| #32 | [G01] Relatório técnico detalhado | 🔴 Aberto |
| #33 | [G02] Avaliação do modelo fine-tunado | 🔴 Aberto |
| #34 | [G03] Diagrama LangGraph como imagem | 🔴 Aberto |
| #35 | [G04] Estratégia de dataset/anonimização | ✅ Fechado |
| #36 | [G06] Agente stateless — sem memória | 🔴 Aberto |
| #37 | [M01] Página de chat no frontend | ✅ Fechado |
| #38 | [M02] Página de fine-tuning no frontend | ✅ Fechado |
| #39 | [M07] README raiz incompleto | ✅ Fechado |
| #40 | [M10] Documentação dos notebooks | 🔴 Aberto |
| #41 | [M06] Explainability limitada | ✅ Fechado |
| #42 | [M03] Guardrails apenas regex | 🔴 Aberto |
| #43 | [M04] Testes de integração | 🔴 Aberto |
| #44 | [M05] Curadoria não documentada | 🔴 Aberto |
| #45 | [M08] HF_TOKEN no .env.example | ✅ Fechado |
| #46 | [M09] Ausência de CI/CD | 🔴 Aberto |
