import os
import sys
from dotenv import load_dotenv
import uvicorn
from server import create_app

# Carregar variáveis de ambiente do arquivo .env
load_dotenv()

# Garantir que src esteja no path para imports
sys_path_dir = os.path.dirname(os.path.abspath(__file__))
if sys_path_dir not in sys.path:
    sys.path.insert(0, sys_path_dir)

app = create_app()


def main():
    """Função principal para executar o servidor FastAPI do agente."""
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        app_dir="src",
    )


if __name__ == "__main__":
    main()

