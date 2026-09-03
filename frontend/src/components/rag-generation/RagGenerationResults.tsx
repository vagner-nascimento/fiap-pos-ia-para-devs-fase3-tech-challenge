import type { ReactNode } from "react";
import type { RagGenerationDocument } from "../../types/ragDatabase";

interface Props {
  document: RagGenerationDocument;
}

interface ResultCardProps {
  label: string;
  value: ReactNode;
}

function statusClassName(status: string): string {
  return `status-badge status-${status}`;
}

function formatDate(value?: string | null): string {
  if (!value) {
    return "-";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleString("pt-BR");
}

function ResultCard({ label, value }: ResultCardProps) {
  return (
    <div className="status-item">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export function RagGenerationResults({ document }: Props) {
  return (
    <>
      <div className="status-grid">
        <ResultCard label="ID" value={document.id} />
        <ResultCard label="Batch ID" value={document.batch_id} />
        <ResultCard label="Preprocess ID" value={document.preprocess_id} />
        <ResultCard
          label="Status"
          value={
            <span className={statusClassName(document.status)}>
              {document.status}
            </span>
          }
        />
        <ResultCard label="Embedding Model" value={document.embedding_model} />
        <ResultCard label="Splitter" value={document.splitter_name} />
        <ResultCard
          label="Chunk Size"
          value={String(document.splitter_chunk_size)}
        />
        <ResultCard
          label="Chunk Overlap"
          value={String(document.splitter_chunk_overlap)}
        />
        <ResultCard
          label="Arquivo de Protocolos Clínicos"
          value={document.clinical_protocols_rag_path}
        />
        <ResultCard
          label="Arquivo de Laudos Médicos"
          value={document.medical_reports_path}
        />
        <ResultCard
          label="Documentos Clínicos"
          value={document.clinical_protocol_documents.toLocaleString("pt-BR")}
        />
        <ResultCard
          label="Documentos de Laudos"
          value={document.medical_report_documents.toLocaleString("pt-BR")}
        />
        <ResultCard
          label="Total Documents"
          value={document.total_documents.toLocaleString("pt-BR")}
        />
        <ResultCard label="Atualizado em" value={formatDate(document.updated_date)} />
      </div>

      {document.preprocess_snapshot && (
        <div className="response-block">
          <h3>Preprocess Snapshot</h3>
          <pre>{JSON.stringify(document.preprocess_snapshot, null, 2)}</pre>
        </div>
      )}

      {document.error_message && (
        <div className="alert alert-error">
          <strong>Erro:</strong> {document.error_message}
        </div>
      )}

      <div className="response-block">
        <h3>Resposta da API</h3>
        <pre>{JSON.stringify(document, null, 2)}</pre>
      </div>
    </>
  );
}
