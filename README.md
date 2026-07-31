# FIAP POS IA — Challenge Fase 3

Este repositório reúne uma aplicação full-stack para realizar o pré-processamento de datasets médicos e acompanhar a execução em uma interface web. A solução foi organizada em três partes principais:

- um backend em FastAPI para processar os dados e persistir o estado em MongoDB;
- um frontend em React + TypeScript para iniciar e acompanhar o processamento;
- um fluxo de execução via Docker Compose para subir toda a stack com um único comando.

## Visão geral da aplicação

A aplicação permite:

1. iniciar o pré-processamento dos datasets PubMedQA e MedQuAD;
2. definir o percentual de dados que será destinado ao conjunto RAG;
3. acompanhar o progresso da execução em tempo real;
4. consultar os arquivos gerados em formato estruturado para treino e recuperação.

O fluxo principal funciona assim:

- o usuário acessa a interface web no frontend;
- a tela envia uma requisição ao backend para iniciar o processamento;
- o backend cria um registro no MongoDB e inicia a tarefa em background;
- o processamento baixa/consulta os datasets, transforma os dados e gera os arquivos de saída;
- o frontend faz polling do estado da execução até a conclusão.

## Como a aplicação funciona

### Arquitetura geral

- Frontend: interface React para iniciar o processo e visualizar progresso.
- Backend: API FastAPI que recebe os pedidos, executa o processamento em background e armazena o estado.
- Banco de dados: MongoDB para persistir o status das execuções.
- Datasets: os dados são baixados automaticamente pelo backend a partir de repositórios públicos.

### Fluxo de execução

1. O usuário informa o percentual de dados do MedQuAD que deve ir para o conjunto RAG.
2. O frontend envia um pedido para o endpoint de preprocessamento no backend.
3. O backend cria um documento de execução no MongoDB e retorna um identificador da tarefa.
4. A tarefa em background:
   - clona ou reutiliza os datasets necessários;
   - processa os dados;
   - gera os arquivos de saída para treino e RAG;
   - atualiza o status da execução.
5. O frontend consulta periodicamente o estado da execução e exibe progresso, contadores e resultado final.

## Documentação específica

Para detalhes mais completos, consulte os READMEs específicos de cada parte do projeto:

- Backend: [backend/README.md](backend/README.md)
- Datasets: [backend/datasets/README.md](backend/datasets/README.md)
- Frontend: [frontend/README.md](frontend/README.md)

Esses arquivos contêm instruções de configuração, endpoints da API, estrutura do projeto e detalhes de execução local.

## Subindo tudo com Docker Compose

A forma recomendada de executar a aplicação completa é usar o arquivo [app-docker-compose.yaml](app-docker-compose.yaml) na raiz do repositório.

Esse arquivo sobe simultaneamente:

- o frontend na porta 8080;
- o backend na porta 3000;
- o MongoDB na porta 27017.

### Comando para subir a stack

```bash
docker compose -f app-docker-compose.yaml up --build -d
```

### Acesso após a subida

- Frontend: http://localhost:8080
- Backend/API: http://localhost:3000
- Documentação Swagger: http://localhost:3000/docs
- MongoDB: localhost:27017

### Para parar os containers

```bash
docker compose -f app-docker-compose.yaml down
```

## Script de reinicialização

O script [restart-app.sh](restart-app.sh) facilita a reinicialização completa da aplicação.

Ele executa os seguintes passos:

1. para todos os containers definidos no arquivo de compose;
2. inicia novamente a stack com build atualizado;
3. mantém a aplicação em execução em modo detached.

### Como usar

```bash
./restart-app.sh
```

Esse script é útil quando você fez alterações no código e quer reiniciar a aplicação inteira de forma simples.

## Observações importantes

- O backend depende do MongoDB para subir corretamente.
- O processamento de datasets é feito em background, então a API responde rapidamente e o estado pode ser acompanhado depois.
- Uma execução pode terminar com status `failed`; nesse caso, o documento retornado pelo backend inclui o campo `error_message` com detalhes do problema.
- Os datasets são baixados automaticamente na primeira execução, mas também podem ser tratados manualmente conforme descrito em [backend/datasets/README.md](backend/datasets/README.md).
