import type { Results } from "../../types/preprocess";

interface Props {
  results: Results;
}

export function ProcessResults({ results }: Props) {
  return (
    <div className="results-container">
      <h3>Resultados</h3>
      <div className="results-grid">
        <div className="result-group">
          <h4>QAs</h4>
          <div className="result-item">
            <span>Total de registros</span>
            <strong>{results.qas_count.toLocaleString("pt-BR")}</strong>
          </div>
          <div className="result-item">
            <span>Arquivo Train (EN)</span>
            <strong>{results.qas_train_path || "Não gerado"}</strong>
          </div>
          <div className="result-item">
            <span>Arquivo Train (PT-BR)</span>
            <strong>{results.qas_train_pt_br_path || "Não gerado"}</strong>
          </div>
        </div>
        <div className="result-group">
          <h4>Clinical Protocols</h4>
          <div className="result-item">
            <span>Total de registros</span>
            <strong>
              {results.clinical_protocols_count.toLocaleString("pt-BR")}
            </strong>
          </div>
          <div className="result-item">
            <span>Arquivo RAG</span>
            <strong>
              {results.clinical_protocols_rag_path || "Não gerado"}
            </strong>
          </div>
        </div>
      </div>
    </div>
  );
}
