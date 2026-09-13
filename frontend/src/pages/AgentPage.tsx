import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { chatWithAgent, getAgentAuditLog } from "../api/agent";
import type { AgentAuditLog, AgentChatResponse, AgentConversationTurn, AgentSource } from "../types/agent";
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
        <div className="agent-section-heading">
          <h2>Resposta do assistente</h2>
          <div className="agent-badges-group">
            {response.patient_context_used && (
              <span className="agent-badge agent-badge-patient">
                🏥 Prontuário consultado
              </span>
            )}
            {response.context_summarized && (
              <span className="agent-badge agent-badge-summarized">
                ⚡ Contexto resumido
              </span>
            )}
          </div>
        </div>
        <div className="agent-answer-text">{response.response}</div>
      </div>

      {response.patient_context_used && response.patient_fields_used && response.patient_fields_used.length > 0 && (
        <details className="agent-source agent-patient-details">
          <summary>
            <span>Dados clínicos do prontuário utilizados</span>
            <strong>{response.patient_fields_used.length} {response.patient_fields_used.length === 1 ? "campo" : "campos"}</strong>
          </summary>
          <div className="agent-source-content">
            <p>Seções clínicas consultadas: {response.patient_fields_used.join(", ")}</p>
          </div>
        </details>
      )}

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

function AuditTrail({ audit }: { audit: AgentAuditLog }) {
  return (
    <div className="agent-audit-detail">
      <div className="agent-audit-meta">
        <span className={`agent-badge ${audit.topic_valid ? "agent-badge-ok" : "agent-badge-warn"}`}>
          {audit.topic_valid ? "Tópico válido" : "Tópico fora do domínio"}
        </span>
        <span className={`agent-badge ${audit.safety_triggered ? "agent-badge-alert" : "agent-badge-ok"}`}>
          {audit.safety_triggered ? "Guardrail acionado" : "Sem bloqueio"}
        </span>
        {audit.patient_record_used && (
          <span className="agent-badge agent-badge-patient">
            🏥 Prontuário consultado
          </span>
        )}
        {audit.context_summarized && (
          <span className="agent-badge agent-badge-summarized">
            ⚡ Contexto resumido ({audit.context_summarizer_mode || "auto"})
          </span>
        )}
        <span className="agent-badge agent-badge-neutral">{audit.rag_documents_count} fontes</span>
      </div>

      <div className="agent-audit-grid">
        <div>
          <strong>Identificador</strong>
          <span>{audit.id}</span>
        </div>
        <div>
          <strong>Data</strong>
          <span>{new Date(audit.created_date).toLocaleString("pt-BR")}</span>
        </div>
        <div>
          <strong>Tempo</strong>
          <span>{audit.duration_ms} ms</span>
        </div>
        <div>
          <strong>Disclaimer</strong>
          <span>{audit.has_disclaimer ? "Presente" : "Ausente"}</span>
        </div>
      </div>

      {audit.safety_reason && (
        <div className="agent-audit-block">
          <h3>Motivo do guardrail</h3>
          <p>{audit.safety_reason}</p>
        </div>
      )}

      {audit.sources_cited.length > 0 && (
        <div className="agent-audit-block">
          <h3>Fontes citadas</h3>
          <ul className="agent-inline-list">
            {audit.sources_cited.map((source) => (
              <li key={source}>{source}</li>
            ))}
          </ul>
        </div>
      )}

      {audit.rag_documents_used.length > 0 && (
        <div className="agent-audit-block">
          <h3>Contexto RAG consultado</h3>
          <div className="agent-rag-list">
            {audit.rag_documents_used.map((document, index) => (
              <details key={`${document.id ?? index}-${document.dataset ?? "doc"}`} className="agent-source">
                <summary>
                  <span>{document.dataset || "Documento RAG"} {index + 1}</span>
                  <strong>{document.similarity_score ? `${(document.similarity_score * 100).toFixed(1)}%` : "similaridade"}</strong>
                </summary>
                <div className="agent-source-content">
                  <span className="agent-source-type">{document.source_type || "Fonte não informada"}</span>
                  <p>{document.content_preview || "Prévia do conteúdo indisponível."}</p>
                </div>
              </details>
            ))}
          </div>
        </div>
      )}

      <div className="agent-audit-block">
        <h3>Resposta final</h3>
        <p>{audit.final_response}</p>
      </div>

      {audit.llm_response_raw && (
        <div className="agent-audit-block">
          <h3>Resposta bruta da LLM</h3>
          <p>{audit.llm_response_raw}</p>
        </div>
      )}
    </div>
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
              <strong>
                Human {turn.patient_name ? `• Paciente: ${turn.patient_name}` : ""}
              </strong>
              <p>{turn.query}</p>
            </div>
            <div className="agent-message agent-message-agent">
              <strong>
                Agent {turn.patient_context_used ? "• 🏥 Prontuário consultado" : ""}
              </strong>
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
  const [patientName, setPatientName] = useState("");
  const [preprocessId, setPreprocessId] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [conversation, setConversation] = useState<AgentConversationTurn[]>([]);
  const [response, setResponse] = useState<AgentChatResponse | null>(null);
  const [auditLog, setAuditLog] = useState<AgentAuditLog | null>(null);
  const [isAuditOpen, setIsAuditOpen] = useState(false);
  const [isLoadingAudit, setIsLoadingAudit] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [auditError, setAuditError] = useState<string | null>(null);

  useEffect(() => {
    if (!response?.audit_id) {
      setAuditLog(null);
      setAuditError(null);
      return;
    }

    let isMounted = true;

    const loadAuditLog = async () => {
      setIsLoadingAudit(true);
      setAuditError(null);
      try {
        const detail = await getAgentAuditLog(response.audit_id);
        if (isMounted) {
          setAuditLog(detail);
        }
      } catch (err) {
        if (isMounted) {
          setAuditError(err instanceof Error ? err.message : "Erro ao carregar a trilha de auditoria.");
          setAuditLog(null);
        }
      } finally {
        if (isMounted) {
          setIsLoadingAudit(false);
        }
      }
    };

    void loadAuditLog();

    return () => {
      isMounted = false;
    };
  }, [response?.audit_id]);

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
        patient_name: patientName.trim() || null,
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
          patient_name: patientName.trim() || null,
          patient_context_used: nextResponse.patient_context_used,
          patient_fields_used: nextResponse.patient_fields_used,
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
    setAuditLog(null);
    setIsAuditOpen(false);
    setAuditError(null);
    setError(null);
    setQuery("");
    setPatientName("");
  };

  return (
    <div className="agent-page">
      <header className="page-header">
        <h1>Assistente Médico</h1>
        <p>Consulte informações gerais ou contextualizadas por prontuário de paciente (Jornada 2).</p>
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
            placeholder="Ex.: Quais são os sintomas da tuberculose? ou Quais cuidados prescrever?"
            disabled={isSubmitting}
            rows={4}
            autoFocus
          />
          <label htmlFor="agent-patient-name">Nome do paciente (Jornada 2 — opcional)</label>
          <input
            id="agent-patient-name"
            value={patientName}
            onChange={(event) => setPatientName(event.target.value)}
            placeholder="Ex.: João da Silva (preencha para contextualizar com prontuário)"
            disabled={isSubmitting}
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
        {response && (
          <>
            <AgentResult response={response} />
            <section className="agent-audit" aria-live="polite">
              <div className="agent-section-heading">
                <h2>Trilha de auditoria</h2>
                <button type="button" className="btn btn-secondary btn-compact" onClick={() => setIsAuditOpen((open) => !open)}>
                  {isAuditOpen ? "Ocultar" : "Mostrar"}
                </button>
              </div>

              {isLoadingAudit && <div className="agent-info">Carregando trilha de auditoria...</div>}
              {auditError && <div className="alert alert-error">{auditError}</div>}
              {isAuditOpen && auditLog && <AuditTrail audit={auditLog} />}
            </section>
          </>
        )}
      </section>
    </div>
  );
}
