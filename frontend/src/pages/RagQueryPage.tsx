import { useState } from "react";
import type { FormEvent } from "react";
import { queryRagDatabase } from "../api/ragDatabase";
import type { RagDocumentResult, RagQueryResponse } from "../types/ragDatabase";
import "./RagQueryPage.css";

interface Props {
  lastPreprocessId?: string | null;
}

export function RagQueryPage({ lastPreprocessId }: Props) {
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(5);
  const [preprocessId, setPreprocessId] = useState(lastPreprocessId ?? "");
  const [similarityThreshold, setSimilarityThreshold] = useState<string>("");
  
  const [response, setResponse] = useState<RagQueryResponse | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showRawJson, setShowRawJson] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmedQuery = query.trim();

    if (!trimmedQuery) {
      setError("A consulta por texto é obrigatória");
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const thresholdVal = similarityThreshold.trim() !== ""
        ? parseFloat(similarityThreshold)
        : null;

      const res = await queryRagDatabase({
        query: trimmedQuery,
        top_k: topK,
        preprocess_id: preprocessId.trim() || null,
        similarity_threshold: thresholdVal !== null && !isNaN(thresholdVal) ? thresholdVal : null,
      });

      setResponse(res);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Erro ao consultar a base RAG";
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleReset = () => {
    setQuery("");
    setTopK(5);
    setPreprocessId(lastPreprocessId ?? "");
    setSimilarityThreshold("");
    setResponse(null);
    setError(null);
  };

  const renderSourceMetadata = (doc: RagDocumentResult) => {
    const sourceObj = doc.metadatas?.source;
    if (!sourceObj || typeof sourceObj !== "object") return null;

    const sourceName = sourceObj.source || sourceObj.name || "Fonte não informada";
    const sourceUrl = sourceObj.url;

    return (
      <div className="source-info">
        <strong>Origem:</strong> {sourceName}{" "}
        {sourceUrl && (
          <a href={sourceUrl} target="_blank" rel="noopener noreferrer">
            (Acessar Link)
          </a>
        )}
      </div>
    );
  };

  return (
    <div className="rag-query-page">
      <header className="page-header">
        <h1>RAG Query</h1>
        <p>
          Realize consultas semânticas por similaridade vetorial na base de conhecimento RAG
          e visualize os documentos mais relevantes retornados pelo backend.
        </p>
      </header>

      <section className="card">
        <form onSubmit={(e) => void handleSubmit(e)} className="query-form">
          <div className="query-input-group">
            <label htmlFor="rag-query-text">Consulta (Pergunta ou Termo Médico)</label>
            <input
              id="rag-query-text"
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              disabled={isSubmitting}
              placeholder="Ex: como tratar tuberculose?"
              autoFocus
            />
          </div>

          <div className="filters-grid">
            <div className="filter-item">
              <label htmlFor="rag-top-k">Resultados (top_k)</label>
              <input
                id="rag-top-k"
                type="number"
                min={1}
                max={50}
                value={topK}
                onChange={(e) => setTopK(parseInt(e.target.value, 10) || 5)}
                disabled={isSubmitting}
              />
            </div>

            <div className="filter-item">
              <label htmlFor="rag-preprocess-id">Filtrar por Preprocess ID (opcional)</label>
              <input
                id="rag-preprocess-id"
                type="text"
                value={preprocessId}
                onChange={(e) => setPreprocessId(e.target.value)}
                disabled={isSubmitting}
                placeholder="Cole o ID se quiser filtrar"
              />
            </div>

            <div className="filter-item">
              <label htmlFor="rag-threshold">Threshold Mínimo (opcional)</label>
              <input
                id="rag-threshold"
                type="number"
                step="0.05"
                min="-1"
                max="1"
                value={similarityThreshold}
                onChange={(e) => setSimilarityThreshold(e.target.value)}
                disabled={isSubmitting}
                placeholder="Ex: 0.2"
              />
            </div>
          </div>

          <div className="actions">
            <button
              type="submit"
              className="btn btn-primary"
              disabled={isSubmitting || !query.trim()}
            >
              {isSubmitting ? "Consultando..." : "Buscar no RAG"}
            </button>

            <button
              type="button"
              className="btn btn-secondary"
              onClick={handleReset}
              disabled={isSubmitting}
            >
              Limpar
            </button>
          </div>
        </form>

        {error && <div className="alert alert-error status-section">{error}</div>}

        {response && (
          <div className="status-section">
            <div className="results-header">
              <h3>
                Resultados para: <em>&quot;{response.query}&quot;</em>
              </h3>
              <span className="results-count">
                {response.total_results} {response.total_results === 1 ? "documento" : "documentos"}
              </span>
            </div>

            {response.documents.length === 0 ? (
              <p className="empty-state">Nenhum documento relevante encontrado para esta busca.</p>
            ) : (
              <div className="documents-list">
                {response.documents.map((doc) => {
                  const isQa = doc.source_type === "qas" || doc.dataset === "qas";
                  const scorePercent = (doc.similarity_score * 100).toFixed(1);

                  return (
                    <div key={doc.id} className="document-card">
                      <div className="card-header-bar">
                        <div className="card-badges">
                          <span className={`badge ${isQa ? "badge-qas" : "badge-clinical"}`}>
                            {isQa ? "QAs RAG" : "Protocolo Clínico"}
                          </span>

                          {doc.chunk_index != null && doc.chunk_total != null && (
                            <span className="badge badge-chunk">
                              Chunk {doc.chunk_index} / {doc.chunk_total}
                            </span>
                          )}
                        </div>

                        <div className="score-badge" title="Score de Similaridade">
                          <span>Similarity:</span>
                          <span className="score-value">
                            {doc.similarity_score.toFixed(4)} ({scorePercent}%)
                          </span>
                        </div>
                      </div>

                      {renderSourceMetadata(doc)}

                      <div className="content-box">{doc.content}</div>

                      <div className="card-footer-meta">
                        ID: {doc.id} | Preprocess: {doc.preprocess_id}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            <div style={{ marginTop: "24px" }}>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setShowRawJson(!showRawJson)}
                style={{ fontSize: "0.85rem", padding: "6px 12px" }}
              >
                {showRawJson ? "Ocultar JSON da API" : "Ver JSON Bruto da API"}
              </button>

              {showRawJson && (
                <div className="response-block" style={{ marginTop: "12px" }}>
                  <h3>Resposta da API (JSON)</h3>
                  <pre>{JSON.stringify(response, null, 2)}</pre>
                </div>
              )}
            </div>
          </div>
        )}

        {!response && !error && (
          <div className="status-section">
            <p className="empty-state">
              Digite uma consulta acima e clique em &quot;Buscar no RAG&quot; para visualizar os resultados.
            </p>
          </div>
        )}
      </section>
    </div>
  );
}
