"""
Testes unitários para o nó context_summarizer.

Verifica:
- Contexto dentro da janela de 3K tokens passa sem modificação (not_needed)
- Contexto acima do limite sem GROQ_API_KEY aciona fallback Python (python_fallback)
- Contexto acima do limite com GROQ_API_KEY aciona API Groq (groq)
- Resiliência: se Groq falhar, sistema recorre automaticamente ao fallback Python
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import services.nodes.context_summarizer as summarizer_module
from services.nodes.context_summarizer import context_summarizer_node


class TestContextSummarizerWithinLimits:
    """Testa quando o contexto total está dentro da janela (caso comum)."""

    def test_contexto_pequeno_passa_sem_modificacao(self):
        state = {
            "query": "Qual a dosagem de dipirona?",
            "rag_context": "Dipirona 500mg a cada 6h.",
            "patient_context": "Diagnosticos: Cefaleia tensional.",
            "conversation_history": [],
        }

        result = context_summarizer_node(state)

        assert result["context_summarized"] is False
        assert result["context_summarizer_mode"] == "not_needed"
        assert result["compressed_rag_context"] == "Dipirona 500mg a cada 6h."
        assert result["compressed_patient_context"] == "Diagnosticos: Cefaleia tensional."


class TestContextSummarizerPythonFallback:
    """Testa o fallback de truncação Python quando não há chave Groq."""

    def test_contexto_grande_aciona_fallback_python(self, monkeypatch):
        monkeypatch.setattr(summarizer_module, "GROQ_API_KEY", "")

        # Cria contexto grande que excede o threshold (~7.6K chars)
        large_rag = "Informação importante sobre tratamento médico. " * 300
        large_patient = "Diagnostico clinico detalhado do paciente. " * 100

        state = {
            "query": "Quais as opções terapêuticas?",
            "rag_context": large_rag,
            "patient_context": large_patient,
            "conversation_history": [
                {"query": "Turno 1", "response": "Resp 1 " * 50},
                {"query": "Turno 2", "response": "Resp 2 " * 50},
            ],
        }

        result = context_summarizer_node(state)

        assert result["context_summarized"] is True
        assert result["context_summarizer_mode"] == "python_fallback"
        # O tamanho comprimido deve ser menor que o original
        assert len(result["compressed_rag_context"]) < len(large_rag)
        assert len(result["compressed_patient_context"]) < len(large_patient)


class TestContextSummarizerGroq:
    """Testa a sumarização via API da Groq."""

    @patch("requests.post")
    def test_contexto_grande_com_groq_aciona_api(self, mock_post, monkeypatch):
        monkeypatch.setattr(summarizer_module, "GROQ_API_KEY", "gsk-mock-key-12345")
        monkeypatch.setattr(summarizer_module, "GROQ_SUMMARIZER_MODEL", "groq/compound-mini")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": (
                            "Paciente hipertenso e diabético em uso de losartana. "
                            "Protocolo FHEMIG recomenda monitorização pressórica."
                        )
                    }
                }
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        large_rag = "Protocolo longo e detalhado. " * 300
        large_patient = "Dados do paciente extensos. " * 100

        state = {
            "query": "Como proceder?",
            "rag_context": large_rag,
            "patient_context": large_patient,
            "conversation_history": [],
        }

        result = context_summarizer_node(state)

        assert result["context_summarized"] is True
        assert result["context_summarizer_mode"] == "groq"
        assert mock_post.called
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["json"]["model"] == "groq/compound-mini"
        assert "Bearer gsk-mock-key-12345" in call_kwargs["headers"]["Authorization"]

    @patch("requests.post")
    def test_groq_falha_aciona_fallback_python(self, mock_post, monkeypatch):
        monkeypatch.setattr(summarizer_module, "GROQ_API_KEY", "gsk-mock-key-12345")
        mock_post.side_effect = Exception("Groq API 503 Service Unavailable")

        large_rag = "Protocolo longo e detalhado. " * 300
        state = {
            "query": "Como proceder?",
            "rag_context": large_rag,
            "patient_context": "",
            "conversation_history": [],
        }

        result = context_summarizer_node(state)

        # Deve degradar para python_fallback sem levantar exceção
        assert result["context_summarized"] is True
        assert result["context_summarizer_mode"] == "python_fallback"
        assert len(result["compressed_rag_context"]) < len(large_rag)
