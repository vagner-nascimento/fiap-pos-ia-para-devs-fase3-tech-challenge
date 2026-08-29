"""
Nó 2: Guardrail de Segurança (Safety Guard)

Detecta padrões proibidos na query do usuário e recusa responder quando:
- O usuário solicita prescrição direta de medicamentos com doses
- O usuário pede um diagnóstico definitivo
- A query tenta usar o assistente como substituto de avaliação médica profissional

Este nó é a segunda camada de segurança após a validação de tópico.
"""
import logging
import re
from typing import Final, List, NamedTuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Padrões proibidos
# ---------------------------------------------------------------------------
class ProhibitedPattern(NamedTuple):
    """Define um padrão proibido com sua descrição."""
    pattern: str
    description: str
    flags: int = re.IGNORECASE


PROHIBITED_PATTERNS: Final[List[ProhibitedPattern]] = [
    # Prescrição direta com dose
    ProhibitedPattern(
        pattern=r"\b(prescrev|receit|indic|recomend).{0,40}\b(\d+\s*mg|\d+\s*ml|\d+\s*g\b|\d+\s*mcg|\d+\s*ui)\b",
        description="Solicitação de prescrição com dose específica",
    ),
    ProhibitedPattern(
        pattern=r"\b(tome|tomar|usar|aplicar|inject).{0,60}\b(\d+\s*mg|\d+\s*ml|\d+\s*(comprimido|ampola|capsula|cápsula)|comprimido(s)?)",
        description="Instrução de administração com dose ou unidade específica",
    ),
    ProhibitedPattern(
        pattern=r"\bme (prescrev|receit).{0,60}(medicament|remedio|remédio|antibiotico|antibiótico)\b",
        description="Pedido direto de prescrição",
    ),
    ProhibitedPattern(
        pattern=r"\bqual (o |a )?(remedio|remédio|medicament|antibiotico|antibiótico|droga).{0,30}(para|que trata|que cura)\b",
        description="Pedido de indicação de medicamento específico para condição",
    ),

    # Diagnóstico definitivo
    ProhibitedPattern(
        pattern=r"\b(eu tenho|tenho|estou com).{0,60}(diagnostico|diagnóstico|confirmad|certez)\b",
        description="Pedido de diagnóstico definitivo",
    ),
    ProhibitedPattern(
        pattern=r"\b(diga|confirme|certifique).{0,40}(que tenho|que estou com|meu diagnostico|minha doenca|minha doença)\b",
        description="Pedido de confirmação de diagnóstico",
    ),
    ProhibitedPattern(
        pattern=r"\b(qual|o que).{0,20}(minha|meu).{0,30}(doenca|doença|condicao|condição|diagnostico|diagnóstico)\b",
        description="Diagnóstico personalizado baseado em sintomas",
    ),

    # Substituição de médico
    ProhibitedPattern(
        pattern=r"\b(sem (ir ao|consultar|ver).{0,20}medico|medico|médico).{0,40}(o que (devo|posso|fazer))\b",
        description="Substituição de consulta médica",
    ),
    ProhibitedPattern(
        pattern=r"\bnao (preciso|quero).{0,20}(medico|médico|hospital|consulta)\b",
        description="Tentativa de evitar consulta médica",
    ),
]


def _check_safety(query: str) -> tuple[bool, str | None]:
    """
    Verifica se a query contém padrões proibidos.

    Args:
        query: Texto da pergunta do usuário.

    Returns:
        Tupla (is_safe: bool, violation_description: str | None).
        Se is_safe=False, violation_description descreve o padrão violado.
    """
    if not query:
        return True, None

    for prohibited in PROHIBITED_PATTERNS:
        match = re.search(prohibited.pattern, query, prohibited.flags)
        if match:
            logger.warning(
                f"[SAFETY] Padrão proibido detectado: '{prohibited.description}' "
                f"em query: '{query[:80]}'"
            )
            return False, prohibited.description

    return True, None


# ---------------------------------------------------------------------------
# Nó LangGraph
# ---------------------------------------------------------------------------
def safety_guard_node(state: dict) -> dict:
    """
    Nó LangGraph: verifica guardrails de segurança.

    Lê `state['query']` e escreve:
    - `state['safety_triggered']` (bool)
    - `state['safety_reason']` (str | None)
    - `state['final_response']` (str) — preenchido apenas se violado
    - `state['done']` (bool) — True se o pipeline deve encerrar aqui

    Args:
        state: Estado atual do grafo LangGraph.

    Returns:
        Estado atualizado.
    """
    query = state.get("query", "")
    is_safe, violation_description = _check_safety(query)

    update = {
        "safety_triggered": not is_safe,
        "safety_reason": violation_description,
    }

    if not is_safe:
        update["final_response"] = (
            "⚠️ **Solicitação não permitida.**\n\n"
            "Por razões de segurança e ética, este assistente médico não pode:\n"
            "- Prescrever medicamentos com doses específicas\n"
            "- Fornecer diagnósticos definitivos\n"
            "- Substituir a avaliação de um profissional de saúde\n\n"
            "Posso fornecer **informações gerais** sobre doenças, sintomas, "
            "tratamentos e protocolos clínicos. Para orientação personalizada, "
            "**consulte um médico ou profissional de saúde habilitado**.\n\n"
            "⚠️ *Este assistente não substitui avaliação médica profissional.*"
        )
        update["done"] = True
        logger.info(f"[SAFETY] Query bloqueada: {violation_description}")
    else:
        update["done"] = False
        logger.info("[SAFETY] Query aprovada pelos guardrails de segurança.")

    return {**state, **update}
