"""
Factory da aplicação FastAPI do serviço de agente médico.

Segue o mesmo padrão arquitetural do backend principal:
- Configuração via lifespan
- Carregamento dinâmico de routers
- Verificação de conexão MongoDB no startup
"""
import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from infra.database.mongodb import test_connection
from routers import get_all_routers

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gerencia eventos de startup e shutdown do serviço.

    No startup, verifica a conexão com o MongoDB. Se a conexão falhar,
    impede a inicialização do serviço.
    """
    logger.info("Iniciando serviço de agente médico...")
    logger.info("Testando conexão com MongoDB...")

    if test_connection():
        logger.info("Conexão com MongoDB estabelecida com sucesso!")
    else:
        logger.error("Falha na conexão com MongoDB. O serviço não será inicializado.")
        raise SystemExit(
            "Não foi possível conectar ao MongoDB. "
            "Verifique as configurações e se o serviço está rodando."
        )

    yield

    logger.info("Encerrando serviço de agente médico...")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------
def create_app() -> FastAPI:
    """
    Cria e configura a aplicação FastAPI do agente médico.

    Returns:
        FastAPI: Aplicação configurada com todos os routers e middleware.
    """
    app = FastAPI(
        title="FIAP POS IA — Agente Médico",
        description=(
            "Assistente médico inteligente com LangChain/LangGraph. "
            "Utiliza RAG sobre datasets médicos (PubMedQA, MedQuAD, FHEMIG) "
            "e o modelo Qwen2.5 fine-tunado para responder perguntas no domínio de saúde."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    # Carregar todos os routers dinamicamente
    routers = get_all_routers()
    for router in routers:
        app.include_router(router)
        logger.info(f"Router registrado: {router.prefix}")

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Em produção, especificar origens permitidas
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health check
    @app.get("/health", tags=["health"])
    async def health_check():
        """Verifica se o serviço está operacional."""
        return {
            "service": "fiap-pos-ia-agent",
            "timestamp": datetime.utcnow().isoformat(),
            "status": "UP",
        }

    return app
