import json
import sys
from pathlib import Path
from typing import Dict, List

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from infra.database.collections import rag_database as rag_collection
from services import rag_database as rag_service


class FakeCollection:
    def __init__(self) -> None:
        self.documents = {}

    def insert_one(self, document: dict) -> None:
        self.documents[document["_id"]] = document.copy()

    def insert_many(self, documents: List[dict]) -> None:
        for document in documents:
            self.insert_one(document)

    def find_one(self, query: dict) -> dict | None:
        return self.documents.get(query.get("_id"))

    def update_one(self, query: dict, update: dict) -> object:
        document = self.documents[query["_id"]]
        if "$set" in update:
            for key, value in update["$set"].items():
                if "." in key:
                    keys = key.split(".")
                    current = document
                    for nested_key in keys[:-1]:
                        if nested_key not in current:
                            current[nested_key] = {}
                        current = current[nested_key]
                    current[keys[-1]] = value
                else:
                    document[key] = value
        return type("Result", (), {"matched_count": 1})()


class DummyEmbeddingModel:
    def __init__(self, model_name: str = "dummy") -> None:
        self.model_name = model_name

    def embed_documents(self, texts):
        return [[float(len(text)), 1.0, 2.0, 3.0] for text in texts]

    def embed_query(self, text):
        return [float(len(text)), 1.0, 2.0, 3.0]


def _make_collections() -> Dict[str, FakeCollection]:
    return {
        rag_collection.RAG_GENERATION_COLLECTION: FakeCollection(),
        rag_collection.RAG_DOCUMENTS_COLLECTION: FakeCollection(),
    }


def test_create_and_update_rag_generation_document(monkeypatch) -> None:
    collections = _make_collections()
    monkeypatch.setattr(rag_collection, "get_collection", lambda name: collections[name])

    document = rag_collection.create_rag_generation_document(
        {
            "_id": "batch-1",
            "preprocess_id": "preprocess-1",
            "preprocess_snapshot": {"_id": "preprocess-1", "status": "completed"},
            "qas_rag_path": "qas.json",
            "clinical_protocols_rag_path": "clinical.json",
        }
    )

    assert document["_id"] == "batch-1"
    assert document["status"] == "pendding"
    assert document["completion_percentage"] == 0

    updated = rag_collection.update_rag_generation_document(
        "batch-1",
        {"status": "in_progress", "completion_percentage": 50, "current_step": 1},
    )

    assert updated is not None
    assert updated["status"] == "in_progress"
    assert updated["completion_percentage"] == 50
    assert updated["current_step"] == 1

    completed = rag_collection.mark_rag_generation_document_completed(
        "batch-1",
        {"current_step": 2, "total_documents": 3},
    )

    assert completed is not None
    assert completed["status"] == "completed"
    assert completed["completion_percentage"] == 100
    assert completed["total_documents"] == 3


def test_generate_rag_database_creates_documents_with_sources(monkeypatch, tmp_path) -> None:
    collections = _make_collections()
    monkeypatch.setattr(rag_collection, "get_collection", lambda name: collections[name])
    monkeypatch.setattr(
        rag_service,
        "get_preprocess_document",
        lambda _: {
            "status": "completed",
            "rag_percent": 0.5,
            "updated_date": "2026-08-13T00:00:00+00:00",
        },
    )
    monkeypatch.setattr(rag_service, "_build_embedding_model", lambda model_name=None: DummyEmbeddingModel(model_name or "dummy"))

    qas_path = tmp_path / "qas.json"
    clinical_path = tmp_path / "clinical.json"

    qas_path.write_text(
        json.dumps(
            [
                {
                    "question": "Qual e a pergunta?",
                    "contexts": ["Contexto A", "Contexto B"],
                    "answer": "Resposta A",
                    "metadata": {"source": "pubmedqa", "url": "https://example.com/q1"},
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    clinical_path.write_text(
        json.dumps(
            [
                {
                    "name": "Protocolo 1.pdf",
                    "url": "https://example.com/p1.pdf",
                    "source": "FHEMIG",
                    "content_text": "Texto clinico longo. " * 40,
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    document = rag_service.generate_rag_database(
        "preprocess-1",
        qas_path,
        clinical_path,
        splitter_chunk_size=120,
        splitter_chunk_overlap=20,
    )

    assert document["status"] == "completed"
    assert document["qas_documents"] == 1
    assert document["clinical_protocol_documents"] > 1
    assert document["total_documents"] == document["qas_documents"] + document["clinical_protocol_documents"]
    assert document["embedding_model"] == rag_service.DEFAULT_RAG_EMBEDDING_MODEL

    stored_documents = list(collections[rag_collection.RAG_DOCUMENTS_COLLECTION].documents.values())
    assert len(stored_documents) == document["total_documents"]

    qas_document = next(item for item in stored_documents if item["source_type"] == "qas")
    assert qas_document["metadatas"]["source"] == {
        "source": "pubmedqa",
        "url": "https://example.com/q1",
    }
    assert qas_document["embedding"]

    clinical_documents = [
        item for item in stored_documents if item["source_type"] == "clinical_protocols"
    ]
    assert clinical_documents
    assert clinical_documents[0]["metadatas"]["source"] == {
        "name": "Protocolo 1.pdf",
        "url": "https://example.com/p1.pdf",
        "source": "FHEMIG",
    }
    assert all(item["batch_id"] == document["batch_id"] for item in stored_documents)
    assert all(len(item["embedding"]) == 4 for item in stored_documents)


def test_generate_rag_database_requires_completed_preprocess(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(rag_service, "get_preprocess_document", lambda _: None)

    with pytest.raises(HTTPException) as exc_info:
        rag_service.generate_rag_database(
            "missing-preprocess",
            tmp_path / "qas.json",
            tmp_path / "clinical.json",
        )

    assert exc_info.value.status_code == 404

    monkeypatch.setattr(rag_service, "get_preprocess_document", lambda _: {"status": "in_progress"})

    with pytest.raises(HTTPException) as exc_info:
        rag_service.generate_rag_database(
            "pending-preprocess",
            tmp_path / "qas.json",
            tmp_path / "clinical.json",
        )

    assert exc_info.value.status_code == 422


def test_generate_rag_database_marks_job_as_error_on_invalid_json(monkeypatch, tmp_path) -> None:
    collections = _make_collections()
    monkeypatch.setattr(rag_collection, "get_collection", lambda name: collections[name])
    monkeypatch.setattr(
        rag_service,
        "get_preprocess_document",
        lambda _: {
            "status": "completed",
            "rag_percent": 0.5,
            "updated_date": "2026-08-13T00:00:00+00:00",
        },
    )
    monkeypatch.setattr(rag_service, "_build_embedding_model", lambda model_name=None: DummyEmbeddingModel(model_name or "dummy"))

    qas_path = tmp_path / "qas.json"
    clinical_path = tmp_path / "clinical.json"
    qas_path.write_text("not-json", encoding="utf-8")
    clinical_path.write_text("[]", encoding="utf-8")

    document = rag_service.generate_rag_database("preprocess-1", qas_path, clinical_path)

    assert document["status"] == "error"
    assert document["error_message"]
