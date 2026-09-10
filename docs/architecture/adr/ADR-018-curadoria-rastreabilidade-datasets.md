# ADR-018 — Curadoria automática versionada e rastreabilidade dos datasets

**Status:** Aceito  
**Data:** 2026-09-10  
**Contexto:** Projeto FIAP POS IA Fase 3 — preparação de datasets médicos  
**Decisores:** Equipe do projeto

---

## Contexto

O edital exige a preparação dos dados com preprocessing, anonimização e curadoria. O pipeline já realizava normalização, extração de PDFs, tradução e anonimização, mas não registrava de forma reproduzível quais registros foram aceitos ou rejeitados, nem os motivos das rejeições.

Além disso, o pipeline reutilizava artefatos pré-processados apenas pela existência e conteúdo não vazio dos arquivos. Isso permitia que um cache criado antes da adoção dos critérios de curadoria fosse apresentado sem estatísticas correspondentes.

## Decisão

A curadoria automática será executada no Step 2, antes da tradução e da geração da base RAG, usando critérios versionados pela chave `curation-v1`.

Os critérios atuais são:

- PubMedQA e MedQuAD: pergunta e resposta não vazias, pergunta com pelo menos 20 caracteres e resposta com pelo menos 40 caracteres;
- MedQuAD: estrutura `QAPair` válida;
- FHEMIG e PCDT: nome presente, PDF localizado e texto extraível.

Cada fonte produz métricas de `input`, `accepted`, `rejected` e `rejection_reasons`. Os registros rejeitados não entram nos arquivos pré-processados finais.

A execução gera `datasets/preprocessed/curation_report.json` e persiste o mesmo relatório no documento da collection MongoDB `preprocess`, em `results.curation`. O caminho é exposto em `results.curation_report_path` e o relatório fica associado ao `preprocess_id`.

O cache só é válido quando os artefatos obrigatórios e um relatório com a versão atual dos critérios estão presentes. Cache sem relatório ou com versão incompatível é reprocessado.

## Justificativa

- Torna a curadoria auditável por fonte e por motivo de rejeição.
- Permite que a interface e a API apresentem evidências quantitativas da preparação dos dados.
- Evita confundir registros aceitos com documentos e chunks posteriormente gerados na RAG.
- Evita que estatísticas antigas ou inexistentes sejam associadas a uma execução atual.
- Mantém a fonte bruta preservada, sem misturar dados descartados com os artefatos consumidos pelo treinamento e pela RAG.

## Alternativas consideradas

| Alternativa | Razão para não escolher |
|---|---|
| Registrar apenas mensagens no console | Não é persistente, não é facilmente auditável e não fica associado ao `preprocess_id`. |
| Criar uma collection MongoDB exclusiva | A collection `preprocess` já representa o estado e os resultados de cada execução; uma nova collection aumentaria a complexidade sem benefício necessário. |
| Reutilizar qualquer arquivo pré-processado não vazio | Não garante que o arquivo foi produzido pelos critérios atuais. |
| Usar apenas o `golden_test_qa.json` como evidência | O golden set é destinado à avaliação do modelo e não representa a curadoria do corpus de treino/RAG. |
| Fazer revisão manual dentro da tarefa automática | Tornaria o serviço não determinístico e não haveria como comprovar uma revisão humana sem registrar amostra, data e revisor. |

## Consequências

**Positivas:**

- A API retorna estatísticas de curadoria junto do resultado do preprocessing.
- O frontend apresenta totais e motivos por fonte antes da resposta JSON bruta.
- Os testes podem verificar critérios e contadores sem depender da quantidade final de chunks.
- Alterações futuras nos critérios podem gerar uma nova versão e invalidar o cache anterior.

**Negativas:**

- A adoção dos critérios pode reduzir a quantidade de dados disponíveis para treino e RAG.
- O arquivo de relatório é um artefato de runtime e precisa ser preservado junto da execução quando for usado como evidência.
- A curadoria automática não substitui revisão manual ou validação clínica especializada.

**Neutras:**

- A etapa de tradução preserva a seleção feita pela curadoria, salvo falha específica de tradução.
- A anonimização de laudos continua sendo uma etapa distinta, documentada no ADR-015.
- O relatório atual cobre automaticamente QAs e protocolos; evidências de revisão manual devem ser documentadas separadamente.
