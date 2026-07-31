import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from typing import Final

from infra.database.mongodb import get_collection

PREPROCESS_COLLECTION: Final[str] = "preprocess"


def _serialize_preprocess_document(document: Dict[str, Any]) -> Dict[str, Any]:
    if "updated_date" in document and isinstance(document["updated_date"], datetime):
        document["updated_date"] = document["updated_date"].isoformat()
    serialized = dict(document)
    if "error_message" in serialized and not serialized["error_message"]:
        serialized.pop("error_message")
    return serialized


def create_preprocess_document() -> Dict[str, Any]:
    """
    Cria um novo documento na collection preprocess.
    
    Gera um UUID único para o documento e cria a estrutura inicial.
    
    Returns:
        Dict com o documento criado, incluindo o _id gerado.
    """
    collection = get_collection(PREPROCESS_COLLECTION)
    
    doc_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    
    document = {
        "_id": doc_id,
        "train_data": 0,
        "rag_data": 0,
        "status": "created",
        "updated_date": now,
        "completion_percentage": 0
    }
    
    collection.insert_one(document)
    
    return _serialize_preprocess_document(document)


def get_preprocess_document(doc_id: str) -> Optional[Dict[str, Any]]:
    """
    Busca um documento na collection preprocess pelo ID.
    
    Args:
        doc_id: ID do documento a buscar.
        
    Returns:
        Dict com o documento encontrado, ou None se não existir.
    """
    collection = get_collection(PREPROCESS_COLLECTION)
    
    document = collection.find_one({"_id": doc_id})
    
    if document:
        return _serialize_preprocess_document(document)
    
    return document


def update_preprocess_document(
    doc_id: str,
    train_data: int,
    rag_data: int,
    completion_percentage: float
) -> Optional[Dict[str, Any]]:
    """
    Atualiza um documento na collection preprocess.
    
    Atualiza:
    - updated_date com o valor atual
    - train_data com o valor passado
    - rag_data com o valor passado
    - completion_percentage com o valor passado
    - status para "in_progress"
    - Se completion_percentage for 100, atualiza status para "completed"
    
    Args:
        doc_id: ID do documento a atualizar.
        train_data: Quantidade de dados de treino processados.
        rag_data: Quantidade de dados RAG processados.
        completion_percentage: Percentual de conclusão (0 a 100).
        
    Returns:
        Dict com o documento atualizado, ou None se não existir.
    """
    collection = get_collection(PREPROCESS_COLLECTION)
    
    now = datetime.now(timezone.utc)
    
    status = "completed" if completion_percentage >= 100 else "in_progress"
    
    update_data = {
        "train_data": train_data,
        "rag_data": rag_data,
        "completion_percentage": completion_percentage,
        "status": status,
        "updated_date": now
    }
    
    result = collection.update_one(
        {"_id": doc_id},
        {
            "$set": update_data,
            "$unset": {"error_message": ""},
        }
    )
    
    if result.matched_count > 0:
        return get_preprocess_document(doc_id)
    
    return None


def mark_preprocess_document_failed(doc_id: str, error_message: str) -> Optional[Dict[str, Any]]:
    """
    Marca um documento de preprocessamento como falho e armazena a mensagem de erro.

    Args:
        doc_id: ID do documento a atualizar.
        error_message: Mensagem de erro a persistir.

    Returns:
        Dict com o documento atualizado, ou None se não existir.
    """
    collection = get_collection(PREPROCESS_COLLECTION)

    now = datetime.now(timezone.utc)
    update_data = {
        "status": "failed",
        "error_message": error_message,
        "updated_date": now,
    }

    result = collection.update_one({"_id": doc_id}, {"$set": update_data})

    if result.matched_count > 0:
        return get_preprocess_document(doc_id)

    return None
