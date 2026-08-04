import { useCallback, useEffect, useState } from "react";
import { startFineTuning } from "../api/fineTuning";
import { useFineTuningPolling } from "../hooks/useFineTuningPolling";
import type { FineTuningDocument } from "../types/fineTuning";
import "./FineTuningPage.css";

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

function formatLoss(value: number | null): string {
  if (value === null) {
    return "-";
  }
  return value.toFixed(4);
}

interface Props {
  lastPreprocessId: string | null;
}

export function FineTuningPage({ lastPreprocessId }: Props) {
  const [useLastPreprocess, setUseLastPreprocess] = useState(lastPreprocessId !== null);
  const [customPreprocessId, setCustomPreprocessId] = useState("");
  const [includeClinicalProtocols, setIncludeClinicalProtocols] = useState(true);
  const [use4bit, setUse4bit] = useState(false);
  const [maxSeqLength, setMaxSeqLength] = useState(2048);
  const [numTrainEpochs, setNumTrainEpochs] = useState(1.0);
  const [perDeviceTrainBatchSize, setPerDeviceTrainBatchSize] = useState(1);
  const [gradientAccumulationSteps, setGradientAccumulationSteps] = useState(4);
  const [learningRate, setLearningRate] = useState(2e-4);
  const [warmupRatio, setWarmupRatio] = useState(0.03);
  const [loggingSteps, setLoggingSteps] = useState(5);
  const [seed, setSeed] = useState(3407);

  const [document, setDocument] = useState<FineTuningDocument | null>(null);
  const [pollingDocId, setPollingDocId] = useState<string | null>(null);
  const [isStarting, setIsStarting] = useState(false);
  const [isPolling, setIsPolling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setUseLastPreprocess(lastPreprocessId !== null);
  }, [lastPreprocessId]);

  const handleStart = async () => {
    setError(null);
    setIsStarting(true);

    const preprocessId = useLastPreprocess
      ? lastPreprocessId
      : customPreprocessId.trim();

    if (!preprocessId) {
      setError("ID do preprocessamento é obrigatório");
      setIsStarting(false);
      return;
    }

    try {
      const created = await startFineTuning({
        preprocess_id: preprocessId,
        include_clinical_protocols: includeClinicalProtocols,
        use_4bit: use4bit,
        max_seq_length: maxSeqLength,
        num_train_epochs: numTrainEpochs,
        per_device_train_batch_size: perDeviceTrainBatchSize,
        gradient_accumulation_steps: gradientAccumulationSteps,
        learning_rate: learningRate,
        warmup_ratio: warmupRatio,
        logging_steps: loggingSteps,
        seed: seed,
      });
      setDocument(created);
      setPollingDocId(created._id);
      setIsPolling(true);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Erro ao iniciar fine tuning";
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

  const handleUpdate = useCallback((updated: FineTuningDocument) => {
    setDocument(updated);
  }, []);

  const handlePollingError = useCallback((message: string) => {
    setError(message);
  }, []);

  const handlePollingComplete = useCallback(() => {
    setIsPolling(false);
    setPollingDocId(null);
  }, []);

  useFineTuningPolling({
    docId: pollingDocId,
    enabled: isPolling,
    onUpdate: handleUpdate,
    onError: handlePollingError,
    onComplete: handlePollingComplete,
  });

  const effectivePreprocessId = useLastPreprocess
    ? lastPreprocessId
    : customPreprocessId;

  return (
    <div className="fine-tuning-page">
      <header className="page-header">
        <h1>Fine Tuning</h1>
        <p>
          Inicie o fine tuning do modelo hospital helper e acompanhe o progresso
          em tempo real.
        </p>
      </header>

      <section className="card">
        {/* Preprocess ID Selection */}
        <div className="form-section">
          <h3>ID do Preprocessamento</h3>
          <div className="radio-group">
            <label className="radio-label">
              <input
                type="radio"
                name="preprocess-source"
                checked={useLastPreprocess}
                onChange={() => setUseLastPreprocess(true)}
                disabled={isStarting || isPolling}
              />
              Usar último preprocessamento
              {lastPreprocessId && (
                <span className="preprocess-id-hint">
                  ({lastPreprocessId})
                </span>
              )}
            </label>
            <label className="radio-label">
              <input
                type="radio"
                name="preprocess-source"
                checked={!useLastPreprocess}
                onChange={() => setUseLastPreprocess(false)}
                disabled={isStarting || isPolling}
              />
              Informar ID manualmente
            </label>
          </div>

          {!useLastPreprocess && (
            <div className="form-row">
              <label htmlFor="custom-preprocess-id">ID do Preprocessamento</label>
              <input
                id="custom-preprocess-id"
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
              Nenhum ID de preprocessamento disponível. Volte para a tela de Pre
              Processing para criar um.
            </div>
          )}
        </div>

        {/* Fine Tuning Parameters */}
        <div className="form-section">
          <h3>Parâmetros do Fine Tuning</h3>
          
          <div className="form-row">
            <label>
              <input
                type="checkbox"
                checked={includeClinicalProtocols}
                onChange={(event) => setIncludeClinicalProtocols(event.target.checked)}
                disabled={isStarting || isPolling}
              />
              Incluir protocolos clínicos no treino
            </label>
          </div>

          <div className="form-row">
            <label>
              <input
                type="checkbox"
                checked={use4bit}
                onChange={(event) => setUse4bit(event.target.checked)}
                disabled={isStarting || isPolling}
              />
              Usar quantização 4-bit (quando disponível)
            </label>
          </div>

          <div className="form-row">
            <label htmlFor="max-seq-length">Max Seq Length</label>
            <input
              id="max-seq-length"
              type="number"
              min={256}
              max={8192}
              step={256}
              value={maxSeqLength}
              onChange={(event) => setMaxSeqLength(Number(event.target.value))}
              disabled={isStarting || isPolling}
            />
          </div>

          <div className="form-row">
            <label htmlFor="num-train-epochs">Num Train Epochs</label>
            <input
              id="num-train-epochs"
              type="number"
              min={0.1}
              max={10}
              step={0.1}
              value={numTrainEpochs}
              onChange={(event) => setNumTrainEpochs(Number(event.target.value))}
              disabled={isStarting || isPolling}
            />
          </div>

          <div className="form-row">
            <label htmlFor="per-device-batch-size">Per Device Batch Size</label>
            <input
              id="per-device-batch-size"
              type="number"
              min={1}
              max={32}
              step={1}
              value={perDeviceTrainBatchSize}
              onChange={(event) => setPerDeviceTrainBatchSize(Number(event.target.value))}
              disabled={isStarting || isPolling}
            />
          </div>

          <div className="form-row">
            <label htmlFor="gradient-accumulation">Gradient Accumulation Steps</label>
            <input
              id="gradient-accumulation"
              type="number"
              min={1}
              max={32}
              step={1}
              value={gradientAccumulationSteps}
              onChange={(event) => setGradientAccumulationSteps(Number(event.target.value))}
              disabled={isStarting || isPolling}
            />
          </div>

          <div className="form-row">
            <label htmlFor="learning-rate">Learning Rate</label>
            <input
              id="learning-rate"
              type="number"
              min={1e-6}
              max={1e-2}
              step={1e-5}
              value={learningRate}
              onChange={(event) => setLearningRate(Number(event.target.value))}
              disabled={isStarting || isPolling}
            />
          </div>

          <div className="form-row">
            <label htmlFor="warmup-ratio">Warmup Ratio</label>
            <input
              id="warmup-ratio"
              type="number"
              min={0}
              max={1}
              step={0.01}
              value={warmupRatio}
              onChange={(event) => setWarmupRatio(Number(event.target.value))}
              disabled={isStarting || isPolling}
            />
          </div>

          <div className="form-row">
            <label htmlFor="logging-steps">Logging Steps</label>
            <input
              id="logging-steps"
              type="number"
              min={1}
              max={100}
              step={1}
              value={loggingSteps}
              onChange={(event) => setLoggingSteps(Number(event.target.value))}
              disabled={isStarting || isPolling}
            />
          </div>

          <div className="form-row">
            <label htmlFor="seed">Seed</label>
            <input
              id="seed"
              type="number"
              min={0}
              max={10000}
              step={1}
              value={seed}
              onChange={(event) => setSeed(Number(event.target.value))}
              disabled={isStarting || isPolling}
            />
          </div>
        </div>

        <div className="actions">
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => void handleStart()}
            disabled={isStarting || isPolling || !effectivePreprocessId}
          >
            {isStarting ? "Iniciando..." : "Iniciar fine tuning"}
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
                  <strong>{document._id}</strong>
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
                  <span>Device</span>
                  <strong>{document.device || "-"}</strong>
                </div>
                <div className="status-item">
                  <span>Dataset Size</span>
                  <strong>{document.dataset_size.toLocaleString("pt-BR")}</strong>
                </div>
                <div className="status-item">
                  <span>QAs Examples</span>
                  <strong>{document.qas_examples.toLocaleString("pt-BR")}</strong>
                </div>
                <div className="status-item">
                  <span>Clinical Protocol Examples</span>
                  <strong>{document.clinical_protocol_examples.toLocaleString("pt-BR")}</strong>
                </div>
                <div className="status-item">
                  <span>Current Step</span>
                  <strong>{document.current_step.toLocaleString("pt-BR")} / {document.estimated_total_steps.toLocaleString("pt-BR")}</strong>
                </div>
                <div className="status-item">
                  <span>Current Epoch</span>
                  <strong>{document.current_epoch ? document.current_epoch.toFixed(2) : "-"}</strong>
                </div>
                <div className="status-item">
                  <span>Current Loss</span>
                  <strong>{formatLoss(document.current_loss)}</strong>
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

              {/* Loss History */}
              {document.loss_history.length > 0 && (
                <div className="loss-history-container">
                  <h3>Histórico de Loss</h3>
                  <div className="loss-history-list">
                    {document.loss_history.slice(-10).map((entry, index) => (
                      <div key={index} className="loss-history-item">
                        <span className="loss-step">Step {entry.step}</span>
                        <span className="loss-epoch">
                          Epoch: {entry.epoch ? entry.epoch.toFixed(2) : "-"}
                        </span>
                        <span className="loss-value">
                          Loss: {entry.loss.toFixed(4)}
                        </span>
                        <span className="loss-timestamp">
                          {new Date(entry.timestamp).toLocaleTimeString("pt-BR")}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Training Metrics */}
              {Object.keys(document.training_metrics).length > 0 && (
                <div className="metrics-container">
                  <h3>Métricas de Treinamento</h3>
                  <div className="metrics-grid">
                    {Object.entries(document.training_metrics).map(([key, value]) => (
                      <div key={key} className="metric-item">
                        <span>{key}</span>
                        <strong>
                          {typeof value === "number" ? value.toFixed(4) : String(value)}
                        </strong>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="response-block">
                <h3>Resposta da API</h3>
                <pre>{JSON.stringify(document, null, 2)}</pre>
              </div>
            </>
          ) : (
            <p className="empty-state">
              Nenhuma execução iniciada. Clique em &quot;Iniciar fine tuning&quot;
              para começar.
            </p>
          )}
        </div>
      </section>
    </div>
  );
}
