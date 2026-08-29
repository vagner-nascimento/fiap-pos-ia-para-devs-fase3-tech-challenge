"""
Testes unitários para a collection de audit logs.

Usa mock do MongoDB para evitar dependência de banco de dados real nos testes.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def _make_mock_collection():
    """Cria um mock da collection MongoDB."""
    col = MagicMock()
    col.insert_one.return_value = MagicMock(inserted_id="mock-id")
    col.find.return_value = iter([])
    col.find_one.return_value = None
    return col


class TestCreateAuditLog:
    """Testa a criação de logs de auditoria."""

    @patch(
        "infra.database.collections.agent_audit_logs.get_collection",
        return_value=_make_mock_collection(),
    )
    def test_cria_log_com_campos_obrigatorios(self, mock_col):
        from infra.database.collections.agent_audit_logs import create_audit_log

        result = create_audit_log(
            session_id="sess-001",
            query="Quais os sintomas da gripe?",
            topic_valid=True,
            safety_triggered=False,
            safety_reason=None,
            rag_documents_used=[
                {
                    "id": "doc-1",
                    "dataset": "qas",
                    "source_type": "qas",
                    "similarity_score": 0.85,
                    "content": "A gripe é...",
                }
            ],
            llm_response_raw="Resposta da LLM",
            final_response="Resposta formatada com disclaimer",
            sources_cited=["PubMedQA/MedQuAD"],
            has_disclaimer=True,
            preprocess_id="prep-123",
            duration_ms=1500,
        )

        assert result["session_id"] == "sess-001"
        assert result["query"] == "Quais os sintomas da gripe?"
        assert result["topic_valid"] is True
        assert result["safety_triggered"] is False
        assert result["has_disclaimer"] is True
        assert result["duration_ms"] == 1500
        assert "_id" in result
        assert "created_date" in result

    @patch(
        "infra.database.collections.agent_audit_logs.get_collection",
        return_value=_make_mock_collection(),
    )
    def test_rag_docs_armazenados_como_preview(self, mock_col):
        """Verifica que apenas previews dos docs RAG são armazenados."""
        from infra.database.collections.agent_audit_logs import create_audit_log

        longa_content = "A" * 1000  # conteúdo muito longo
        result = create_audit_log(
            session_id="sess-002",
            query="Teste",
            topic_valid=True,
            safety_triggered=False,
            safety_reason=None,
            rag_documents_used=[
                {
                    "id": "doc-2",
                    "dataset": "clinical_protocols",
                    "source_type": "clinical_protocols",
                    "similarity_score": 0.7,
                    "content": longa_content,
                }
            ],
            llm_response_raw="resp",
            final_response="final",
            sources_cited=["FHEMIG"],
            has_disclaimer=True,
            preprocess_id=None,
            duration_ms=800,
        )

        # O preview deve ter no máximo 200 caracteres
        for doc_summary in result["rag_documents_used"]:
            assert len(doc_summary["content_preview"]) <= 200

    @patch(
        "infra.database.collections.agent_audit_logs.get_collection",
        return_value=_make_mock_collection(),
    )
    def test_safety_triggered_registrado(self, mock_col):
        """Verifica que o motivo de safety é registrado corretamente."""
        from infra.database.collections.agent_audit_logs import create_audit_log

        result = create_audit_log(
            session_id="sess-003",
            query="Me prescreve amoxicilina",
            topic_valid=True,
            safety_triggered=True,
            safety_reason="Solicitação de prescrição com dose específica",
            rag_documents_used=[],
            llm_response_raw="",
            final_response="Resposta de segurança",
            sources_cited=[],
            has_disclaimer=True,
            preprocess_id=None,
            duration_ms=50,
        )

        assert result["safety_triggered"] is True
        assert result["safety_reason"] == "Solicitação de prescrição com dose específica"
        assert result["rag_documents_count"] == 0
