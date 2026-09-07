# ADR-016 — Metodologia de Avaliação Empírica e Calibração de Decodificação do Modelo Fine-Tunado

**Status:** Aceito  
**Data:** 2026-09-07  
**Contexto:** Projeto FIAP POS IA Fase 3 — Avaliação formal de métricas e calibração de hiperparâmetros de inferência (GAP02 / M10)  
**Decisores:** Equipe do projeto  

---

## Contexto

Após a conclusão das rodadas de fine-tuning do modelo (`fiap-hospital-helper/hospital-helper-qwen2.5-1.5b:v2.0`), identificou-se a necessidade de:
1. **Estabelecer uma metodologia formal e reproduzível de avaliação quantitativa** para atender integralmente ao edital do Tech Challenge (GAP02 / M10), com métricas padronizadas de Processamento de Linguagem Natural (ROUGE-1, ROUGE-2, ROUGE-L, BLEU-1..4 e latência de geração).
2. **Mitigar comportamentos degenerativos observados na inferência base**: quando submetido a geração padrão sem penalidade de repetição ou com `max_new_tokens` excessivo (512 tokens), o modelo apresentava propensão a loops circulares de repetição ("*..., ..., ...*") e esgotamento forçado da janela de contexto, elevando a latência média para mais de 13 segundos por consulta.
3. **Determinar os hiperparâmetros de decodificação ótimos** a serem configurados como padrão no agente clínico e nos endpoints de inferência (Hugging Face Spaces ZeroGPU e FastAPI/ngrok).

## Decisão

Adotou-se uma metodologia formal de avaliação empírica composta por:

1. **Curadoria de Dataset Golden Test:** Criação do arquivo `backend/datasets/evaluation/golden_test_qa.json`, composto por 50 casos clínicos desafiadores em português (pt-BR), balanceando questões de múltipla escolha (estilo USMLE/PubMedQA), perguntas abertas sobre patologias e farmacologia (MedQuAD) e condutas baseadas em protocolos clínicos (FHEMIG/PCDT).
2. **Pipeline Automatizada de Métricas:** Desenvolvimento do notebook template [`FIAP_PosTech_IA4Devs_Fase3_TechChallenge_AvaliacaoModelos.ipynb`](../../../backend/src/notebooks/FIAP_PosTech_IA4Devs_Fase3_TechChallenge_AvaliacaoModelos.ipynb), computando métricas ROUGE e BLEU contra as respostas de referência (*ground truth*), além de rastrear tempo médio de inferência e número de tokens gerados.
3. **Varredura Sistemática de Três Regimes de Decodificação:**
   - **Configuração A (Baseline Greedy):** `max_new_tokens=512`, `temperature=0.0`, `do_sample=False`.
   - **Configuração B (Amostragem Criativa):** `max_new_tokens=512`, `temperature=0.7`, `top_p=0.90`, `do_sample=True`.
   - **Configuração C (Determinístico Calibrado com Penalidade de Repetição):** `max_new_tokens=450`, `temperature=0.10`, `top_p=0.85`, `repetition_penalty=1.10`, `do_sample=False`.
4. **Padronização da Configuração C para Produção:** Os parâmetros da **Configuração C** foram adotados como a recomendação canônica do projeto para a camada de inferência do agente médico.

## Justificativa e Resultados Empíricos

Os resultados consolidados na execução com o modelo canônico `v2.0` no Google Colab (GPU T4) demonstraram a superioridade inequívoca da Configuração C:

| Métrica | Configuração A (Base Greedy) | Configuração B (Amostragem) | Configuração C (Calibrada) | Variação (C vs A) |
|---|:---:|:---:|:---:|:---:|
| **ROUGE-1** | 0.2878 | 0.2798 | **0.2978** | **+3,47%** |
| **ROUGE-2** | 0.1471 | 0.1384 | **0.1477** | **+0,41%** |
| **ROUGE-L** | 0.2227 | 0.2078 | **0.2562** | **+15,04%** |
| **BLEU-1** | 0.2458 | 0.2459 | **0.2537** | **+3,21%** |
| **BLEU-4** | 0.0549 | 0.0464 | **0.0677** | **+23,32%** |
| **Latência Média** | 13.15 s | 12.06 s | **5.58 s** | **-57,57% (2.36x mais rápido)** |
| **Tokens Médios** | 468.9 tokens | 424.3 tokens | **198.8 tokens** | Respostas concisas e objetivas |

### Benefícios Clínicos e Operacionais da Configuração C:
- **Eliminação de Loops Circulares:** A adição de `repetition_penalty=1.10` força a penalização logarítmica de tokens repetidos, impedindo que o modelo entre em loops de pontuação ou repetição de frases.
- **Encerramento Natural no Token `<|im_end|>` / `eos_token`:** O modelo aprendeu a finalizar a resposta após responder diretamente à pergunta clínica, emitindo o token de parada por volta do 198º token em vez de arrastar a geração até o limite artificial de 512.
- **Redução Drástica do Custo Computacional:** A latência por inferência caiu de 13,15s para 5,58s, permitindo maior vazão no Hugging Face Spaces ZeroGPU e tempo de resposta ágil para o usuário no chat.

## Alternativas consideradas

| Alternativa | Razão para não escolher |
|---|---|
| Avaliação puramente manual/subjetiva | Não oferece rastreabilidade, repetibilidade nem atende aos critérios formais de avaliação científica exigidos no edital. |
| Manter Configuração A (512 tokens greedy) | Mantém o modelo suscetível a loops repetitivos e gera latência média de 13s por consulta. |
| Adotar Configuração B (alta temperatura/top-p) | Piora todas as métricas de precisão (BLEU-4 cai para 0.0464) e introduz alucinações incompatíveis com a área médica. |
| Fine-tuning adicional apenas para parada | Custo desnecessário de novo treinamento; o problema foi resolvido de forma mais elegante e robusta via calibração de decodificação. |

## Consequências

**Positivas:**
- Resolução formal do GAP02 e item M10 do edital, com relatório detalhado em `docs/avaliacao-modelo.md`.
- Geração de artefatos reproduzíveis (`golden_test_qa.json` e `metrics_evaluation_config[A|B|C].json`).
- Respostas do assistente no chat tornam-se clinicamente mais concisas, diretas e sem alucinações circulares.
- Latência média de resposta da LLM reduzida em 57%.

**Negativas:**
- Em cenários raros onde uma resposta exigir mais de 450 tokens de texto contínuo, a resposta poderá ser truncada (embora 98% das respostas de referência possuam menos de 250 tokens).

**Neutras:**
- As variáveis de ambiente do agente (`agent/.env.example`) passam a refletir os novos valores calibrados (`AGENT_MAX_TOKENS=450`, `AGENT_TEMPERATURE=0.10`, `AGENT_TOP_P=0.85`, `AGENT_REPETITION_PENALTY=1.10`).

## Referências

- Relatório Técnico Completo: [`docs/avaliacao-modelo.md`](../../avaliacao-modelo.md)
- Dataset de Avaliação: [`backend/datasets/evaluation/golden_test_qa.json`](../../../backend/datasets/evaluation/golden_test_qa.json)
- Notebooks Executados: [`backend/src/notebooks/`](../../../backend/src/notebooks/)
- Hugging Face Model: [`fiap-hospital-helper/hospital-helper-qwen2.5-1.5b`](https://huggingface.co/fiap-hospital-helper/hospital-helper-qwen2.5-1.5b)
