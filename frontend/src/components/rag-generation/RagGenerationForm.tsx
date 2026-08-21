import type { FormEvent } from "react";

interface Props {
  preprocessId: string;
  isSubmitting: boolean;
  onPreprocessIdChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onReset: () => void;
}

export function RagGenerationForm({
  preprocessId,
  isSubmitting,
  onPreprocessIdChange,
  onSubmit,
  onReset,
}: Props) {
  return (
    <form onSubmit={onSubmit} className="form-section">
      <h3>Preprocessamento</h3>

      <div className="form-row">
        <label htmlFor="rag-preprocess-id">ID</label>
        <input
          id="rag-preprocess-id"
          type="text"
          value={preprocessId}
          onChange={(event) => onPreprocessIdChange(event.target.value)}
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
          onClick={onReset}
          disabled={isSubmitting}
        >
          Limpar
        </button>
      </div>
    </form>
  );
}
