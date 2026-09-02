# Datasets Downloader

Este diretorio contem os scripts usados pelo backend para obter os dados brutos e preparar a base de pre-processamento.

## O que e baixado / preparado / gerado

O script [`get_datasets.py`](get_datasets.py) trabalha com cinco entradas:

1. **PubMedQA** - [https://github.com/pubmedqa/pubmedqa](https://github.com/pubmedqa/pubmedqa) (clonado via `git`)
2. **MedQuAD** - [https://github.com/abachaa/MedQuAD](https://github.com/abachaa/MedQuAD) (clonado via `git`)
3. **Protocolos clinicos FHEMIG** - [https://www.fhemig.mg.gov.br/index.php/acesso-rapido/protocolos-clinicos](https://www.fhemig.mg.gov.br/index.php/acesso-rapido/protocolos-clinicos) (download HTTP)
4. **PCDT - Protocolos Clinicos e Diretrizes Terapeuticas (Ministerio da Saude)** - PDFs versionados no repositorio em `files/pcdt/pcdt.zip` (Git LFS); o script apenas extrai o ZIP e gera o catalogo `pcdt_protocols.json`
5. **Dataset estruturado de laudos medicos (pt-BR)** - JSON versionado no repositorio em `files/laudos_medicos/dataset_laudos_medicos.json` (50 laudos ja em formato `{id_laudo, cabecalho_identificador, corpo_tecnico, conclusao}`, ideal para fine-tuning)

O script [`generate_medical_reports.py`](generate_medical_reports.py) gera uma sexta entrada, complementar aos laudos estruturados:

6. **Laudos Médicos Sintéticos em PDF** - 500 PDFs gerados localmente com `reportlab` (SEED determinística), armazenados em `medical_reports/` junto com um `index.csv`. Diferentemente do item 5, aqui os laudos sao **documentos PDF** que simulam laudos reais — uteis para pipelines de RAG / extracao de texto.

## Estrutura gerada

Arquivos **versionados no repositorio** (fonte de verdade compartilhada):

- `backend/datasets/files/pcdt/pcdt.zip` (Git LFS)
- `backend/datasets/files/laudos_medicos/dataset_laudos_medicos.json`

Arquivos **gerados em runtime** (ignorados pelo git):

- `backend/datasets/files/qas/pubmedqa/` (clone do repositorio)
- `backend/datasets/files/qas/MedQuAD/` (clone do repositorio)
- `backend/datasets/files/clinical_protocols/clinical_protocols.json` (catalogo FHEMIG)
- `backend/datasets/files/clinical_protocols/data/` (PDFs FHEMIG baixados)
- `backend/datasets/files/pcdt/pcdt_protocols.json` (catalogo PCDT gerado)
- `backend/datasets/files/pcdt/data/` (PDFs PCDT extraidos do `pcdt.zip`)
- `backend/datasets/medical_reports/`
- `backend/datasets/preprocessed/qas/`
- `backend/datasets/preprocessed/clinical_protocols/` (FHEMIG + PCDT no mesmo `clinical_protocols_rag.json`)
- `backend/datasets/preprocessed/laudos_medicos/laudos_medicos.json`

## Pre-requisitos

Para executar os scripts voce precisa de:

1. Python 3.x
2. Git no PATH, para os clones dos repositórios de QA
3. **Git LFS** instalado e inicializado (`git lfs install`), para baixar o `pcdt.zip` (~216 MB) durante o `git clone` / `git pull`
4. A dependencia `beautifulsoup4`, usada para extrair os links dos PDFs da pagina da FHEMIG
5. A dependencia `requests`, usada para baixar os arquivos
6. A dependencia `reportlab`, usada pelo script de geração de laudos médicos


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
python generate_medical_reports.py
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
|-- medical_reports/
`-- preprocessed/
    |-- qas/
    |-- clinical_protocols/
    `-- laudos_medicos/
```

## Observacoes

- O backend processa PubMedQA, MedQuAD, protocolos clinicos FHEMIG, PCDT e o dataset estruturado de laudos medicos em etapas separadas.
- PubMedQA e MedQuAD geram registros no formato de QA.
- Os protocolos clinicos FHEMIG e os PDFs do PCDT geram registros com o campo `content_text`, extraido dos PDFs, gravados no mesmo arquivo `preprocessed/clinical_protocols/clinical_protocols_rag.json` (com o campo `source` diferenciando a origem).
- O dataset estruturado de laudos medicos (`dataset_laudos_medicos.json`) ja esta em pt-BR e e apenas normalizado para `preprocessed/laudos_medicos/laudos_medicos.json` (nao passa pela etapa de traducao).
- Os PDFs em `medical_reports/` sao gerados por `generate_medical_reports.py` e **nao** entram no pipeline `get_datasets.py`/`preprocess`. Eles ficam disponiveis para uso futuro (por exemplo, ingestao em RAG). A geracao usa SEED fixa, entao a saida e reproduzivel.
- O pré-processamento atual não recebe percentual de split. PubMedQA e MedQuAD são normalizados em `preprocessed/qas/qas_train.json`; os protocolos clínicos (FHEMIG + PCDT) são extraídos dos PDFs e salvos em `preprocessed/clinical_protocols/clinical_protocols_rag.json`.
- A etapa seguinte traduz todos os QAs para pt-BR e grava `preprocessed/qas/qas_train_pt_br.json`. A tradução preserva `metadata` e traduz `question`, `contexts` textuais e `answer`.
