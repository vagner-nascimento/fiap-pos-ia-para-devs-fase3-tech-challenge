# ADR-015 — Anonimização de laudos médicos antes da RAG

**Status:** Aceito  
**Data:** 2026-09-03  
**Contexto:** Projeto FIAP POS IA Fase 3 — Pré-processamento, privacidade e base RAG  
**Decisores:** Equipe do projeto  

---

## Contexto

O dataset estruturado de laudos médicos está versionado em `backend/datasets/files/laudos_medicos/dataset_laudos_medicos.json`. Os registros contêm informações clínicas e campos potencialmente identificáveis, como nome do paciente, médico solicitante, CRM, data e local do exame.

A base RAG precisa consultar o conteúdo clínico dos laudos, mas não deve indexar identificadores pessoais desnecessários. É necessário estabelecer uma etapa explícita de tratamento antes que os dados sejam transformados em chunks, embeddings e documentos persistidos no MongoDB.

## Decisão

Adicionar o Step 4 de anonimização ao pipeline de pré-processamento. O serviço `backend/src/services/preprocess/step_four_anonymization.py` lê o dataset bruto, preserva a estrutura dos registros e gera:

`backend/datasets/preprocessed/medical_reports/anonymizated_medical_reports.json`

A técnica atualmente aplicada é pseudonimização visual por mascaramento:

- `cabecalho_identificador.nome_paciente` é substituído por uma sequência de asteriscos com o mesmo comprimento do valor original;
- `cabecalho_identificador.medico_solicitante` preserva o prefixo `Dr(a).` e substitui o nome por asteriscos;
- os campos clínicos são preservados para manter a utilidade do dataset;
- `id_laudo`, `nome_paciente`, `medico_solicitante` e `crm_solicitante` não são enviados para o conteúdo nem para os metadados indexados no RAG.

A geração da RAG usa somente o arquivo anonimizado. O serviço serializa explicitamente os campos clínicos, divide o texto com o splitter recursivo, gera embeddings e persiste os chunks na coleção `rag_documents` com `dataset` e `source_type` iguais a `medical_reports`.

## Justificativa

A decisão aplica o princípio de minimização de dados da LGPD (Lei Geral de Proteção de Dados Pessoais, Lei nº 13.709/2018): somente os dados necessários para a finalidade de recuperação de conhecimento clínico seguem para a RAG.

A separação entre arquivo bruto e arquivo anonimizado cria uma fronteira verificável no pipeline. Também evita que uma serialização genérica do registro reintroduza campos pessoais nos documentos ou embeddings.

> O mascaramento reduz a exposição no artefato consumido pela RAG, mas não deve ser interpretado isoladamente como garantia de anonimização irreversível. O acesso, armazenamento, descarte e controle do arquivo bruto continuam sujeitos às políticas de segurança e governança de dados do projeto.

## Alternativas consideradas

| Alternativa | Razão para não escolher |
|---|---|
| Indexar diretamente o dataset bruto | Expõe identificadores desnecessários na base de recuperação e nos embeddings. |
| Remover o laudo inteiro | Elimina o valor clínico necessário para a busca e o agente médico. |
| Criptografar campos pessoais e indexá-los | Mantém dados pessoais na base RAG sem necessidade funcional. |
| Anonimização irreversível completa de todos os campos | Exigiria uma análise adicional de risco de reidentificação e poderia remover contexto clínico útil; permanece como evolução possível. |

## Consequências

**Positivas:**

- A RAG recebe apenas o artefato produzido após o Step 4;
- o conteúdo clínico permanece pesquisável por tipo de exame, diagnóstico, CID e conduta;
- o contrato de dados explicita quais campos pessoais não podem ser indexados;
- o processamento é rastreável por `medical_reports_path` no documento de preprocessamento.

**Negativas:**

- O arquivo bruto ainda exige controles de acesso e retenção adequados;
- data e local do exame podem continuar sendo dados potencialmente identificáveis e devem ser revisados conforme o contexto de uso;
- alterações futuras no schema dos laudos precisam atualizar a serialização explícita e os testes de privacidade.

## Verificação

- Testar que o Step 4 preserva a quantidade e a estrutura dos registros.
- Testar que o arquivo anonimizado é o único arquivo de laudos lido pela geração da RAG.
- Testar que `id_laudo`, nomes, médico solicitante e CRM não aparecem em conteúdo ou metadados indexados.
- Testar que documentos `medical_reports` podem ser recuperados por conteúdo clínico.
