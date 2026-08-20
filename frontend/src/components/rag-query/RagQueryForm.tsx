import type { FormEvent } from "react";

interface Props {
  query: string;
  topK: number;
  preprocessId: string;
  similarityThreshold: string;
  isSubmitting: boolean;
  onQueryChange: (value: string) => void;
  onTopKChange: (value: number) => void;
  onPreprocessIdChange: (value: string) => void;
  onSimilarityThresholdChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onReset: () => void;
}

export function RagQueryForm({
  query,
  topK,
  preprocessId,
  similarityThreshold,
  isSubmitting,
  onQueryChange,
  onTopKChange,
  onPreprocessIdChange,
  onSimilarityThresholdChange,
  onSubmit,
  onReset,
}: Props) {
  return (
    <form onSubmit={onSubmit} className="query-form">
      <div className="query-input-group">
        <label htmlFor="rag-query-text">Consulta (Pergunta ou Termo Médico)</label>
        <input
          id="rag-query-text"
          type="text"
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          disabled={isSubmitting}
          placeholder="Ex: como tratar tuberculose?"
          autoFocus
        />
      </div>

      <div className="filters-grid">
        <div className="filter-item">
          <label htmlFor="rag-top-k">Resultados (top_k)</label>
          <input
            id="rag-top-k"
            type="number"
            min={1}
            max={50}
            value={topK}
            onChange={(event) => onTopKChange(parseInt(event.target.value, 10) || 5)}
            disabled={isSubmitting}
          />
        </div>

        <div className="filter-item">
          <label htmlFor="rag-preprocess-id">Filtrar por Preprocess ID (opcional)</label>
          <input
            id="rag-preprocess-id"
            type="text"
            value={preprocessId}
            onChange={(event) => onPreprocessIdChange(event.target.value)}
            disabled={isSubmitting}
            placeholder="Cole o ID se quiser filtrar"
          />
        </div>

        <div className="filter-item">
          <label htmlFor="rag-threshold">Threshold Mínimo (opcional)</label>
          <input
            id="rag-threshold"
            type="number"
            step="0.05"
            min="-1"
            max="1"
            value={similarityThreshold}
            onChange={(event) => onSimilarityThresholdChange(event.target.value)}
            disabled={isSubmitting}
            placeholder="Ex: 0.2"
          />
        </div>
      </div>

      <div className="actions">
        <button
          type="submit"
          className="btn btn-primary"
          disabled={isSubmitting || !query.trim()}
        >
          {isSubmitting ? "Consultando..." : "Buscar no RAG"}
        </button>

        <button
          type="button"
          className="btn btn-secondary"
          onClick={onReset}
          disabled={isSubmitting}
        >
          Limpar
        </button>
      </div>
    </form>
  );
}
