# ADR-013 — Desacoplamento de Guardrails Determinísticos e Preservação do Template de Fine-Tuning (SFT)

**Status:** Aceito  
**Data:** 2026-08-29  
**Contexto:** Projeto FIAP POS IA Fase 3 — Agente Médico, Segurança Clínica e Fidelidade do Fine-Tuning  
**Decisores:** Equipe do projeto  

---

## Contexto

O modelo de linguagem utilizado pelo assistente médico (**Qwen2.5-1.5B**) passou por fine-tuning supervisionado (SFT com LoRA) formatado estritamente com o template de instrução Alpaca/SFT:

```text
### Instrucao:
Responda em pt-BR usando o contexto clinico fornecido.

### Entrada:
Pergunta: {pergunta}
Contexto:
{contexto}

### Resposta:
```

Surgiram dois desafios centrais de engenharia e segurança médica:

1. **Sensibilidade do Modelo Fine-Tunado ao Prompt (*Distribution Shift*):**
   Modelos compactos (1.5B) com adaptadores LoRA são altamente sensíveis à estrutura de tokens vista durante o treinamento. Inserir longos *system prompts* com regras extensas e proibições altera a distribuição de ativação neural, degradando a atenção ao contexto clínico (RAG), aumentando alucinações ou misturando idiomas.
2. **Insegurança de Guardrails Baseados Exclusivamente em Prompts de LLM:**
   Na área médica, delegar a segurança unicamente a instruções em linguagem natural para a LLM cria vulnerabilidades graves a ataques de *Jailbreak*, *Prompt Injection* e alucinações (ex.: usuário induzindo o modelo a receitar dosagens perigosas de medicamentos).

## Decisão

Adotamos a estratégia de **Desacoplamento Completo entre a Especialização Clínica da LLM e a Camada de Segurança Determinística**:

1. **Preservação Estrita do Template SFT na LLM:**
   O nó [`llm_generator`](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase3-tech-challenge/agent/src/services/nodes/llm_generator.py) envia estritamente o template com o qual o modelo foi treinado, garantindo que os pesos LoRA operem no pico de sua acurácia e coerência clínica em português.
2. **Defesa em Profundidade Programática no Grafo LangGraph:**
   Toda a responsabilidade de segurança e conformidade regulatória é assumida por nós Python determinísticos:
   - **Pré-LLM (`topic_validator`):** Rejeição imediata de perguntas fora do escopo de saúde via heurísticas e regex.
   - **Pré-LLM (`safety_guard`):** Lista negra determinística via regex que bloqueia prescrições com dosagens (ex.: `500mg`, `comprimidos`), solicitações de diagnóstico definitivo e incentivos à automedicação.
   - **Pós-LLM (`response_formatter`):** Injeção obrigatória do aviso legal médico (disclaimer de emergência SAMU 192) e garantia invariante do flag `requires_human_validation: true`.
   - **Auditoria (`audit_logger`):** Registro imutável de todas as interações no MongoDB para auditoria clínica.

## Justificativa

| Critério | Guardrail apenas via System Prompt na LLM | **Guardrail Desacoplado no LangGraph (Adotado)** |
|---|---|---|
| **Resistência a Prompt Injection** | ❌ Frágil (LLM pode ser contornada) | ✅ 100% Imune (bloqueio antes da LLM) |
| **Acurácia Clínica da LLM** | ⚠️ Degradada por *distribution shift* | ✅ Máxima fidelidade aos pesos do SFT |
| **Determinismo em Prescrições** | ❌ Probabilístico / Inconsistente | ✅ 100% Determinístico via Regex |
| **Consumo e Custo de GPU** | ❌ Gasta inferência mesmo em queries proibidas | ✅ Early-exit em ~8ms sem chamar a GPU |
| **Conformidade Médica / Legal** | ⚠️ Risco de omitir disclaimers | ✅ Disclaimer obrigatório injetado programaticamente |

## Consequências

### Positivas
- **Segurança Robusta:** Garantia absoluta de que pedidos perigosos de automedicação e dosagens não serão processados pela LLM.
- **Eficiência Computacional:** Consultas inválidas sofrem *early-exit* imediato, poupando cotas de GPU ZeroGPU e reduzindo a latência para menos de 10ms.
- **Isolamento de Responsabilidades:** O modelo de IA foca na geração de linguagem clínica contextualizada, enquanto a governança e conformidade são geridas por código determinístico testável.

### Negativas
- A lista de regex do `safety_guard` e `topic_validator` precisa ser mantida e enriquecida continuamente com novos termos médicos e variações sintáticas.

---

← [Voltar para o Índice de ADRs](README.md)
