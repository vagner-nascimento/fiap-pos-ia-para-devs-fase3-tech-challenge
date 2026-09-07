# ADR-011 — Opção de pular a tradução no pré-processamento

**Status:** Aceito
**Data:** 2026-08-28
**Contexto:** Projeto FIAP POS IA Fase 3 — Pré-processamento e Tradução de Datasets
**Decisores:** Equipe do projeto

---

## Contexto

A etapa de pré-processamento dos datasets (PubMedQA e MedQuAD) envolve a tradução dos textos para o português (pt-BR) utilizando um modelo de tradução local (`Helsinki-NLP/opus-mt-tc-big-en-pt`). Em hardwares mais modestos, especialmente aqueles sem GPU dedicada (fazendo fallback para CPU), essa tradução é um processo extremamente lento, criando um grande gargalo de tempo na execução do pipeline e prejudicando a usabilidade e a validação rápida da aplicação.

## Decisão

Foi implementada uma opção para **pular a etapa de tradução** (`skip_translation`). Quando ativada (via interface web com um checkbox ou via payload da API `POST /preprocess`), o backend pula a execução do modelo de machine translation e passa a utilizar um dataset já previamente traduzido, que está fixado e embarcado na aplicação no diretório `backend/datasets/preprocessed/fixed/qas`.

## Justificativa

| Critério | Avaliação |
|---|---|
| Usabilidade | Permite a execução rápida de todo o fluxo de pré-processamento por desenvolvedores e usuários com hardware limitado. |
| Inclusão de Hardware | Viabiliza o uso da aplicação (frontend e backend) sem a necessidade imperativa de uma GPU Nvidia para não travar na etapa de tradução. |
| Complexidade | A implementação é simples: apenas um flag booleano na API e um checkbox no frontend. |

## Alternativas consideradas

| Alternativa | Razão para não escolher |
|---|---|
| Tradução via API externa (ex: Google Translate, OpenAI) | Adicionaria custos financeiros e dependeria de chaves de API externas configuradas pelos usuários. |
| Reduzir a quantidade de dados processados | Limitaria a utilidade do modelo final de fine-tuning. |
| Manter a tradução obrigatória | Continuaria inviabilizando testes e demonstrações rápidas do sistema completo. |

## Consequências

**Positivas:**
- Execução do pré-processamento consideravelmente mais rápida para quem não deseja ou não pode traduzir o dataset localmente.
- Maior acessibilidade do projeto para diferentes tipos de hardware.

**Negativas:**
- Se os datasets de origem (PubMedQA ou MedQuAD) forem atualizados no futuro, quem utilizar a opção `skip_translation` não se beneficiará dessas atualizações até que o dataset "fixado" no código fonte seja atualizado manualmente pela equipe.

**Neutras:**
- Adiciona a necessidade de manter o diretório `backend/datasets/preprocessed/fixed/qas` versionado com os arquivos traduzidos no repositório.
