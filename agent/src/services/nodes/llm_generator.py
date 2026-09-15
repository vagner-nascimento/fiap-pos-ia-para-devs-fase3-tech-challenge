"""
Nó 4: Gerador LLM (LLM Generator)

Injeta o contexto RAG recuperado, formata o prompt de acordo com o padrão
de fine-tuning (SFT) do modelo Qwen2.5 (hospital-helper) e chama a LLM
através do cliente híbrido (Hugging Face Spaces ZeroGPU ou FastAPI ngrok).

Se `patient_context` estiver no estado (Jornada 2), é injetado no prompt
com uma seção dedicada de dados clínicos anônimos do paciente, orientando
a LLM a cruzar protocolo com histórico clínico.
"""
import logging
import os
import re
from typing import List

from services.llm_client import build_llm_client

logger = logging.getLogger(__name__)


def _build_prompt(
    question: str,
    context: str = "",
    patient_context: str = "",
    medical_reports_context: str = "",
    conversation_history: list[dict[str, str]] | None = None,
) -> str:
    """
    Constrói o prompt no formato EXATO utilizado durante o fine-tuning SFT
    do modelo hospital-helper-qwen2.5-1.5b.

    Se `patient_context` for fornecido (Jornada 2), uma seção de dados clínicos
    anônimos do paciente é inserida no prompt, orientando a LLM a cruzar
    protocolo com histórico clínico individual.

    Args:
        question: Pergunta do usuário.
        context: Contexto recuperado do RAG (opcional).
        patient_context: Dados clínicos anônimos do paciente (opcional, Jornada 2).
        medical_reports_context: Laudos médicos consolidados do paciente (opcional, Jornada 2).

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
    if patient_context:
        lines.extend([
            "",
            "### Dados Clinicos do Paciente (sem identificacao pessoal):",
            patient_context,
            "",
            "(Use os dados clinicos acima para contextualizar sua resposta, "
            "citando-os quando relevante para a pergunta.)",
        ])
    if medical_reports_context and medical_reports_context not in (patient_context or ""):
        lines.extend([
            "",
            "### Laudos Medicos do Paciente (texto consolidado):",
            medical_reports_context,
            "",
        ])
    if context:
        lines.extend(["Contexto:", context])
    lines.extend(["", "### Resposta:"])
    logger.info(
        f"[LLM] Prompt final construído: {lines}"
    )
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


def _looks_like_exam_history_question(question: str) -> bool:
    """Heurística para detectar perguntas sobre exames/resultados/relatórios."""
    text = question.lower()
    keywords = (
        "exame",
        "exames",
        "resultado",
        "resultados",
        "laudo",
        "laudos",
        "relatorio",
        "relatórios",
        "arquivo",
        "ultima",
        "última",
        "últimos",
        "histórico",
    )
    return bool(re.search(r"\b(?:" + "|".join(re.escape(k) for k in keywords) + r")\b", text))


def _has_grounded_exam_evidence(text: str) -> bool:
    """Indica se o texto do paciente ou laudo contém indicadores confiáveis de um exame registrado."""
    if not text:
        return False
    pattern = r"(?:tipo de exame|descricao tecnica|impressao diagnostica|cid-10|conduta|laudo\s*\d+|resultado)"
    return bool(re.search(pattern, text, flags=re.IGNORECASE))


def _extract_direct_exam_answer(question: str, patient_context: str, medical_reports_context: str) -> str | None:
    """Responde de forma direta perguntas sobre tipo/último exame quando há contexto de laudo."""
    q = question.lower()
    evidence = "\n".join(filter(None, [patient_context, medical_reports_context]))
    if not evidence or not _looks_like_exam_history_question(question):
        return None

    exam_type = None
    exam_date = None
    impression = None
    conduta = None

    for pattern in [
        r"tipo de exame\s*[:\-]?\s*([^\n.;]+)",
        r"tipo do exame\s*[:\-]?\s*([^\n.;]+)",
    ]:
        match = re.search(pattern, evidence, flags=re.IGNORECASE)
        if match:
            exam_type = match.group(1).strip()
            break

    match_date = re.search(r"data\s*[:\-]?\s*(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})", evidence, flags=re.IGNORECASE)
    if match_date:
        exam_date = match_date.group(1).strip()

    for pattern in [
        r"impressao diagnostica\s*[:\-]?\s*([^\n.;]+)",
        r"diagnostico\s*[:\-]?\s*([^\n.;]+)",
    ]:
        match = re.search(pattern, evidence, flags=re.IGNORECASE)
        if match:
            impression = match.group(1).strip()
            break

    match_conduta = re.search(r"conduta\s*[:\-]?\s*([^\n.;]+)", evidence, flags=re.IGNORECASE)
    if match_conduta:
        conduta = match_conduta.group(1).strip()

    if any(term in q for term in ("tipo do último exame", "tipo do exame", "qual foi o tipo", "quais foram os últimos exames", "último exame")):
        if exam_type:
            details = [f"O último exame registrado foi um {exam_type}."]
            if exam_date:
                details.append(f"Ele foi realizado em {exam_date}.")
            if impression:
                details.append(f"A impressão diagnóstica registrada foi: {impression}.")
            if conduta:
                details.append(f"A conduta documentada foi: {conduta}.")
            return " ".join(details)

    if any(term in q for term in ("resultado", "resultados")):
        has_exam_indicators = bool(re.search(r"(?:tipo de exame|impressao diagnostica|cid-10|conduta|laudo)\b", evidence, flags=re.IGNORECASE))
        if not has_exam_indicators:
            return None
        if impression:
            result = impression
            details = [f"O resultado registrado foi: {result}."]
            if exam_type:
                details.insert(0, f"No contexto do último exame ({exam_type}),")
            if conduta:
                details.append(f"A conduta documentada foi: {conduta}.")
            return " ".join(details)

    return None


def _build_contextual_patient_answer(question: str, patient_context: str, medical_reports_context: str) -> str | None:
    """Gera uma resposta segura e mais explicativa para dúvidas sobre cuidado/conduta com base no contexto do paciente."""
    q = question.lower()
    if not any(term in q for term in ("cuidados", "prescrever", "prescrição", "tratamento", "conduta", "quadro clínico", "orienta")):
        return None

    evidence = "\n".join(filter(None, [patient_context, medical_reports_context]))
    if not evidence:
        return None

    diagnosis = None
    for pattern in [
        r"impressao diagnostica\s*[:\-]?\s*([^\n.;]+)",
        r"diagnostico\s*[:\-]?\s*([^\n.;]+)",
        r"diagnosticos?/avaliacao\s*[:\-]?\s*([^\n.;]+)",
    ]:
        match = re.search(pattern, evidence, flags=re.IGNORECASE)
        if match:
            diagnosis = match.group(1).strip()
            break

    conduta = None
    match = re.search(r"conduta\s*[:\-]?\s*([^\n.;]+)", evidence, flags=re.IGNORECASE)
    if match:
        conduta = match.group(1).strip()
    else:
        match = re.search(r"orientacoes\s*[:\-]?\s*([^\n.;]+)", evidence, flags=re.IGNORECASE)
        if match:
            conduta = match.group(1).strip()

    if diagnosis:
        sentence = f"O contexto clínico do paciente aponta para {diagnosis}."
        if conduta:
            sentence += f" A conduta registrada no histórico foi: {conduta}."
        sentence += " Em termos gerais, o manejo deve ser individualizado por um profissional de saúde, com avaliação clínica e acompanhamento adequado do quadro atual."
        return sentence

    return None


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
    # Preferência por contextos já comprimidos pelo context_summarizer (se ativado)
    rag_context = state.get("compressed_rag_context") or state.get("rag_context", "")
    patient_context = state.get("compressed_patient_context") or state.get("patient_context", "")
    medical_reports_context = (
        state.get("compressed_medical_reports_context")
        or state.get("medical_reports_context", "")
    )
    rag_documents = state.get("rag_documents", [])
    conversation_history = state.get("conversation_history", [])

    logger.info(
        f"[LLM] Gerando resposta para: '{query[:80]}' "
        f"patient_context={'sim' if patient_context else 'nao'} "
        f"medical_reports_context={'sim' if medical_reports_context else 'nao'} "
    )

    direct_answer = _extract_direct_exam_answer(query, patient_context, medical_reports_context)
    if direct_answer:
        logger.info("[LLM] Resposta direta de contexto clínico aplicada para pergunta de exame: %s", query)
        return {
            **state,
            "llm_response_raw": direct_answer,
            "sources_cited": [],
        }

    contextual_answer = _build_contextual_patient_answer(query, patient_context, medical_reports_context)
    if contextual_answer:
        logger.info("[LLM] Resposta contextualizada do paciente aplicada para: %s", query)
        return {
            **state,
            "llm_response_raw": contextual_answer,
            "sources_cited": [],
        }

    if (
        not rag_documents
        and _looks_like_exam_history_question(query)
        and not _has_grounded_exam_evidence(patient_context)
        and not _has_grounded_exam_evidence(medical_reports_context)
    ):
        fallback = (
            "Não encontrei exames ou laudos registrados para esse paciente nos dados disponíveis. "
            "Sem um laudo ou resultado clínico confiável no contexto acessível, não posso responder "
            "com precisão sobre exames específicos."
        )
        logger.warning(
            "[LLM] Bloqueando resposta sem grounding para pergunta de exames/resultados: %s",
            query,
        )
        return {
            **state,
            "llm_response_raw": fallback,
            "sources_cited": [],
        }

    prompt = _build_prompt(
        question=query,
        context=rag_context,
        patient_context=patient_context,
        medical_reports_context=medical_reports_context,
        conversation_history=conversation_history,
    )

    # -----------------------------------------------------------------------
    # Métricas de consumo da janela de contexto
    # O Qwen2.5 usa tokenização similar ao GPT-4 (cl100k).
    # Proporção empírica para PT-BR: ~3.5 chars/token.
    # -----------------------------------------------------------------------
    CHARS_PER_TOKEN = 3.5
    # Limite real da janela do SFT (fine-tuning), não do modelo base (32K).
    # O modelo foi treinado com sequências de até 3K tokens, passar mais
    # degrada a qualidade da resposta.
    MAX_CONTEXT_TOKENS = int(os.getenv("LLM_MAX_CONTEXT_TOKENS", "3000"))
    max_new_tokens = getattr(_get_llm_client(), "max_new_tokens", 450)
    if not isinstance(max_new_tokens, (int, float)):
        max_new_tokens = 450

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
