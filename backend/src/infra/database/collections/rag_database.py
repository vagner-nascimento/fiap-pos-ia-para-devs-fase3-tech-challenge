import copy
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Final, List, Optional

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


def get_rag_documents_for_search(preprocess_id: Optional[str] = None) -> List[Dict[str, Any]]:
    collection = get_collection(RAG_DOCUMENTS_COLLECTION)
    filter_query: Dict[str, Any] = {}
    if preprocess_id:
        filter_query["preprocess_id"] = preprocess_id

    projection = {
        "_id": 1,
        "batch_id": 1,
        "preprocess_id": 1,
        "dataset": 1,
        "source_type": 1,
        "content": 1,
        "metadatas": 1,
        "embedding": 1,
        "chunk_index": 1,
        "chunk_total": 1,
    }

    if hasattr(collection, "find"):
        try:
            cursor = collection.find(filter_query, projection)
        except TypeError:
            cursor = collection.find(filter_query)
        documents = list(cursor)
    elif hasattr(collection, "documents"):
        raw_docs = list(collection.documents.values())
        if preprocess_id:
            documents = [doc for doc in raw_docs if doc.get("preprocess_id") == preprocess_id]
        else:
            documents = raw_docs
    else:
        documents = []

    return [_serialize_document(doc) for doc in documents]

