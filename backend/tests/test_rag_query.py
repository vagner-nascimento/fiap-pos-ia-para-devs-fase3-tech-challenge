import sys
from pathlib import Path
from typing import Dict, List

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from infra.database.collections import rag_database as rag_collection
from server import create_app
from services import rag_database as rag_service


class FakeCollection:
    def __init__(self, documents: List[dict] = None) -> None:
        self.documents = {doc["_id"]: doc.copy() for doc in (documents or [])}

    def insert_one(self, document: dict) -> None:
        self.documents[document["_id"]] = document.copy()

    def insert_many(self, documents: List[dict]) -> None:
        for document in documents:
            self.insert_one(document)

    def find(self, filter_query: dict = None, projection: dict = None):
        filter_query = filter_query or {}
        results = []
        for doc in self.documents.values():
            match = True
            for k, v in filter_query.items():
                if doc.get(k) != v:
                    match = False
                    break
            if match:
                results.append(doc.copy())
        return results


class DummyEmbeddingModel:
    def __init__(self, model_name: str = "dummy") -> None:
        self.model_name = model_name

    def embed_documents(self, texts):
        return [[float(len(text)), 1.0, 0.0, 0.0] for text in texts]

    def embed_query(self, text):
        return [float(len(text)), 1.0, 0.0, 0.0]


def _make_sample_documents() -> List[dict]:
    return [
        {
            "_id": "doc-1",
            "batch_id": "batch-1",
            "preprocess_id": "prep-1",
            "dataset": "qas",
            "source_type": "qas",
            "content": "Tratamento para hipertensão arterial",
            "embedding": [35.0, 1.0, 0.0, 0.0],
            "metadatas": {"source": {"name": "PubmedQA"}},
        },
        {
            "_id": "doc-2",
            "batch_id": "batch-1",
            "preprocess_id": "prep-1",
            "dataset": "clinical_protocols",
            "source_type": "clinical_protocols",
            "content": "Protocolo de diabetes mellitus tipo 2",
            "embedding": [36.0, 1.0, 0.0, 0.0],
            "chunk_index": 1,
            "chunk_total": 2,
            "metadatas": {"source": {"name": "MS Protocol"}},
        },
        {
            "_id": "doc-3",
            "batch_id": "batch-2",
            "preprocess_id": "prep-2",
            "dataset": "qas",
            "source_type": "qas",
            "content": "Sintomas do coronavírus COVID-19",
            "embedding": [32.0, 1.0, 0.0, 0.0],
            "metadatas": {"source": {"name": "MedQuAD"}},
        },
    ]


def test_cosine_similarity_edge_cases() -> None:
    # Identical vectors
    score = rag_service._cosine_similarity([1.0, 0.0], [1.0, 0.0])
    assert pytest.approx(score, 0.0001) == 1.0

    # Orthogonal vectors
    score_ortho = rag_service._cosine_similarity([1.0, 0.0], [0.0, 1.0])
    assert pytest.approx(score_ortho, 0.0001) == 0.0

    # Zero vector
    assert rag_service._cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0

    # Dimension mismatch
    assert rag_service._cosine_similarity([1.0, 0.0], [1.0, 0.0, 0.0]) == 0.0


def test_query_rag_documents_service(monkeypatch) -> None:
    fake_coll = FakeCollection(_make_sample_documents())
    monkeypatch.setattr(rag_collection, "get_collection", lambda name: fake_coll)
    monkeypatch.setattr(
        rag_service,
        "_build_embedding_model",
        lambda model_name=None: DummyEmbeddingModel(model_name or "dummy"),
    )

    result = rag_service.query_rag_documents(
        query="Tratamento para hipertensao arterial",
        top_k=2,
    )

    assert result["query"] == "Tratamento para hipertensao arterial"
    assert result["total_results"] == 2
    assert len(result["documents"]) == 2
    assert result["documents"][0]["similarity_score"] >= result["documents"][1]["similarity_score"]


def test_query_rag_documents_filter_preprocess_id(monkeypatch) -> None:
    fake_coll = FakeCollection(_make_sample_documents())
    monkeypatch.setattr(rag_collection, "get_collection", lambda name: fake_coll)
    monkeypatch.setattr(
        rag_service,
        "_build_embedding_model",
        lambda model_name=None: DummyEmbeddingModel(model_name or "dummy"),
    )

    result = rag_service.query_rag_documents(
        query="coronavírus",
        preprocess_id="prep-2",
    )

    assert result["total_results"] == 1
    assert result["documents"][0]["id"] == "doc-3"
    assert result["documents"][0]["preprocess_id"] == "prep-2"


def test_query_rag_documents_empty_query_raises() -> None:
    with pytest.raises(HTTPException) as exc_info:
        rag_service.query_rag_documents("   ")
    assert exc_info.value.status_code == 400


def test_query_rag_endpoint_via_client(monkeypatch) -> None:
    fake_coll = FakeCollection(_make_sample_documents())
    monkeypatch.setattr(rag_collection, "get_collection", lambda name: fake_coll)
    monkeypatch.setattr(
        rag_service,
        "_build_embedding_model",
        lambda model_name=None: DummyEmbeddingModel(model_name or "dummy"),
    )
    monkeypatch.setattr("server.test_connection", lambda: True)

    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/rag-database/query",
        json={"query": "hipertensão", "top_k": 3},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "hipertensão"
    assert data["total_results"] == 3
    assert len(data["documents"]) == 3
    assert "similarity_score" in data["documents"][0]
    assert "content" in data["documents"][0]
