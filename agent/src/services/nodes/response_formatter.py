"""
Nó 5: Formatador de Resposta (Response Formatter)

Pós-processa a resposta bruta da LLM para:
1. Garantir que o disclaimer obrigatório esteja presente ao final
2. Validar e completar a citação de fontes inline
3. Garantir que `requires_human_validation` seja sempre True

Este nó é o ponto de controle final antes da auditoria, assegurando que
todas as respostas saiam padronizadas independentemente do conteúdo da LLM.
"""
import difflib
import logging
import re
from typing import List, Optional

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


def _add_missing_source_summary(
    response: str,
    sources_cited: List[str],
    rag_documents: Optional[List[dict]] = None,
) -> str:
    """
    Se a LLM não citou as fontes inline, adiciona um rodapé com as fontes usadas
    e links públicos (URLs) quando disponíveis nos metadados dos documentos.

    Args:
        response: Texto da resposta da LLM.
        sources_cited: Lista de fontes utilizadas no RAG.
        rag_documents: Lista de documentos brutos do RAG com metadados/URLs.

    Returns:
        Resposta com rodapé de fontes se necessário.
    """
    if not sources_cited and not rag_documents:
        return response

    # Verifica se a LLM já citou pelo menos uma fonte inline
    has_inline_citation = bool(re.search(r"\[Fonte:", response, re.IGNORECASE))

    if not has_inline_citation:
        formatted_links = []
        seen_urls = set()

        if rag_documents:
            for doc in rag_documents:
                meta = doc.get("metadatas") or {}
                if isinstance(meta, dict):
                    url = meta.get("url") or (meta.get("source", {}).get("url") if isinstance(meta.get("source"), dict) else None)
                    name = meta.get("name") or meta.get("source_label") or doc.get("dataset", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        clean_name = name.replace(".pdf", "")
                        if "---" in clean_name:
                            code, rest = clean_name.split("---", 1)
                            clean_name = f"{code} — {rest.replace('-', ' ')}"
                        clean_name = re.sub(r"\s+", " ", clean_name).strip()
                        source_label = meta.get("source_label")
                        display_title = f"{source_label}: {clean_name}" if source_label and clean_name != source_label else clean_name
                        formatted_links.append(f"[{display_title}]({url})")

        if formatted_links:
            sources_list = ", ".join(formatted_links)
        elif sources_cited:
            sources_list = ", ".join(sources_cited)
        else:
            return response

        footer = f"\n\n📚 **Fontes consultadas**: {sources_list}"
        return response + footer

    return response


def _blocks_are_similar(block1: List[str], block2: List[str], threshold: float = 0.85) -> bool:
    """Verifica se dois blocos de sentenças são aproximadamente idênticos."""
    if len(block1) != len(block2):
        return False
    t1 = " ".join(block1).lower()
    t2 = " ".join(block2).lower()
    return difflib.SequenceMatcher(None, t1, t2).ratio() >= threshold


def _remove_repetition_loops(text: str) -> str:
    """
    Detecta e remove loops de degeneração/repetição de frases ou blocos de sentenças,
    comum em modelos LLM menores (ex: 1.5B) operando com amostragem gananciosa.

    Exemplos tratados:
    - Sentença repetida consecutivamente: "Frase A. Frase A. Frase A." -> "Frase A."
    - Quase-duplicatas morfológicas (singular/plural, sinônimos com ratio >= 0.85).
    - Ciclos de blocos de sentenças repetidas com fuzzy matching (ratio >= 0.85).
    - Frases repetidas intra-sentença: "tosse seca tosse seca tosse seca" -> "tosse seca".
    - Sentença final incompleta (dangling sentence) gerada por estouro de tokens.
    """
    if not text:
        return text

    # 1. Trata repetições de frases intra-sentença (mínimo de 6 caracteres repetidos 2+ vezes consecutivas)
    text = re.sub(r"(\b[a-zA-ZÀ-ÿ0-9\s,]{6,}?\b)(\s+\1){2,}", r"\1", text)

    paragraphs = text.split("\n")
    cleaned_paras = []

    for para in paragraphs:
        stripped = para.strip()
        if not stripped:
            cleaned_paras.append(para)
            continue

        # Divide sentenças preservando pontuação final
        raw_sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", stripped) if s.strip()]
        if not raw_sentences:
            cleaned_paras.append(para)
            continue

        # Remove sentença final incompleta (dangling sentence) gerada por estouro de tokens
        if len(raw_sentences) > 1 and not re.search(r"[.!?:]$", raw_sentences[-1]):
            raw_sentences.pop()

        # Colapsa sentenças consecutivas idênticas ou fuzzy similares (ratio >= 0.85)
        deduped = []
        for s in raw_sentences:
            if not deduped:
                deduped.append(s)
                continue

            prev = deduped[-1]
            sim = difflib.SequenceMatcher(None, prev.lower(), s.lower()).ratio()
            if sim >= 0.85:
                continue

            # Prefixo longo compartilhado
            common_len = 0
            for c1, c2 in zip(prev.lower(), s.lower()):
                if c1 == c2:
                    common_len += 1
                else:
                    break
            max_l = max(len(prev), len(s))
            if common_len >= 25 and (common_len / max_l) > 0.5:
                continue

            deduped.append(s)

        # Detecta e remove repetições cíclicas de blocos de sentenças (k=2, 3, 4) com fuzzy matching
        for k in (2, 3, 4):
            while len(deduped) >= 2 * k:
                last_block = deduped[-k:]
                prev_block = deduped[-2 * k : -k]
                if _blocks_are_similar(last_block, prev_block, threshold=0.85):
                    deduped = deduped[:-k]
                else:
                    break

        cleaned_paras.append(" ".join(deduped))

    return "\n".join(cleaned_paras)


def _clean_llm_artifacts(text: str) -> str:
    """
    Remove artefatos comuns gerados pela LLM que não devem aparecer na resposta.

    - Remove tokens especiais residuais do formato ChatML
    - Remove loops de repetição/degeneração de sentenças
    - Remove repetições excessivas de pontuação
    """
    # Remove tokens ChatML residuais
    text = re.sub(r"<\|im_(start|end)\|>", "", text)
    text = re.sub(r"\b(system|assistant|user)\b\n?", "", text, flags=re.IGNORECASE)

    # Remove loops de repetição de sentenças (defesa contra degeneração da LLM)
    text = _remove_repetition_loops(text)

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
    - `state['rag_documents']` — lista de documentos RAG com metadados

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
    rag_documents = state.get("rag_documents", [])

    logger.info("[FORMAT] Formatando resposta final...")

    # 1. Limpar artefatos da LLM
    cleaned = _clean_llm_artifacts(raw_response)

    # 2. Garantir rodapé de fontes se não há citações inline (com URLs se disponíveis)
    with_sources = _add_missing_source_summary(cleaned, sources_cited, rag_documents=rag_documents)

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
