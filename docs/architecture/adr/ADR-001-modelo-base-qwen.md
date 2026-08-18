# ADR-001 — Escolha do modelo base Qwen2.5-1.5B-Instruct

**Status:** Aceito  
**Data:** 2026-08-18  
**Contexto:** Projeto FIAP POS IA Fase 3 — Fine-tuning de LLM para domínio médico em português  
**Decisores:** Equipe do projeto  

---

## Contexto

O projeto exige um modelo de linguagem capaz de responder perguntas no domínio médico em português. O modelo precisa:

- Ser treinável (fine-tuning) com recursos de hardware limitados (sem datacenter dedicado);
- Ter boa capacidade de compreensão de linguagem natural em inglês e português;
- Ser suficientemente pequeno para caber na memória de GPUs consumer-grade (ex.: T4 16GB do Google Colab);
- Estar disponível para uso comercial/acadêmico de forma aberta.

## Decisão

Utilizamos o modelo **Qwen2.5-1.5B-Instruct** da Alibaba Cloud, disponível no HuggingFace Hub (`Qwen/Qwen2.5-1.5B-Instruct`), como modelo base para o fine-tuning.

## Justificativa

| Critério | Avaliação |
|---|---|
| Tamanho | 1.5B parâmetros — cabe em GPU T4 com quantização |
| Multilíngue | Suporte nativo a português e inglês |
| Instruction-tuned | Já pré-treinado para seguir instruções (chat/instrução) |
| Licença | Apache 2.0 — uso acadêmico e comercial permitido |
| Benchmarks | Excelente desempenho para seu tamanho em tarefas de Q&A |
| Disponibilidade | Disponível via HuggingFace `transformers` e `datasets` |

## Alternativas consideradas

| Modelo | Razão para não escolher |
|---|---|
| LLaMA 3.2 1B | Menor capacidade multilíngue no português |
| Mistral 7B | Muito grande para GPU T4 sem quantização agressiva |
| GPT-2 | Muito antigo, fraco para Q&A estruturado |
| BioMedLM | Apenas inglês, sem suporte a português |

## Consequências

**Positivas:**
- Fine-tuning viável em hardware acessível (T4/A100 Colab);
- Boa qualidade de respostas após SFT com dados do domínio médico;
- Facilidade de integração com HuggingFace `transformers` e `trl`.

**Negativas:**
- Modelo relativamente pequeno: capacidade de raciocínio limitada em comparação a modelos maiores;
- Dependência de um modelo de terceiro (Alibaba) para a base do fine-tuning.

**Neutras:**
- O modelo base em inglês requer que os dados de treino sejam traduzidos para pt-BR para maximizar a qualidade das respostas em português (ver [ADR-007](ADR-007-split-train-rag.md)).
