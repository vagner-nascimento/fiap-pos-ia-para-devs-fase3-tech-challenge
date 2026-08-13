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


class DummyEmbeddingModel:
    def __init__(self, model_name: str = "dummy") -> None:
        self.model_name = model_name

    def embed_documents(self, texts):
        return [[float(len(text)), 1.0, 2.0, 3.0] for text in texts]

    def embed_query(self, text):
        return [float(len(text)), 1.0, 2.0, 3.0]


def _make_collections() -> Dict[str, FakeCollection]:
    return {
        rag_collection.RAG_DOCUMENTS_COLLECTION: FakeCollection(),
    }


def test_insert_rag_documents_serializes_documents(monkeypatch) -> None:
    collections = _make_collections()
    monkeypatch.setattr(rag_collection, "get_collection", lambda name: collections[name])

    inserted = rag_collection.insert_rag_documents(
        [
            {
                "_id": "rag-1",
                "batch_id": "batch-1",
                "content": "conteudo",
                "metadatas": {"source": {"name": "Doc"}},
            }
        ]
    )

    assert len(inserted) == 1
    assert inserted[0]["_id"] == "rag-1"
    assert "created_date" in inserted[0]
    assert "updated_date" in inserted[0]


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
    monkeypatch.setattr(
        rag_service,
        "_build_embedding_model",
        lambda model_name=None: DummyEmbeddingModel(model_name or "dummy"),
    )

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
    assert document["preprocess_snapshot"]["_id"] == "preprocess-1"

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


def test_generate_rag_database_raises_on_invalid_json(monkeypatch, tmp_path) -> None:
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
    monkeypatch.setattr(
        rag_service,
        "_build_embedding_model",
        lambda model_name=None: DummyEmbeddingModel(model_name or "dummy"),
    )

    qas_path = tmp_path / "qas.json"
    clinical_path = tmp_path / "clinical.json"
    qas_path.write_text("not-json", encoding="utf-8")
    clinical_path.write_text("[]", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        rag_service.generate_rag_database("preprocess-1", qas_path, clinical_path)
