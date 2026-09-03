# Gaps e Melhorias — Tech Challenge Fase 3

> Análise comparativa entre os **requisitos do edital** e o **estado atual do repositório**.
> Data de análise: 2026-09-03

---

## Resumo Executivo

O projeto está bem estruturado e atende à maioria dos requisitos do edital. A arquitetura modular (backend, agent, frontend, MongoDB), o pipeline LangGraph com 6 nós, os guardrails de segurança, o logging de auditoria e os notebooks de fine-tuning cobrem os pilares principais da entrega. No entanto, foram identificados **6 gaps críticos para a nota** e diversas melhorias que podem elevar a qualidade da apresentação.

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

---

### G02 — Avaliação do Modelo Fine-tunado sem métricas formais

**Requisito do edital:**
> "Avaliação do modelo e análise dos resultados."

**Situação atual:**
- Há um notebook `FIAP_PosTech_IA4Devs_Fase3_TechChallenge_TestesValidacoes.ipynb` (3.8 KB — muito pequeno, possivelmente incompleto).
- Não há no repositório principal nenhum arquivo com métricas de avaliação formais (BLEU, ROUGE, eval loss, perplexidade).
- A comparação "antes vs. depois do fine-tuning" não está documentada de forma acessível.

**Ação recomendada:**
- Expandir o notebook de validação com avaliação quantitativa no conjunto de teste;
- Exportar as métricas como artefato (ex.: `backend/datasets/evaluation/metrics.json` ou tabela no relatório técnico);
- Incluir 3–5 exemplos de respostas do modelo base versus o modelo fine-tunado sobre perguntas médicas reais.

---

### G03 — Diagrama do Fluxo LangChain/LangGraph ausente no formato visual

**Requisito do edital:**
> "Diagrama do fluxo LangChain."

**Situação atual:**
- O grafo LangGraph está documentado como diagrama ASCII no `docs/agent-walkthrough.md` e como diagramas Mermaid no `docs/architecture/README.md`.
- Os diagramas existentes são tecnicamente corretos, mas em formato textual (ASCII art + Mermaid).
- O edital sugere um diagrama visual mais formal, que possa ser exibido em apresentação/vídeo.

**Ação recomendada:** Adicionar uma imagem exportada (PNG/SVG) do diagrama LangGraph em `docs/architecture/` ou no relatório técnico para facilitar referência no vídeo e na entrega.

---

### G04 — Dataset anonimizado ou sintético não explicitado no repositório raiz

**Requisito do edital:**
> "Dataset anonimizado ou exemplo de dados sintéticos."

**Situação atual:**
- Os datasets PubMedQA e MedQuAD são datasets públicos (não requerem anonimização).
- Os protocolos FHEMIG/PCDT são documentos públicos.
- O script `generate_medical_reports.py` (58 KB) existe no `backend/datasets/`, mas não está claro se ele gera dados sintéticos ou é apenas para geração de relatórios para fine-tuning.
- **Não há na documentação do repositório raiz** uma referência clara a "dados sintéticos" ou à estratégia de anonimização aplicada.

**Ação recomendada:**
- Clarificar no README principal e no relatório técnico que PubMedQA/MedQuAD são datasets públicos já anonimizados por natureza;
- Documentar o papel do `generate_medical_reports.py` — se gera dados sintéticos, isso precisa ser explicitado como entregável;
- Adicionar uma seção "Dataset" no relatório técnico descrevendo fontes, volumes e estratégia de anonimização/curadoria.

---

### ~~G05~~ — ~~Fine-tuning executado via Colab sem integração demonstrável no repositório~~ ✅ Resolvido

**Situação atual:**
- O modelo está **público** no HuggingFace: [`fiap-hospital-helper/hospital-helper-qwen2.5-1.5b`](https://huggingface.co/fiap-hospital-helper/hospital-helper-qwen2.5-1.5b). ✅
- O `README.md` raiz agora possui link clicável e navegável para o modelo. ✅
- O `agent/.env.example` foi atualizado com as 3 opções de configuração (`LLM_API_TOKEN` documentado para cada modo). ✅
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

**Ação recomendada:**
- Implementar memória de sessão usando a coleção `agent_audit_logs` existente: ao receber uma query, recuperar as últimas N interações da mesma `session_id` e injetá-las como contexto adicional no prompt;
- Alternativamente, usar `LangGraph Checkpointer` (ex.: `MongoDBSaver`) para persistência nativa de estado entre invocações.

---

## 🟡 Melhorias Importantes (Qualidade, Robustez e Apresentação)

### M01 — Página de Chat com o Agente Médico ausente no Frontend

**Situação atual:**
- O frontend tem páginas para: Pré-processamento, Geração de RAG e Consulta RAG (`/rag-query`).
- **Não há uma página de chat** dedicada ao agente médico (`/agent/chat`).
- O endpoint `POST /agent/chat` existe no backend do agente (porta 8001), mas não está integrado à interface.

**Ação recomendada:**
- Criar `frontend/src/pages/AgentChatPage.tsx` com interface de chat (input de pergunta, exibição de resposta formatada com fontes e disclaimer, histórico de sessão);
- Adicionar rota `/chat` no `App.tsx` e link no layout de navegação.
- Esta é a funcionalidade mais visível para demonstração no vídeo.

---

### M02 — Página de Fine-tuning incompleta no Frontend

**Situação atual:**
- Existe `frontend/src/pages/FineTuningPage.css` (5.2 KB) mas **não há** `FineTuningPage.tsx` correspondente — a página está incompleta ou removida.

**Ação recomendada:**
- Criar o componente `FineTuningPage.tsx` que permita disparar e acompanhar o fine-tuning local via API (`POST /fine-tuning/start`, `GET /fine-tuning/{id}`);
- Adicionar à rota e ao menu de navegação.

---

### M03 — Guardrails baseados apenas em regex — ausência de validação semântica

**Situação atual:**
- O `topic_validator.py` e o `safety_guard.py` usam exclusivamente regex e listas de keywords.
- Regex pode ter falsos positivos (bloquear consultas legítimas) e falsos negativos (deixar passar consultas perigosas mal formuladas).

**Ação recomendada:**
- Adicionar como segunda camada de validação uma chamada leve à LLM para classificar a intenção da query (ex.: zero-shot: *"Esta query solicita prescrição direta? Responda sim/não."*);
- Documentar a decisão de usar regex por desempenho/latência (já existe ADR-013, expandir para mencionar a limitação conhecida).

---

### M04 — Ausência de testes de integração end-to-end

**Situação atual:**
- Os testes do `agent/` cobrem os nós individualmente com mocks.
- Os testes do `backend/` cobrem preprocessing, RAG e datasets.
- **Faltam** testes de integração que testem o fluxo completo: frontend → backend → agent → MongoDB.

**Ação recomendada:**
- Adicionar ao menos um teste de integração que suba o Docker Compose e execute um fluxo real de ponta a ponta;
- Ou adicionar testes de contrato de API (ex.: verificar que `/agent/chat` retorna o schema correto com dados reais).

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

---

### M06 — Explainability limitada a citação de fontes

**Requisito do edital:**
> "Garantir explainability das respostas da LLM (exemplo: indicar a fonte da informação utilizada)."

**Situação atual:**
- As fontes são indicadas no `response_formatter.py` via rodapé ou inline — requisito básico atendido. ✅
- **Faltam:** indicar qual trecho específico do documento RAG embasou a resposta e mostrar o score de similaridade ao usuário final.

**Ação recomendada:**
- Expor os `content_preview` e `similarity_score` dos documentos RAG na resposta da API (já existem nos dados) e exibi-los no frontend como "Fontes consultadas" expansíveis;
- Quando um guardrail é ativado, retornar o `safety_reason` em linguagem natural amigável.

---

### M07 — README principal incompleto

**Situação atual:**
- O `README.md` na raiz do projeto tem a seção **"## Como a aplicação funciona"** com título mas **sem conteúdo**.
- Não há um quickstart passo-a-passo para avaliadores.

**Ação recomendada:**
- Preencher a seção vazia com o fluxo end-to-end em linguagem simples;
- Adicionar uma seção "Quick Start para Avaliadores" com os 3–5 comandos mínimos para subir e testar o sistema;
- Adicionar link direto para o vídeo de demonstração e para o modelo no HuggingFace.

---

### M08 — Instrução de configuração do HF_TOKEN ausente no .env.example

**Situação atual:**
- O modelo `fiap-hospital-helper/hospital-helper-qwen2.5-1.5b` já está **público** no HuggingFace. ✅
- Porém, o `.env.example` do agente não documenta claramente para que serve o `HF_TOKEN` e quando ele é necessário (endpoint de inferência pago vs. Space ZeroGPU gratuito).

**Ação recomendada:**
- Adicionar comentários explicativos no `.env.example` do agente sobre quando o `HF_TOKEN` é obrigatório;
- Documentar no README a diferença entre rodar via HF Spaces ZeroGPU (gratuito, sem token) e via Inference API (requer token com créditos).

---

### M09 — Ausência de CI/CD pipeline

**Situação atual:**
- Não há arquivo `.github/workflows/` ou equivalente.
- Testes são executados manualmente.

**Ação recomendada (opcional para a nota, mas agrega valor):**
- Adicionar um workflow GitHub Actions que rode `pytest` nos módulos `agent/` e `backend/` a cada push;
- Adicionar verificação de lint (`ruff` ou `flake8`).

---

### M10 — Documentação dos notebooks de fine-tuning fragmentada

**Situação atual:**
- Os notebooks `v1, v2, v3, v4` e o notebook de runtime estão em `backend/src/notebooks/`, mas não há um `README.md` na pasta explicando a sequência de uso e o que cada versão faz.
- A referência no `README.md` raiz menciona os notebooks mas não distingue qual usar.

**Ação recomendada:**
- Criar `backend/src/notebooks/README.md` documentando qual notebook usar, em que ordem, diferenças entre as versões e como rodar no Colab;
- Marcar o notebook mais atual (v4) como canônico.

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
| Explainability básica (fontes citadas) | ✅ Atendido | `response_formatter.py` com rodapé de fontes |
| Disclaimer obrigatório | ✅ Atendido | Invariante em toda resposta (`requires_human_validation: True`) |
| Projeto modularizado em Python | ✅ Atendido | Módulos separados: `agent/`, `backend/`, com `pyproject.toml` |
| Dataset anonimizado / sintético | ⚠️ Parcial | Datasets públicos; curadoria não documentada explicitamente |
| Instruções no README | ⚠️ Parcial | README existe mas tem seção vazia; link do modelo agora corrigido |
| Modelo HuggingFace público | ✅ Atendido | Modelo público em `fiap-hospital-helper/hospital-helper-qwen2.5-1.5b` |
| Relatório técnico | ❌ Ausente | Arquitetura documentada, mas falta relatório narrativo com métricas do modelo |
| Avaliação do modelo | ❌ Ausente | Notebook de validação incompleto, sem métricas formais |
| Diagrama formal do fluxo | ⚠️ Parcial | Existe como ASCII art e Mermaid, mas não como imagem exportada |
| Frontend com chat do agente | ❌ Ausente | Endpoint existe na API, mas não há página de chat no frontend |

---

## 📋 Backlog Priorizado de Ações

| Prioridade | ID | Título | Esforço Estimado |
|---|---|---|---|
| 🔴 Alta | G01 | Criar relatório técnico detalhado | 4–6h |
| 🔴 Alta | G02 | Adicionar métricas de avaliação do modelo | 3–4h |
| 🔴 Alta | M01 | Criar página de Chat com o agente no Frontend | 4–6h |
| 🔴 Alta | G05 | ~~Documentar pipeline Colab + instruções do HF_TOKEN~~ | ~~0.5h~~ ✅ |
| 🟡 Média | G04 | Documentar estratégia de dataset/anonimização | 1–2h |
| 🟡 Média | G03 | Exportar diagrama LangGraph como imagem | 1h |
| 🟡 Média | M07 | Completar README raiz (seção vazia + quickstart) | 1–2h |
| 🟡 Média | M02 | Criar página de Fine-tuning no Frontend | 3–4h |
| 🟡 Média | G06 | Implementar memória de sessão no agente | 3–5h |
| 🟡 Média | M10 | Criar README nos notebooks de fine-tuning | 1h |
| 🟢 Baixa | M06 | Enriquecer explainability com scores RAG no frontend | 2–3h |
| 🟢 Baixa | M03 | Adicionar validação semântica nos guardrails | 3–4h |
| 🟢 Baixa | M04 | Testes de integração end-to-end | 4–6h |
| 🟢 Baixa | M05 | Documentar curadoria dos dados | 1h |
| 🟢 Baixa | M08 | Documentar HF_TOKEN no .env.example | 0.5h |
| 🟢 Baixa | M09 | Adicionar CI/CD com GitHub Actions | 2–3h |
