import type { CurationSourceStats, Results } from "../../types/preprocess";

interface Props {
  results: Results;
}

const sourceLabels: Record<string, string> = {
  pubmedqa: "PubMedQA",
  medquad: "MedQuAD",
  clinical_protocols: "Protocolos clínicos",
  pcdt: "PCDT",
};

function formatNumber(value: number): string {
  return value.toLocaleString("pt-BR");
}

function formatReason(reason: string): string {
  return reason
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function SourceRow({ stats }: { stats: CurationSourceStats }) {
  const reasons = Object.entries(stats.rejection_reasons);

  return (
    <div className="curation-source">
      <div className="curation-source-header">
        <strong>{sourceLabels[stats.source] || stats.source}</strong>
        <span>{formatNumber(stats.input)} entradas</span>
      </div>
      <div className="curation-source-metrics">
        <span className="curation-accepted">{formatNumber(stats.accepted)} aceitos</span>
        <span className="curation-rejected">{formatNumber(stats.rejected)} rejeitados</span>
      </div>
      {reasons.length > 0 && (
        <div className="curation-reasons">
          {reasons.map(([reason, count]) => (
            <span key={reason} className="curation-reason">
              {formatReason(reason)}: {formatNumber(count)}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export function CurationReport({ results }: Props) {
  const report = results.curation;

  return (
    <section className="curation-report" aria-labelledby="curation-report-title">
      <div className="curation-report-heading">
        <div>
          <h3 id="curation-report-title">Relatório da Curadoria</h3>
          <p>Critérios aplicados durante a preparação dos datasets.</p>
        </div>
        {report && <span className="curation-version">{report.criteria_version}</span>}
      </div>

      {report ? (
        <>
          <div className="curation-summary">
            <div className="curation-summary-item">
              <span>Total avaliado</span>
              <strong>{formatNumber(report.accepted + report.rejected)}</strong>
            </div>
            <div className="curation-summary-item accepted">
              <span>Registros aceitos</span>
              <strong>{formatNumber(report.accepted)}</strong>
            </div>
            <div className="curation-summary-item rejected">
              <span>Registros rejeitados</span>
              <strong>{formatNumber(report.rejected)}</strong>
            </div>
          </div>
          <div className="curation-sources">
            {Object.values(report.sources).map((stats) => (
              <SourceRow key={stats.source} stats={stats} />
            ))}
          </div>
          {results.curation_report_path && (
            <p className="curation-path">Relatório: {results.curation_report_path}</p>
          )}
        </>
      ) : (
        <p className="curation-empty">
          O relatório de curadoria será disponibilizado quando a extração for concluída.
        </p>
      )}
    </section>
  );
}
