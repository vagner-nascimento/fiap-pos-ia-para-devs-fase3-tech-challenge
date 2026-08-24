import type { RagDocumentResult, RagQueryResponse } from "../../types/ragDatabase";

interface Props {
  response: RagQueryResponse;
  showRawJson: boolean;
  onToggleRawJson: () => void;
}

function SourceMetadata({ document }: { document: RagDocumentResult }) {
  const sourceObj = document.metadatas?.source;
  if (!sourceObj || typeof sourceObj !== "object") {
    return null;
  }

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
}

function RagDocumentCard({ document }: { document: RagDocumentResult }) {
  const isQa = document.source_type === "qas" || document.dataset === "qas";
  const scorePercent = (document.similarity_score * 100).toFixed(1);

  return (
    <div className="document-card">
      <div className="card-header-bar">
        <div className="card-badges">
          <span className={`badge ${isQa ? "badge-qas" : "badge-clinical"}`}>
            {isQa ? "QAs RAG" : "Protocolo Clínico"}
          </span>

          {document.chunk_index != null && document.chunk_total != null && (
            <span className="badge badge-chunk">
              Chunk {document.chunk_index} / {document.chunk_total}
            </span>
          )}
        </div>

        <div className="score-badge" title="Score de Similaridade">
          <span>Similarity:</span>
          <span className="score-value">
            {document.similarity_score.toFixed(4)} ({scorePercent}%)
          </span>
        </div>
      </div>

      <SourceMetadata document={document} />
      <div className="content-box">{document.content}</div>
      <div className="card-footer-meta">
        ID: {document.id} | Preprocess: {document.preprocess_id}
      </div>
    </div>
  );
}

export function RagQueryResults({
  response,
  showRawJson,
  onToggleRawJson,
}: Props) {
  return (
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
          {response.documents.map((document) => (
            <RagDocumentCard key={document.id} document={document} />
          ))}
        </div>
      )}

      <div style={{ marginTop: "24px" }}>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={onToggleRawJson}
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
  );
}
