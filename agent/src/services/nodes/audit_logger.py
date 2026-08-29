"""
Nó 6: Logger de Auditoria (Audit Logger)

Persiste o log completo da interação no MongoDB (collection `agent_audit_logs`).
Registra todos os campos necessários para rastreamento, auditoria e explainability:
- Query original do usuário
- Resultado de cada guardrail (tópico + segurança)
- Documentos RAG utilizados como contexto
- Resposta bruta e final
- Fontes citadas
- Tempo de execução

Este nó é sempre executado, mesmo quando a resposta foi bloqueada pelos guardrails.
"""
import logging
import time
from typing import Any, Dict

from infra.database.collections.agent_audit_logs import create_audit_log

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Nó LangGraph
# ---------------------------------------------------------------------------
def audit_logger_node(state: dict) -> dict:
    """
    Nó LangGraph: persiste o log de auditoria da interação.

    Lê todos os campos relevantes do estado e cria um documento de auditoria
    completo no MongoDB.

    Args:
        state: Estado final do grafo LangGraph.

    Returns:
        Estado atualizado com `state['audit_id']` contendo o ID do log criado.
    """
    session_id = state.get("session_id", "unknown")
    query = state.get("query", "")
    topic_valid = state.get("topic_valid", False)
    safety_triggered = state.get("safety_triggered", False)
    safety_reason = state.get("safety_reason")
    rag_documents = state.get("rag_documents", [])
    llm_response_raw = state.get("llm_response_raw", "")
    final_response = state.get("final_response", "")
    sources_cited = state.get("sources_cited", [])
    has_disclaimer = state.get("has_disclaimer", False)
    preprocess_id = state.get("preprocess_id")

    # Calcula a duração total do pipeline
    started_at = state.get("_started_at", time.time())
    duration_ms = int((time.time() - started_at) * 1000)

    logger.info(
        f"[AUDIT] Persistindo log: session={session_id} "
        f"topic_valid={topic_valid} safety_triggered={safety_triggered} "
        f"rag_docs={len(rag_documents)} duration_ms={duration_ms}"
    )

    try:
        audit_doc: Dict[str, Any] = create_audit_log(
            session_id=session_id,
            query=query,
            topic_valid=topic_valid,
            safety_triggered=safety_triggered,
            safety_reason=safety_reason,
            rag_documents_used=rag_documents,
            llm_response_raw=llm_response_raw,
            final_response=final_response,
            sources_cited=sources_cited,
            has_disclaimer=has_disclaimer,
            preprocess_id=preprocess_id,
            duration_ms=duration_ms,
        )
        audit_id = audit_doc.get("_id", "")
        logger.info(f"[AUDIT] Log persistido com sucesso: audit_id={audit_id}")
    except Exception as exc:
        # O log de auditoria não deve interromper o retorno da resposta ao usuário
        logger.error(f"[AUDIT] Falha ao persistir log de auditoria: {exc}")
        audit_id = ""

    return {
        **state,
        "audit_id": audit_id,
        "duration_ms": duration_ms,
    }
