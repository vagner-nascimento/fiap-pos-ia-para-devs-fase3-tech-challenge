# Datasets Downloader

Este diretorio contem os scripts usados pelo backend para obter os dados brutos e preparar a base de pre-processamento.

## O que e baixado / preparado / gerado

O script [`get_datasets.py`](get_datasets.py) trabalha com cinco entradas:

1. **PubMedQA** - [https://github.com/pubmedqa/pubmedqa](https://github.com/pubmedqa/pubmedqa) (clonado via `git`)
2. **MedQuAD** - [https://github.com/abachaa/MedQuAD](https://github.com/abachaa/MedQuAD) (clonado via `git`)
3. **Protocolos clinicos FHEMIG** - [https://www.fhemig.mg.gov.br/index.php/acesso-rapido/protocolos-clinicos](https://www.fhemig.mg.gov.br/index.php/acesso-rapido/protocolos-clinicos) (download HTTP)
4. **PCDT - Protocolos Clinicos e Diretrizes Terapeuticas (Ministerio da Saude)** - PDFs versionados no repositorio em `files/pcdt/pcdt.zip` (Git LFS); o script apenas extrai o ZIP e gera o catalogo `pcdt_protocols.json`
5. **Dataset estruturado de laudos medicos (pt-BR)** - JSON versionado no repositorio em `files/laudos_medicos/dataset_laudos_medicos.json`, usado como entrada do Step 4 de anonimização

## Estrutura gerada

Arquivos **versionados no repositorio** (fonte de verdade compartilhada):

- `backend/datasets/files/pcdt/pcdt.zip` (Git LFS)
- `backend/datasets/files/laudos_medicos/dataset_laudos_medicos.json`
- `backend/datasets/evaluation/golden_test_qa.json` (Dataset curado de 50 casos clínicos em pt-BR com ground truth para avaliação formal)
- `backend/datasets/evaluation/metrics_evaluation*.json` (Métricas consolidadas ROUGE-1/2/L, BLEU-1..4 e latência por configuração)

Arquivos **gerados em runtime** (ignorados pelo git):

- `backend/datasets/files/qas/pubmedqa/` (clone do repositorio)
- `backend/datasets/files/qas/MedQuAD/` (clone do repositorio)
- `backend/datasets/files/clinical_protocols/clinical_protocols.json` (catalogo FHEMIG)
- `backend/datasets/files/clinical_protocols/data/` (PDFs FHEMIG baixados)
- `backend/datasets/files/pcdt/pcdt_protocols.json` (catalogo PCDT gerado)
- `backend/datasets/files/pcdt/data/` (PDFs PCDT extraidos do `pcdt.zip`)
- `backend/datasets/preprocessed/qas/`
- `backend/datasets/preprocessed/clinical_protocols/` (FHEMIG + PCDT no mesmo `clinical_protocols_rag.json`)
- `backend/datasets/preprocessed/medical_reports/anonymizated_medical_reports.json` (laudos anonimizados usados na base RAG)

## Pre-requisitos

Para executar os scripts voce precisa de:

1. Python 3.x
2. Git no PATH, para os clones dos repositórios de QA
3. **Git LFS** instalado e inicializado (`git lfs install`), para baixar o `pcdt.zip` (~216 MB) durante o `git clone` / `git pull`
4. A dependencia `beautifulsoup4`, usada para extrair os links dos PDFs da pagina da FHEMIG
5. A dependencia `requests`, usada para baixar os arquivos


### Como o colega obtem os datasets locais

Os dois datasets locais estao versionados no repositorio:

- **`files/laudos_medicos/dataset_laudos_medicos.json`** (~44 KB) - vai no clone normalmente.
- **`files/pcdt/pcdt.zip`** (~216 MB) - versionado via **Git LFS**. Precisa ter Git LFS instalado antes do clone/pull; caso contrario, o arquivo vem como um ponteiro texto.

Passo a passo apos clonar:

```bash
# 1. Instalar Git LFS (uma vez por maquina)
brew install git-lfs        # macOS
# ou: sudo apt install git-lfs
git lfs install

# 2. Puxar os blobs LFS caso ja tenha clonado antes de instalar o LFS
cd fiap-pos-ia-para-devs-fase3-tech-challenge
git lfs pull

# 3. Rodar o pipeline. Na primeira execucao o get_datasets extrai
#    o pcdt.zip automaticamente para files/pcdt/data/
cd backend/datasets
python get_datasets.py
```

Os artefatos de runtime (`files/pcdt/data/`, `files/pcdt/pcdt_protocols.json`, tudo em `preprocessed/`) sao gerados localmente e **nao** entram no git.

## Como usar

### Baixar e gerar os datasets

```bash
cd backend/datasets
python get_datasets.py
```

### Saida esperada

Ao final, a estrutura fica parecida com:

```text
backend/datasets/
|-- files/
|   |-- qas/
|   |   |-- pubmedqa/
|   |   `-- MedQuAD/
|   |-- clinical_protocols/
|   |   |-- clinical_protocols.json
|   |   `-- data/
|   |-- pcdt/
|   |   |-- pcdt_protocols.json
|   |   `-- data/
|   `-- laudos_medicos/
|       `-- dataset_laudos_medicos.json
|-- evaluation/
|   |-- golden_test_qa.json
|   |-- metrics_evaluation.json
|   |-- metrics_evaluation_configA.json
|   |-- metrics_evaluation_configB.json
|   `-- metrics_evaluation_configC.json
`-- preprocessed/
    |-- qas/
    |-- clinical_protocols/
    `-- laudos_medicos/
```

## Observacoes

- O backend processa PubMedQA, MedQuAD, protocolos clinicos FHEMIG e PCDT em etapas separadas.
- PubMedQA e MedQuAD geram registros no formato de QA.
- Os protocolos clinicos FHEMIG e os PDFs do PCDT geram registros com o campo `content_text`, extraido dos PDFs, gravados no mesmo arquivo `preprocessed/clinical_protocols/clinical_protocols_rag.json` (com o campo `source` diferenciando a origem).
- O dataset estruturado de laudos medicos (`files/laudos_medicos/dataset_laudos_medicos.json`) e lido no Step 4, que gera `preprocessed/medical_reports/anonymizated_medical_reports.json`.
- A anonimização substitui o nome do paciente por asteriscos e mascara o medico solicitante, preservando a estrutura clinica necessaria para busca. O arquivo anonimizado e a unica versao de laudos enviada para a base RAG.
- A geração da RAG lê o arquivo anonimizado, serializa campos clínicos de exame, descrição, evolução, impressão diagnóstica, CID e conduta, divide o texto em chunks, gera embeddings e persiste os documentos na coleção MongoDB `rag_documents` com `dataset/source_type` igual a `medical_reports`.
- Identificadores do laudo, nome do paciente, medico solicitante e CRM nao sao indexados. O arquivo bruto permanece somente como fonte de entrada do processamento e deve ser tratado conforme os controles de acesso e armazenamento do projeto.
- O pré-processamento atual não recebe percentual de split. PubMedQA e MedQuAD são normalizados em `preprocessed/qas/qas_train.json`; os protocolos clínicos (FHEMIG + PCDT) são extraídos dos PDFs e salvos em `preprocessed/clinical_protocols/clinical_protocols_rag.json`.
- A etapa seguinte traduz todos os QAs para pt-BR e grava `preprocessed/qas/qas_train_pt_br.json`. A tradução preserva `metadata` e traduz `question`, `contexts` textuais e `answer`.
- **Dataset e Métricas de Avaliação (`evaluation/`):** Contém o arquivo `golden_test_qa.json` com 50 casos clínicos desafiadores e os arquivos de métricas `metrics_evaluation*.json` resultantes da avaliação formal do modelo fine-tunado no Google Colab. Para detalhes das métricas e conclusões de calibração, consulte [docs/avaliacao-modelo.md](../../docs/avaliacao-modelo.md) e [ADR-016](../../docs/architecture/adr/ADR-016-metodologia-avaliacao-e-calibracao-decodificacao-llm.md).

## Curadoria e rastreabilidade

O Step 2 aplica os critérios versionados `curation-v1` aos QAs e aos protocolos clínicos:

- QAs precisam ter pergunta e resposta não vazias;
- perguntas precisam ter pelo menos 20 caracteres;
- respostas precisam ter pelo menos 40 caracteres;
- protocolos precisam ter nome, PDF disponível e texto extraível.

Cada execução que realiza a extração gera `preprocessed/curation_report.json`, contendo entradas, aceitos, rejeitados e motivos de rejeição por fonte. O mesmo relatório é associado ao `preprocess_id` em `results.curation` e é obrigatório para que os artefatos sejam considerados um cache válido.

Essa contagem representa registros de origem aceitos ou rejeitados. Ela não deve ser confundida com a quantidade posterior de documentos ou chunks gerados na base RAG. A revisão manual de amostras deve ser registrada separadamente como evidência de curadoria humana; o `golden_test_qa.json` é um conjunto de avaliação e não substitui essa revisão.

O relatório é associado ao documento MongoDB da execução em `results.curation`, e seu caminho aparece em `results.curation_report_path`. Quando o cache não possui esse relatório ou usa uma versão diferente de `curation-v1`, a pipeline refaz a extração para evitar apresentar artefatos antigos como evidência da curadoria atual.
