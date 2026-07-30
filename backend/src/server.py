import logging
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI
from routers import get_all_routers
from infra.database.mongodb import test_connection

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Context manager for application lifespan events.
    
    Tests MongoDB connection on startup and prevents application
    initialization if the connection fails.
    """
    # Startup event
    logger.info("Iniciando aplicação...")
    logger.info("Testando conexão com MongoDB...")
    
    if test_connection():
        logger.info("Conexão com MongoDB estabelecida com sucesso!")
    else:
        logger.error("Falha na conexão com MongoDB. A aplicação não será inicializada.")
        raise SystemExit("Não foi possível conectar ao MongoDB. Verifique as configurações e se o serviço está rodando.")
    
    yield
    
    # Shutdown event
    logger.info("Encerrando aplicação...")


def create_app() -> FastAPI:
    """
    Cria e configura a aplicação FastAPI.
    
    Esta função instancia o FastAPI, carrega dinamicamente todas as rotas
    do pacote routers e configura o middleware necessário.
    
    Returns:
        FastAPI: Aplicação FastAPI configurada com todas as rotas.
    """
    app = FastAPI(
        title="FIAP POS IA Backend",
        description="Backend para processamento de dados médicos PubMedQA e MedQuAD",
        version="0.1.0",
        lifespan=lifespan
    )
    
    # Carregar todas as rotas dinamicamente
    routers = get_all_routers()
    for router in routers:
        app.include_router(router)
        print(f"Rota incluída: {router.prefix}")
    
    # Configurar CORS se necessário
    from fastapi.middleware.cors import CORSMiddleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Em produção, especificar origens permitidas
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Adicionar rota /health
    @app.get("/health")
    async def health_check():
        """Rota de health check padrão."""
        return {
            "app_name": "FIAP POS IA Backend",
            "timestamp": datetime.utcnow().isoformat(),
            "status": "UP"
        }
    
    return app
