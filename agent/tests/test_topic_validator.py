"""
Testes unitários para o nó de validação de tópico (topic_validator).

Verifica que:
- Queries médicas são aceitas
- Queries fora do domínio são rejeitadas
- O nó LangGraph atualiza o estado corretamente
"""
import sys
from pathlib import Path

# Garante que o src está no path para importações
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from services.nodes.topic_validator import is_medical_topic, topic_validator_node


class TestIsMedicalTopic:
    """Testes da função de classificação de tópico."""

    def test_sintoma_dengue_aceito(self):
        valid, reason = is_medical_topic("Quais são os sintomas da dengue?")
        assert valid is True

    def test_tratamento_tuberculose_aceito(self):
        valid, reason = is_medical_topic("Como é o tratamento da tuberculose?")
        assert valid is True

    def test_diabetes_aceito(self):
        valid, reason = is_medical_topic("O que é diabetes tipo 2?")
        assert valid is True

    def test_protocolo_clinico_aceito(self):
        valid, reason = is_medical_topic("Qual o protocolo clínico para hipertensão?")
        assert valid is True

    def test_cancer_aceito(self):
        valid, reason = is_medical_topic("Quais os tipos de câncer mais comuns?")
        assert valid is True

    def test_culinaria_rejeitada(self):
        valid, reason = is_medical_topic("Como fazer bolo de chocolate?")
        assert valid is False

    def test_futebol_rejeitado(self):
        valid, reason = is_medical_topic("Quem ganhou a Copa do Mundo de 2022?")
        assert valid is False

    def test_programacao_rejeitada(self):
        valid, reason = is_medical_topic("Como criar uma API REST com FastAPI?")
        assert valid is False

    def test_query_vazia_rejeitada(self):
        valid, reason = is_medical_topic("")
        assert valid is False

    def test_query_apenas_espacos_rejeitada(self):
        valid, reason = is_medical_topic("   ")
        assert valid is False

    def test_dor_cabeca_aceita(self):
        valid, reason = is_medical_topic("Tenho dor de cabeça frequente, o que pode ser?")
        assert valid is True

    def test_english_query_aceita(self):
        valid, reason = is_medical_topic("What are the symptoms of pneumonia?")
        assert valid is True


class TestTopicValidatorNode:
    """Testes do nó LangGraph de validação de tópico."""

    def test_query_valida_nao_marca_done(self):
        state = {"query": "Quais são os sintomas da gripe?"}
        result = topic_validator_node(state)
        assert result["topic_valid"] is True
        assert result["done"] is False
        assert "final_response" not in result or result.get("final_response") == ""

    def test_query_invalida_marca_done(self):
        state = {"query": "Qual é a capital da França?"}
        result = topic_validator_node(state)
        assert result["topic_valid"] is False
        assert result["done"] is True
        assert "final_response" in result
        assert len(result["final_response"]) > 0

    def test_preserva_estado_existente(self):
        state = {
            "query": "O que é asma?",
            "session_id": "test-session",
            "preprocess_id": "some-id",
        }
        result = topic_validator_node(state)
        assert result["session_id"] == "test-session"
        assert result["preprocess_id"] == "some-id"
