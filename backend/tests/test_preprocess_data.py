import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.infra.database.collections import preprocess as preprocess_collection
from src.services.preprocess_data import split_dataset_for_rag


class FakeCollection:
    def __init__(self) -> None:
        self.documents = {}

    def insert_one(self, document: dict) -> None:
        self.documents[document["_id"]] = document.copy()

    def find_one(self, query: dict) -> dict | None:
        return self.documents.get(query.get("_id"))

    def update_one(self, query: dict, update: dict) -> object:
        document = self.documents[query["_id"]]
        if "$set" in update:
            for key, value in update["$set"].items():
                document[key] = value
        if "$unset" in update:
            for key in update["$unset"]:
                document.pop(key, None)
        return type("Result", (), {"matched_count": 1})()


def test_split_dataset_for_rag_uses_requested_percent() -> None:
    data = list(range(10))

    rag_data, train_data = split_dataset_for_rag(data, 0.5)

    assert rag_data == list(range(5))
    assert train_data == list(range(5, 10))


def test_mark_preprocess_document_failed_stores_error_message(monkeypatch) -> None:
    fake_collection = FakeCollection()
    monkeypatch.setattr(preprocess_collection, "get_collection", lambda _: fake_collection)

    document = preprocess_collection.create_preprocess_document()
    updated = preprocess_collection.mark_preprocess_document_failed(document["_id"], "boom")

    assert updated is not None
    assert updated["status"] == "failed"
    assert updated["error_message"] == "boom"


def test_update_preprocess_document_clears_error_message_on_success(monkeypatch) -> None:
    fake_collection = FakeCollection()
    monkeypatch.setattr(preprocess_collection, "get_collection", lambda _: fake_collection)

    document = preprocess_collection.create_preprocess_document()
    preprocess_collection.mark_preprocess_document_failed(document["_id"], "boom")

    updated = preprocess_collection.update_preprocess_document(document["_id"], 3, 2, 100)

    assert updated is not None
    assert updated["status"] == "completed"
    assert "error_message" not in updated
