import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.infra.database.collections import preprocess as preprocess_collection


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
                # Handle nested keys like "steps.one_download_datasets.status"
                if "." in key:
                    keys = key.split(".")
                    current = document
                    for k in keys[:-1]:
                        if k not in current:
                            current[k] = {}
                        current = current[k]
                    current[keys[-1]] = value
                else:
                    document[key] = value
        if "$unset" in update:
            for key in update["$unset"]:
                if "." in key:
                    keys = key.split(".")
                    current = document
                    for k in keys[:-1]:
                        if k in current:
                            current = current[k]
                        else:
                            break
                    else:
                        current.pop(keys[-1], None)
                else:
                    document.pop(key, None)
        return type("Result", (), {"matched_count": 1})()


def test_create_preprocess_document_initializes_new_structure(monkeypatch) -> None:
    fake_collection = FakeCollection()
    monkeypatch.setattr(preprocess_collection, "get_collection", lambda _: fake_collection)

    document = preprocess_collection.create_preprocess_document(rag_percent=0.7)

    assert document is not None
    assert "rag_percent" in document
    assert document["rag_percent"] == 0.7
    assert "steps" in document
    assert "one_download_datasets" in document["steps"]
    assert "step_two_data_extraction" in document["steps"]
    assert document["steps"]["one_download_datasets"]["status"] == "pending"
    assert document["steps"]["step_two_data_extraction"]["status"] == "pending"
    assert "results" in document
    assert "QAs" in document["results"]
    assert "clinical_protocols" in document["results"]
    assert document["status"] == "created"
    assert document["completion_percentage"] == 0


def test_update_step_status_updates_individual_step(monkeypatch) -> None:
    fake_collection = FakeCollection()
    monkeypatch.setattr(preprocess_collection, "get_collection", lambda _: fake_collection)

    document = preprocess_collection.create_preprocess_document()
    updated = preprocess_collection.update_step_status(
        document["_id"], "one_download_datasets", "in_progress"
    )

    assert updated is not None
    assert updated["steps"]["one_download_datasets"]["status"] == "in_progress"
    assert updated["status"] == "in_progress"


def test_update_step_status_with_error(monkeypatch) -> None:
    fake_collection = FakeCollection()
    monkeypatch.setattr(preprocess_collection, "get_collection", lambda _: fake_collection)

    document = preprocess_collection.create_preprocess_document()
    updated = preprocess_collection.update_step_status(
        document["_id"], "one_download_datasets", "error", "Connection failed"
    )

    assert updated is not None
    assert updated["steps"]["one_download_datasets"]["status"] == "error"
    assert updated["steps"]["one_download_datasets"]["error_message"] == "Connection failed"
    assert updated["status"] == "error"
    assert updated["error_message"] == "Connection failed"


def test_update_step_status_completed_updates_overall_status(monkeypatch) -> None:
    fake_collection = FakeCollection()
    monkeypatch.setattr(preprocess_collection, "get_collection", lambda _: fake_collection)

    document = preprocess_collection.create_preprocess_document()
    
    # Marcar primeiro step como completed
    preprocess_collection.update_step_status(
        document["_id"], "one_download_datasets", "completed"
    )
    
    # Marcar segundo step como completed
    updated = preprocess_collection.update_step_status(
        document["_id"], "step_two_data_extraction", "completed"
    )

    assert updated is not None
    assert updated["steps"]["one_download_datasets"]["status"] == "completed"
    assert updated["steps"]["step_two_data_extraction"]["status"] == "completed"
    assert updated["status"] == "completed"


def test_update_preprocess_document_with_results(monkeypatch) -> None:
    fake_collection = FakeCollection()
    monkeypatch.setattr(preprocess_collection, "get_collection", lambda _: fake_collection)

    document = preprocess_collection.create_preprocess_document()
    
    results = {
        "QAs": {
            "train_data": 100,
            "rag_data": 50
        },
        "clinical_protocols": {
            "train_data": 80,
            "rag_data": 40
        }
    }
    
    updated = preprocess_collection.update_preprocess_document(
        document["_id"], results, 50
    )

    assert updated is not None
    assert updated["results"]["QAs"]["train_data"] == 100
    assert updated["results"]["QAs"]["rag_data"] == 50
    assert updated["results"]["clinical_protocols"]["train_data"] == 80
    assert updated["results"]["clinical_protocols"]["rag_data"] == 40
    assert updated["completion_percentage"] == 50


def test_mark_preprocess_document_failed_stores_error_message(monkeypatch) -> None:
    fake_collection = FakeCollection()
    monkeypatch.setattr(preprocess_collection, "get_collection", lambda _: fake_collection)

    document = preprocess_collection.create_preprocess_document()
    updated = preprocess_collection.mark_preprocess_document_failed(document["_id"], "boom")

    assert updated is not None
    assert updated["status"] == "failed"
    assert updated["error_message"] == "boom"
