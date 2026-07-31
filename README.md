# FIAP POS IA - Challenge Fase 3

Este repositório reúne uma aplicação full-stack para pré-processar datasets médicos e acompanhar a execução em uma interface web. A solução está organizada em três partes:

- backend em FastAPI para processar os dados e persistir o estado em MongoDB;
- frontend em React + TypeScript para iniciar e acompanhar o processamento;
- stack completa via Docker Compose para subir tudo com um comando.

## Visão geral

A aplicação permite:

1. iniciar o pré-processamento dos datasets PubMedQA, MedQuAD e protocolos clínicos FHEMIG;
2. definir o percentual de dados destinado ao conjunto RAG;
3. acompanhar o progresso da execução em tempo real;
4. consultar os arquivos gerados em formato estruturado para treino e recuperação;
5. visualizar contagens separadas para `QAs` e `clinical_protocols`.

O fluxo principal funciona assim:

- o usuário acessa a interface web no frontend;
- a tela envia uma requisição ao backend para iniciar o processamento;
- o backend cria um registro no MongoDB e inicia a tarefa em background;
- o processamento baixa ou consulta os datasets, extrai texto dos PDFs dos protocolos clínicos, transforma os dados e gera os arquivos de saída;
- o frontend faz polling do estado da execução até a conclusão.

## Como a aplicação funciona

### Arquitetura geral

- Frontend: interface React para iniciar o processo e visualizar progresso.
- Backend: API FastAPI que recebe os pedidos, executa o processamento em background e armazena o estado.
- Banco de dados: MongoDB para persistir o status das execuções.
- Datasets: os dados são baixados ou consultados automaticamente pelo backend a partir de fontes públicas.

### Fluxo de execução

1. O usuário informa o percentual de dados que deve ir para o conjunto RAG.
2. O frontend envia um pedido para o endpoint de preprocessamento no backend.
3. O backend cria um documento de execução no MongoDB e retorna um identificador da tarefa.
4. A tarefa em background:
   - clona ou reutiliza os datasets necessários;
   - processa os dados de QA e protocolos clínicos;
   - extrai texto dos PDFs dos protocolos clínicos;
   - gera os arquivos de saída para treino e RAG;
   - atualiza o status da execução.
5. O frontend consulta periodicamente o estado da execução e exibe progresso, contadores e resultado final.

## Documentação específica

Para detalhes mais completos, consulte os READMEs específicos de cada parte do projeto:

- Backend: [backend/README.md](backend/README.md)
- Datasets: [backend/datasets/README.md](backend/datasets/README.md)
- Frontend: [frontend/README.md](frontend/README.md)

## Subindo tudo com Docker Compose

O arquivo [app-docker-compose.yaml](app-docker-compose.yaml) sobe a aplicação completa.

### Comando

```bash
docker compose -f app-docker-compose.yaml up --build -d
```

### Acesso

- Frontend: http://localhost:8080
- Backend/API: http://localhost:3000
- Documentação Swagger: http://localhost:3000/docs
- MongoDB: localhost:27017

### Parar os containers

```bash
docker compose -f app-docker-compose.yaml down
```

## Script de reinicialização

O script [restart-app.sh](restart-app.sh) facilita a reinicialização completa da aplicação.

```bash
./restart-app.sh
```

## Observações importantes

- O backend depende do MongoDB para subir corretamente.
- O processamento de datasets é feito em background, então a API responde rapidamente e o estado pode ser acompanhado depois.
- Uma execução pode terminar com status `error`; em cenários de falha de fallback interno, também pode aparecer `failed`.
- Os datasets são baixados automaticamente na primeira execução, mas também podem ser tratados manualmente conforme descrito em [backend/datasets/README.md](backend/datasets/README.md).
