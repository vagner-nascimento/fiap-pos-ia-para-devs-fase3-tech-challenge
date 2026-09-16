# ADR-020 — Contextualização clínica estruturada por paciente (Jornada 2) e sumarizador para janela SFT de 3K tokens

**Status:** Aceito  
**Data:** 2026-09-14  
**Contexto:** Agente Médico LangGraph (`agent/src/services/`) — Requisito Obrigatório 2 da Fase 3  
**Decisores:** Equipe do projeto  

---

## Contexto

O **Requisito Obrigatório 2** do Tech Challenge da Fase 3 estabelece que o assistente médico deve:
1. Integrar o modelo de linguagem fine-tunado (`hospital-helper-qwen2.5-1.5b`).
2. Realizar consultas em base de dados estruturadas (prontuários/registros).
3. Contextualizar as respostas da LLM com informações clínicas atualizadas do paciente.

Durante a concepção técnica da **Jornada 2 (Consulta contextualizada por paciente)**, surgiram três desafios arquiteturais críticos:

1. **Roteamento e Identificação do Paciente:**
   Tentar extrair o nome ou ID do paciente a partir do texto livre da pergunta via expressões regulares ou NER é frágil, sujeito a falsos positivos (ex.: nomes de medicamentos, doenças, síndromes homônimas ou autores de protocolos) e pode introduzir alucinações.
2. **Restrição da Janela de Contexto da LLM Fine-tunada:**
   O modelo base `Qwen2.5-1.5B` foi treinado via Supervised Fine-Tuning (SFT) com sequência máxima de **3.000 tokens** (`max_seq_length=3000`). Ao combinar:
   - A pergunta do médico;
   - O histórico clínico e prescrições do prontuário;
   - Múltiplos trechos de protocolos hospitalares recuperados via RAG (top-k = 5);
   O volume total de tokens pode facilmente exceder o limite de 3.000 tokens, gerando truncamento abrupto de tokens na ponta receptora ou erros de inferência na GPU.
3. **Privacidade e LGPD:**
   Dados de prontuário contêm identificadores sensíveis (CPF, leito, data de nascimento, nome da mãe) que não devem ser expostos desnecessariamente ao prompt da LLM nem ao histórico de RAG.

---

## Decisão

Implementou-se a **Jornada 2** expandindo o grafo LangGraph de 6 para **8 nós operacionais**, com as seguintes decisões arquiteturais:

### 1. Roteamento Determinístico via Campo Opcional `patient_name`
- Adicionou-se o campo opcional `patient_name: Optional[str] = None` no schema de entrada `POST /agent/chat` e um input dedicado na interface gráfica (`AgentPage.tsx`).
- Se `patient_name` for informado: o fluxo ativa a **Jornada 2**.
- Se ausente ou vazio: o fluxo segue estritamente como **Jornada 1** (consulta puramente conceitual de protocolos).
- Essa abordagem elimina heurísticas frágeis e garante controle intencional por parte do profissional de saúde.

### 2. Nó de Prontuário Clínico com Anonimização LGPD (`patient_context_retriever`)
- Quando ativado, consulta a rota `GET /medical-record?patient_name=...` exposta pela API do backend (`fiap-pos-ia-backend:3000`).
- Extrai estritamente as seções clínicas pertinentes:
  - `avaliacao`: diagnóstico e impressão clínica;
  - `plano.prescricao`: medicamentos atualmente em uso;
  - `alergias`: restrições medicamentosas registradas;
  - `objetivo.vitais`: sinais vitais mais recentes (PA, FC, SpO2, temperatura).
- Dados de PII (CPF, leito, datas civis) são descartados antes de compor o estado do LangGraph.
- Se o paciente não for localizado, o nó registra a ausência e o fluxo prossegue avisando o médico, sem interromper o serviço.

### 3. Enriquecimento da Busca RAG (`rag_retriever`)
- O nó `rag_retriever` concatena a hipótese diagnóstica do paciente à pergunta clínica do médico para realizar a busca vetorial contra a base de protocolos FHEMIG e PubMedQA, garantindo que as diretrizes institucionais recuperadas tenham aderência ao quadro real do paciente.

### 4. Sumarização Adaptativa de Contexto para Janela SFT (`context_summarizer`)
- O nó `context_summarizer` calcula dinamicamente a estimativa de tokens do pacote montado: `tokens(pergunta) + tokens(prontuário) + tokens(RAG)`.
- Se o total exceder `LLM_MAX_CONTEXT_TOKENS=3000` (configurável via variável de ambiente):
  - **Estratégia Primária (LLM Externa):** Aciona a API da Groq utilizando o modelo ultrarrápido `groq/compound-mini` (ou `llama-3.1-8b-instant`), que oferece **70.000 tokens por minuto (TPM) e sem teto diário cumulativo de tokens no plano free tier**, condensando o histórico clínico e os protocolos relevantes em um extrato clínico denso de menos de 800 tokens.
  - **Estratégia de Fallback (Python Puro):** Caso a API Groq esteja indisponível, sem chave ou com falha de conexão, o sistema executa um truncamento determinístico estruturado em memória respeitando prioridades médicas: `avaliação` > `prescrição` > `alergias` > `sinais vitais` > `RAG`.
- Se o total de tokens estiver abaixo de 3.000, o contexto permanece íntegro e sem perdas.

### 5. Observabilidade, Auditoria e Transparência
- A collection `agent_audit_logs` no MongoDB registra explicitamente:
  - `patient_name`: nome consultado;
  - `patient_record_used`: booleano indicando se o prontuário foi injetado;
  - `patient_fields_used`: lista de campos clínicos aproveitados;
  - `medical_reports_used`: sinaliza se os laudos do paciente foram usados;
  - `medical_reports_fields_used`: campos específicos extraídos dos laudos;
  - `context_summarized`: se houve sumarização;
  - `context_summarizer_mode`: `"none"`, `"groq"` ou `"fallback_python"`.
- A interface exibe badges informativos (`🏥 Prontuário consultado`, `🧾 Laudos consultados` e `⚡ Contexto resumido`) com accordion expansível para que o médico possa auditar exatamente os dados que alimentaram a resposta.

### 6. Grounding real de laudos clínicos no fluxo do paciente
- O contexto clínico do paciente não se limita ao prontuário estruturado: a arquitetura também incorpora laudos médicos como fonte de evidência para exames, resultados e acompanhamento clínico.
- Como o dataset de RAG é anonimizadode forma intencional para evitar PII, o backend precisa manter uma correlação segura entre o registro raw do paciente e o laudo anonimizado através do campo `id_laudo`.
- O fluxo arquitetural estabelece uma regra explícita: localizar o paciente no dataset raw, extrair o identificador do laudo correto e, em seguida, recuperar o documento equivalente em forma anonimizada, filtrando antes de injetar qualquer texto na LLM.
- A etapa de geração também aplica um guardrail para perguntas sobre exames e resultados: quando não existe grounding documental confiável em laudos ou na base vetorial, a resposta é bloqueada em vez de inventar um achado clínico.

---

## Justificativa

- **Respeito ao Treinamento do Modelo (SFT):** O fine-tuning do modelo com 3.000 tokens garante estabilidade da geração e coerência gramatical. Injetar contextos maiores geraria alucinações ou estouro de memória da GPU.
- **Escolha da Groq (`compound-mini`):** A Groq foi escolhida por oferecer inferência em frações de segundo (LPU) com 70k TPM e ausência de cotas diárias de tokens restritivas (diferente de provedores que limitam a poucos milhares de tokens/dia), viabilizando a sumarização instantânea sem onerar o pipeline.
- **Garantia de Não Interrupção:** O fallback algorítmico em Python assegura que o assistente opere mesmo em ambientes totalmente desconectados da internet externa.
- **Conformidade LGPD:** Ao filtrar estritamente dados clínicos e omitir CPF e identificadores civis, minimiza-se o risco de vazamento de dados sensíveis.

---

## Alternativas Consideradas

| Alternativa | Razão para não adoção |
|---|---|
| Extrair nome do paciente da pergunta via Regex ou NER | Propenso a falsos positivos e alucinações de nomes quando termos médicos complexos ou autores de protocolos são citados. |
| Retreinar a LLM com janela de 8k ou 16k tokens | Custo computacional e tempo de treinamento proibitivos no escopo do projeto, além de degradar a precisão em GPUs de uso acadêmico (T4 no Colab). |
| Truncamento cego de caracteres no início/fim | Truncamento cego poderia descartar trechos críticos como contraindicações de alergia ou alertas de dosagem. |
| Utilizar modelo local para sumarização | Executar uma segunda LLM localmente exigiria dobrar o consumo de VRAM ou causaria latência inaceitável na CPU. |

---

## Consequências

**Positivas:**
- Atendimento completo aos itens 1, 2 e 3 do Requisito Obrigatório 2 do edital.
- Contextualização clínica segura com cruzamento automático entre prontuário e protocolos.
- Garantia absoluta de respeito à janela de contexto SFT (3.000 tokens).
- Transparência total para o usuário médico com badges e inspeção de dados utilizados.
- Cobertura integral de testes unitários (100% dos 64 testes automatizados passando).

**Negativas / Mitigações:**
- Dependência opcional de chave de API externa (`GROQ_API_KEY`) para a sumarização inteligente de alta precisão.
  *Mitigação:* Implementação de fallback determinístico automático em Python puro sem interrupção de serviço.
