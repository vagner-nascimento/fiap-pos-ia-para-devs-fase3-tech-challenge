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
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
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
    return SimpleNamespace(invoke=lambda prompt: MOCK_LLM_RESPONSE)


def _mock_rag_query(*args, **kwargs):
    """Mock da chamada HTTP ao RAG endpoint."""
    return MOCK_RAG_DOCUMENTS


def _mock_create_audit_log(**kwargs):
    """Mock do persist de auditoria no MongoDB."""
    return {"_id": "mock-audit-id-123", **kwargs}


@pytest.fixture(autouse=True)
def _isolated_graph(monkeypatch):
    """Desabilita o MongoDBSaver nos testes unitários do pipeline."""
    import services.medical_agent as medical_agent

    medical_agent._compiled_graph = None
    monkeypatch.setattr(medical_agent, "get_checkpointer", lambda: None)
    monkeypatch.setattr(
        medical_agent,
        "_get_graph",
        lambda: medical_agent._build_graph(None),
    )
    yield
    medical_agent._compiled_graph = None


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
# Testes da Jornada 2 (Consulta contextualizada por prontuário)
# ---------------------------------------------------------------------------
class TestMedicalAgentJornada2:
    """Testa a Jornada 2 quando patient_name é fornecido."""

    @patch("services.nodes.audit_logger.create_audit_log", side_effect=_mock_create_audit_log)
    @patch("services.nodes.rag_retriever._query_rag", side_effect=_mock_rag_query)
    @patch("services.nodes.llm_generator._get_llm_client", return_value=_make_mock_llm())
    @patch("services.nodes.patient_context_retriever.requests.get")
    def test_jornada_2_paciente_encontrado_usa_contexto(
        self, mock_patient_get, mock_llm, mock_rag, mock_audit
    ):
        from services.medical_agent import run_medical_agent

        mock_resp = MagicMock()
        mock_resp.json.return_value = [
            {
                "avaliacao": {"itens": ["Hipertensão"]},
                "plano": {"prescricao": "Losartana 50mg"},
                "alergias": ["Dipirona"],
            }
        ]
        mock_resp.raise_for_status.return_value = None
        mock_patient_get.return_value = mock_resp

        result = run_medical_agent(
            query="Quais orientações para o quadro clínico deste paciente?",
            session_id="test-jornada-2",
            patient_name="João Silva",
        )

        assert result["patient_context_used"] is True
        assert "avaliacao" in result["patient_fields_used"]
        assert result["topic_valid"] is True
        assert result["safety_triggered"] is False
        assert len(result["final_response"]) > 0

    @patch("services.nodes.audit_logger.create_audit_log", side_effect=_mock_create_audit_log)
    @patch("services.nodes.rag_retriever._query_rag", side_effect=_mock_rag_query)
    @patch("services.nodes.llm_generator._get_llm_client", return_value=_make_mock_llm())
    @patch("services.nodes.patient_context_retriever.requests.get")
    def test_jornada_2_paciente_nao_encontrado_degrada_jornada_1(
        self, mock_patient_get, mock_llm, mock_rag, mock_audit
    ):
        from services.medical_agent import run_medical_agent

        mock_resp = MagicMock()
        mock_resp.json.return_value = []
        mock_resp.raise_for_status.return_value = None
        mock_patient_get.return_value = mock_resp

        result = run_medical_agent(
            query="Quais orientações para o quadro clínico?",
            session_id="test-jornada-2-fallback",
            patient_name="Paciente Inexistente",
        )

        assert result["patient_context_used"] is False
        assert result["patient_fields_used"] == []
        assert result["topic_valid"] is True
        assert len(result["final_response"]) > 0

    @patch("services.nodes.audit_logger.create_audit_log", side_effect=_mock_create_audit_log)
    @patch("services.nodes.rag_retriever._query_rag", return_value=[])
    @patch("services.nodes.llm_generator._get_llm_client")
    @patch("services.nodes.patient_context_retriever.requests.get")
    def test_jornada_2_sem_laudo_nao_hallucina_exames(
        self, mock_patient_get, mock_llm_factory, mock_rag, mock_audit
    ):
        from services.medical_agent import run_medical_agent

        record_resp = MagicMock()
        record_resp.json.return_value = [{
            "avaliacao": {"itens": ["Hipertensão arterial sistêmica"]},
            "plano": {"orientacoes": "Manter acompanhamento ambulatorial."},
        }]
        record_resp.raise_for_status.return_value = None

        report_resp = MagicMock()
        report_resp.json.return_value = []
        report_resp.raise_for_status.return_value = None
        mock_patient_get.side_effect = [record_resp, report_resp]

        result = run_medical_agent(
            query="Quais foram os últimos exames e resultados realizados pela paciente?",
            session_id="test-jornada-2-sem-laudo",
            patient_name="Maria Santos Almeida",
        )

        assert "Não encontrei exames" in result["final_response"]
        mock_llm_factory.assert_not_called()

    @patch("services.nodes.audit_logger.create_audit_log", side_effect=_mock_create_audit_log)
    @patch("services.nodes.rag_retriever._query_rag", return_value=[])
    @patch("services.nodes.llm_generator._get_llm_client")
    @patch("services.nodes.patient_context_retriever.requests.get")
    def test_jornada_2_exame_com_erro_de_digitacao_usa_laudo_consolidado(
        self, mock_patient_get, mock_llm_factory, mock_rag, mock_audit
    ):
        from services.medical_agent import run_medical_agent

        record_resp = MagicMock()
        record_resp.json.return_value = [{
            "avaliacao": {"diagnostico_principal": "Asma brônquica"},
            "plano": {"orientacoes": "Acompanhamento ambulatorial em 30 dias."},
        }]
        record_resp.raise_for_status.return_value = None

        report_resp = MagicMock()
        report_resp.json.return_value = [{
            "cabecalho_identificador": {"data_exame": "2026-08-15"},
            "corpo_tecnico": {
                "tipo_exame": "Exame Cardiorespiratório",
                "descricao_tecnica": "Teste de função pulmonar revelou redução do VEF1 e broncoespasmo reversível.",
            },
            "conclusao": {
                "impressao_diagnostica": "Asma brônquica",
                "conduta_terapeutica": "Início de tratamento com corticosteroides inalados e broncodilatadores.",
            },
        }]
        report_resp.raise_for_status.return_value = None
        mock_patient_get.side_effect = [record_resp, report_resp]

        result = run_medical_agent(
            query="Qual foi o examente que o paciente fez?",
            session_id="test-jornada-2-exame-digitacao",
            patient_name="Lucas Almeida Santos",
        )

        assert "Exame Cardiorespiratório" in result["final_response"]
        assert "Asma brônquica" in result["final_response"]
        mock_llm_factory.assert_not_called()

    @patch("services.nodes.audit_logger.create_audit_log", side_effect=_mock_create_audit_log)
    @patch("services.nodes.rag_retriever._query_rag", return_value=[])
    @patch("services.nodes.llm_generator._get_llm_client")
    @patch("services.nodes.patient_context_retriever.requests.get")
    def test_jornada_2_tipo_exame_usa_laudo_consolidado(
        self, mock_patient_get, mock_llm_factory, mock_rag, mock_audit
    ):
        from services.medical_agent import run_medical_agent

        record_resp = MagicMock()
        record_resp.json.return_value = [{
            "avaliacao": {"diagnostico_principal": "Bloqueio de ramo direito"},
            "plano": {"orientacoes": "Acompanhamento cardiológico."},
        }]
        record_resp.raise_for_status.return_value = None

        report_resp = MagicMock()
        report_resp.json.return_value = [{
            "cabecalho_identificador": {"data_exame": "2025-10-18"},
            "corpo_tecnico": {
                "tipo_exame": "Eletrocardiograma (ECG)",
                "descricao_tecnica": "Ritmo sinusal. Bloqueio de ramo direito incompleto.",
            },
            "conclusao": {
                "impressao_diagnostica": "Bloqueio de ramo direito",
                "conduta_terapeutica": "Avaliação com especialista em caráter de urgência.",
            },
        }]
        report_resp.raise_for_status.return_value = None
        mock_patient_get.side_effect = [record_resp, report_resp]

        result = run_medical_agent(
            query="Qual foi o tipo do último exame feito pela paciente?",
            session_id="test-jornada-2-tipo-exame",
            patient_name="Ana Souza Ferreira",
        )

        assert "Eletrocardiograma (ECG)" in result["final_response"]
        assert "conduta" in result["final_response"].lower()
        mock_llm_factory.assert_not_called()

    @patch("services.nodes.audit_logger.create_audit_log", side_effect=_mock_create_audit_log)
    @patch("services.nodes.rag_retriever._query_rag", return_value=[])
    @patch("services.nodes.llm_generator._get_llm_client")
    @patch("services.nodes.patient_context_retriever.requests.get")
    def test_jornada_2_cuidados_prescricao_contextualiza(self, mock_patient_get, mock_llm_factory, mock_rag, mock_audit):
        from services.medical_agent import run_medical_agent

        record_resp = MagicMock()
        record_resp.json.return_value = [{
            "avaliacao": {"diagnostico_principal": "Bloqueio de ramo direito"},
            "plano": {"orientacoes": "Acompanhamento cardiológico e avaliação com especialista."},
        }]
        record_resp.raise_for_status.return_value = None

        report_resp = MagicMock()
        report_resp.json.return_value = [{
            "corpo_tecnico": {
                "tipo_exame": "Eletrocardiograma (ECG)",
            },
            "conclusao": {
                "impressao_diagnostica": "Bloqueio de ramo direito",
                "conduta_terapeutica": "Avaliação com especialista em caráter de urgência.",
            },
        }]
        report_resp.raise_for_status.return_value = None
        mock_patient_get.side_effect = [record_resp, report_resp]

        result = run_medical_agent(
            query="Quais cuidados prescrever para o quadro clínico deste paciente?",
            session_id="test-jornada-2-cuidados",
            patient_name="Ana Souza Ferreira",
        )

        assert "Bloqueio de ramo direito" in result["final_response"]
        assert "avaliação" in result["final_response"].lower() or "especialista" in result["final_response"].lower()
        mock_llm_factory.assert_not_called()


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


class TestMedicalAgentSessionMemory:
    """Verifica que o session_id é transmitido como identidade do thread."""

    @patch("services.nodes.audit_logger.create_audit_log", side_effect=_mock_create_audit_log)
    def test_session_id_isola_checkpoints(self, mock_audit, _isolated_graph, monkeypatch):
        import services.medical_agent as medical_agent

        graph = MagicMock()
        graph.invoke.return_value = {"session_id": "session-memory-001"}
        monkeypatch.setattr(medical_agent, "_get_graph", lambda: graph)

        medical_agent.run_medical_agent(
            query="Quais são os sintomas da tuberculose?",
            session_id="session-memory-001",
        )
        medical_agent.run_medical_agent(
            query="Quais são os sintomas da pneumonia?",
            session_id="session-memory-002",
        )

        configs = [call.kwargs["config"] for call in graph.invoke.call_args_list]
        assert [config["configurable"]["thread_id"] for config in configs] == [
            "session-memory-001",
            "session-memory-002",
        ]

    @patch("services.nodes.audit_logger.create_audit_log", side_effect=_mock_create_audit_log)
    def test_historico_do_checkpoint_e_enviado_ao_grafo(self, mock_audit, monkeypatch):
        import services.medical_agent as medical_agent

        graph = MagicMock()
        graph.get_state.return_value = SimpleNamespace(
            values={
                "conversation_history": [
                    {"query": "O que é diabetes?", "response": "É uma condição metabólica."}
                ]
            }
        )
        graph.invoke.return_value = {"session_id": "session-memory-003"}
        monkeypatch.setattr(medical_agent, "_get_graph", lambda: graph)

        medical_agent.run_medical_agent(
            query="Quais são os sintomas?",
            session_id="session-memory-003",
        )

        state = graph.invoke.call_args.args[0]
        assert state["conversation_history"] == [
            {"query": "O que é diabetes?", "response": "É uma condição metabólica."}
        ]
