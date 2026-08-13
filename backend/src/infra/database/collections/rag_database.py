import copy
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Final, List

from infra.database.mongodb import get_collection


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
