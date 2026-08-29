import { useState } from "react";
import type { FormEvent } from "react";
import { queryRagDatabase } from "../api/ragDatabase";
import { RagQueryForm } from "../components/rag-query/RagQueryForm";
import { RagQueryResults } from "../components/rag-query/RagQueryResults";
import type { RagQueryResponse } from "../types/ragDatabase";
import "./RagQueryPage.css";

interface Props {
  lastPreprocessId?: string | null;
}

export function RagQueryPage({ lastPreprocessId }: Props) {
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(5);
  const [preprocessId, setPreprocessId] = useState(lastPreprocessId ?? "");
  const [similarityThreshold, setSimilarityThreshold] = useState<string>("");
  
  const [response, setResponse] = useState<RagQueryResponse | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showRawJson, setShowRawJson] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmedQuery = query.trim();

    if (!trimmedQuery) {
      setError("A consulta por texto é obrigatória");
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const thresholdVal = similarityThreshold.trim() !== ""
        ? parseFloat(similarityThreshold)
        : null;

      const res = await queryRagDatabase({
        query: trimmedQuery,
        top_k: topK,
        preprocess_id: preprocessId.trim() || null,
        similarity_threshold: thresholdVal !== null && !isNaN(thresholdVal) ? thresholdVal : null,
      });

      setResponse(res);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Erro ao consultar a base RAG";
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleReset = () => {
    setQuery("");
    setTopK(5);
    setPreprocessId(lastPreprocessId ?? "");
    setSimilarityThreshold("");
    setResponse(null);
    setError(null);
  };

  return (
    <div className="rag-query-page">
      <header className="page-header">
        <h1>RAG Query</h1>
        <p>
          Realize consultas semânticas por similaridade vetorial na base de conhecimento RAG
          e visualize os documentos mais relevantes retornados pelo backend.
        </p>
      </header>

      <section className="card">
        <RagQueryForm
          query={query}
          topK={topK}
          preprocessId={preprocessId}
          similarityThreshold={similarityThreshold}
          isSubmitting={isSubmitting}
          onQueryChange={setQuery}
          onTopKChange={setTopK}
          onPreprocessIdChange={setPreprocessId}
          onSimilarityThresholdChange={setSimilarityThreshold}
          onSubmit={(event) => void handleSubmit(event)}
          onReset={handleReset}
        />

        {error && <div className="alert alert-error status-section">{error}</div>}

        {response && (
          <RagQueryResults
            response={response}
            showRawJson={showRawJson}
            onToggleRawJson={() => setShowRawJson(!showRawJson)}
          />
        )}

        {!response && !error && (
          <div className="status-section">
            <p className="empty-state">
              Digite uma consulta acima e clique em &quot;Buscar no RAG&quot; para visualizar os resultados.
            </p>
          </div>
        )}
      </section>
    </div>
  );
}
