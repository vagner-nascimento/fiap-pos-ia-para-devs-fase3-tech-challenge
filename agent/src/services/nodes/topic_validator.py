"""
Nó 1: Validador de Tópico (Topic Validator)

Verifica se a pergunta do usuário pertence ao domínio médico/saúde.
Perguntas fora do domínio são rejeitadas antes de qualquer processamento,
evitando desperdício de recursos e usos inadequados do assistente.

Estratégia: Verificação baseada em heurística de palavras-chave médicas em
português e inglês. Simples, determinística e sem custo de LLM.
"""
import logging
import re
from typing import Final, Set

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Keywords do domínio médico/saúde
# ---------------------------------------------------------------------------
MEDICAL_KEYWORDS: Final[Set[str]] = {
    # Termos gerais de saúde
    "saude", "saúde", "medico", "médico", "medica", "médica", "medicina",
    "hospital", "clinica", "clínica", "doenca", "doença", "sintoma", "sintomas",
    "tratamento", "terapia", "diagnostico", "diagnóstico", "prognostico",
    "prognóstico", "prevencao", "prevenção", "vacina", "vacinacao", "vacinação",
    "exame", "cirurgia", "cirurgiao", "cirurgião", "enfermagem", "enfermeiro",
    "enfermeira", "farmacia", "farmácia", "farmacologia", "medicamento",
    "remedio", "remédio", "droga", "dose", "posologia", "prescricao",
    "prescrição", "receita",
    # Anatomia e fisiologia
    "coracao", "coração", "pulmao", "pulmão", "figado", "fígado", "rim",
    "cerebro", "cérebro", "nervoso", "osseo", "ósseo", "musculo", "músculo",
    "sangue", "veia", "arteria", "artéria", "celula", "célula", "tecido",
    "orgao", "órgão", "sistema", "imunologico", "imunológico",
    # Doenças e condições
    "diabetes", "hipertensao", "hipertensão", "cancer", "câncer", "cancro", "tumor",
    "infeccao", "infecção", "virus", "vírus", "bacteria", "bactéria",
    "pneumonia", "tuberculose", "dengue", "malaria", "malária", "covid",
    "gripe", "influenza", "asma", "bronquite", "hepatite", "cirrose",
    "alzheimer", "parkinson", "depressao", "depressão", "ansiedade",
    "esquizofrenia", "epilepsia", "avc", "infarto", "trombose", "anemia",
    "leucemia", "lupus", "lúpus", "artrite", "osteoporose", "obesidade",
    "colesterol", "triglicerides", "triglicérides", "neoplasia", "oncologico",
    # Procedimentos e especialidades
    "radiografia", "tomografia", "ressonancia", "ressonância", "biopsia",
    "biópsia", "endoscopia", "colonoscopia", "cardiologia", "neurologia",
    "oncologia", "ortopedia", "pediatria", "ginecologia", "obstetricia",
    "obstetrícia", "dermatologia", "psiquiatria", "psicologia", "urologia",
    "oftalmologia", "otorrinolaringologia", "gastroenterologia",
    # Protocolos e termos clínicos
    "protocolo", "clinico", "clínico", "prontuario", "prontuário", "cid",
    "fhemig", "sus", "uti", "upa", "aps",
    # Termos em inglês (para queries mistas)
    "health", "medical", "disease", "patient", "therapy", "diagnosis",
    "treatment", "drug", "medicine", "symptom", "clinical", "hospital",
    "surgery", "infection", "virus", "bacteria", "cancer", "diabetes",
    "hypertension", "vaccine", "antibody", "immune",
}

# Palavras que indicam contexto de saúde indiretamente
CONTEXTUAL_MEDICAL_PATTERNS: Final[list] = [
    r"\b(como|qual|quais|quando|por que|porque)\b.{0,50}\b(tratar|curar|prevenir|diagnosticar|identificar)\b",
    r"\b(dor|dores)\b.{0,30}\b(cabeca|cabeça|de cabeça|peito|costas|abdomen|abdômen|estomago|estômago|garganta|barriga)\b",
    r"\bdor\b.{0,10}\bde\b.{0,10}\b(cabeça|dente|garganta|barriga|costas|peito)\b",
    r"\b(exame|resultado|laudo)\b",
    r"\bpaciente\b",
    r"\b(tomar|usar|aplicar)\b.{0,30}\b(medicament|remedio|remédio|antibiotico|antibiótico)\b",
    r"\b(câncer|cancer|cancro|neoplas|tumor|maligno|benigno)\b",
]


def _normalize(text: str) -> str:
    """Remove acentos e converte para minúsculas para comparação."""
    import unicodedata
    normalized = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in normalized if unicodedata.category(c) != "MN")


def is_medical_topic(query: str, last_history_turn: str = "") -> tuple[bool, str]:
    """
    Verifica se a query pertence ao domínio médico/saúde.

    Para suportar perguntas de follow-up em conversas multi-turno (ex: "pode
    resumir o que discutimos?"), quando a query isolada não passa nas
    verificações, o validador re-tenta concatenando-a com o último turno do
    histórico. A aprovação ainda exige keywords médicas — o histórico apenas
    fornece o contexto semântico, não é um bypass do guardrail.

    Args:
        query: Texto da pergunta do usuário.
        last_history_turn: Último turno da conversa (query + resposta anterior),
            usado como contexto de fallback quando a query isolada é ambígua.

    Returns:
        Tupla (is_valid: bool, reason: str) onde reason descreve o resultado.
    """
    if not query or not query.strip():
        return False, "Query vazia."

    # Normaliza a query (remove acentos) para comparação com keywords
    normalized_query = _normalize(query)
    # Também usa versão lower-case COM acentos para padrões contextuais
    lower_query = query.lower()

    # Verificação 1: Keywords diretas — normaliza as keywords também
    normalized_keywords = {_normalize(kw) for kw in MEDICAL_KEYWORDS}
    query_words = set(re.findall(r"\b[a-z0-9]{2,}\b", normalized_query))
    matched_keywords = query_words.intersection(normalized_keywords)
    if matched_keywords:
        sample = list(matched_keywords)[:3]
        logger.debug(f"[TOPIC] Keywords médicas encontradas: {sample}")
        return True, f"Domínio médico confirmado via keywords: {sample}"

    # Verificação 2: Padrões contextuais (usa texto original lower-case para preservar acentos)
    for pattern in CONTEXTUAL_MEDICAL_PATTERNS:
        if re.search(pattern, lower_query, re.IGNORECASE):
            logger.debug(f"[TOPIC] Padrão contextual médico encontrado.")
            return True, "Domínio médico confirmado via padrão contextual."

    # Verificação 3: Fallback com contexto do histórico (apenas para follow-ups)
    # Concatena a query com o último turno e re-valida as keywords.
    # Isso permite perguntas como "pode resumir?" ou "e os sinais de alerta?"
    # desde que o histórico imediato contenha termos médicos.
    if last_history_turn:
        expanded_text = f"{last_history_turn} {query}"
        normalized_expanded = _normalize(expanded_text)
        expanded_words = set(re.findall(r"\b[a-z0-9]{2,}\b", normalized_expanded))
        matched_in_history = expanded_words.intersection(normalized_keywords)
        if matched_in_history:
            sample = list(matched_in_history)[:3]
            logger.info(
                f"[TOPIC] Query aprovada via contexto do histórico (keywords: {sample}). "
                f"Query original: '{query[:60]}'"
            )
            return True, f"Domínio médico confirmado via contexto do histórico: {sample}"

    logger.info(f"[TOPIC] Query fora do domínio médico: '{query[:80]}'")
    return False, "A pergunta não pertence ao domínio médico/saúde."


# ---------------------------------------------------------------------------
# Nó LangGraph
# ---------------------------------------------------------------------------
def topic_validator_node(state: dict) -> dict:
    """
    Nó LangGraph: valida se a query é do domínio médico.

    Lê `state['query']` e escreve:
    - `state['topic_valid']` (bool)
    - `state['topic_reason']` (str)
    - `state['final_response']` (str) — preenchido apenas se rejeitado
    - `state['done']` (bool) — True se o pipeline deve encerrar aqui

    Para suportar follow-ups em conversas multi-turno, também lê
    `state['conversation_history']` para fornecer contexto ao validador
    quando a query isolada não contém keywords médicas explícitas.

    Args:
        state: Estado atual do grafo LangGraph.

    Returns:
        Estado atualizado.
    """
    query = state.get("query", "")

    # Monta o contexto do último turno para validação de follow-ups
    history = state.get("conversation_history", [])
    logger.info("[TOPIC] Histórico recebido no estado: %d turnos", len(history))
    last_history_turn = ""
    if history and isinstance(history, list):
        last_turn = history[-1]
        if isinstance(last_turn, dict):
            last_history_turn = (
                f"{last_turn.get('query', '')} {last_turn.get('response', '')}"
            ).strip()

    is_valid, reason = is_medical_topic(query, last_history_turn=last_history_turn)

    update = {
        "topic_valid": is_valid,
        "topic_reason": reason,
    }

    if not is_valid:
        update["final_response"] = (
            "❌ Desculpe, sou um assistente especializado exclusivamente no domínio "
            "médico e de saúde. Não posso responder perguntas sobre outros tópicos.\n\n"
            "Por favor, reformule sua pergunta relacionando-a a saúde, doenças, "
            "tratamentos, medicamentos ou protocolos clínicos."
        )
        update["done"] = True
        logger.info(f"[TOPIC] Query rejeitada: {reason}")
    else:
        update["done"] = False
        logger.info(f"[TOPIC] Query aprovada: {reason}")

    return {**state, **update}
