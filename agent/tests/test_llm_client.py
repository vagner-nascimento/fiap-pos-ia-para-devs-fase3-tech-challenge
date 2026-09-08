"""Testes unitários para o cliente LLM híbrido e suporte a repetition_penalty."""
from unittest.mock import MagicMock, patch
import pytest

from services.llm_client import GradioSpaceLLMClient, FastApiLLMClient, build_llm_client


def test_gradio_client_predict_com_repetition_penalty():
    client = GradioSpaceLLMClient(
        space_url_or_id="fiap/hospital-helper",
        repetition_penalty=1.20,
    )
    mock_gradio = MagicMock()
    mock_gradio.predict.return_value = "Resposta gerada"

    with patch.object(client, "_get_gradio_client", return_value=mock_gradio):
        res = client.invoke("Qual o protocolo?")
        assert res == "Resposta gerada"
        mock_gradio.predict.assert_called_once_with(
            prompt="Qual o protocolo?",
            max_new_tokens=450.0,
            temperature=0.10,
            top_p=0.85,
            repetition_penalty=1.20,
            api_name="/generate",
        )


def test_gradio_client_fallback_retrocompatibilidade_se_space_nao_suportar_repetition_penalty():
    """Garante que se o Space no HF ainda não tiver sido atualizado, não quebra a requisição."""
    client = GradioSpaceLLMClient(
        space_url_or_id="fiap/hospital-helper",
        repetition_penalty=1.15,
    )
    mock_gradio = MagicMock()

    def mock_predict(**kwargs):
        if "repetition_penalty" in kwargs:
            raise TypeError("Parameter `repetition_penalty` is not a valid key-word argument.")
        return "Resposta via fallback sem repetition_penalty"

    mock_gradio.predict.side_effect = mock_predict

    with patch.object(client, "_get_gradio_client", return_value=mock_gradio):
        res = client.invoke("Qual o protocolo?")
        assert res == "Resposta via fallback sem repetition_penalty"


def test_build_llm_client_passa_repetition_penalty():
    client = build_llm_client(
        endpoint_url="https://lbaroni-hospital-helper.hf.space",
        repetition_penalty=1.25,
    )
    assert isinstance(client, GradioSpaceLLMClient)
    assert client.repetition_penalty == 1.25
