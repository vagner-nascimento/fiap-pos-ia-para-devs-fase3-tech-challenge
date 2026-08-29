import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { startRagGeneration } from "../api/ragDatabase";
import { RagGenerationForm } from "../components/rag-generation/RagGenerationForm";
import { RagGenerationResults } from "../components/rag-generation/RagGenerationResults";
import type { RagGenerationDocument } from "../types/ragDatabase";
import "./RagGenerationPage.css";

interface Props {
  lastPreprocessId?: string | null;
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
        <RagGenerationForm
          preprocessId={preprocessId}
          isSubmitting={isSubmitting}
          onPreprocessIdChange={setPreprocessId}
          onSubmit={(event) => void handleSubmit(event)}
          onReset={handleReset}
        />

        {error && <div className="alert alert-error status-section">{error}</div>}

        <div className="status-section">
          {document ? (
            <RagGenerationResults document={document} />
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
