"""Testes do prompt conversacional enviado à LLM."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_prompt_inclui_historico_da_sessao():
    from services.nodes.llm_generator import _build_prompt

    prompt = _build_prompt(
        question="E quais cuidados devo ter?",
        conversation_history=[
            {
                "query": "O que é diabetes?",
                "response": "É uma condição metabólica que exige acompanhamento.",
            }
        ],
    )

    assert "### Historico da conversa:" in prompt
    assert "Usuario: O que é diabetes?" in prompt
    assert "Assistente: É uma condição metabólica que exige acompanhamento." in prompt
    assert "Pergunta: E quais cuidados devo ter?" in prompt
