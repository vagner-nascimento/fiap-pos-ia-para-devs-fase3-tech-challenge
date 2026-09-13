import { useState } from "react";
import type { FormEvent } from "react";
import { chatWithAgent } from "../api/agent";
import type { AgentChatResponse, AgentConversationTurn, AgentSource } from "../types/agent";
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

function Conversation({ turns }: { turns: AgentConversationTurn[] }) {
  return (
    <section className="agent-conversation" aria-label="Histórico da conversa">
      <div className="agent-section-heading">
        <h2>Conversa</h2>
        <span>{turns.length} {turns.length === 1 ? "turno" : "turnos"}</span>
      </div>
      <div className="agent-messages">
        {turns.map((turn, index) => (
          <div className="agent-turn" key={`${index}-${turn.query}`}>
            <div className="agent-message agent-message-human">
              <strong>Human</strong>
              <p>{turn.query}</p>
            </div>
            <div className="agent-message agent-message-agent">
              <strong>Agent</strong>
              <p>{turn.response}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

export function AgentPage() {
  const [query, setQuery] = useState("");
  const [preprocessId, setPreprocessId] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [conversation, setConversation] = useState<AgentConversationTurn[]>([]);
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
      const nextResponse = await chatWithAgent({
        query: trimmedQuery,
        session_id: sessionId ?? undefined,
        preprocess_id: preprocessId.trim() || null,
      });
      setSessionId(nextResponse.session_id);
      setResponse(nextResponse);
      setConversation((turns) => [
        ...turns,
        {
          query: trimmedQuery,
          response: nextResponse.response,
          sources: nextResponse.sources,
          safety_triggered: nextResponse.safety_triggered,
          safety_reason: nextResponse.safety_reason,
        },
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao consultar o assistente");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleNewConversation = () => {
    setSessionId(null);
    setConversation([]);
    setResponse(null);
    setError(null);
    setQuery("");
  };

  return (
    <div className="agent-page">
      <header className="page-header">
        <h1>Assistente Médico</h1>
        <p>Consulte informações gerais baseadas na base de conhecimento clínica.</p>
        {conversation.length > 0 && (
          <button className="btn btn-secondary" type="button" onClick={handleNewConversation}>
            Nova conversa
          </button>
        )}
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
        {conversation.length > 0 && <Conversation turns={conversation} />}
        {response && <AgentResult response={response} />}
      </section>
    </div>
  );
}
