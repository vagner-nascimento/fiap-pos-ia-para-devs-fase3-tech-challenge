import { useState } from "react";
import type { FormEvent } from "react";
import { chatWithAgent } from "../api/agent";
import type { AgentChatResponse, AgentSource } from "../types/agent";
import "./AgentPage.css";

function SourceDetails({ source, index }: { source: AgentSource; index: number }) {
  const score = (source.similarity_score * 100).toFixed(1);

  return (
    <details className="agent-source">
      <summary>
        <span>Fonte {index + 1}: {source.dataset || "Documento RAG"}</span>
        <strong>{score}% de similaridade</strong>
      </summary>
      <div className="agent-source-content">
        <span className="agent-source-type">{source.source_type || "Fonte não informada"}</span>
        <p>{source.content_preview || "Prévia do conteúdo indisponível."}</p>
      </div>
    </details>
  );
}

function AgentResult({ response }: { response: AgentChatResponse }) {
  return (
    <section className="agent-result" aria-live="polite">
      {response.safety_triggered && (
        <div className="agent-safety-alert" role="alert">
          <strong>Por segurança, esta solicitação foi bloqueada.</strong>
          <p>{response.safety_reason || "A solicitação exige avaliação de um profissional de saúde."}</p>
        </div>
      )}

      <div className="agent-answer">
        <h2>Resposta do assistente</h2>
        <div className="agent-answer-text">{response.response}</div>
      </div>

      {!response.safety_triggered && response.sources.length > 0 && (
        <div className="agent-sources">
          <div className="agent-section-heading">
            <h2>Fontes consultadas</h2>
            <span>{response.sources.length} {response.sources.length === 1 ? "documento" : "documentos"}</span>
          </div>
          {response.sources.map((source, index) => (
            <SourceDetails key={`${source.dataset}-${index}`} source={source} index={index} />
          ))}
        </div>
      )}
    </section>
  );
}

export function AgentPage() {
  const [query, setQuery] = useState("");
  const [preprocessId, setPreprocessId] = useState("");
  const [response, setResponse] = useState<AgentChatResponse | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmedQuery = query.trim();
    if (!trimmedQuery) {
      setError("Digite uma pergunta para consultar o assistente.");
      return;
    }

    setIsSubmitting(true);
    setError(null);
    try {
      setResponse(await chatWithAgent({
        query: trimmedQuery,
        preprocess_id: preprocessId.trim() || null,
      }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao consultar o assistente");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="agent-page">
      <header className="page-header">
        <h1>Assistente Médico</h1>
        <p>Consulte informações gerais baseadas na base de conhecimento clínica.</p>
      </header>

      <section className="card agent-card">
        <form className="agent-form" onSubmit={(event) => void handleSubmit(event)}>
          <label htmlFor="agent-query">Sua pergunta</label>
          <textarea
            id="agent-query"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Ex.: Quais são os sintomas da tuberculose?"
            disabled={isSubmitting}
            rows={4}
            autoFocus
          />
          <label htmlFor="agent-preprocess-id">Preprocess ID (opcional)</label>
          <input
            id="agent-preprocess-id"
            value={preprocessId}
            onChange={(event) => setPreprocessId(event.target.value)}
            placeholder="Filtre a base RAG por um preprocessamento"
            disabled={isSubmitting}
          />
          <button className="btn btn-primary" type="submit" disabled={isSubmitting || !query.trim()}>
            {isSubmitting ? "Consultando..." : "Consultar assistente"}
          </button>
        </form>

        {error && <div className="alert alert-error agent-error">{error}</div>}
        {response && <AgentResult response={response} />}
      </section>
    </div>
  );
}
