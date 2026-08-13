import { useEffect, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { startRagGeneration } from "../api/ragDatabase";
import type { RagGenerationDocument } from "../types/ragDatabase";
import "./RagGenerationPage.css";

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

interface ResultCardProps {
  label: string;
  value: ReactNode;
}

interface Props {
  lastPreprocessId?: string | null;
}

function ResultCard({ label, value }: ResultCardProps) {
  return (
    <div className="status-item">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export function RagGenerationPage({ lastPreprocessId }: Props) {
  const [preprocessId, setPreprocessId] = useState(lastPreprocessId ?? "");
  const [document, setDocument] = useState<RagGenerationDocument | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (lastPreprocessId) {
      setPreprocessId(lastPreprocessId);
    }
  }, [lastPreprocessId]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmedPreprocessId = preprocessId.trim();

    if (!trimmedPreprocessId) {
      setError("ID do preprocessamento e obrigatorio");
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const created = await startRagGeneration({
        preprocess_id: trimmedPreprocessId,
      });
      setDocument(created);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Erro ao gerar a base RAG";
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleReset = () => {
    setPreprocessId("");
    setDocument(null);
    setError(null);
  };

  return (
    <div className="rag-generation-page">
      <header className="page-header">
        <h1>RAG Generation</h1>
        <p>
          Gere a base RAG de forma sincrona e veja o resultado final assim que a
          resposta da API voltar.
        </p>
      </header>

      <section className="card">
        <form onSubmit={(event) => void handleSubmit(event)} className="form-section">
          <h3>ID do Preprocessamento</h3>

          <div className="form-row">
            <label htmlFor="rag-preprocess-id">ID do Preprocessamento</label>
            <input
              id="rag-preprocess-id"
              type="text"
              value={preprocessId}
              onChange={(event) => setPreprocessId(event.target.value)}
              disabled={isSubmitting}
              placeholder="Cole o ID do preprocessamento aqui"
            />
          </div>

          <div className="actions">
            <button
              type="submit"
              className="btn btn-primary"
              disabled={isSubmitting || !preprocessId.trim()}
            >
              {isSubmitting ? "Gerando..." : "Gerar base RAG"}
            </button>

            <button
              type="button"
              className="btn btn-secondary"
              onClick={handleReset}
              disabled={isSubmitting}
            >
              Limpar
            </button>
          </div>
        </form>

        {error && <div className="alert alert-error status-section">{error}</div>}

        <div className="status-section">
          {document ? (
            <>
              <div className="status-grid">
                <ResultCard label="ID" value={document.id} />
                <ResultCard label="Batch ID" value={document.batch_id} />
                <ResultCard label="Preprocess ID" value={document.preprocess_id} />
                <ResultCard
                  label="Status"
                  value={<span className={statusClassName(document.status)}>{document.status}</span>}
                />
                <ResultCard
                  label="Embedding Model"
                  value={document.embedding_model}
                />
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
                  label="QAs Documents"
                  value={document.qas_documents.toLocaleString("pt-BR")}
                />
                <ResultCard
                  label="Clinical Docs"
                  value={document.clinical_protocol_documents.toLocaleString("pt-BR")}
                />
                <ResultCard
                  label="Total Documents"
                  value={document.total_documents.toLocaleString("pt-BR")}
                />
                <ResultCard
                  label="Atualizado em"
                  value={formatDate(document.updated_date)}
                />
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
