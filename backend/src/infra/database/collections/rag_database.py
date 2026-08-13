import copy
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Final, List, Optional

from infra.database.mongodb import get_collection


RAG_GENERATION_COLLECTION: Final[str] = "rag_database_generation"
RAG_DOCUMENTS_COLLECTION: Final[str] = "rag_documents"


def _serialize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize_value(item) for key, item in value.items()}
    return value


def _serialize_document(document: Dict[str, Any]) -> Dict[str, Any]:
    return _serialize_value(copy.deepcopy(document))


def create_rag_generation_document(payload: Dict[str, Any]) -> Dict[str, Any]:
    collection = get_collection(RAG_GENERATION_COLLECTION)
    now = datetime.now(timezone.utc)

    document = {
        "_id": payload.get("_id") or str(uuid.uuid4()),
        "status": "pendding",
        "completion_percentage": 0,
        "error_message": None,
        "created_date": now,
        "updated_date": now,
        "started_date": None,
        "finished_date": None,
        "current_step": 0,
        "estimated_total_steps": 2,
        "qas_documents": 0,
        "clinical_protocol_documents": 0,
        "total_documents": 0,
        **payload,
    }

    collection.insert_one(document)
    inserted_document = collection.find_one({"_id": document["_id"]})
    return _serialize_document(inserted_document or document)


def get_rag_generation_document(doc_id: str) -> Optional[Dict[str, Any]]:
    collection = get_collection(RAG_GENERATION_COLLECTION)
    document = collection.find_one({"_id": doc_id})
    if document is None:
        return None
    return _serialize_document(document)


def update_rag_generation_document(doc_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    collection = get_collection(RAG_GENERATION_COLLECTION)
    update_data = dict(updates)
    update_data["updated_date"] = datetime.now(timezone.utc)

    result = collection.update_one({"_id": doc_id}, {"$set": update_data})
    if result.matched_count > 0:
        return get_rag_generation_document(doc_id)

    return None


def mark_rag_generation_document_failed(doc_id: str, error_message: str) -> Optional[Dict[str, Any]]:
    return update_rag_generation_document(
        doc_id,
        {
            "status": "error",
            "error_message": error_message,
            "finished_date": datetime.now(timezone.utc),
        },
    )


def mark_rag_generation_document_completed(
    doc_id: str,
    updates: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    completed_updates = dict(updates)
    completed_updates["status"] = "completed"
    completed_updates["completion_percentage"] = 100
    completed_updates["error_message"] = None
    completed_updates["finished_date"] = datetime.now(timezone.utc)
    return update_rag_generation_document(doc_id, completed_updates)


def insert_rag_documents(documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    collection = get_collection(RAG_DOCUMENTS_COLLECTION)
    now = datetime.now(timezone.utc)
    inserted_documents: List[Dict[str, Any]] = []

    if not documents:
        return inserted_documents

    prepared_documents: List[Dict[str, Any]] = []
    for document in documents:
        prepared_document = dict(document)
        prepared_document.setdefault("_id", str(uuid.uuid4()))
        prepared_document.setdefault("created_date", now)
        prepared_document.setdefault("updated_date", now)
        prepared_documents.append(prepared_document)

    if hasattr(collection, "insert_many"):
        collection.insert_many(prepared_documents)
    else:
        for prepared_document in prepared_documents:
            collection.insert_one(prepared_document)

    for prepared_document in prepared_documents:
        inserted_documents.append(_serialize_document(prepared_document))

    return inserted_documents
