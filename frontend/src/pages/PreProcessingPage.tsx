import { useCallback } from "react";
import { startPreprocess } from "../api/preprocess";
import { ApiResponseBlock } from "../components/preprocessing/ApiResponseBlock";
import { ProcessResults } from "../components/preprocessing/ProcessResults";
import { ProcessStatus } from "../components/preprocessing/ProcessStatus";
import { ProcessSteps } from "../components/preprocessing/ProcessSteps";
import { usePreprocessPolling } from "../hooks/usePreprocessPolling";
import { preprocessStore, usePreprocessStore } from "../stores/preprocessStore";
import type { PreprocessDocument, StepStatus } from "../types/preprocess";
import "./PreProcessingPage.css";

interface Props {
  onPreprocessComplete?: (id: string) => void;
}

export function PreProcessingPage({ onPreprocessComplete }: Props) {
  const { document, pollingDocId, isStarting, isPolling, error } =
    usePreprocessStore();

  const handleStart = async () => {
    preprocessStore.setStarting(true);

    try {
      const created = await startPreprocess({});
      preprocessStore.setStarted(created);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Erro ao iniciar preprocessamento";
      preprocessStore.setPollingError(message);
    } finally {
      preprocessStore.setStarting(false);
    }
  };

  const handleReset = () => {
    preprocessStore.reset();
  };

  const handleUpdate = useCallback((updated: PreprocessDocument) => {
    preprocessStore.updateDocument(updated);
  }, []);

  const handlePollingError = useCallback((message: string) => {
    preprocessStore.setPollingError(message);
  }, []);

  const handlePollingComplete = useCallback(
    (completedDocument: PreprocessDocument | null) => {
      preprocessStore.stopPolling();
      if (completedDocument?.status === "completed" && onPreprocessComplete) {
        onPreprocessComplete(completedDocument.id);
      }
    },
    [onPreprocessComplete],
  );

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
          Inicie o preprocessamento dos datasets PubMedQA, MedQuAD e protocolos
          clínicos da FHEMIG e acompanhe o progresso em tempo real.
        </p>
      </header>

      <section className="card">
        <div className="actions">
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => void handleStart()}
            disabled={isStarting || isPolling || document !== null}
          >
            {isStarting ? "Iniciando..." : "Iniciar preprocessamento"}
          </button>

          {document?.status === "completed" && (
            <button
              type="button"
              className="btn btn-secondary"
              onClick={handleReset}
              disabled={isStarting}
            >
              Iniciar Novo Processamento
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
              <ProcessStatus document={document} />
              <ProcessSteps steps={document.steps} />
              <ProcessResults results={document.results} />
              <ApiResponseBlock document={document} />
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
