"""
Nó 3: Recuperador RAG (RAG Retriever)

Busca documentos relevantes na base RAG do MongoDB usando busca híbrida
(vetorial + textual) implementada no serviço `rag_database` do backend.

A busca é feita via chamada HTTP à API do backend para reutilizar toda a
lógica de embeddings e scoring já implementada, mantendo o princípio de
responsabilidade única entre serviços.
"""
import logging
import os
import re
from typing import Any, Dict, List, Optional

import requests

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://localhost:3000")
RAG_QUERY_ENDPOINT = f"{BACKEND_API_URL}/rag-database/query"


def _get_similarity_threshold() -> float:
    """Carrega o threshold de similaridade do .env com override de variáveis antigas."""
    load_dotenv(override=True)
    raw = os.getenv("RAG_SIMILARITY_THRESHOLD", "0.48")
    try:
        val = float(raw)
        return max(val, 0.48)
    except ValueError:
        return 0.48


def _get_top_k() -> int:
    raw = os.getenv("RAG_TOP_K", "3")
    try:
        return int(raw)
    except ValueError:
        return 3


# ---------------------------------------------------------------------------
# Funções auxiliares
# ---------------------------------------------------------------------------
def _clean_content_for_prompt(content: str) -> str:
    """
    Remove cabeçalhos artificiais, URLs longas e metadados repetidos inseridos
    no texto bruto do chunk durante a indexação, deixando texto clínico limpo
    para não poluir a atenção de modelos compactos (1.5B).
    """
    if not content:
        return ""
    cleaned = re.sub(
        r"^###\s*Protocolo\s+clinico\s+RAG\s*\n(?:Nome:[^\n]*\n)?(?:Fonte:[^\n]*\n)?(?:URL:[^\n]*\n)?(?:\n*Conteudo:\s*\n)?",
        "",
        content.strip(),
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\bPág\.\s*\d+\b", "", cleaned)
    return cleaned.strip()


def _query_rag(
    query: str,
    top_k: Optional[int] = None,
    preprocess_id: Optional[str] = None,
    similarity_threshold: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    Consulta a API RAG do backend e retorna os documentos mais relevantes.

    Args:
        query: Texto da consulta.
        top_k: Número máximo de documentos a retornar.
        preprocess_id: Filtro por pré-processamento (opcional).
        similarity_threshold: Score mínimo de similaridade.

    Returns:
        Lista de documentos RAG com scores e metadados.
    """
    if similarity_threshold is None:
        similarity_threshold = _get_similarity_threshold()
    if top_k is None:
        top_k = _get_top_k()

    payload: Dict[str, Any] = {
        "query": query,
        "top_k": top_k,
        "similarity_threshold": similarity_threshold,
    }
    if preprocess_id:
        payload["preprocess_id"] = preprocess_id

    try:
        response = requests.post(
            RAG_QUERY_ENDPOINT,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        raw_documents = data.get("documents", [])
        documents = [
            doc for doc in raw_documents
            if float(doc.get("similarity_score", 0.0)) >= similarity_threshold
        ]
        logger.info(
            f"[RAG] Busca concluída: {len(documents)} documentos aprovados "
            f"(de {len(raw_documents)} retornados pelo backend, threshold={similarity_threshold})."
        )
        return documents
    except requests.exceptions.ConnectionError:
        logger.error(
            f"[RAG] Não foi possível conectar ao backend em {RAG_QUERY_ENDPOINT}. "
            "Verifique se o backend está rodando."
        )
        return []
    except requests.exceptions.Timeout:
        logger.error("[RAG] Timeout na consulta RAG.")
        return []
    except requests.exceptions.RequestException as exc:
        logger.error(f"[RAG] Erro na consulta RAG: {exc}")
        return []


# ---------------------------------------------------------------------------
# Nó LangGraph
# ---------------------------------------------------------------------------
def rag_retriever_node(state: dict) -> dict:
    """
    Nó LangGraph: recupera documentos relevantes da base RAG.

    Agora executa duas consultas separadas ao backend RAG: uma focada em
    'clinical_protocols' e outra em 'medical_reports'. Os resultados são
    filtrados por dataset e mesclados (protocolos têm prioridade na ordenação).

    Lê:
    - `state['query']` — texto da consulta
    - `state['preprocess_id']` — filtro opcional de pré-processamento

    Escreve:
    - `state['rag_documents']` — lista de documentos recuperados
    - `state['rag_context']` — contexto formatado para o prompt da LLM
    """
    query = state.get("query", "")
    preprocess_id = state.get("preprocess_id")
    conversation_history = state.get("conversation_history", [])
    patient_context = state.get("patient_context", "")

    # Enriquece a query com histórico de conversa se necessário
    rag_query = query
    if conversation_history and isinstance(conversation_history, list):
        last_turn = conversation_history[-1]
        if isinstance(last_turn, dict):
            last_query = last_turn.get("query", "").strip()
            is_short_followup = len(query.split()) <= 20
            if last_query and is_short_followup:
                rag_query = f"{last_query} {query}"
                logger.info(
                    f"[RAG] Query enriquecida com contexto do histórico "
                    f"({len(query.split())} → {len(rag_query.split())} palavras)."
                )

    # Enriquece com contexto do paciente (se houver)
    if patient_context:
        patient_excerpt = " ".join(patient_context.splitlines()[:3])
        rag_query = f"{rag_query} {patient_excerpt}".strip()
        logger.info(
            f"[RAG] Query enriquecida com dados do paciente: '{rag_query[:120]}'"
        )

    logger.info(f"[RAG] Buscando contexto para: '{rag_query[:120]}'")

    # Executa duas consultas RAG separadas e filtra por dataset
    try:
        raw_protocols = _query_rag(query=rag_query, preprocess_id=preprocess_id)
    except Exception:
        raw_protocols = []
    protocols = [d for d in raw_protocols if str(d.get("dataset", "")).lower() == "clinical_protocols"]

    try:
        raw_reports = _query_rag(query=rag_query, preprocess_id=preprocess_id)
    except Exception:
        raw_reports = []
    reports = [d for d in raw_reports if str(d.get("dataset", "")).lower() == "medical_reports"]

    logger.info(f"[RAG] Protocolos encontrados: {len(protocols)}; Laudos encontrados: {len(reports)}")

    # Mescla resultados: protocolos primeiro, depois laudos (sem duplicatas)
    ids_seen = set()
    merged_documents: List[Dict[str, Any]] = []
    for doc in protocols + reports:
        doc_id = str(doc.get("id") or doc.get("_id") or "")
        if not doc_id or doc_id in ids_seen:
            continue
        ids_seen.add(doc_id)
        merged_documents.append(doc)

    # Formata o contexto para injeção no prompt
    context_parts: List[str] = []
    for i, doc in enumerate(merged_documents, start=1):
        dataset = doc.get("dataset", "desconhecido")
        score = doc.get("similarity_score", 0.0)
        content = doc.get("content", "").strip()
        cleaned_content = _clean_content_for_prompt(content)

        dataset_label = {
            "qas": "PubMedQA/MedQuAD",
            "clinical_protocols": "FHEMIG (Protocolos Clínicos)",
        }.get(dataset, dataset)

        meta = doc.get("metadatas") or {}
        doc_name = ""
        if isinstance(meta, dict):
            raw_name = meta.get("name") or meta.get("source_label", "")
            doc_name = raw_name.replace(".pdf", "").replace("---", " - ")

        title = f"{dataset_label} ({doc_name})" if doc_name else dataset_label

        part = (
            f"[Contexto {i} — Fonte: {title}, score: {score:.2f}]\n"
            f"{cleaned_content}"
        )
        context_parts.append(part)

    rag_context = "\n\n".join(context_parts) if context_parts else ""

    if not merged_documents:
        logger.warning("[RAG] Nenhum documento relevante encontrado na base RAG.")
    else:
        logger.info(f"[RAG] {len(merged_documents)} documentos recuperados e contexto montado.")

    return {
        **state,
        "rag_documents": merged_documents,
        "rag_context": rag_context,
    }
