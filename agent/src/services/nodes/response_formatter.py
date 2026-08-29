"""
Nó 5: Formatador de Resposta (Response Formatter)

Pós-processa a resposta bruta da LLM para:
1. Garantir que o disclaimer obrigatório esteja presente ao final
2. Validar e completar a citação de fontes inline
3. Garantir que `requires_human_validation` seja sempre True

Este nó é o ponto de controle final antes da auditoria, assegurando que
todas as respostas saiam padronizadas independentemente do conteúdo da LLM.
"""
import logging
import re
from typing import List

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes de formatação
# ---------------------------------------------------------------------------
DISCLAIMER = (
    "\n\n---\n"
    "⚠️ **AVISO IMPORTANTE**: Este assistente médico fornece informações gerais "
    "baseadas em literatura médica e protocolos clínicos. "
    "**Não substitui a avaliação, diagnóstico ou prescrição de um profissional de saúde habilitado.** "
    "Em caso de dúvidas ou emergências médicas, consulte um médico ou ligue para o SAMU (192)."
)


def _has_disclaimer(text: str) -> bool:
    """Verifica se o disclaimer já está presente na resposta."""
    return "AVISO IMPORTANTE" in text or "não substitui" in text.lower()


def _add_missing_source_summary(response: str, sources_cited: List[str]) -> str:
    """
    Se a LLM não citou as fontes inline, adiciona um rodapé com as fontes usadas.

    Args:
        response: Texto da resposta da LLM.
        sources_cited: Lista de fontes utilizadas no RAG.

    Returns:
        Resposta com rodapé de fontes se necessário.
    """
    if not sources_cited:
        return response

    # Verifica se a LLM já citou pelo menos uma fonte inline
    has_inline_citation = bool(re.search(r"\[Fonte:", response, re.IGNORECASE))

    if not has_inline_citation:
        sources_list = ", ".join(sources_cited)
        footer = (
            f"\n\n📚 **Fontes consultadas**: {sources_list}"
        )
        return response + footer

    return response


def _clean_llm_artifacts(text: str) -> str:
    """
    Remove artefatos comuns gerados pela LLM que não devem aparecer na resposta.

    - Remove tokens especiais residuais do formato ChatML
    - Remove repetições excessivas de pontuação
    """
    # Remove tokens ChatML residuais
    text = re.sub(r"<\|im_(start|end)\|>", "", text)
    text = re.sub(r"\b(system|assistant|user)\b\n?", "", text, flags=re.IGNORECASE)

    # Remove linhas em branco excessivas (mais de 2 consecutivas)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


# ---------------------------------------------------------------------------
# Nó LangGraph
# ---------------------------------------------------------------------------
def response_formatter_node(state: dict) -> dict:
    """
    Nó LangGraph: formata a resposta final da LLM.

    Lê:
    - `state['llm_response_raw']` — resposta bruta da LLM
    - `state['sources_cited']` — lista de fontes utilizadas

    Escreve:
    - `state['final_response']` — resposta final formatada e com disclaimer
    - `state['has_disclaimer']` — confirmação de que o disclaimer está presente

    Args:
        state: Estado atual do grafo LangGraph.

    Returns:
        Estado atualizado com a resposta formatada.
    """
    raw_response = state.get("llm_response_raw", "")
    sources_cited = state.get("sources_cited", [])

    logger.info("[FORMAT] Formatando resposta final...")

    # 1. Limpar artefatos da LLM
    cleaned = _clean_llm_artifacts(raw_response)

    # 2. Garantir rodapé de fontes se não há citações inline
    with_sources = _add_missing_source_summary(cleaned, sources_cited)

    # 3. Garantir disclaimer obrigatório
    if not _has_disclaimer(with_sources):
        final_response = with_sources + DISCLAIMER
    else:
        final_response = with_sources

    logger.info(
        f"[FORMAT] Resposta formatada: {len(final_response)} chars, "
        f"disclaimer={'sim' if _has_disclaimer(final_response) else 'NÃO'}"
    )

    return {
        **state,
        "final_response": final_response,
        "has_disclaimer": True,  # sempre True após este nó
        "requires_human_validation": True,  # invariante do sistema
    }
