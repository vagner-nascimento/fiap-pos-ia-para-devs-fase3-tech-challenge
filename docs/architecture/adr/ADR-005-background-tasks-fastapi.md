# ADR-005 — Processamento assíncrono via FastAPI BackgroundTasks

**Status:** Aceito  
**Data:** 2026-08-18  
**Contexto:** Projeto FIAP POS IA Fase 3 — Execução das pipelines de longa duração sem bloquear a API  
**Decisores:** Equipe do projeto  

---

## Contexto

As pipelines de pré-processamento (download, extração, tradução) e fine-tuning (treinamento de LLM) são tarefas que levam de **minutos a horas** para completar. Se executadas de forma síncrona, a requisição HTTP ficaria bloqueada durante todo esse tempo, o que é inaceitável tanto do ponto de vista técnico (timeouts) quanto de experiência do usuário.

O sistema precisa:

1. Aceitar a requisição imediatamente e retornar uma resposta com o ID da tarefa;
2. Executar a pipeline em segundo plano, atualizando o estado no MongoDB conforme avança;
3. Permitir que o frontend faça polling do status via `GET /{resource}/{id}`.

## Decisão

Utilizamos o mecanismo nativo de **`BackgroundTasks`** do FastAPI para despachar as pipelines em background.

### Padrão adotado nos endpoints

```python
@router.post("/")
async def preprocess_endpoint(
    request: PreprocessRequest,
    background_tasks: BackgroundTasks
):
    document = create_preprocess_document()
    background_tasks.add_task(preprocess_data_background, document["_id"])
    return document  # retorna imediatamente com status "pending"
```

### Fluxo de estado

```
pending → in_progress → completed
                      ↘ error / failed
```

O MongoDB é o meio de comunicação entre a background task e o endpoint de consulta. A task atualiza o documento a cada step concluído; o frontend faz polling de `GET /preprocess/{id}`.

## Justificativa

| Critério | BackgroundTasks | Celery + Redis | asyncio Tasks | Thread Pool |
|---|---|---|---|---|
| Complexidade de setup | Mínima (built-in) | Alta (broker, worker) | Média | Baixa |
| Dependências externas | Nenhuma | Redis/RabbitMQ + Celery | Nenhuma | Nenhuma |
| Adequado para CPU-bound | ⚠️ (mesma thread async) | ✅ | ❌ | ✅ |
| Adequado para I/O-bound | ✅ | ✅ | ✅ | ✅ |
| Escopo do projeto | ✅ (1 worker) | ❌ (overengineering) | ✅ | ✅ |

> **Nota:** As pipelines envolvem operações de I/O (download de datasets, leitura/escrita de arquivos, consultas ao MongoDB) intercaladas com CPU-bound intenso (tradução, treinamento). Para o escopo de um único worker do projeto, `BackgroundTasks` é suficiente.

## Alternativas consideradas

| Alternativa | Razão para não escolher |
|---|---|
| Celery + Redis | Adiciona dois serviços extras (broker e worker); overengineering para um único usuário |
| FastAPI `asyncio.create_task` | Não integrado com o request lifecycle do FastAPI; risco de tasks órfãs |
| Endpoint síncrono (timeout longo) | Impraticável: HTTP timeout em minutos a horas |
| WebSocket com streaming | Mais complexo de implementar e manter; overkill para progresso em polling |

## Consequências

**Positivas:**
- Zero dependências adicionais além do próprio FastAPI;
- Implementação simples e de fácil compreensão;
- Suporte nativo ao padrão de injeção de dependência do FastAPI.

**Negativas:**
- Se o processo Uvicorn reiniciar durante a execução, a task é perdida (sem retry automático);
- Não suporta múltiplos workers de forma nativa (limite para escala horizontal);
- Tasks CPU-bound muito intensas podem impactar o loop de eventos do Uvicorn.

**Neutras:**
- O design com `preprocess_id` e `fine_tunning_id` no MongoDB viabiliza retomada manual de uma execução interrompida, se necessário.
