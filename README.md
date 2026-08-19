# FIAP POS IA - Challenge Fase 3

Este repositório reúne uma aplicação full-stack para pré-processar datasets médicos e acompanhar a execução em uma interface web. A solução está organizada em três partes:

- backend em FastAPI para processar os dados e persistir o estado em MongoDB;
- frontend em React + TypeScript para iniciar e acompanhar o processamento;
- stack completa via Docker Compose para subir tudo com um comando.

## Visão geral

A aplicação permite:

1. iniciar o pré-processamento dos datasets PubMedQA, MedQuAD e protocolos clínicos FHEMIG;
2. acompanhar o progresso da execução em tempo real;
3. consultar os arquivos gerados em formato estruturado para fine-tuning e recuperação;
4. visualizar contagens separadas para `QAs` e `clinical_protocols`.

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

1. O frontend envia um pedido sem parâmetros para o endpoint de preprocessamento no backend.
2. O backend cria um documento de execução no MongoDB e retorna um identificador da tarefa.
3. A tarefa em background:
   - clona ou reutiliza os datasets necessários;
   - processa os dados de QA e protocolos clínicos;
   - extrai texto dos PDFs dos protocolos clínicos;
   - gera um JSON único de QAs e um JSON único de protocolos clínicos;
   - traduz os campos textuais dos QAs para pt-BR e grava uma cópia traduzida;
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

Observação: o primeiro build pode demorar bastante, principalmente por causa do backend, que baixa dependências grandes de IA e pacotes de suporte à execução em GPU Nvidia.

Depois de subir a aplicação, acompanhe os logs em tempo real com `docker compose logs -f` ou, usando o arquivo deste projeto, `docker compose -f app-docker-compose.yaml logs -f`:

```bash
docker compose -f app-docker-compose.yaml logs -f
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
- A tradução usa `Helsinki-NLP/opus-mt-tc-big-en-pt`, em lotes e com fragmentação de textos longos; quando houver uma GPU Nvidia compatível, o backend usa CUDA, caso contrário faz fallback para CPU.
- Uma execução pode terminar com status `error`; em cenários de falha de fallback interno, também pode aparecer `failed`.
- Os datasets são baixados automaticamente na primeira execução, mas também podem ser tratados manualmente conforme descrito em [backend/datasets/README.md](backend/datasets/README.md).
- Devido a restrições de hardware, o finetunning do modelo escolhido foi feito através de notebook no Google Colab. Os arquivos relacionados ao processo estão na pasta [backend/notebooks/](backend/notebooks/) e o modelo treinado foi disponibilizado como private no [HuggingFace](fiap-hospital-helper/hospital-helper-qwen2.5-1.5b).
