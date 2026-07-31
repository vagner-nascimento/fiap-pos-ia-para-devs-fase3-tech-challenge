# Datasets Downloader (PubMedQA & MedQuAD)

Este diretório contém o script responsável por baixar os datasets necessários para o projeto a partir de repositórios públicos no GitHub.

## O que o script faz?

O script [`get_datasets.py`](file:///c:/code/fiap-pos-ia/fase-3/fiap-pos-ia-para-devs-fase3-tech-challenge/backend/datasets/get_datasets.py) faz o download automático dos seguintes repositórios:
1. **PubMedQA**: [https://github.com/pubmedqa/pubmedqa](https://github.com/pubmedqa/pubmedqa)
2. **MedQuAD**: [https://github.com/abachaa/MedQuAD](https://github.com/abachaa/MedQuAD)

Os repositórios clonados são salvos no subdiretório `files/` dentro deste diretório (`backend/datasets/files/`):
* `backend/datasets/files/pubmedqa`
* `backend/datasets/files/MedQuAD`

> [!NOTE]
> Se o repositório já tiver sido clonado anteriormente e a respectiva pasta já existir no destino, o script detectará a presença da pasta e pulará o download para evitar redundância.

---

## Pré-requisitos

Para que o script funcione corretamente, você precisará dos seguintes softwares instalados em seu ambiente:

1. **Python 3.x**: O ambiente de execução do script.
2. **Git**: O utilitário Git CLI deve estar instalado e disponível no seu `PATH` global, pois o script utiliza comandos Git via subprocesso para realizar os clones.

---

## Como Utilizar

1. Abra um terminal na pasta onde o script está localizado:
   ```bash
   cd backend/datasets
   ```

2. Execute o script utilizando o Python:
   ```bash
   python get_datasets.py
   ```

3. Acompanhe a saída no terminal. Ao final, a estrutura do diretório de datasets ficará da seguinte forma:
   ```text
   backend/datasets/
   ├── files/
   │   ├── MedQuAD/
   │   └── pubmedqa/
   ├── get_datasets.py
   └── README.md
   ```
