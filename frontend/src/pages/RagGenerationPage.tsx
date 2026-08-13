import { useCallback, useEffect, useMemo, useState } from "react";
import { startRagGeneration } from "../api/ragDatabase";
import { useRagGenerationPolling } from "../hooks/useRagGenerationPolling";
import type { RagGenerationDocument } from "../types/ragDatabase";
import "./RagGenerationPage.css";

function statusClassName(status: string): string {
  return `status-badge status-${status}`;
}

function formatPercentage(value: number): string {
  if (!Number.isFinite(value)) {
    return "0%";
  }

  if (value < 1) {
    return `${value.toFixed(2)}%`;
  }

  if (value < 10) {
    return `${value.toFixed(1)}%`;
  }

  return `${value.toFixed(0)}%`;
}

function getDocumentId(document: RagGenerationDocument): string {
  return document.id || document._id || "";
}

interface Props {
  lastPreprocessId: string | null;
}

export function RagGenerationPage({ lastPreprocessId }: Props) {
  const [useLastPreprocess, setUseLastPreprocess] = useState(lastPreprocessId !== null);
  const [customPreprocessId, setCustomPreprocessId] = useState("");

  const [document, setDocument] = useState<RagGenerationDocument | null>(null);
  const [pollingDocId, setPollingDocId] = useState<string | null>(null);
  const [isStarting, setIsStarting] = useState(false);
  const [isPolling, setIsPolling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setUseLastPreprocess(lastPreprocessId !== null);
  }, [lastPreprocessId]);

  const effectivePreprocessId = useLastPreprocess ? lastPreprocessId : customPreprocessId.trim();

  const handleStart = async () => {
    setError(null);
    setIsStarting(true);

    if (!effectivePreprocessId) {
      setError("ID do preprocessamento é obrigatório");
      setIsStarting(false);
      return;
    }

    try {
      const created = await startRagGeneration({
        preprocess_id: effectivePreprocessId,
      });
      setDocument(created);
      setPollingDocId(getDocumentId(created));
      setIsPolling(true);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Erro ao iniciar geração da base RAG";
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

  const handleUpdate = useCallback((updated: RagGenerationDocument) => {
    setDocument(updated);
  }, []);

  const handlePollingError = useCallback((message: string) => {
    setError(message);
  }, []);

  const handlePollingComplete = useCallback(() => {
    setIsPolling(false);
    setPollingDocId(null);
  }, []);

  useRagGenerationPolling({
    docId: pollingDocId,
    enabled: isPolling,
    onUpdate: handleUpdate,
    onError: handlePollingError,
    onComplete: handlePollingComplete,
  });

  const sourceHint = useMemo(() => {
    if (useLastPreprocess) {
      return lastPreprocessId ? `(${lastPreprocessId})` : "";
    }
    return "";
  }, [lastPreprocessId, useLastPreprocess]);

  return (
    <div className="rag-generation-page">
      <header className="page-header">
        <h1>RAG Generation</h1>
        <p>
          Inicie a geracao da base RAG e acompanhe o progresso em tempo real, com
          atualizacoes automaticas a cada 5 segundos.
        </p>
      </header>

      <section className="card">
        <div className="form-section">
          <h3>ID do Preprocessamento</h3>
          <div className="radio-group">
            <label className="radio-label">
              <input
                type="radio"
                name="rag-preprocess-source"
                checked={useLastPreprocess}
                onChange={() => setUseLastPreprocess(true)}
                disabled={isStarting || isPolling}
              />
              Usar ultimo preprocessamento
              {sourceHint && <span className="preprocess-id-hint">{sourceHint}</span>}
            </label>
            <label className="radio-label">
              <input
                type="radio"
                name="rag-preprocess-source"
                checked={!useLastPreprocess}
                onChange={() => setUseLastPreprocess(false)}
                disabled={isStarting || isPolling}
              />
              Informar ID manualmente
            </label>
          </div>

          {!useLastPreprocess && (
            <div className="form-row">
              <label htmlFor="rag-preprocess-id">ID do Preprocessamento</label>
              <input
                id="rag-preprocess-id"
                type="text"
                value={customPreprocessId}
                onChange={(event) => setCustomPreprocessId(event.target.value)}
                disabled={isStarting || isPolling}
                placeholder="Cole o ID do preprocessamento aqui"
              />
            </div>
          )}

          {!useLastPreprocess && !lastPreprocessId && !customPreprocessId && (
            <div className="alert alert-warning">
              Nenhum ID de preprocessamento disponivel. Volte para a tela de Pre
              Processing para criar um.
            </div>
          )}
        </div>

        <div className="actions">
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => void handleStart()}
            disabled={isStarting || isPolling || !effectivePreprocessId}
          >
            {isStarting ? "Iniciando..." : "Gerar base RAG"}
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
              Atualizando status a cada 5 segundos...
            </div>
          )}

          {document ? (
            <>
              <div className="status-grid">
                <div className="status-item">
                  <span>ID</span>
                  <strong>{getDocumentId(document)}</strong>
                </div>
                <div className="status-item">
                  <span>Batch ID</span>
                  <strong>{document.batch_id}</strong>
                </div>
                <div className="status-item">
                  <span>Preprocess ID</span>
                  <strong>{document.preprocess_id}</strong>
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
                  <span>Progresso</span>
                  <strong>{formatPercentage(document.completion_percentage)}</strong>
                </div>
                <div className="status-item">
                  <span>Embedding Model</span>
                  <strong>{document.embedding_model}</strong>
                </div>
                <div className="status-item">
                  <span>Splitter</span>
                  <strong>{document.splitter_name}</strong>
                </div>
                <div className="status-item">
                  <span>Chunk Size</span>
                  <strong>{document.splitter_chunk_size}</strong>
                </div>
                <div className="status-item">
                  <span>Chunk Overlap</span>
                  <strong>{document.splitter_chunk_overlap}</strong>
                </div>
                <div className="status-item">
                  <span>QAs Documents</span>
                  <strong>{document.qas_documents.toLocaleString("pt-BR")}</strong>
                </div>
                <div className="status-item">
                  <span>Clinical Docs</span>
                  <strong>
                    {document.clinical_protocol_documents.toLocaleString("pt-BR")}
                  </strong>
                </div>
                <div className="status-item">
                  <span>Total Documents</span>
                  <strong>{document.total_documents.toLocaleString("pt-BR")}</strong>
                </div>
                <div className="status-item">
                  <span>Atualizado em</span>
                  <strong>
                    {new Date(document.updated_date).toLocaleString("pt-BR")}
                  </strong>
                </div>
              </div>

              {document.error_message && (
                <div className="alert alert-error">
                  <strong>Erro:</strong> {document.error_message}
                </div>
              )}

              <div>
                <div className="status-item">
                  <span>Conclusão - {formatPercentage(document.completion_percentage)}</span>
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
              Nenhuma execucao iniciada. Clique em &quot;Gerar base RAG&quot; para
              comecar.
            </p>
          )}
        </div>
      </section>
    </div>
  );
}
