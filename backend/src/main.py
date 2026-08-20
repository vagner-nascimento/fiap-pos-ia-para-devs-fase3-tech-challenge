import os
import sys
from dotenv import load_dotenv
from huggingface_hub import login
import uvicorn
from server import create_app

# Carregar variáveis de ambiente do arquivo .env
load_dotenv()


def authenticate_hugging_face():
    hf_token = os.getenv("HF_TOKEN")
    if hf_token and hf_token.strip():
        login(token=hf_token.strip(), add_to_git_credential=True)
    else:
        print("Aviso: executando sem token do Hugging Face.")


authenticate_hugging_face()

# Configurar PYTHONPATH a partir da variável de ambiente
pythonpath = os.getenv('PYTHONPATH')
if pythonpath and pythonpath not in sys.path:
    sys.path.insert(0, pythonpath)


def main():
    """Função principal para executar o servidor FastAPI."""
    app = create_app()
    
    # Executar o servidor com uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=3000
    )


if __name__ == "__main__":
    main()
