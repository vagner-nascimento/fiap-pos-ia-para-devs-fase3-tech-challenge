"""
Router do Agente Médico

Expõe dois endpoints:
- POST /agent/chat       — Envia uma query ao agente e recebe a resposta
- GET  /agent/audit/{session_id} — Consulta o histórico de auditoria de uma sessão
"""
import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from infra.database.collections.agent_audit_logs import (
    get_audit_log_by_id,
    get_audit_logs_by_session,
)
from services.medical_agent import run_medical_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])


# ---------------------------------------------------------------------------
# Schemas de Request / Response
# ---------------------------------------------------------------------------
class AgentChatRequest(BaseModel):
    """Payload de entrada para uma consulta ao agente médico."""

    session_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Identificador da sessão do usuário. Gerado automaticamente se não informado.",
    )
    query: str = Field(
        ...,
        min_length=3,
        max_length=2000,
        description="Pergunta em linguagem natural sobre saúde ou medicina.",
        examples=["Quais são os sintomas da tuberculose?"],
    )
    preprocess_id: Optional[str] = Field(
        None,
        description=(
            "ID do pré-processamento para filtrar a base RAG. "
            "Se não informado, usa todos os documentos disponíveis."
        ),
    )


class RagDocumentSummary(BaseModel):
    """Resumo de um documento RAG utilizado na resposta."""

    dataset: str
    source_type: str
    similarity_score: float
    content_preview: str


class AgentChatResponse(BaseModel):
    """Resposta estruturada do agente médico."""

    session_id: str
    response: str = Field(description="Resposta do assistente com fontes inline e disclaimer.")
    sources: List[RagDocumentSummary] = Field(
        default_factory=list,
        description="Documentos RAG utilizados como contexto.",
    )
    sources_cited: List[str] = Field(
        default_factory=list,
        description="Nomes das fontes citadas (ex: PubMedQA/MedQuAD, FHEMIG).",
    )
    topic_valid: bool = Field(description="Se a pergunta pertence ao domínio médico.")
    safety_triggered: bool = Field(description="Se algum guardrail de segurança foi ativado.")
    safety_reason: Optional[str] = Field(None, description="Motivo do guardrail, se ativado.")
    requires_human_validation: bool = Field(
        True,
        description="Sempre True — toda resposta requer validação humana.",
    )
    audit_id: str = Field(description="ID do log de auditoria criado no MongoDB.")
    duration_ms: int = Field(description="Tempo total de processamento em milissegundos.")


class AuditLogResponse(BaseModel):
    """Log de auditoria de uma interação."""

    id: str
    session_id: str
    query: str
    topic_valid: bool
    safety_triggered: bool
    safety_reason: Optional[str]
    rag_documents_count: int
    sources_cited: List[str]
    has_disclaimer: bool
    preprocess_id: Optional[str]
    duration_ms: int
    created_date: str
    final_response: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.post(
    "/chat",
    response_model=AgentChatResponse,
    summary="Consultar o assistente médico",
    description=(
        "Envia uma pergunta ao agente médico e recebe uma resposta contextualizada, "
        "com citação de fontes inline e disclaimer obrigatório. "
        "O agente valida o tópico, aplica guardrails de segurança, "
        "recupera contexto via RAG e gera a resposta com o modelo Qwen2.5 fine-tunado."
    ),
)
def agent_chat(request: AgentChatRequest) -> Dict[str, Any]:
    """
    Endpoint principal do agente médico.

    Executa o pipeline LangGraph completo e retorna a resposta estruturada.
    """
    logger.info(
        f"[ROUTER] POST /agent/chat — session={request.session_id} "
        f"query='{request.query[:80]}'"
    )

    try:
        result = run_medical_agent(
            query=request.query,
            session_id=request.session_id,
            preprocess_id=request.preprocess_id,
        )
    except Exception as exc:
        logger.error(f"[ROUTER] Erro ao executar o agente: {exc}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno ao processar a consulta: {str(exc)}",
        )

    # Formata os documentos RAG como resumos para a resposta
    rag_summaries = [
        RagDocumentSummary(
            dataset=doc.get("dataset", ""),
            source_type=doc.get("source_type", ""),
            similarity_score=doc.get("similarity_score", 0.0),
            content_preview=str(doc.get("content", ""))[:200],
        )
        for doc in result.get("rag_documents", [])
    ]

    return {
        "session_id": result.get("session_id", request.session_id),
        "response": result.get("final_response", ""),
        "sources": [s.model_dump() for s in rag_summaries],
        "sources_cited": result.get("sources_cited", []),
        "topic_valid": result.get("topic_valid", False),
        "safety_triggered": result.get("safety_triggered", False),
        "safety_reason": result.get("safety_reason"),
        "requires_human_validation": True,
        "audit_id": result.get("audit_id", ""),
        "duration_ms": result.get("duration_ms", 0),
    }


@router.get(
    "/audit/{session_id}",
    response_model=List[AuditLogResponse],
    summary="Histórico de auditoria de uma sessão",
    description=(
        "Retorna todos os logs de auditoria de uma sessão específica, "
        "ordenados cronologicamente. Inclui detalhes completos de cada interação "
        "para fins de rastreamento e compliance."
    ),
)
def get_audit_history(session_id: str) -> List[Dict[str, Any]]:
    """
    Retorna o histórico de auditoria de uma sessão de usuário.
    """
    logger.info(f"[ROUTER] GET /agent/audit/{session_id}")

    try:
        logs = get_audit_logs_by_session(session_id)
    except Exception as exc:
        logger.error(f"[ROUTER] Erro ao consultar logs de auditoria: {exc}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao recuperar logs de auditoria: {str(exc)}",
        )

    return [
        {
            "id": str(log.get("_id", "")),
            "session_id": log.get("session_id", ""),
            "query": log.get("query", ""),
            "topic_valid": log.get("topic_valid", False),
            "safety_triggered": log.get("safety_triggered", False),
            "safety_reason": log.get("safety_reason"),
            "rag_documents_count": log.get("rag_documents_count", 0),
            "sources_cited": log.get("sources_cited", []),
            "has_disclaimer": log.get("has_disclaimer", False),
            "preprocess_id": log.get("preprocess_id"),
            "duration_ms": log.get("duration_ms", 0),
            "created_date": log.get("created_date", ""),
            "final_response": log.get("final_response", ""),
        }
        for log in logs
    ]


@router.get(
    "/audit/log/{audit_id}",
    response_model=AuditLogResponse,
    summary="Detalhe de um log de auditoria",
    description="Retorna um log de auditoria específico pelo seu ID.",
)
def get_audit_log(audit_id: str) -> Dict[str, Any]:
    """Retorna o detalhe de um log de auditoria específico."""
    logger.info(f"[ROUTER] GET /agent/audit/log/{audit_id}")

    try:
        log = get_audit_log_by_id(audit_id)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao recuperar log: {str(exc)}",
        )

    if not log:
        raise HTTPException(
            status_code=404,
            detail=f"Log de auditoria com ID '{audit_id}' não encontrado.",
        )

    return {
        "id": str(log.get("_id", "")),
        "session_id": log.get("session_id", ""),
        "query": log.get("query", ""),
        "topic_valid": log.get("topic_valid", False),
        "safety_triggered": log.get("safety_triggered", False),
        "safety_reason": log.get("safety_reason"),
        "rag_documents_count": log.get("rag_documents_count", 0),
        "sources_cited": log.get("sources_cited", []),
        "has_disclaimer": log.get("has_disclaimer", False),
        "preprocess_id": log.get("preprocess_id"),
        "duration_ms": log.get("duration_ms", 0),
        "created_date": log.get("created_date", ""),
        "final_response": log.get("final_response", ""),
    }
