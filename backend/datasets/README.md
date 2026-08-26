# Datasets Downloader

Este diretorio contem os scripts usados pelo backend para obter os dados brutos e preparar a base de pre-processamento.

## O que e baixado e gerado

O script [`get_datasets.py`](get_datasets.py) trabalha com tres entradas:

1. **PubMedQA** - [https://github.com/pubmedqa/pubmedqa](https://github.com/pubmedqa/pubmedqa)
2. **MedQuAD** - [https://github.com/abachaa/MedQuAD](https://github.com/abachaa/MedQuAD)
3. **Protocolos clinicos FHEMIG** - [https://www.fhemig.mg.gov.br/index.php/acesso-rapido/protocolos-clinicos](https://www.fhemig.mg.gov.br/index.php/acesso-rapido/protocolos-clinicos)

O script [`generate_medical_reports.py`](generate_medical_reports.py) gera o quarto dataset:

4. **Laudos Médicos Sintéticos** - PDFs gerados localmente para simular exames e laudos reais em formato PDF.

## Estrutura gerada

Os arquivos baixados, gerados e intermediarios ficam em:

- `backend/datasets/files/qas/pubmedqa`
- `backend/datasets/files/qas/MedQuAD`
- `backend/datasets/files/clinical_protocols/clinical_protocols.json`
- `backend/datasets/files/clinical_protocols/data/`
- `backend/datasets/medical_reports/`

Os arquivos processados ficam em:

- `backend/datasets/preprocessed/qas/`
- `backend/datasets/preprocessed/clinical_protocols/`

## Pre-requisitos

Para executar os scripts voce precisa de:

1. Python 3.x
2. Git no PATH, para os clones dos repositórios de QA
3. A dependencia `beautifulsoup4`, usada para extrair os links dos PDFs da pagina da FHEMIG
4. A dependencia `requests`, usada para baixar os arquivos
5. A dependencia `reportlab`, usada pelo script de geração de laudos médicos

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
|   `-- clinical_protocols/
|       |-- clinical_protocols.json
|       `-- data/
|-- medical_reports/
`-- preprocessed/
    |-- qas/
    `-- clinical_protocols/
```

## Observacoes

- O backend processa PubMedQA, MedQuAD e protocolos clinicos em etapas separadas.
- PubMedQA e MedQuAD geram registros no formato de QA.
- Os protocolos clinicos geram registros com o campo `content_text`, extraido dos PDFs.
- Os laudos médicos geram arquivos PDF na pasta `medical_reports/`.
- O pré-processamento atual não recebe percentual de split. PubMedQA e MedQuAD são normalizados em `preprocessed/qas/qas_train.json`; os protocolos clínicos são extraídos dos PDFs e salvos em `preprocessed/clinical_protocols/clinical_protocols_rag.json`.
- A etapa seguinte traduz todos os QAs para pt-BR e grava `preprocessed/qas/qas_train_pt_br.json`. A tradução preserva `metadata` e traduz `question`, `contexts` textuais e `answer`.
