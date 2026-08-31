"""
Testes de integração para o pipeline completo do agente médico (medical_agent).

Utiliza mocks para isolar dependências externas:
- LLM (HuggingFaceEndpoint / HTTP)
- RAG retriever (backend API)
- MongoDB (audit logger)

Verifica o comportamento end-to-end do grafo LangGraph:
- Fluxo feliz (query médica → resposta com fontes e disclaimer)
- Rejeição por tópico inválido (early exit)
- Rejeição por guardrail de segurança (early exit)
- Garantia de disclaimer sempre presente
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------
MOCK_RAG_DOCUMENTS = [
    {
        "id": "doc-001",
        "dataset": "qas",
        "source_type": "qas",
        "content": "### QAs RAG\nPergunta: O que é tuberculose?\nResposta: A tuberculose é...",
        "similarity_score": 0.87,
        "metadatas": {"source": {"dataset": "PubMedQA"}},
    }
]

MOCK_LLM_RESPONSE = (
    "A tuberculose é uma doença infecciosa causada pelo Mycobacterium tuberculosis. "
    "[Fonte: PubMedQA/MedQuAD, score: 0.87]\n"
    "Os principais sintomas incluem tosse persistente, febre e perda de peso."
)


def _make_mock_llm():
    """Cria um mock do cliente LLM."""
    llm = MagicMock()
    llm.invoke.return_value = MOCK_LLM_RESPONSE
    return llm


def _mock_rag_query(*args, **kwargs):
    """Mock da chamada HTTP ao RAG endpoint."""
    return MOCK_RAG_DOCUMENTS


def _mock_create_audit_log(**kwargs):
    """Mock do persist de auditoria no MongoDB."""
    return {"_id": "mock-audit-id-123", **kwargs}


# ---------------------------------------------------------------------------
# Testes do fluxo principal
# ---------------------------------------------------------------------------
class TestMedicalAgentHappyPath:
    """Testa o fluxo feliz: query médica válida → resposta completa."""

    @patch("services.nodes.audit_logger.create_audit_log", side_effect=_mock_create_audit_log)
    @patch("services.nodes.rag_retriever._query_rag", side_effect=_mock_rag_query)
    @patch("services.nodes.llm_generator._get_llm_client", return_value=_make_mock_llm())
    def test_fluxo_completo_retorna_resposta(self, mock_llm, mock_rag, mock_audit):
        from services.medical_agent import run_medical_agent

        result = run_medical_agent(
            query="Quais são os sintomas da tuberculose?",
            session_id="test-session-001",
        )

        assert result["topic_valid"] is True
        assert result["safety_triggered"] is False
        assert len(result["final_response"]) > 0
        assert result["has_disclaimer"] is True
        assert result["requires_human_validation"] is True
        assert result["audit_id"] == "mock-audit-id-123"

    @patch("services.nodes.audit_logger.create_audit_log", side_effect=_mock_create_audit_log)
    @patch("services.nodes.rag_retriever._query_rag", side_effect=_mock_rag_query)
    @patch("services.nodes.llm_generator._get_llm_client", return_value=_make_mock_llm())
    def test_disclaimer_sempre_presente(self, mock_llm, mock_rag, mock_audit):
        from services.medical_agent import run_medical_agent

        result = run_medical_agent(
            query="O que é diabetes tipo 2?",
            session_id="test-session-002",
        )

        assert "AVISO IMPORTANTE" in result["final_response"] or \
               "não substitui" in result["final_response"].lower()

    @patch("services.nodes.audit_logger.create_audit_log", side_effect=_mock_create_audit_log)
    @patch("services.nodes.rag_retriever._query_rag", side_effect=_mock_rag_query)
    @patch("services.nodes.llm_generator._get_llm_client", return_value=_make_mock_llm())
    def test_rag_documents_preenchidos(self, mock_llm, mock_rag, mock_audit):
        from services.medical_agent import run_medical_agent

        result = run_medical_agent(
            query="Quais os sintomas da pneumonia?",
            session_id="test-session-003",
        )

        assert len(result["rag_documents"]) > 0


# ---------------------------------------------------------------------------
# Testes de rejeição por tópico inválido
# ---------------------------------------------------------------------------
class TestMedicalAgentTopicRejection:
    """Testa o early-exit quando a query é fora do domínio médico."""

    @patch("services.nodes.audit_logger.create_audit_log", side_effect=_mock_create_audit_log)
    def test_query_off_topic_nao_chama_rag(self, mock_audit):
        from services.medical_agent import run_medical_agent

        with patch("services.nodes.rag_retriever._query_rag") as mock_rag:
            result = run_medical_agent(
                query="Qual é a receita do brigadeiro?",
                session_id="test-off-topic",
            )
            mock_rag.assert_not_called()

        assert result["topic_valid"] is False
        assert len(result["final_response"]) > 0

    @patch("services.nodes.audit_logger.create_audit_log", side_effect=_mock_create_audit_log)
    def test_query_off_topic_nao_chama_llm(self, mock_audit):
        from services.medical_agent import run_medical_agent

        with patch("services.nodes.llm_generator._get_llm_client") as mock_llm_factory:
            result = run_medical_agent(
                query="Como funciona o algoritmo de Dijkstra?",
                session_id="test-off-topic-2",
            )
            mock_llm_factory.assert_not_called()

        assert result["topic_valid"] is False


# ---------------------------------------------------------------------------
# Testes de rejeição por guardrails de segurança
# ---------------------------------------------------------------------------
class TestMedicalAgentSafetyRejection:
    """Testa o early-exit quando um guardrail é ativado."""

    @patch("services.nodes.audit_logger.create_audit_log", side_effect=_mock_create_audit_log)
    def test_prescricao_nao_chama_rag(self, mock_audit):
        from services.medical_agent import run_medical_agent

        with patch("services.nodes.rag_retriever._query_rag") as mock_rag:
            result = run_medical_agent(
                query="Me prescreve amoxicilina 500mg para infecção",
                session_id="test-safety-001",
            )
            mock_rag.assert_not_called()

        assert result["safety_triggered"] is True
        assert result["topic_valid"] is True  # passou na validação de tópico

    @patch("services.nodes.audit_logger.create_audit_log", side_effect=_mock_create_audit_log)
    def test_safety_response_contem_orientacao(self, mock_audit):
        from services.medical_agent import run_medical_agent

        result = run_medical_agent(
            query="Devo tomar 500mg de amoxicilina?",
            session_id="test-safety-002",
        )

        assert result["safety_triggered"] is True
        # A resposta deve orientar a consultar um médico
        response_lower = result["final_response"].lower()
        assert any(
            word in response_lower
            for word in ["médico", "medico", "profissional", "saúde"]
        )
