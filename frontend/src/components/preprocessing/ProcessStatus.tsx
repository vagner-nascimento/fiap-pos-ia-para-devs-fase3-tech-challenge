import { useState } from "react";
import type { PreprocessDocument } from "../../types/preprocess";

interface Props {
  document: PreprocessDocument;
}

function statusClassName(status: string): string {
  return `status-badge status-${status}`;
}

export function formatPercentage(value: number): string {
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

export function ProcessStatus({ document }: Props) {
  const [isIdCopied, setIsIdCopied] = useState(false);

  const handleCopyId = async () => {
    try {
      await navigator.clipboard.writeText(document.id);
      setIsIdCopied(true);
      window.setTimeout(() => setIsIdCopied(false), 2000);
    } catch {
      setIsIdCopied(false);
    }
  };

  return (
    <>
      <div className="status-grid">
        <div className="status-item">
          <span>ID</span>
          <button
            type="button"
            className="copy-id-button"
            onClick={() => void handleCopyId()}
            title="Copiar ID do preprocessamento"
            aria-label="Copiar ID do preprocessamento"
          >
            {isIdCopied ? "Copiado" : document.id}
          </button>
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

      <div>
        <div className="status-item">
          <span>Conclusão — {formatPercentage(document.completion_percentage)}</span>
          <div className="progress-bar" aria-hidden="true">
            <div
              className="progress-bar-fill"
              style={{ width: `${document.completion_percentage}%` }}
            />
          </div>
        </div>
      </div>
    </>
  );
}
