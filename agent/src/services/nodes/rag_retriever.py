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
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://localhost:3000")
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "5"))
RAG_SIMILARITY_THRESHOLD = float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.25"))
RAG_QUERY_ENDPOINT = f"{BACKEND_API_URL}/rag-database/query"


# ---------------------------------------------------------------------------
# Funções auxiliares
# ---------------------------------------------------------------------------
def _query_rag(
    query: str,
    top_k: int = RAG_TOP_K,
    preprocess_id: Optional[str] = None,
    similarity_threshold: float = RAG_SIMILARITY_THRESHOLD,
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
        documents = data.get("documents", [])
        logger.info(
            f"[RAG] Busca concluída: {len(documents)} documentos retornados "
            f"de {data.get('total_results', 0)} encontrados."
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

    Lê:
    - `state['query']` — texto da consulta
    - `state['preprocess_id']` — filtro opcional de pré-processamento

    Escreve:
    - `state['rag_documents']` — lista de documentos recuperados
    - `state['rag_context']` — contexto formatado para o prompt da LLM

    Args:
        state: Estado atual do grafo LangGraph.

    Returns:
        Estado atualizado com documentos RAG.
    """
    query = state.get("query", "")
    preprocess_id = state.get("preprocess_id")

    logger.info(f"[RAG] Buscando contexto para: '{query[:80]}'")

    documents = _query_rag(
        query=query,
        preprocess_id=preprocess_id,
    )

    # Formata o contexto para injeção no prompt
    context_parts: List[str] = []
    for i, doc in enumerate(documents, start=1):
        dataset = doc.get("dataset", "desconhecido")
        score = doc.get("similarity_score", 0.0)
        content = doc.get("content", "").strip()
        source_type = doc.get("source_type", "")

        # Mapeia dataset para nome amigável para citação inline
        dataset_label = {
            "qas": "PubMedQA/MedQuAD",
            "clinical_protocols": "FHEMIG (Protocolos Clínicos)",
        }.get(dataset, dataset)

        part = (
            f"[Contexto {i} — Fonte: {dataset_label}, score: {score:.2f}]\n"
            f"{content}"
        )
        context_parts.append(part)

    rag_context = "\n\n".join(context_parts) if context_parts else ""

    if not documents:
        logger.warning("[RAG] Nenhum documento relevante encontrado na base RAG.")
    else:
        logger.info(f"[RAG] {len(documents)} documentos recuperados e contexto montado.")

    return {
        **state,
        "rag_documents": documents,
        "rag_context": rag_context,
    }
