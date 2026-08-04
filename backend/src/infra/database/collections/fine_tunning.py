import copy
from datetime import datetime, timezone
from typing import Any, Dict, Final, Optional

from infra.database.mongodb import get_collection

FINE_TUNNING_COLLECTION: Final[str] = "fine_tunning"


def _serialize_fine_tunning_document(document: Dict[str, Any]) -> Dict[str, Any]:
    serialized = copy.deepcopy(document)

    def _serialize_value(value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, list):
            return [_serialize_value(item) for item in value]
        if isinstance(value, dict):
            return {key: _serialize_value(item) for key, item in value.items()}
        return value

    return _serialize_value(serialized)


def create_fine_tunning_document(payload: Dict[str, Any]) -> Dict[str, Any]:
    collection = get_collection(FINE_TUNNING_COLLECTION)

    now = datetime.now(timezone.utc)

    document = {
        "status": "pendding",
        "completion_percentage": 0,
        "error_message": None,
        "created_date": now,
        "updated_date": now,
        "started_date": None,
        "finished_date": None,
        "current_loss": None,
        "loss_history": [],
        "training_metrics": {},
        **payload,
    }

    result = collection.insert_one(document)
    # Buscar o documento inserido para obter o _id gerado pelo MongoDB
    inserted_document = collection.find_one({"_id": result.inserted_id})
    if inserted_document:
        return _serialize_fine_tunning_document(inserted_document)
    return _serialize_fine_tunning_document(document)


def get_fine_tunning_document(doc_id: str) -> Optional[Dict[str, Any]]:
    collection = get_collection(FINE_TUNNING_COLLECTION)
    document = collection.find_one({"_id": doc_id})
    if document:
        return _serialize_fine_tunning_document(document)
    return None


def update_fine_tunning_document(doc_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    collection = get_collection(FINE_TUNNING_COLLECTION)
    now = datetime.now(timezone.utc)

    update_data = dict(updates)
    update_data["updated_date"] = now

    result = collection.update_one({"_id": doc_id}, {"$set": update_data})
    if result.matched_count > 0:
        return get_fine_tunning_document(doc_id)

    return None


def mark_fine_tunning_document_failed(doc_id: str, error_message: str) -> Optional[Dict[str, Any]]:
    return update_fine_tunning_document(
        doc_id,
        {
            "status": "error",
            "error_message": error_message,
            "finished_date": datetime.now(timezone.utc),
        },
    )


def mark_fine_tunning_document_completed(
    doc_id: str,
    updates: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    completed_updates = dict(updates)
    completed_updates["status"] = "completed"
    completed_updates["completion_percentage"] = 100
    completed_updates["error_message"] = None
    completed_updates["finished_date"] = datetime.now(timezone.utc)
    return update_fine_tunning_document(doc_id, completed_updates)
