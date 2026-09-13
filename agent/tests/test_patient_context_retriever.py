"""
Testes unitários para o nó patient_context_retriever.

Verifica:
- Roteamento da Jornada 1 (sem patient_name -> no-op, sem chamada ao backend)
- Roteamento da Jornada 2 (com patient_name -> busca prontuário, extrai dados clínicos anonimizados)
- Degradação graciosa quando prontuário não é encontrado ou backend está inacessível
- Garantia de que identificadores pessoais do paciente não vazam para o prompt
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from services.nodes.patient_context_retriever import (
    _extract_clinical_fields,
    _fetch_medical_record,
    patient_context_retriever_node,
)


# Mock de prontuário completo retornado pelo backend
MOCK_PATIENT_RECORD = {
    "_id": "record-12345",
    "paciente": {
        "nome": "Maria de Oliveira",
        "cpf": "123.456.789-00",
        "telefone": "(31) 98765-4321",
        "data_nascimento": "1980-05-15",
    },
    "avaliacao": {
        "itens": ["Hipertensão Arterial Sistêmica", "Diabetes Mellitus Tipo 2"],
    },
    "plano": {
        "prescricao": "Losartana 50mg 1x ao dia; Metformina 850mg 2x ao dia",
        "orientacoes": "Dieta hipossódica e caminhadas 30min",
    },
    "alergias": ["Dipirona"],
    "objetivo": {
        "pressao_arterial": "130/85 mmHg",
        "frequencia_cardiaca": "72 bpm",
        "exame_fisico": "BEG, hidratada, acianótica.",
    },
}


class TestPatientContextRetrieverJornada1:
    """Testa o comportamento da Jornada 1 (Q&A genérico, sem paciente)."""

    @patch("services.nodes.patient_context_retriever.requests.get")
    def test_patient_name_none_nao_chama_backend(self, mock_get):
        state = {"patient_name": None, "query": "O que é dengue?"}
        result = patient_context_retriever_node(state)

        assert result["patient_context"] == ""
        assert result["patient_context_used"] is False
        assert result["patient_fields_used"] == []
        mock_get.assert_not_called()

    @patch("services.nodes.patient_context_retriever.requests.get")
    def test_patient_name_vazio_nao_chama_backend(self, mock_get):
        state = {"patient_name": "   ", "query": "Sintomas de pneumonia"}
        result = patient_context_retriever_node(state)

        assert result["patient_context"] == ""
        assert result["patient_context_used"] is False
        assert result["patient_fields_used"] == []
        mock_get.assert_not_called()


class TestPatientContextRetrieverJornada2:
    """Testa o comportamento da Jornada 2 (com paciente)."""

    @patch("services.nodes.patient_context_retriever.requests.get")
    def test_sucesso_extrai_campos_clinicos(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = [MOCK_PATIENT_RECORD]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        state = {
            "patient_name": "Maria de Oliveira",
            "query": "Quais cuidados prescrever para essa paciente?",
        }
        result = patient_context_retriever_node(state)

        assert result["patient_context_used"] is True
        assert "avaliacao" in result["patient_fields_used"]
        assert "plano.prescricao" in result["patient_fields_used"]
        assert "alergias" in result["patient_fields_used"]
        assert "Hipertensão" in result["patient_context"]
        assert "Dipirona" in result["patient_context"]
        assert "Losartana" in result["patient_context"]

        # Garantia de anonimização: CPF, telefone e nome não devem constar no contexto clínico
        assert "123.456.789-00" not in result["patient_context"]
        assert "(31) 98765-4321" not in result["patient_context"]
        assert "Maria de Oliveira" not in result["patient_context"]

    @patch("services.nodes.patient_context_retriever.requests.get")
    def test_prontuario_nao_encontrado_degrada_silenciosamente(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        state = {
            "patient_name": "Paciente Inexistente",
            "query": "Qual a conduta?",
        }
        result = patient_context_retriever_node(state)

        assert result["patient_context"] == ""
        assert result["patient_context_used"] is False
        assert result["patient_fields_used"] == []

    @patch("services.nodes.patient_context_retriever.requests.get")
    def test_erro_conexao_backend_degrada_silenciosamente(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")

        state = {
            "patient_name": "João da Silva",
            "query": "Pode tomar amoxicilina?",
        }
        result = patient_context_retriever_node(state)

        assert result["patient_context"] == ""
        assert result["patient_context_used"] is False
        assert result["patient_fields_used"] == []
