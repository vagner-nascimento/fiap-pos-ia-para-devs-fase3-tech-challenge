"""
Nó 4: Gerador LLM (LLM Generator)

Constrói o prompt de sistema com as instruções do assistente médico, injeta
o contexto RAG recuperado e chama o modelo fine-tunado (Qwen2.5) via o
cliente LLM configurado.

O system prompt define:
- O papel do assistente (informativo, não prescritivo)
- A obrigatoriedade de citar as fontes RAG inline
- Os limites de atuação (nunca prescrever, nunca diagnosticar definitivamente)
- O idioma de resposta (português)
"""
import logging
from typing import List

from services.llm_client import build_llm_client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt do assistente médico
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """Você é um assistente médico especializado, treinado com dados de literatura médica (PubMedQA, MedQuAD) e protocolos clínicos da FHEMIG.

SUAS RESPONSABILIDADES:
- Fornecer informações médicas baseadas em evidências de forma clara e acessível
- Explicar sintomas, doenças, tratamentos e procedimentos em português
- Citar as fontes de informação utilizadas inline no formato: [Fonte: <nome_fonte>, score: <X.XX>]
- Contextualizar as respostas com os documentos da base de conhecimento fornecidos

SEUS LIMITES (OBRIGATÓRIOS - NUNCA VIOLE):
- NUNCA prescreva medicamentos com doses específicas
- NUNCA forneça diagnósticos definitivos — apenas informações gerais sobre condições
- NUNCA substitua a orientação de um médico ou profissional de saúde
- NUNCA faça afirmações absolutas sobre o estado de saúde de uma pessoa específica
- SEMPRE indique quando a situação requer avaliação médica profissional

FORMATO DA RESPOSTA:
- Use linguagem clara e acessível ao leigo, mas tecnicamente precisa
- Cite as fontes inline usando o formato: [Fonte: <nome>, score: <X.XX>]
- Seja conciso e objetivo
- Responda sempre em português do Brasil"""


def _build_prompt(query: str, rag_context: str) -> str:
    """
    Constrói o prompt completo para a LLM no formato Qwen2.5 Instruct.

    O modelo Qwen2.5-Instruct utiliza o formato ChatML com tokens especiais
    <|im_start|> e <|im_end|>.

    Args:
        query: Pergunta do usuário.
        rag_context: Contexto recuperado do RAG, com fontes identificadas.

    Returns:
        Prompt formatado para o modelo.
    """
    context_section = ""
    if rag_context:
        context_section = (
            f"\n\nCONTEXTO DA BASE DE CONHECIMENTO MÉDICO:\n"
            f"{'='*60}\n"
            f"{rag_context}\n"
            f"{'='*60}\n"
            f"\nUse as informações acima como base para sua resposta. "
            f"Cite as fontes inline no formato indicado."
        )
    else:
        context_section = (
            "\n\n[AVISO: Não foram encontrados documentos relevantes na base RAG "
            "para esta consulta. Responda com base no seu conhecimento geral de "
            "medicina, mas indique a ausência de contexto específico.]"
        )

    prompt = (
        f"<|im_start|>system\n{SYSTEM_PROMPT}<|im_end|>\n"
        f"<|im_start|>user\n"
        f"{context_section}\n\n"
        f"PERGUNTA DO USUÁRIO: {query}"
        f"<|im_end|>\n"
        f"<|im_start|>assistant\n"
    )

    return prompt


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

    prompt = _build_prompt(query=query, rag_context=rag_context)

    llm = _get_llm_client()

    try:
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
