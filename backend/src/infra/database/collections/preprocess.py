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
    # Serialize step error messages
    if "steps" in serialized:
        for step_name, step_info in serialized["steps"].items():
            if "error_message" in step_info and not step_info["error_message"]:
                step_info.pop("error_message")
    return serialized


def _calculate_overall_status(steps: Dict[str, Dict[str, Any]]) -> str:
    """
    Calcula o status geral baseado nos status dos steps individuais.
    
    Args:
        steps: Dicionário com informações de cada step
        
    Returns:
        Status geral: "created", "in_progress", "completed", ou "error"
    """
    if not steps:
        return "created"
    
    step_statuses = [step_info.get("status", "pending") for step_info in steps.values()]
    
    # Se algum step está em erro, status geral é error
    if "error" in step_statuses:
        return "error"
    
    # Se algum step está em progresso, status geral é in_progress
    if "in_progress" in step_statuses:
        return "in_progress"
    
    # Se todos estão completed, status geral é completed
    if all(status == "completed" for status in step_statuses):
        return "completed"
    
    # Se todos estão pending, status geral é created
    return "created"


def create_preprocess_document(rag_percent: float = 0.5) -> Dict[str, Any]:
    """
    Cria um novo documento na collection preprocess.
    
    Gera um UUID único para o documento e cria a estrutura inicial com steps.
    
    Args:
        rag_percent: Percentual de dados para RAG (0.0 a 1.0).
    
    Returns:
        Dict com o documento criado, incluindo o _id gerado.
    """
    collection = get_collection(PREPROCESS_COLLECTION)
    
    doc_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    
    document = {
        "_id": doc_id,
        "rag_percent": rag_percent,
        "steps": {
            "one_download_datasets": {
                "status": "pending",
                "error_message": None
            },
            "step_two_data_extraction": {
                "status": "pending",
                "error_message": None
            },
            "step_three_translating": {
                "status": "pending",
                "error_message": None
            }
        },
        "results": {
            "QAs": {
                "train_data": 0,
                "rag_data": 0
            },
            "clinical_protocols": {
                "train_data": 0,
                "rag_data": 0
            }
        },
        "status": "created",
        "error_message": None,
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


def update_step_status(
    doc_id: str,
    step_name: str,
    status: str,
    error_message: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Atualiza o status de um step específico e recalcula o status geral.
    
    Args:
        doc_id: ID do documento a atualizar.
        step_name: Nome do step (ex: "one_download_datasets").
        status: Novo status do step ("pending", "in_progress", "completed", "error").
        error_message: Mensagem de erro (apenas se status for "error").
        
    Returns:
        Dict com o documento atualizado, ou None se não existir.
    """
    collection = get_collection(PREPROCESS_COLLECTION)
    
    now = datetime.now(timezone.utc)
    
    # Buscar documento atual para calcular novo status geral
    current_doc = collection.find_one({"_id": doc_id})
    if not current_doc:
        return None
    
    # Atualizar o step específico
    step_key = f"steps.{step_name}"
    update_data = {
        f"{step_key}.status": status,
        f"{step_key}.error_message": error_message if status == "error" else None,
        "updated_date": now
    }
    
    result = collection.update_one(
        {"_id": doc_id},
        {"$set": update_data}
    )
    
    if result.matched_count > 0:
        # Buscar documento atualizado para calcular status geral
        updated_doc = collection.find_one({"_id": doc_id})
        if updated_doc:
            overall_status = _calculate_overall_status(updated_doc.get("steps", {}))
            
            # Atualizar status geral e error_message
            overall_update = {
                "status": overall_status,
                "error_message": error_message if overall_status == "error" else None
            }
            
            collection.update_one(
                {"_id": doc_id},
                {"$set": overall_update}
            )
            
            return get_preprocess_document(doc_id)
    
    return None


def update_preprocess_document(
    doc_id: str,
    results: Dict[str, Dict[str, int]],
    completion_percentage: float
) -> Optional[Dict[str, Any]]:
    """
    Atualiza os resultados e o progresso de um documento na collection preprocess.
    
    Atualiza:
    - updated_date com o valor atual
    - results com os dados passados
    - completion_percentage com o valor passado
    - status geral (recalculado baseado nos steps)
    
    Args:
        doc_id: ID do documento a atualizar.
        results: Dicionário com resultados (QAs e clinical_protocols).
        completion_percentage: Percentual de conclusão (0 a 100).
        
    Returns:
        Dict com o documento atualizado, ou None se não existir.
    """
    collection = get_collection(PREPROCESS_COLLECTION)
    
    now = datetime.now(timezone.utc)
    
    # Buscar documento atual para calcular status geral
    current_doc = collection.find_one({"_id": doc_id})
    if not current_doc:
        return None
    
    overall_status = _calculate_overall_status(current_doc.get("steps", {}))
    
    update_data = {
        "results": results,
        "completion_percentage": completion_percentage,
        "status": overall_status,
        "updated_date": now
    }
    
    # Limpar error_message se não estiver em erro
    if overall_status != "error":
        update_data["error_message"] = None
    
    result = collection.update_one(
        {"_id": doc_id},
        {"$set": update_data}
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
