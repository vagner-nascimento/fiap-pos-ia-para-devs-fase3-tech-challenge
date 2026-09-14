# ADR-019 — Compatibilização do InstructorEmbedding com Sentence-Transformers modernos e alinhamento de dimensão vetorial no RAG

**Status:** Aceito  
**Data:** 2026-09-13  
**Contexto:** Backend — Serviço de Geração e Consulta da Base RAG (`services/rag_database.py`)  
**Decisores:** Equipe do projeto  

---

## Contexto

A base de conhecimento RAG do projeto utiliza o modelo de embedding `hkunlp/instructor-base` por meio da classe `HuggingFaceInstructEmbeddings` da biblioteca `langchain-community`, que por sua vez encapsula o pacote `InstructorEmbedding`.

Após atualizações das dependências do ambiente Python (onde `sentence-transformers` foi instalado na versão `>=3.0.0` / `6.0.1`), as consultas à base RAG via `POST /rag-database/query` passaram a falhar com erro `500 Internal Server Error`, acompanhado dos seguintes sintomas nos logs:
1. `WARNING - INSTRUCTOR._target_device has been deprecated. Please use INSTRUCTOR.device instead.`
2. `AttributeError: 'INSTRUCTOR' object has no attribute '_text_length'` ao executar `embedding_model.embed_query(...)`.

Investigação detalhada revelou que a classe `INSTRUCTOR` herda de `SentenceTransformer`. Na versão 3.0 do `sentence-transformers`, a arquitetura interna foi refatorada: o método auxiliar `_text_length` foi removido da classe base e a propriedade `_target_device` foi descontinuada em favor de `device`. Como o pacote upstream `InstructorEmbedding` é legado e não recebeu novas versões, essa incompatibilidade causava a falha imediata da inferência de embeddings.

Adicionalmente, identificou-se que caso a base armazenada no MongoDB tivesse sido gerada sob o modelo de fallback (256 dimensões), o código de consulta anterior tentava recalcular síncronamente em runtime o embedding de todos os documentos (mais de 1.700 chunks) um a um, causando travamento da requisição HTTP por timeout (estimado em mais de 50 minutos na CPU).

## Decisão

Adotou-se uma estratégia em três partes no serviço [services/rag_database.py](../../../backend/src/services/rag_database.py) e no roteador [routers/rag_database.py](../../../backend/src/routers/rag_database.py):

1. **Monkeypatch Dinâmico de Compatibilidade (`_patch_instructor_compatibility`):**
   - Injeção controlada do método `_text_length` na classe `INSTRUCTOR` caso ausente, calculando o comprimento de sequências/dicionários de tokens conforme esperado pelo algoritmo de batching original.
   - Redirecionamento silencioso de `_target_device` diretamente para `self.device`, eliminando alertas de depreciação repetitivos a cada cálculo de vetor.

2. **Detecção Dinâmica da Dimensionalidade da Base (`database_embedding_dim`):**
   - Ao executar [query_rag_documents](../../../backend/src/services/rag_database.py), o sistema inspeciona uma amostra dos embeddings armazenados no MongoDB.
   - Se a base foi populada com o modelo determinístico de fallback (256 dimensões) e nenhum modelo alternativo foi solicitado explicitamente na requisição, a query utiliza o mesmo modelo de fallback (256d), garantindo compatibilidade matemática imediata e resposta em menos de 100 ms.
   - Quando a base é gerada com o modelo Instructor real (768 dimensões), a consulta automaticamente utiliza o modelo de 768 dimensões.

3. **Prevenção de Gargalo Síncrono e Melhoria de Observabilidade:**
   - Remoção do loop de recomputação massiva síncrona dentro da requisição HTTP de busca. Se um documento específico possuir embedding inválido ou divergente da query, atribui-se similaridade zero ($0.0$) a ele, impedindo travamentos do servidor.
   - Inclusão de `logger.exception` no roteador do FastAPI para registrar o traceback completo de eventuais falhas futuras.

## Justificativa

- **Isolamento de Impacto:** O `sentence-transformers` moderno (`>=3.0.0`) é compartilhado com a suite do Hugging Face. Forçar o downgrade para `sentence-transformers<3.0.0` forçaria o rebaixamento em cascata de `transformers`, `huggingface-hub` e `tokenizers`, arriscando quebrar o serviço de tradução médica Marian (`step_three_translation.py`) e exigindo regeneração do `uv.lock` e rebuild demorado de imagem Docker com PyTorch/CUDA.
- **Eficiência e Disponibilidade:** Elimina o risco de timeout de requisições HTTP na busca RAG, garantindo que consultas respondam em tempo hábil independentemente do estado em que a base foi indexada.
- **Suporte Total ao Modelo Oficial:** Permite utilizar o modelo oficial `hkunlp/instructor-base` (768 dimensões) sem falhas de runtime.

## Alternativas consideradas

| Alternativa | Razão para não escolher |
|---|---|
| Fixar `sentence-transformers<3.0.0` no `pyproject.toml` | Desencadeia rebaixamento em cascata de `transformers` e `huggingface-hub`, arriscando quebrar a etapa de tradução de laudos e exigindo rebuild completo do Docker (`uv.lock`). |
| Migrar imediatamente para `langchain-huggingface` | Exigiria adicionar nova dependência no projeto e refatorar a serialização dos vetores antes de testes extensivos na entrega da fase. |
| Manter apenas o modelo determinístico de fallback de 256d | Embora rápido, o modelo de hash não possui a capacidade semântica contextual avançada provida pelo modelo treinado `hkunlp/instructor-base`. |
| Recalcular documentos em runtime na requisição de busca | Inviável em produção: com 1.712 documentos a ~2s cada na CPU, a requisição levaria cerca de 57 minutos, estourando o timeout do gateway/cliente. |

## Consequências

**Positivas:**
- Resolução imediata do HTTP 500 em `POST /rag-database/query`.
- Geração de embeddings com `hkunlp/instructor-base` executada com sucesso e sem warnings de depreciação.
- Consultas com tempo de resposta sub-100ms quando alinhadas à base existente.
- Preservação intacta de todas as demais dependências do projeto (`transformers`, `torch`, `huggingface-hub`).

**Negativas:**
- O monkeypatch permanece no arquivo `rag_database.py` até uma eventual migração futura para bibliotecas de embeddings mais recentes (ex: `langchain-huggingface`).
