"""
Agente Médico — Grafo LangGraph

Define o `StateGraph` completo do assistente médico com 6 nós sequenciais
e roteamento condicional para early-exit quando guardrails são ativados.

Fluxo do grafo:
    [START]
      │
      ▼
    topic_validator ──── (topic inválido) ──→ audit_logger → [END]
      │
      ▼ (topic válido)
    safety_guard ──────── (safety violado) ─→ audit_logger → [END]
      │
      ▼ (safe)
    rag_retriever
      │
      ▼
    llm_generator
      │
      ▼
    response_formatter
      │
      ▼
    audit_logger
      │
      ▼
    [END]

O nó `audit_logger` é sempre o último nó executado, garantindo que toda
interação seja registrada para auditoria independentemente do resultado.
"""
import logging
import time
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from services.nodes.audit_logger import audit_logger_node
from services.nodes.llm_generator import llm_generator_node
from services.nodes.rag_retriever import rag_retriever_node
from services.nodes.response_formatter import response_formatter_node
from services.nodes.safety_guard import safety_guard_node
from services.nodes.topic_validator import topic_validator_node

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tipagem do estado do grafo
# ---------------------------------------------------------------------------
class AgentState(TypedDict, total=False):
    """Estado compartilhado entre todos os nós do grafo LangGraph."""

    # --- Entrada ---
    session_id: str
    query: str
    preprocess_id: Optional[str]

    # --- Rastreamento interno ---
    _started_at: float

    # --- Validação de tópico ---
    topic_valid: bool
    topic_reason: str

    # --- Guardrails de segurança ---
    safety_triggered: bool
    safety_reason: Optional[str]

    # --- RAG ---
    rag_documents: List[Dict[str, Any]]
    rag_context: str

    # --- LLM ---
    llm_response_raw: str
    sources_cited: List[str]

    # --- Formatação ---
    final_response: str
    has_disclaimer: bool
    requires_human_validation: bool

    # --- Auditoria ---
    audit_id: str
    duration_ms: int

    # --- Controle de fluxo ---
    done: bool


# ---------------------------------------------------------------------------
# Roteadores condicionais
# ---------------------------------------------------------------------------
def _route_after_topic_validator(state: AgentState) -> str:
    """
    Decide o próximo nó após a validação de tópico.

    Se a query for fora do domínio médico, pula direto para o audit_logger.
    Caso contrário, prossegue para o guardrail de segurança.
    """
    if state.get("done"):
        logger.info("[GRAPH] Roteando: topic_validator → audit_logger (tópico inválido)")
        return "audit_logger"
    logger.info("[GRAPH] Roteando: topic_validator → safety_guard")
    return "safety_guard"


def _route_after_safety_guard(state: AgentState) -> str:
    """
    Decide o próximo nó após o guardrail de segurança.

    Se um guardrail foi ativado, pula direto para o audit_logger.
    Caso contrário, prossegue para o RAG retriever.
    """
    if state.get("done"):
        logger.info("[GRAPH] Roteando: safety_guard → audit_logger (safety ativado)")
        return "audit_logger"
    logger.info("[GRAPH] Roteando: safety_guard → rag_retriever")
    return "rag_retriever"


# ---------------------------------------------------------------------------
# Wrapper para inicializar o timestamp no estado
# ---------------------------------------------------------------------------
def _init_node(state: AgentState) -> AgentState:
    """Nó inicial que injeta o timestamp de início no estado."""
    return {**state, "_started_at": time.time()}


# ---------------------------------------------------------------------------
# Construção do grafo
# ---------------------------------------------------------------------------
def _build_graph() -> StateGraph:
    """
    Constrói e compila o grafo LangGraph do agente médico.

    Returns:
        StateGraph compilado e pronto para execução.
    """
    graph = StateGraph(AgentState)

    # Registrar nós
    graph.add_node("init", _init_node)
    graph.add_node("topic_validator", topic_validator_node)
    graph.add_node("safety_guard", safety_guard_node)
    graph.add_node("rag_retriever", rag_retriever_node)
    graph.add_node("llm_generator", llm_generator_node)
    graph.add_node("response_formatter", response_formatter_node)
    graph.add_node("audit_logger", audit_logger_node)

    # Arestas fixas
    graph.add_edge(START, "init")
    graph.add_edge("init", "topic_validator")

    # Roteamento condicional pós topic_validator
    graph.add_conditional_edges(
        "topic_validator",
        _route_after_topic_validator,
        {
            "safety_guard": "safety_guard",
            "audit_logger": "audit_logger",
        },
    )

    # Roteamento condicional pós safety_guard
    graph.add_conditional_edges(
        "safety_guard",
        _route_after_safety_guard,
        {
            "rag_retriever": "rag_retriever",
            "audit_logger": "audit_logger",
        },
    )

    # Pipeline principal (sem desvios)
    graph.add_edge("rag_retriever", "llm_generator")
    graph.add_edge("llm_generator", "response_formatter")
    graph.add_edge("response_formatter", "audit_logger")

    # Finalização
    graph.add_edge("audit_logger", END)

    return graph.compile()


# Grafo compilado (singleton)
_compiled_graph = None


def _get_graph():
    """Retorna o grafo compilado (singleton)."""
    global _compiled_graph
    if _compiled_graph is None:
        logger.info("[GRAPH] Compilando grafo LangGraph do agente médico...")
        _compiled_graph = _build_graph()
        logger.info("[GRAPH] Grafo compilado com sucesso.")
    return _compiled_graph


# ---------------------------------------------------------------------------
# Interface pública
# ---------------------------------------------------------------------------
def run_medical_agent(
    query: str,
    session_id: str,
    preprocess_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Executa o pipeline completo do agente médico para uma query.

    Args:
        query: Pergunta do usuário em linguagem natural.
        session_id: Identificador da sessão do usuário (para rastreamento).
        preprocess_id: ID do pré-processamento para filtrar a base RAG (opcional).

    Returns:
        Dicionário com o estado final do agente, incluindo:
        - `final_response`: Resposta formatada com fontes e disclaimer
        - `sources_cited`: Lista de fontes utilizadas
        - `topic_valid`: Se a query passou na validação de domínio
        - `safety_triggered`: Se algum guardrail foi ativado
        - `requires_human_validation`: Sempre True
        - `audit_id`: ID do log de auditoria criado
        - `duration_ms`: Tempo total de execução
    """
    graph = _get_graph()

    initial_state: AgentState = {
        "session_id": session_id,
        "query": query,
        "preprocess_id": preprocess_id,
        # Defaults para campos opcionais
        "topic_valid": False,
        "topic_reason": "",
        "safety_triggered": False,
        "safety_reason": None,
        "rag_documents": [],
        "rag_context": "",
        "llm_response_raw": "",
        "sources_cited": [],
        "final_response": "",
        "has_disclaimer": False,
        "requires_human_validation": True,
        "audit_id": "",
        "duration_ms": 0,
        "done": False,
    }

    logger.info(
        f"[AGENT] Iniciando pipeline: session={session_id} "
        f"query='{query[:80]}' preprocess_id={preprocess_id}"
    )

    try:
        final_state = graph.invoke(initial_state)
        logger.info(
            f"[AGENT] Pipeline concluído: audit_id={final_state.get('audit_id')} "
            f"duration_ms={final_state.get('duration_ms')}"
        )
        return final_state
    except Exception as exc:
        logger.error(f"[AGENT] Erro crítico no pipeline: {exc}")
        return {
            **initial_state,
            "final_response": (
                "Desculpe, ocorreu um erro interno ao processar sua consulta. "
                "Por favor, tente novamente.\n\n"
                "⚠️ *Este assistente não substitui avaliação médica profissional.*"
            ),
            "has_disclaimer": True,
            "requires_human_validation": True,
        }
