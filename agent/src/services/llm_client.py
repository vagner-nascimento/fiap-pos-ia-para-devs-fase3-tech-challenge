"""
Cliente LLM para o agente médico.

Abstrai a conexão com o modelo fine-tunado servido via:
- ngrok endpoint (Google Colab / desenvolvimento)
- HuggingFace ZeroGPU Inference Endpoint (produção)

Utiliza `langchain_community.llms.HuggingFaceEndpoint` para compatibilidade
com o ecossistema LangChain, com fallback para chamada HTTP direta caso a
biblioteca não esteja disponível.
"""
import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Variáveis de ambiente
# ---------------------------------------------------------------------------
DEFAULT_LLM_ENDPOINT_URL = os.getenv("LLM_ENDPOINT_URL", "")
DEFAULT_LLM_API_TOKEN = os.getenv("LLM_API_TOKEN", "")
DEFAULT_MAX_TOKENS = int(os.getenv("AGENT_MAX_TOKENS", "512"))
DEFAULT_TEMPERATURE = float(os.getenv("AGENT_TEMPERATURE", "0.1"))

# ---------------------------------------------------------------------------
# Tentativa de importar HuggingFaceEndpoint do LangChain
# ---------------------------------------------------------------------------
try:
    from langchain_community.llms import HuggingFaceEndpoint as _HFEndpoint

    _HF_AVAILABLE = True
except Exception:  # pragma: no cover
    _HFEndpoint = None
    _HF_AVAILABLE = False
    logger.warning(
        "[LLM] langchain_community.llms.HuggingFaceEndpoint não disponível. "
        "Usando fallback HTTP direto."
    )


# ---------------------------------------------------------------------------
# Fallback: chamada HTTP direta ao endpoint
# ---------------------------------------------------------------------------
class _FallbackLLMClient:
    """
    Cliente HTTP simples para chamadas ao endpoint do modelo quando
    o LangChain HuggingFaceEndpoint não está disponível.
    """

    def __init__(
        self,
        endpoint_url: str,
        api_token: str,
        max_new_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
    ) -> None:
        self.endpoint_url = endpoint_url
        self.api_token = api_token
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature

    def invoke(self, prompt: str) -> str:
        """Envia o prompt ao endpoint e retorna a resposta gerada."""
        import requests

        if not self.endpoint_url:
            logger.error("[LLM] LLM_ENDPOINT_URL não configurado.")
            return "[ERRO] O endpoint da LLM não está configurado."

        headers = {
            "Content-Type": "application/json",
        }
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"

        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": self.max_new_tokens,
                "temperature": self.temperature,
                "do_sample": self.temperature > 0,
                "return_full_text": False,
            },
        }

        try:
            response = requests.post(
                self.endpoint_url,
                json=payload,
                headers=headers,
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()

            # HuggingFace Inference API retorna lista de dicts com "generated_text"
            if isinstance(data, list) and data:
                return data[0].get("generated_text", "")
            if isinstance(data, dict):
                return data.get("generated_text", str(data))
            return str(data)

        except requests.exceptions.Timeout:
            logger.error("[LLM] Timeout ao chamar o endpoint LLM.")
            return "[ERRO] Timeout ao processar a consulta. Tente novamente."
        except requests.exceptions.RequestException as exc:
            logger.error(f"[LLM] Erro ao chamar o endpoint LLM: {exc}")
            return f"[ERRO] Falha na comunicação com o modelo: {exc}"


# ---------------------------------------------------------------------------
# Factory pública
# ---------------------------------------------------------------------------
def build_llm_client(
    endpoint_url: Optional[str] = None,
    api_token: Optional[str] = None,
    max_new_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
) -> Any:
    """
    Constrói e retorna o cliente LLM.

    Tenta usar `HuggingFaceEndpoint` do LangChain primeiro. Se não estiver
    disponível, usa o fallback HTTP direto.

    Args:
        endpoint_url: URL do endpoint de inferência do modelo.
        api_token: Token de autenticação HuggingFace.
        max_new_tokens: Número máximo de tokens na resposta.
        temperature: Temperatura de amostragem (0 = determinístico).

    Returns:
        Objeto com método `invoke(prompt: str) -> str`.
    """
    resolved_url = endpoint_url or DEFAULT_LLM_ENDPOINT_URL
    resolved_token = api_token or DEFAULT_LLM_API_TOKEN

    if not resolved_url:
        logger.warning(
            "[LLM] LLM_ENDPOINT_URL não configurado. "
            "O agente retornará respostas de erro nas chamadas à LLM."
        )

    if _HF_AVAILABLE and _HFEndpoint is not None and resolved_url:
        try:
            client = _HFEndpoint(
                endpoint_url=resolved_url,
                huggingfacehub_api_token=resolved_token or None,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                task="text-generation",
            )
            logger.info(f"[LLM] HuggingFaceEndpoint configurado: {resolved_url}")
            return client
        except Exception as exc:
            logger.warning(
                f"[LLM] Falha ao criar HuggingFaceEndpoint: {exc}. "
                "Usando fallback HTTP."
            )

    logger.info(f"[LLM] Usando fallback HTTP para: {resolved_url}")
    return _FallbackLLMClient(
        endpoint_url=resolved_url,
        api_token=resolved_token,
        max_new_tokens=max_new_tokens,
        temperature=temperature,
    )
