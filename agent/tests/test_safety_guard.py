"""
Testes unitários para o nó de guardrail de segurança (safety_guard).

Verifica que:
- Padrões de prescrição com dose são bloqueados
- Pedidos de diagnóstico definitivo são bloqueados
- Perguntas informativas legítimas são permitidas
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from services.nodes.safety_guard import _check_safety, safety_guard_node


class TestCheckSafety:
    """Testes da função de verificação de segurança."""

    # --- Casos que DEVEM ser bloqueados ---

    def test_prescricao_com_dose_mg_bloqueada(self):
        is_safe, reason = _check_safety("Pode me prescrever amoxicilina 500mg?")
        assert is_safe is False
        assert reason is not None

    def test_instrucao_dose_bloqueada(self):
        is_safe, reason = _check_safety("Devo tomar 2 comprimidos de paracetamol?")
        assert is_safe is False

    def test_pedido_direto_prescricao_bloqueado(self):
        is_safe, reason = _check_safety("Me receita um antibiótico para a tosse")
        assert is_safe is False

    def test_diagnostico_definitivo_bloqueado(self):
        is_safe, reason = _check_safety("Tenho certeza que meu diagnóstico é lupus")
        assert is_safe is False

    # --- Casos que DEVEM ser permitidos ---

    def test_sintomas_gerais_permitido(self):
        is_safe, reason = _check_safety("Quais são os sintomas da dengue?")
        assert is_safe is True
        assert reason is None

    def test_informacao_sobre_tratamento_permitida(self):
        is_safe, reason = _check_safety(
            "Quais são as opções de tratamento disponíveis para diabetes tipo 2?"
        )
        assert is_safe is True

    def test_protocolo_clinico_permitido(self):
        is_safe, reason = _check_safety(
            "O que diz o protocolo clínico da FHEMIG sobre hipertensão?"
        )
        assert is_safe is True

    def test_query_vazia_permitida(self):
        is_safe, reason = _check_safety("")
        assert is_safe is True

    def test_prevencao_doenca_permitida(self):
        is_safe, reason = _check_safety(
            "Como prevenir a tuberculose em comunidades vulneráveis?"
        )
        assert is_safe is True


class TestSafetyGuardNode:
    """Testes do nó LangGraph de guardrail de segurança."""

    def test_query_segura_nao_marca_done(self):
        state = {
            "query": "O que é pneumonia?",
            "topic_valid": True,
            "done": False,
        }
        result = safety_guard_node(state)
        assert result["safety_triggered"] is False
        assert result["done"] is False

    def test_query_insegura_marca_done(self):
        state = {
            "query": "Me prescreve amoxicilina 500mg por favor",
            "topic_valid": True,
            "done": False,
        }
        result = safety_guard_node(state)
        assert result["safety_triggered"] is True
        assert result["done"] is True
        assert "final_response" in result
        assert "não pode" in result["final_response"].lower() or "não permitida" in result["final_response"].lower()

    def test_preserva_estado(self):
        state = {
            "query": "Quais os sintomas da malária?",
            "session_id": "sess-xyz",
            "topic_valid": True,
            "done": False,
        }
        result = safety_guard_node(state)
        assert result["session_id"] == "sess-xyz"
        assert result["topic_valid"] is True
