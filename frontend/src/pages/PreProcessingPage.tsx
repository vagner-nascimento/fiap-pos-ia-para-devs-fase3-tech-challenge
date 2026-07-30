import { useCallback, useState } from "react";
import { startPreprocess } from "../api/preprocess";
import { usePreprocessPolling } from "../hooks/usePreprocessPolling";
import type { PreprocessDocument } from "../types/preprocess";
import "./PreProcessingPage.css";

function statusClassName(status: string): string {
  return `status-badge status-${status}`;
}

export function PreProcessingPage() {
  const [ragPercent, setRagPercent] = useState(0.5);
  const [document, setDocument] = useState<PreprocessDocument | null>(null);
  const [pollingDocId, setPollingDocId] = useState<string | null>(null);
  const [isStarting, setIsStarting] = useState(false);
  const [isPolling, setIsPolling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleStart = async () => {
    setError(null);
    setIsStarting(true);

    try {
      const created = await startPreprocess({ rag_percent: ragPercent });
      setDocument(created);
      setPollingDocId(created.id);
      setIsPolling(true);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Erro ao iniciar preprocessamento";
      setError(message);
    } finally {
      setIsStarting(false);
    }
  };

  const handleReset = () => {
    setDocument(null);
    setPollingDocId(null);
    setIsPolling(false);
    setError(null);
  };

  const handleUpdate = useCallback((updated: PreprocessDocument) => {
    setDocument(updated);
  }, []);

  const handlePollingError = useCallback((message: string) => {
    setError(message);
  }, []);

  const handlePollingComplete = useCallback(() => {
    setIsPolling(false);
    setPollingDocId(null);
  }, []);

  usePreprocessPolling({
    docId: pollingDocId,
    enabled: isPolling,
    onUpdate: handleUpdate,
    onError: handlePollingError,
    onComplete: handlePollingComplete,
  });

  return (
    <div className="preprocessing-page">
      <header className="page-header">
        <h1>Pre Processing</h1>
        <p>
          Inicie o preprocessamento dos datasets PubMedQA e MedQuAD e acompanhe
          o progresso em tempo real.
        </p>
      </header>

      <section className="card">
        <div className="form-row">
          <label htmlFor="rag-percent">RAG percent</label>
          <input
            id="rag-percent"
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={ragPercent}
            onChange={(event) => setRagPercent(Number(event.target.value))}
            disabled={isStarting || isPolling}
          />
          <span className="rag-value">{ragPercent.toFixed(2)}</span>
        </div>

        <div className="actions">
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => void handleStart()}
            disabled={isStarting || isPolling}
          >
            {isStarting ? "Iniciando..." : "Iniciar preprocessamento"}
          </button>

          {document && (
            <button
              type="button"
              className="btn btn-secondary"
              onClick={handleReset}
              disabled={isStarting}
            >
              Limpar
            </button>
          )}
        </div>

        {error && <div className="alert alert-error status-section">{error}</div>}

        <div className="status-section">
          {isPolling && (
            <div className="polling-indicator">
              <span className="polling-dot" aria-hidden="true" />
              Atualizando status a cada 2 segundos...
            </div>
          )}

          {document ? (
            <>
              <div className="status-grid">
                <div className="status-item">
                  <span>ID</span>
                  <strong>{document.id}</strong>
                </div>
                <div className="status-item">
                  <span>Status</span>
                  <strong>
                    <span className={statusClassName(document.status)}>
                      {document.status}
                    </span>
                  </strong>
                </div>
                <div className="status-item">
                  <span>Train data</span>
                  <strong>{document.train_data.toLocaleString("pt-BR")}</strong>
                </div>
                <div className="status-item">
                  <span>RAG data</span>
                  <strong>{document.rag_data.toLocaleString("pt-BR")}</strong>
                </div>
                <div className="status-item">
                  <span>Atualizado em</span>
                  <strong>
                    {new Date(document.updated_date).toLocaleString("pt-BR")}
                  </strong>
                </div>
              </div>

              <div>
                <div className="status-item">
                  <span>Conclusão — {document.completion_percentage.toFixed(1)}%</span>
                  <div className="progress-bar" aria-hidden="true">
                    <div
                      className="progress-bar-fill"
                      style={{ width: `${document.completion_percentage}%` }}
                    />
                  </div>
                </div>
              </div>

              <div className="response-block">
                <h3>Resposta da API</h3>
                <pre>{JSON.stringify(document, null, 2)}</pre>
              </div>
            </>
          ) : (
            <p className="empty-state">
              Nenhuma execução iniciada. Clique em &quot;Iniciar preprocessamento&quot;
              para começar.
            </p>
          )}
        </div>
      </section>
    </div>
  );
}
