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


def _build_prompt(
    question: str,
    context: str = "",
    conversation_history: list[dict[str, str]] | None = None,
) -> str:
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
    if conversation_history:
        lines.extend(["", "### Historico da conversa:"])
        for turn in conversation_history:
            lines.extend(
                [
                    f"Usuario: {turn.get('query', '')}",
                    f"Assistente: {turn.get('response', '')}",
                ]
            )
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
    conversation_history = state.get("conversation_history", [])

    logger.info(f"[LLM] Gerando resposta para: '{query[:80]}'")

    prompt = _build_prompt(
        question=query,
        context=rag_context,
        conversation_history=conversation_history,
    )

    # -----------------------------------------------------------------------
    # Métricas de consumo da janela de contexto
    # O Qwen2.5 usa tokenização similar ao GPT-4 (cl100k).
    # Proporção empírica para PT-BR: ~3.5 chars/token.
    # -----------------------------------------------------------------------
    CHARS_PER_TOKEN = 3.5
    MAX_CONTEXT_TOKENS = 32_768  # Qwen2.5-1.5B context window
    max_new_tokens = getattr(_get_llm_client(), "max_new_tokens", 450)

    # Detalha o tamanho de cada componente do prompt
    history_text = ""
    for turn in conversation_history:
        history_text += f"{turn.get('query','')} {turn.get('response','')}"

    input_tokens_est = int(len(prompt) / CHARS_PER_TOKEN)
    output_tokens_est = max_new_tokens
    total_tokens_est = input_tokens_est + output_tokens_est
    window_pct = total_tokens_est / MAX_CONTEXT_TOKENS * 100

    logger.info(
        "[LLM] Consumo de contexto estimado: "
        "input=~%d tokens | output_max=%d tokens | total=~%d tokens | "
        "janela=%d tokens (%.1f%% usado) | "
        "detalhes=[query=%d chars, historico=%d chars (%d turnos), rag=%d chars]",
        input_tokens_est, output_tokens_est, total_tokens_est,
        MAX_CONTEXT_TOKENS, window_pct,
        len(query), len(history_text), len(conversation_history), len(rag_context),
    )

    if window_pct > 80:
        logger.warning(
            "[LLM] ⚠️ Uso da janela de contexto acima de 80%% (%.1f%%). "
            "Considere reduzir AGENT_HISTORY_MAX_TURNS ou RAG_TOP_K.", window_pct
        )

    logger.debug(f"[LLM] Prompt completo ({len(prompt)} chars):\n{prompt}")

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

        output_tokens_real = int(len(raw_response) / CHARS_PER_TOKEN)
        logger.info(
            f"[LLM] Resposta gerada: {len(raw_response)} chars (~{output_tokens_real} tokens)."
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
