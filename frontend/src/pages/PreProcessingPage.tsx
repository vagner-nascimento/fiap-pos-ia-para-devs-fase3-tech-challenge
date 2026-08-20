import { useCallback } from "react";
import { startPreprocess } from "../api/preprocess";
import { usePreprocessPolling } from "../hooks/usePreprocessPolling";
import { preprocessStore, usePreprocessStore } from "../stores/preprocessStore";
import type { PreprocessDocument, StepStatus } from "../types/preprocess";
import "./PreProcessingPage.css";

function statusClassName(status: string): string {
  return `status-badge status-${status}`;
}

function stepStatusClassName(status: StepStatus): string {
  return `step-status step-${status}`;
}

function stepStatusLabel(status: StepStatus): string {
  const labels: Record<StepStatus, string> = {
    pending: "Pendente",
    in_progress: "Em andamento",
    completed: "ConcluÃ­do",
    error: "Erro",
  };
  return labels[status];
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

const STEP_NAMES: Record<string, string> = {
  one_download_datasets: "Download dos Datasets",
  two_data_extraction: "ExtraÃ§Ã£o de Dados",
  three_translating: "Curadoria - TraduÃ§Ã£o dos Dados",
};

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
                  <span>Atualizado em</span>
                  <strong>
                    {new Date(document.updated_date).toLocaleString("pt-BR")}
                  </strong>
                </div>
              </div>

              {document.error_message && (
                <div className="alert alert-error">
                  <strong>Erro geral:</strong> {document.error_message}
                </div>
              )}

              <div className="steps-container">
                <h3>Status dos Steps</h3>
                {Object.entries(document.steps).map(([stepKey, stepInfo]) => {
                  const stepCompletion = stepInfo.completion_percentage ?? 0;
                  return (
                    <div key={stepKey} className="step-item">
                      <div className="step-header">
                        <div>
                          <span className="step-name">
                            {STEP_NAMES[stepKey] || stepKey}
                          </span>
                          <span className="step-percent">
                            {formatPercentage(stepCompletion)}
                          </span>
                        </div>
                        <span className={stepStatusClassName(stepInfo.status)}>
                          {stepStatusLabel(stepInfo.status)}
                        </span>
                      </div>
                      {stepInfo.error_message && (
                        <div className="step-error">
                          <strong>Erro:</strong> {stepInfo.error_message}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              <div className="results-container">
                <h3>Resultados</h3>
                <div className="results-grid">
                  <div className="result-group">
                    <h4>QAs</h4>
                    <div className="result-item">
                      <span>Total de registros</span>
                      <strong>
                        {document.results.qas_count.toLocaleString("pt-BR")}
                      </strong>
                    </div>
                    <div className="result-item">
                      <span>Arquivo Train (EN)</span>
                      <strong>
                        {document.results.qas_train_path || "Não gerado"}
                      </strong>
                    </div>
                    <div className="result-item">
                      <span>Arquivo Train (PT-BR)</span>
                      <strong>
                        {document.results.qas_train_pt_br_path || "Não gerado"}
                      </strong>
                    </div>
                  </div>
                  <div className="result-group">
                    <h4>Clinical Protocols</h4>
                    <div className="result-item">
                      <span>Total de registros</span>
                      <strong>
                        {document.results.clinical_protocols_count.toLocaleString(
                          "pt-BR",
                        )}
                      </strong>
                    </div>
                    <div className="result-item">
                      <span>Arquivo RAG</span>
                      <strong>
                        {document.results.clinical_protocols_rag_path || "Não gerado"}
                      </strong>
                    </div>
                  </div>
                </div>
              </div>

              <div>
                <div className="status-item">
                  <span>ConclusÃ£o — {formatPercentage(document.completion_percentage)}</span>
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
              Nenhuma execuÃ§Ã£o iniciada. Clique em &quot;Iniciar preprocessamento&quot;
              para comeÃ§ar.
            </p>
          )}
        </div>
      </section>
    </div>
  );
}
