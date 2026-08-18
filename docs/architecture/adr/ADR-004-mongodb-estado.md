# ADR-004 — MongoDB como banco de estado do processamento

**Status:** Aceito  
**Data:** 2026-08-18  
**Contexto:** Projeto FIAP POS IA Fase 3 — Rastreamento de estado das pipelines de pré-processamento e fine-tuning  
**Decisores:** Equipe do projeto  

---

## Contexto

As pipelines de pré-processamento e fine-tuning são tarefas de longa duração (minutos a horas) executadas em background. O sistema precisa:

- Persistir o estado das tarefas (status, progresso, resultados, erros) para que o frontend possa fazer polling;
- Armazenar documentos com estrutura variável (steps com sub-documentos, listas de `loss_history`, métricas de treino);
- Rastrear múltiplas execuções independentes (cada execução gera um documento com `_id` único);
- Ser facilmente executável via Docker sem configuração complexa.

## Decisão

Utilizamos **MongoDB** como banco de dados para persistência do estado das pipelines, acessado via **pymongo**.

### Coleções utilizadas

| Coleção | Finalidade |
|---|---|
| `preprocess` | Documentos de rastreamento do pré-processamento (steps, progresso, resultados) |
| `fine_tunning` | Documentos de rastreamento do fine-tuning (epochs, loss, métricas, caminhos de saída) |

### Exemplo de documento `preprocess`

```json
{
  "_id": "...",
  "status": "completed",
  "rag_percent": 0.5,
  "completion_percentage": 100.0,
  "steps": {
    "one_download_datasets": { "status": "completed", "completion_percentage": 100 },
    "two_data_extraction": { "status": "completed", "completion_percentage": 100 },
    "three_translating": { "status": "completed", "completion_percentage": 100 }
  },
  "results": {
    "QAs": { "train_data": 4500, "rag_data": 500 },
    "clinical_protocols": { "train_data": 120, "rag_data": 15 }
  },
  "updated_date": "2026-08-18T12:00:00Z"
}
```

## Justificativa

| Critério | MongoDB | PostgreSQL | SQLite | Redis |
|---|---|---|---|---|
| Schema flexível | ✅ | ❌ (requer migrations) | ❌ | ✅ |
| Sub-documentos aninhados | ✅ nativo | ❌ (JSON columns) | ❌ | ❌ |
| Lista de loss_history | ✅ array nativo | ❌ tabela extra | ❌ | ✅ |
| Docker-friendly | ✅ imagem oficial | ✅ | ✅ (arquivo) | ✅ |
| Persistência | ✅ com volume | ✅ | ✅ | ⚠️ (requer AOF) |
| Curva de aprendizado | Baixa | Média | Baixa | Baixa |

A natureza **document-oriented** do MongoDB se encaixa perfeitamente com os dados variáveis e aninhados dos documentos de rastreamento, eliminando a necessidade de ORM, migrations ou join tables.

## Alternativas consideradas

| Alternativa | Razão para não escolher |
|---|---|
| PostgreSQL | Schema rígido; sub-documentos e arrays requerem tabelas extras ou JSON columns; overhead de configuração |
| SQLite | Não adequado para acesso concorrente de background tasks; sem server mode |
| Redis | Volátil por padrão; sem consultas ad-hoc; mais adequado para cache |
| TinyDB (arquivo JSON) | Sem suporte a concorrência; não escalável |

## Consequências

**Positivas:**
- Schema flexível permite adicionar campos aos documentos sem migrations;
- Sub-documentos (steps, results, loss_history) são armazenados nativamente;
- `pymongo` é simples e direto; sem necessidade de ORM;
- Imagem Docker oficial `mongo:latest` facilita o setup.

**Negativas:**
- MongoDB não possui suporte nativo a transações ACID complexas (mitigado pelo modelo de documento único por execução);
- Maior footprint de memória vs SQLite ou Redis;
- Não há schema enforcement nativo (pode gerar inconsistências se não houver cuidado na camada de serviço).

**Neutras:**
- Os dados de rastreamento não são relacionais, tornando o modelo de documento a escolha natural.
