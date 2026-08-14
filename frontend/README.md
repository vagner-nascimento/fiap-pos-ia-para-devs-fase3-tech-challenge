# FIAP POS IA - Frontend

Interface web em React + TypeScript (Vite) para iniciar e acompanhar o pre-processamento dos datasets medicos via API REST do backend. A tela principal mostra o progresso em tempo real com polling automatico.

## Sumario

- Visao geral
- Arquitetura
- Pre-requisitos
- Configuracao
- Como subir a aplicacao
- Fluxo da interface
- Integracao com a API
- Estrutura do projeto

## Visao geral

O frontend permite:

1. configurar o percentual RAG;
2. iniciar o pre-processamento;
3. acompanhar o progresso com polling a cada 5 segundos;
4. visualizar os resultados separados para `QAs` e `clinical_protocols`.

A aplicacao e uma SPA servida pelo Vite em desenvolvimento e pelo nginx em producao.

## Arquitetura

```text
src/
|-- main.tsx
|-- App.tsx
|-- components/
|   `-- Layout.tsx
|-- pages/
|   `-- PreProcessingPage.tsx
|-- api/
|   |-- client.ts
|   `-- preprocess.ts
|-- hooks/
|   `-- usePreprocessPolling.ts
`-- types/
    `-- preprocess.ts
```

## Pre-requisitos

| Requisito | Versao minima | Observacao |
|-----------|---------------|------------|
| Node.js | 20+ | Usado no Dockerfile |
| npm | - | Gerenciador de dependencias |
| Backend | - | API FastAPI rodando em `http://localhost:3000` |

### Dependencias npm

Definidas em `package.json`:

| Pacote | Uso |
|--------|-----|
| `react` / `react-dom` | Interface de usuario |
| `vite` | Bundler e dev server |
| `@vitejs/plugin-react` | Suporte a React no Vite |
| `typescript` | Tipagem estatica |

## Configuracao

Copie o arquivo de exemplo e ajuste conforme seu ambiente:

```bash
cp .env.example .env
```

| Variavel | Descricao | Padrao |
|----------|-----------|--------|
| `VITE_BACKEND_URL` | URL base da API do backend | `http://localhost:3000` |

## Como subir a aplicacao

### Opcao 1 - Docker Compose

```bash
docker compose -f app-docker-compose.yaml up --build -d
```

Servicos:

- Frontend: `http://localhost:8080`
- Backend: `http://localhost:3000`

### Opcao 2 - Desenvolvimento local

1. Garanta que o backend esteja rodando.
2. Instale as dependencias:

   ```bash
   cd frontend
   npm install
   ```

3. Inicie o dev server:

   ```bash
   npm run dev
   ```

4. Acesse a aplicacao em `http://localhost:5173`.

### Build de producao

```bash
npm run build
npm run preview
```

## Fluxo da interface

Quando o usuario clica em Iniciar preprocessamento:

```mermaid
flowchart TD
    A[Usuario define rag_percent] --> B[Clica em Iniciar]
    B --> C[POST /preprocess]
    C --> D[Exibe documento retornado]
    D --> E[Polling a cada 5s]
    E --> F{GET /preprocess/id}
    F -->|created / in_progress| E
    F -->|completed / error| G[Para polling]
    G --> H[Exibe resultado final]
```

### Elementos da tela

| Elemento | Descricao |
|----------|-----------|
| Slider RAG percent | Percentual destinado ao RAG |
| Botao Iniciar | Dispara o preprocessamento |
| Botao Limpar | Reseta o estado da tela |
| Status badge | Mostra o status atual da execucao |
| Contadores | Exibe `train_data` e `rag_data` em pt-BR |
| Barra de progresso | Mostra `completion_percentage` |
| Resposta da API | JSON bruto retornado pelo backend |

## Integracao com a API

O frontend consome os endpoints do backend:

| Metodo | Endpoint | Uso |
|--------|----------|-----|
| `POST` | `/preprocess/` | Inicia a execucao |
| `GET` | `/preprocess/{id}` | Faz polling de progresso |

### Status terminais

O polling encerra automaticamente quando a execucao atinge um status terminal.

| Status | Significado |
|--------|-------------|
| `completed` | Processamento concluido com sucesso |
| `error` | Falha no processamento |

## Estrutura do projeto

```text
frontend/
|-- Dockerfile
|-- nginx.conf
|-- package.json
|-- package-lock.json
|-- .env.example
|-- vite.config.ts
|-- index.html
`-- src/
```

## RAG Generation

O frontend tambem contem a tela de `RAG Generation`, que faz uma chamada sincrona para `POST /rag-database/`.

### Fluxo

```mermaid
flowchart TD
    A[Usuario informa preprocess_id] --> B[Clica em Gerar base RAG]
    B --> C[POST /rag-database]
    C --> D[Backend valida preprocess concluido]
    D --> E[Lê os JSONs preprocessados]
    E --> F[Normaliza metadados e gera embeddings]
    F --> G[Persiste os documentos em MongoDB]
    G --> H[Exibe resposta final na tela]
```

### Elementos da tela de RAG Generation

| Elemento | Descricao |
|----------|-----------|
| Campo ID | Recebe o `preprocess_id` concluido |
| Botao Gerar base RAG | Dispara a geracao sincrona |
| Botao Limpar | Reseta o formulario e a resposta |
| Resumo final | Mostra `batch_id`, contagens e modelo usado |
| Resposta da API | JSON bruto retornado pelo backend |
