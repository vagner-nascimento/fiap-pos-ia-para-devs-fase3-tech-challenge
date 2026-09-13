"""
Cliente LLM unificado para o agente médico.

Suporta dois modos de inferência do modelo fine-tunado (Qwen2.5):
1. **Hugging Face Spaces ZeroGPU (Produção / Oficial)**:
   - Aplicação Gradio (`hospital-helper`) com endpoint `api_name="generate"`.
   - Executa via `gradio_client` ou requisição HTTP Gradio.
   - Envia o prompt completo formatado com o template SFT.

2. **Custom FastAPI / ngrok (Desenvolvimento / Fallback)**:
   - Endpoint FastAPI com rota `/generate`.
   - Payload: `{"pergunta": "...", "contexto": "...", "max_new_tokens": 512}`.
   - Headers: `ngrok-skip-browser-warning: true`.
"""
import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Variáveis de ambiente
# ---------------------------------------------------------------------------
DEFAULT_LLM_ENDPOINT_URL = os.getenv("LLM_ENDPOINT_URL", "")
DEFAULT_LLM_API_TOKEN = os.getenv("LLM_API_TOKEN", "") or os.getenv("HF_TOKEN", "")
DEFAULT_LLM_PROVIDER = os.getenv("LLM_PROVIDER", "auto").lower()  # "auto", "hf_space", "fastapi"
DEFAULT_MAX_TOKENS = int(os.getenv("AGENT_MAX_TOKENS", "450"))
DEFAULT_TEMPERATURE = float(os.getenv("AGENT_TEMPERATURE", "0.10"))
DEFAULT_TOP_P = float(os.getenv("AGENT_TOP_P", "0.85"))
DEFAULT_REPETITION_PENALTY = float(os.getenv("AGENT_REPETITION_PENALTY", "1.15"))


def _build_sft_prompt(question: str, context: str = "") -> str:
    """
    Template SFT oficial do modelo fine-tunado.
    Idêntico ao _build_prompt do hospital-helper (app.py).
    """
    lines = [
        "### Instrucao:",
        "Responda em pt-BR usando o contexto clinico fornecido.",
        "",
        "### Entrada:",
        f"Pergunta: {question}",
    ]
    if context:
        lines.extend(["Contexto:", context])
    lines.extend(["", "### Resposta:"])
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Cliente para Hugging Face Space (Gradio API)
# ---------------------------------------------------------------------------
class GradioSpaceLLMClient:
    """Cliente para Hugging Face Spaces (Gradio) via gradio_client ou HTTP."""

    def __init__(
        self,
        space_url_or_id: str,
        hf_token: Optional[str] = None,
        max_new_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
        top_p: float = DEFAULT_TOP_P,
        repetition_penalty: float = DEFAULT_REPETITION_PENALTY,
    ) -> None:
        self.space_url_or_id = space_url_or_id.strip()
        self.hf_token = hf_token
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        self.top_p = top_p
        self.repetition_penalty = repetition_penalty
        self._client = None

        # Normalizar identificador para o gradio_client
        # Se for "https://huggingface.co/spaces/owner/space_name" -> extrai "owner/space_name"
        cleaned = self.space_url_or_id.rstrip("/")
        if "huggingface.co/spaces/" in cleaned:
            self.space_id = cleaned.split("huggingface.co/spaces/")[-1]
        else:
            self.space_id = cleaned

    def _get_gradio_client(self):
        if self._client is None:
            try:
                from gradio_client import Client
                # gradio_client >= 1.0 usa 'token', versões anteriores usavam 'hf_token'
                try:
                    self._client = Client(
                        self.space_id,
                        token=self.hf_token or None,
                    )
                except TypeError:
                    self._client = Client(
                        self.space_id,
                        hf_token=self.hf_token or None,
                    )
            except Exception as exc:
                logger.warning(f"[LLM-Space] gradio_client falhou ao inicializar: {exc}. Usará fallback HTTP.")
                self._client = False
        return self._client

    def generate(
        self,
        pergunta: str,
        contexto: str = "",
        prompt: Optional[str] = None,
    ) -> str:
        """Gera resposta no Space ZeroGPU passando o prompt formatado."""
        full_prompt = prompt or _build_sft_prompt(question=pergunta, context=contexto)
        return self.invoke(full_prompt)

    def invoke(self, prompt: str) -> str:
        """Envia o prompt completo para a API generate do Gradio."""
        client = self._get_gradio_client()
        if client:
            predict_kwargs = {
                "prompt": prompt,
                "max_new_tokens": float(self.max_new_tokens),
                "temperature": float(self.temperature),
                "top_p": float(self.top_p),
                "repetition_penalty": float(self.repetition_penalty),
                "api_name": "/generate",
            }
            try:
                result = client.predict(**predict_kwargs)
                return str(result).strip()
            except TypeError as te:
                # Pode ocorrer se o client em cache foi criado com schema desatualizado
                logger.info(f"[LLM-Space] TypeError no predict ({te}). Reconectando com client atualizado...")
                self._client = None
                fresh_client = self._get_gradio_client()
                if fresh_client:
                    try:
                        result = fresh_client.predict(**predict_kwargs)
                        return str(result).strip()
                    except Exception as retry_exc:
                        logger.error(f"[LLM-Space] Erro ao retentar com client atualizado: {retry_exc}")
                        if "repetition_penalty" in str(retry_exc):
                            predict_kwargs.pop("repetition_penalty")
                            try:
                                result = fresh_client.predict(**predict_kwargs)
                                return str(result).strip()
                            except Exception as legacy_exc:
                                self._client = None
                                return f"[ERRO] Falha na comunicação com o Space: {legacy_exc}"
                        self._client = None
                        return f"[ERRO] Falha na comunicação com o Space: {retry_exc}"
            except Exception as exc:
                logger.error(f"[LLM-Space] Erro na inferência via gradio_client: {exc}")
                self._client = None  # Invalida cache para reconectar na próxima chamada
                return f"[ERRO] Falha na comunicação com o Space: {exc}"

        # Fallback HTTP direto para Gradio 4/5 API
        import requests

        if "/" in self.space_id and not self.space_id.startswith("http"):
            owner, repo = self.space_id.split("/", 1)
            direct_host = f"https://{owner.replace('_', '-')}-{repo.replace('_', '-')}.hf.space"
        elif self.space_id.startswith("http"):
            direct_host = self.space_id.rstrip("/")
            if "huggingface.co/spaces/" in direct_host:
                parts = direct_host.split("huggingface.co/spaces/")[-1].split("/")
                if len(parts) >= 2:
                    direct_host = f"https://{parts[0].replace('_', '-')}-{parts[1].replace('_', '-')}.hf.space"
        else:
            direct_host = f"https://{self.space_id}.hf.space"

        target_url = f"{direct_host}/api/generate"
        headers = {"Content-Type": "application/json"}
        if self.hf_token:
            headers["Authorization"] = f"Bearer {self.hf_token}"

        payload = {
            "data": [
                prompt,
                self.max_new_tokens,
                self.temperature,
                self.top_p,
                self.repetition_penalty,
            ]
        }

        try:
            res = requests.post(target_url, json=payload, headers=headers, timeout=90)
            if res.status_code >= 400:
                payload_legacy = {
                    "data": [
                        prompt,
                        self.max_new_tokens,
                        self.temperature,
                        self.top_p,
                    ]
                }
                res_legacy = requests.post(target_url, json=payload_legacy, headers=headers, timeout=90)
                if res_legacy.status_code < 400:
                    res = res_legacy
            res.raise_for_status()
            data = res.json()
            if isinstance(data, dict) and "data" in data and data["data"]:
                return str(data["data"][0]).strip()
            return str(data).strip()
        except requests.exceptions.RequestException as exc:
            logger.error(f"[LLM-Space] Erro no fallback HTTP Gradio: {exc}")
            return f"[ERRO] Falha na comunicação com o modelo no Space: {exc}"


# ---------------------------------------------------------------------------
# Cliente para Custom FastAPI / ngrok
# ---------------------------------------------------------------------------
class FastApiLLMClient:
    """Cliente para endpoint FastAPI customizado (ngrok / desenvolvimento)."""

    def __init__(
        self,
        endpoint_url: str,
        api_token: Optional[str] = None,
        max_new_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
        top_p: float = DEFAULT_TOP_P,
        repetition_penalty: float = DEFAULT_REPETITION_PENALTY,
    ) -> None:
        self.endpoint_url = endpoint_url.rstrip("/")
        self.api_token = api_token
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        self.top_p = top_p
        self.repetition_penalty = repetition_penalty

    def _resolve_generate_url(self) -> str:
        if self.endpoint_url.endswith("/generate"):
            return self.endpoint_url
        return f"{self.endpoint_url}/generate"

    def generate(
        self,
        pergunta: str,
        contexto: str = "",
        prompt: Optional[str] = None,
    ) -> str:
        """Envia pergunta e contexto para o endpoint POST /generate do FastAPI."""
        import requests

        if not self.endpoint_url:
            logger.error("[LLM-FastAPI] LLM_ENDPOINT_URL não configurado.")
            return "[ERRO] O endpoint da LLM não está configurado."

        url = self._resolve_generate_url()
        headers = {
            "Content-Type": "application/json",
            "ngrok-skip-browser-warning": "true",
        }
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"

        payload = {
            "pergunta": pergunta,
            "contexto": contexto or "",
            "max_new_tokens": self.max_new_tokens,
            "repetition_penalty": self.repetition_penalty,
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=60)
            response.raise_for_status()
            data = response.json()

            if isinstance(data, dict) and "resposta" in data:
                return str(data["resposta"]).strip()
            if isinstance(data, dict) and "generated_text" in data:
                return str(data["generated_text"]).strip()
            return str(data).strip()

        except requests.exceptions.Timeout:
            logger.error("[LLM-FastAPI] Timeout ao chamar endpoint FastAPI.")
            return "[ERRO] Timeout ao processar a consulta. Tente novamente."
        except requests.exceptions.RequestException as exc:
            logger.error(f"[LLM-FastAPI] Erro ao chamar endpoint FastAPI: {exc}")
            return f"[ERRO] Falha na comunicação com o modelo: {exc}"

    def invoke(self, prompt: str) -> str:
        """Compatibilidade com LangChain: envia prompt como pergunta direta."""
        return self.generate(pergunta=prompt, contexto="")


# ---------------------------------------------------------------------------
# Factory do Cliente LLM
# ---------------------------------------------------------------------------
def build_llm_client(
    endpoint_url: Optional[str] = None,
    api_token: Optional[str] = None,
    provider: Optional[str] = None,
    max_new_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
    top_p: float = DEFAULT_TOP_P,
    repetition_penalty: float = DEFAULT_REPETITION_PENALTY,
) -> Any:
    """
    Constrói e retorna o cliente LLM adequado com base na URL e configuração.

    Identifica se o destino é um Hugging Face Space (Gradio) ou FastAPI (ngrok).
    """
    resolved_url = endpoint_url or DEFAULT_LLM_ENDPOINT_URL
    resolved_token = api_token or DEFAULT_LLM_API_TOKEN
    resolved_provider = (provider or DEFAULT_LLM_PROVIDER).lower()

    if not resolved_url:
        logger.warning(
            "[LLM] LLM_ENDPOINT_URL não configurado. "
            "O agente retornará mensagens de erro nas chamadas à LLM."
        )

    # Identificação automática de provedor
    is_hf_space = (
        resolved_provider == "hf_space"
        or "hf.space" in resolved_url
        or "huggingface.co/spaces" in resolved_url
        or (not resolved_url.startswith("http") and "/" in resolved_url)
    )

    if is_hf_space:
        logger.info(f"[LLM] Inicializando GradioSpaceLLMClient para: {resolved_url}")
        return GradioSpaceLLMClient(
            space_url_or_id=resolved_url,
            hf_token=resolved_token,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            top_p=top_p,
            repetition_penalty=repetition_penalty,
        )

    logger.info(f"[LLM] Inicializando FastApiLLMClient para: {resolved_url}")
    return FastApiLLMClient(
        endpoint_url=resolved_url,
        api_token=resolved_token,
        max_new_tokens=max_new_tokens,
        temperature=temperature,
        top_p=top_p,
        repetition_penalty=repetition_penalty,
    )
