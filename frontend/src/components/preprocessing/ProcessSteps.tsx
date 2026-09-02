import type { StepInfo, StepStatus } from "../../types/preprocess";
import { formatPercentage } from "./ProcessStatus";

interface Props {
  steps: Record<string, StepInfo>;
}

const STEP_NAMES: Record<string, string> = {
  one_download_datasets: "Download dos Datasets",
  two_data_extraction: "Extração de Dados",
  three_translating: "Curadoria - Tradução dos Dados",
  four_anonymization: "Anonimização dos Laudos Médicos",
};

function stepStatusClassName(status: StepStatus): string {
  return `step-status step-${status}`;
}

function stepStatusLabel(status: StepStatus): string {
  const labels: Record<StepStatus, string> = {
    pending: "Pendente",
    in_progress: "Em andamento",
    completed: "Concluído",
    error: "Erro",
  };
  return labels[status];
}

export function ProcessSteps({ steps }: Props) {
  return (
    <div className="steps-container">
      <h3>Status dos Steps</h3>
      {Object.entries(steps).map(([stepKey, stepInfo]) => {
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
  );
}
