"""
Nó 4: Gerador LLM (LLM Generator)

Injeta o contexto RAG recuperado, formata o prompt de acordo com o padrão
de fine-tuning (SFT) do modelo Qwen2.5 (hospital-helper) e chama a LLM
através do cliente híbrido (Hugging Face Spaces ZeroGPU ou FastAPI ngrok).
"""
import logging
from typing import List

from services.llm_client import build_llm_client

logger = logging.getLogger(__name__)


def _build_prompt(question: str, context: str = "") -> str:
    """
    Constrói o prompt no formato EXATO utilizado durante o fine-tuning SFT
    do modelo hospital-helper-qwen2.5-1.5b.

    Args:
        question: Pergunta do usuário.
        context: Contexto recuperado do RAG (opcional).

    Returns:
        Prompt formatado para o modelo.
    """
    lines = [
        "### Instrucao:",
        "Responda em pt-BR usando o contexto clinico fornecido.",
        "",
        "### Entrada:",
        f"Pergunta: {question}",
    ]
    if context:
        lines.extend(["Contexto:", context])
    lines.extend(["", "### Resposta:"])
    return "\n".join(lines)


def _extract_sources_from_context(rag_documents: list) -> List[str]:
    """
    Extrai os nomes únicos das fontes dos documentos RAG utilizados.

    Args:
        rag_documents: Lista de documentos RAG.

    Returns:
        Lista de nomes de fontes únicos.
    """
    dataset_labels = {
        "qas": "PubMedQA/MedQuAD",
        "clinical_protocols": "FHEMIG (Protocolos Clínicos)",
    }
    sources = set()
    for doc in rag_documents:
        dataset = doc.get("dataset", "")
        label = dataset_labels.get(dataset, dataset)
        if label:
            sources.add(label)
    return sorted(sources)


# Singleton do cliente LLM (inicializado na primeira chamada)
_llm_client = None


def _get_llm_client():
    """Retorna o cliente LLM singleton."""
    global _llm_client
    if _llm_client is None:
        _llm_client = build_llm_client()
    return _llm_client


# ---------------------------------------------------------------------------
# Nó LangGraph
# ---------------------------------------------------------------------------
def llm_generator_node(state: dict) -> dict:
    """
    Nó LangGraph: gera a resposta utilizando a LLM fine-tunada.

    Lê:
    - `state['query']` — pergunta do usuário
    - `state['rag_context']` — contexto RAG formatado
    - `state['rag_documents']` — documentos RAG para extração de fontes

    Escreve:
    - `state['llm_response_raw']` — resposta bruta da LLM
    - `state['sources_cited']` — lista de fontes utilizadas

    Args:
        state: Estado atual do grafo LangGraph.

    Returns:
        Estado atualizado com a resposta da LLM.
    """
    query = state.get("query", "")
    rag_context = state.get("rag_context", "")
    rag_documents = state.get("rag_documents", [])

    logger.info(f"[LLM] Gerando resposta para: '{query[:80]}'")

    prompt = _build_prompt(question=query, context=rag_context)

    llm = _get_llm_client()

    try:
        if hasattr(llm, "generate"):
            raw_response = llm.generate(
                pergunta=query,
                contexto=rag_context,
                prompt=prompt,
            )
        else:
            raw_response = llm.invoke(prompt)

        logger.info(
            f"[LLM] Resposta gerada com {len(raw_response)} caracteres."
        )
    except Exception as exc:
        logger.error(f"[LLM] Erro ao chamar a LLM: {exc}")
        raw_response = (
            "Desculpe, ocorreu um erro ao processar sua consulta. "
            "Por favor, tente novamente."
        )

    sources = _extract_sources_from_context(rag_documents)

    return {
        **state,
        "llm_response_raw": raw_response,
        "sources_cited": sources,
    }
