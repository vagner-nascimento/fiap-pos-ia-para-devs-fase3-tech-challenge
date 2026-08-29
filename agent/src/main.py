"""
Entrypoint do serviço de agente médico.

Inicializa a aplicação FastAPI via factory e expõe para o Uvicorn.
"""
from server import create_app

app = create_app()
