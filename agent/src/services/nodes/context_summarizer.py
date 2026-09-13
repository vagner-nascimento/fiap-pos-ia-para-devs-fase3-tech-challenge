"""
Nó 3.2: Sumarizador de Contexto (Context Summarizer)

Garante que o prompt enviado à LLM fine-tunada caiba dentro da janela de
contexto do SFT (3.000 tokens). O modelo foi treinado com sequências de até
3K tokens — passar mais não causa erro, mas degrada a qualidade da resposta.

Estratégia em três camadas:
1. Contexto total ≤ 85% do limite → passa sem modificação (caso mais comum).
2. Contexto total > 85% + GROQ_API_KEY configurada → sumariza via
   `groq/compound-mini` (70K TPM, sem limite de tokens/dia).
3. Contexto total > 85% + sem GROQ_API_KEY → fallback de truncação Python
   por prioridade estrita (query > alergias/diagnóstico > RAG top-score
   > histórico), garantindo funcionamento sem dependência externa.

Rate limits do groq/compound-mini (free tier):
  30 RPM | 250 RPD | 70K TPM | sem limite de tokens/dia
"""
import logging
import os
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

CHARS_PER_TOKEN: float = 3.5
MAX_CONTEXT_TOKENS: int = int(os.getenv("LLM_MAX_CONTEXT_TOKENS", "3000"))
# Reserva para system prompt, cabeçalhos e margem de segurança
RESERVED_TOKENS: int = 400
# Budget disponível para conteúdo dinâmico (tokens → chars)
BUDGET_CHARS: int = int((MAX_CONTEXT_TOKENS - RESERVED_TOKENS) * CHARS_PER_TOKEN)
# Threshold para acionar o sumarizador (85% do budget)
SUMMARIZE_THRESHOLD_CHARS: int = int(BUDGET_CHARS * 0.85)

GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GROQ_SUMMARIZER_MODEL: str = os.getenv("GROQ_SUMMARIZER_MODEL", "groq/compound-mini")
GROQ_API_BASE: str = "https://api.groq.com/openai/v1"


# ---------------------------------------------------------------------------
# Estimativa de tamanho
# ---------------------------------------------------------------------------

def _estimate_chars(state: dict) -> int:
    """Estima o total de chars que comporão o prompt do llm_generator."""
    query = state.get("query", "")
    rag = state.get("rag_context", "")
    patient = state.get("patient_context", "")
    history = state.get("conversation_history", [])
    history_text = "".join(
        f"{t.get('query','')}{t.get('response','')}" for t in history
    )
    return len(query) + len(rag) + len(patient) + len(history_text)


# ---------------------------------------------------------------------------
# Fallback Python — truncação por prioridade
# ---------------------------------------------------------------------------

def _truncate_at_sentence(text: str, max_chars: int) -> str:
    """Trunca o texto no limite preservando a última frase completa."""
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    last_period = max(truncated.rfind("."), truncated.rfind("!"), truncated.rfind("?"))
    return truncated[:last_period + 1] if last_period > max_chars * 0.6 else truncated


def _python_fallback_compress(state: dict) -> dict:
    """
    Comprime o contexto por prioridade estrita sem chamar nenhuma API externa.

    Prioridade (maior → menor):
      1. query — nunca truncada
      2. patient_context (alergias e diagnósticos)
      3. rag_context (chunks com maior similarity_score primeiro)
      4. conversation_history (turnos mais antigos removidos primeiro)
    """
    remaining = BUDGET_CHARS

    query = state.get("query", "")
    remaining -= len(query)

    # Patient context — trunca preservando início (diagnósticos/alergias)
    patient_raw = state.get("patient_context", "")
    patient_alloc = min(len(patient_raw), int(BUDGET_CHARS * 0.30))
    patient_compressed = _truncate_at_sentence(patient_raw, patient_alloc)
    remaining -= len(patient_compressed)

    # RAG context — trunca preservando início (chunk mais relevante)
    rag_raw = state.get("rag_context", "")
    rag_alloc = min(len(rag_raw), max(0, remaining - int(BUDGET_CHARS * 0.10)))
    rag_compressed = _truncate_at_sentence(rag_raw, rag_alloc)
    remaining -= len(rag_compressed)

    # Histórico — remove turnos mais antigos até caber
    history: List[Dict[str, Any]] = list(state.get("conversation_history", []))
    while history and remaining < 0:
        history.pop(0)
        history_chars = sum(
            len(t.get("query", "")) + len(t.get("response", "")) for t in history
        )
        remaining = BUDGET_CHARS - len(query) - len(patient_compressed) - len(rag_compressed) - history_chars

    logger.info(
        "[SUMMARIZER] Fallback Python: "
        "patient=%d→%d chars | rag=%d→%d chars | history=%d turnos",
        len(patient_raw), len(patient_compressed),
        len(rag_raw), len(rag_compressed),
        len(history),
    )

    return {
        **state,
        "compressed_patient_context": patient_compressed,
        "compressed_rag_context": rag_compressed,
        "conversation_history": history,
        "context_summarized": True,
        "context_summarizer_mode": "python_fallback",
    }


# ---------------------------------------------------------------------------
# Sumarização via Groq
# ---------------------------------------------------------------------------

def _groq_summarize(query: str, full_context: str, max_chars: int) -> str:
    """
    Chama groq/compound-mini para sumarizar o contexto clínico combinado.

    Args:
        query: Pergunta do médico (usada para focar o resumo).
        full_context: Contexto completo (prontuário + RAG) a resumir.
        max_chars: Limite de caracteres para o resumo gerado.

    Returns:
        Texto resumido ou o contexto original se a chamada falhar.
    """
    try:
        import requests as req

        system_prompt = (
            "Voce e um assistente que resume contextos clinicos para uso em sistemas de IA medica. "
            "Preserve: (1) diagnosticos e condicoes ativas, (2) medicamentos e alergias, "
            "(3) informacoes de protocolos relevantes para a pergunta. "
            "NAO inclua dados de identificacao do paciente. "
            f"Responda em no maximo {max_chars} caracteres."
        )
        user_prompt = f"Pergunta: {query}\n\nContexto:\n{full_context}"

        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": GROQ_SUMMARIZER_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": int(max_chars / CHARS_PER_TOKEN),
            "temperature": 0.1,
        }

        response = req.post(
            f"{GROQ_API_BASE}/chat/completions",
            json=payload,
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        summary = data["choices"][0]["message"]["content"].strip()
        logger.info(
            "[SUMMARIZER] Groq resumiu: %d → %d chars (%s)",
            len(full_context), len(summary), GROQ_SUMMARIZER_MODEL,
        )
        return summary

    except Exception as exc:
        logger.warning("[SUMMARIZER] Groq falhou (%s). Usando fallback Python.", exc)
        return ""


# ---------------------------------------------------------------------------
# Nó LangGraph
# ---------------------------------------------------------------------------

def context_summarizer_node(state: dict) -> dict:
    """
    Nó LangGraph: garante que o contexto caiba na janela de 3K tokens do SFT.

    Lê:
    - `state['query']` — pergunta do médico
    - `state['rag_context']` — contexto RAG formatado
    - `state['patient_context']` — dados clínicos do paciente (Jornada 2)
    - `state['conversation_history']` — histórico da sessão

    Escreve:
    - `state['compressed_rag_context']` — RAG (possivelmente comprimido)
    - `state['compressed_patient_context']` — dados do paciente (possivelmente comprimidos)
    - `state['context_summarized']` — se a compressão foi aplicada
    - `state['context_summarizer_mode']` — "not_needed" | "groq" | "python_fallback"

    Args:
        state: Estado atual do grafo LangGraph.

    Returns:
        Estado atualizado com contextos possivelmente comprimidos.
    """
    total_chars = _estimate_chars(state)

    logger.info(
        "[SUMMARIZER] Contexto total estimado: %d chars (~%d tokens) | "
        "threshold: %d chars (~%d tokens)",
        total_chars, int(total_chars / CHARS_PER_TOKEN),
        SUMMARIZE_THRESHOLD_CHARS, int(SUMMARIZE_THRESHOLD_CHARS / CHARS_PER_TOKEN),
    )

    if total_chars <= SUMMARIZE_THRESHOLD_CHARS:
        # Contexto cabe na janela — passa os campos brutos como comprimidos
        logger.info("[SUMMARIZER] Contexto dentro do limite — sem compressão.")
        return {
            **state,
            "compressed_rag_context": state.get("rag_context", ""),
            "compressed_patient_context": state.get("patient_context", ""),
            "context_summarized": False,
            "context_summarizer_mode": "not_needed",
        }

    logger.info(
        "[SUMMARIZER] Contexto excede threshold (%d chars). "
        "GROQ_API_KEY=%s → modo: %s",
        total_chars,
        "configurada" if GROQ_API_KEY else "ausente",
        "groq" if GROQ_API_KEY else "python_fallback",
    )

    if not GROQ_API_KEY:
        return _python_fallback_compress(state)

    # Sumarização via Groq — combina patient_context + rag_context
    query = state.get("query", "")
    patient_ctx = state.get("patient_context", "")
    rag_ctx = state.get("rag_context", "")
    full_context = "\n\n".join(filter(None, [patient_ctx, rag_ctx]))

    max_summary_chars = int(BUDGET_CHARS * 0.80)
    summary = _groq_summarize(query, full_context, max_summary_chars)

    if not summary:
        # Groq falhou → fallback Python
        return _python_fallback_compress(state)

    # Divide o resumo entre patient e rag proporcionalmente
    if patient_ctx and rag_ctx:
        split = int(len(summary) * 0.35)  # ~35% para dados do paciente
        compressed_patient = summary[:split].strip()
        compressed_rag = summary[split:].strip()
    elif patient_ctx:
        compressed_patient = summary
        compressed_rag = ""
    else:
        compressed_patient = ""
        compressed_rag = summary

    return {
        **state,
        "compressed_rag_context": compressed_rag,
        "compressed_patient_context": compressed_patient,
        "context_summarized": True,
        "context_summarizer_mode": "groq",
    }
