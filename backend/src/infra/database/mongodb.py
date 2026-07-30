import os
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.collection import Collection
from typing import Optional

# Singleton para o client MongoDB
_mongo_client: Optional[MongoClient] = None


def get_mongo_client() -> MongoClient:
    """
    Retorna o client MongoDB (singleton).
    
    Constrói a URI usando variáveis de ambiente:
    - MONGODB_USER: usuário do MongoDB
    - MONGODB_PASSWORD: senha do MongoDB
    - MONGODB_HOST: host do MongoDB (default: localhost)
    - MONGODB_PORT: porta do MongoDB (default: 27017)
    
    Returns:
        MongoClient: Instância do client MongoDB.
    """
    global _mongo_client
    
    if _mongo_client is None:
        mongodb_user = os.getenv("MONGODB_USER", "db_user")
        mongodb_password = os.getenv("MONGODB_PASSWORD", "db_pass")
        mongodb_host = os.getenv("MONGODB_HOST", "localhost")
        mongodb_port = os.getenv("MONGODB_PORT", "27017")
        
        # Construir URI de conexão
        mongo_uri = f"mongodb://{mongodb_user}:{mongodb_password}@{mongodb_host}:{mongodb_port}"
        
        _mongo_client = MongoClient(
            mongo_uri,
            connectTimeoutMS=5000,
            serverSelectionTimeoutMS=5000,
            socketTimeoutMS=5000
        )
    
    return _mongo_client


def get_db() -> Database:
    """
    Retorna o banco de dados MongoDB.
    
    Usa a variável de ambiente DB_NAME para selecionar o banco.
    
    Returns:
        Database: Instância do banco de dados.
    """
    db_name = os.getenv("DB_NAME", "fiap_pos_ia_fase3")
    client = get_mongo_client()
    return client[db_name]


def get_collection(collection_name: str) -> Collection:
    """
    Retorna uma collection específica do banco de dados.
    
    Args:
        collection_name: Nome da collection.
        
    Returns:
        Collection: Instância da collection.
    """
    db = get_db()
    return db[collection_name]


def test_connection() -> bool:
    """
    Testa a conexão com o banco de dados MongoDB.
    
    Returns:
        bool: True se a conexão for bem-sucedida, False caso contrário.
    """
    global _mongo_client
    try:
        # Resetar o client para garantir que os timeouts sejam aplicados
        _mongo_client = None
        client = get_mongo_client()
        # Enviar comando ping para testar conexão
        client.admin.command('ping')
        return True
    except Exception as e:
        print(f"Erro ao testar conexão com MongoDB: {e}")
        return False