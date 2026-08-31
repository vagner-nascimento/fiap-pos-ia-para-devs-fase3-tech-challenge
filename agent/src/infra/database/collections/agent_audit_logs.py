"""
Collection `agent_audit_logs` — auditoria completa das interações do agente médico.

Cada documento registra:
- A query do usuário
- Resultado da validação de tópico
- Resultado dos guardrails de segurança
- Documentos RAG utilizados como contexto
- Resposta bruta da LLM
- Resposta final formatada (com fontes e disclaimer)
- Metadados de rastreamento (sessão, tempo de execução, timestamp)
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from infra.database.mongodb import get_collection

logger = logging.getLogger(__name__)

COLLECTION_NAME = "agent_audit_logs"


# ---------------------------------------------------------------------------
# Criação / Inserção
# ---------------------------------------------------------------------------

def create_audit_log(
    *,
    session_id: str,
    query: str,
    topic_valid: bool,
    safety_triggered: bool,
    safety_reason: Optional[str],
    rag_documents_used: List[Dict[str, Any]],
    llm_response_raw: str,
    final_response: str,
    sources_cited: List[str],
    has_disclaimer: bool,
    preprocess_id: Optional[str],
    duration_ms: int,
) -> Dict[str, Any]:
    """
    Persiste um log de auditoria completo no MongoDB.

    Args:
        session_id: Identificador da sessão do usuário.
        query: Pergunta original do usuário.
        topic_valid: Se a pergunta passou na validação de domínio médico.
        safety_triggered: Se algum guardrail de segurança foi ativado.
        safety_reason: Motivo do guardrail (None se não ativado).
        rag_documents_used: Lista de documentos RAG utilizados como contexto.
        llm_response_raw: Resposta bruta retornada pela LLM.
        final_response: Resposta final formatada (com fontes e disclaimer).
        sources_cited: Lista de datasets citados (ex: ['PubMedQA', 'FHEMIG']).
        has_disclaimer: Se o disclaimer obrigatório está presente na resposta.
        preprocess_id: ID do pré-processamento usado para filtrar o RAG (opcional).
        duration_ms: Tempo total de execução do pipeline em milissegundos.

    Returns:
        Dict com o documento criado incluindo o _id.
    """
    collection = get_collection(COLLECTION_NAME)

    doc_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    # Armazena apenas um preview do conteúdo dos documentos RAG para não inflar o log
    rag_docs_summary = [
        {
            "id": doc.get("id", ""),
            "dataset": doc.get("dataset", ""),
            "source_type": doc.get("source_type", ""),
            "similarity_score": doc.get("similarity_score", 0.0),
            "content_preview": str(doc.get("content", ""))[:200],
        }
        for doc in rag_documents_used
    ]

    document: Dict[str, Any] = {
        "_id": doc_id,
        "session_id": session_id,
        "query": query,
        "topic_valid": topic_valid,
        "safety_triggered": safety_triggered,
        "safety_reason": safety_reason,
        "rag_documents_used": rag_docs_summary,
        "rag_documents_count": len(rag_documents_used),
        "llm_response_raw": llm_response_raw,
        "final_response": final_response,
        "sources_cited": sources_cited,
        "has_disclaimer": has_disclaimer,
        "preprocess_id": preprocess_id,
        "duration_ms": duration_ms,
        "created_date": now.isoformat(),
    }

    collection.insert_one(document)
    logger.info(
        f"[AUDIT] Log criado: id={doc_id} session={session_id} "
        f"topic_valid={topic_valid} safety_triggered={safety_triggered} "
        f"duration_ms={duration_ms}"
    )
    return document


# ---------------------------------------------------------------------------
# Consulta
# ---------------------------------------------------------------------------

def get_audit_logs_by_session(session_id: str) -> List[Dict[str, Any]]:
    """
    Retorna todos os logs de auditoria de uma sessão, ordenados por data.

    Args:
        session_id: Identificador da sessão.

    Returns:
        Lista de documentos de auditoria.
    """
    collection = get_collection(COLLECTION_NAME)
    cursor = collection.find(
        {"session_id": session_id},
        sort=[("created_date", 1)],
    )
    return list(cursor)


def get_audit_log_by_id(audit_id: str) -> Optional[Dict[str, Any]]:
    """
    Retorna um log de auditoria específico pelo ID.

    Args:
        audit_id: ID do documento de auditoria.

    Returns:
        Documento de auditoria ou None se não encontrado.
    """
    collection = get_collection(COLLECTION_NAME)
    return collection.find_one({"_id": audit_id})
