import json
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.infra.database.collections import preprocess as preprocess_collection
from src.services import preprocess_data


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

    document = preprocess_collection.create_preprocess_document()

    assert document is not None
    assert "steps" in document
    assert "one_download_datasets" in document["steps"]
    assert "two_data_extraction" in document["steps"]
    assert document["steps"]["one_download_datasets"]["status"] == "pending"
    assert document["steps"]["two_data_extraction"]["status"] == "pending"
    assert document["steps"]["one_download_datasets"]["completion_percentage"] == 0
    assert document["steps"]["two_data_extraction"]["completion_percentage"] == 0
    assert document["steps"]["three_translating"]["completion_percentage"] == 0
    assert "results" in document
    assert "qas_train_path" in document["results"]
    assert "qas_train_pt_br_path" in document["results"]
    assert "clinical_protocols_rag_path" in document["results"]
    assert "qas_count" in document["results"]
    assert "clinical_protocols_count" in document["results"]
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
    
    # Marcar segundo e terceiro steps como completed
    updated = preprocess_collection.update_step_status(
        document["_id"], "two_data_extraction", "completed"
    )
    updated = preprocess_collection.update_step_status(
        document["_id"], "three_translating", "completed"
    )

    assert updated is not None
    assert updated["steps"]["one_download_datasets"]["status"] == "completed"
    assert updated["steps"]["two_data_extraction"]["status"] == "completed"
    assert updated["steps"]["three_translating"]["status"] == "completed"
    assert updated["status"] == "completed"


def test_update_preprocess_document_with_results(monkeypatch) -> None:
    fake_collection = FakeCollection()
    monkeypatch.setattr(preprocess_collection, "get_collection", lambda _: fake_collection)

    document = preprocess_collection.create_preprocess_document()
    
    results = {
        "qas_train_path": "datasets/preprocessed/qas/qas_train.json",
        "qas_train_pt_br_path": "datasets/preprocessed/qas/qas_train_pt_br.json",
        "clinical_protocols_rag_path": "datasets/preprocessed/clinical_protocols/clinical_protocols_rag.json",
        "qas_count": 150,
        "clinical_protocols_count": 120
    }
    
    updated = preprocess_collection.update_preprocess_document(
        document["_id"], results, 50
    )

    assert updated is not None
    assert updated["results"]["qas_train_path"] == "datasets/preprocessed/qas/qas_train.json"
    assert updated["results"]["qas_train_pt_br_path"] == "datasets/preprocessed/qas/qas_train_pt_br.json"
    assert updated["results"]["clinical_protocols_rag_path"] == "datasets/preprocessed/clinical_protocols/clinical_protocols_rag.json"
    assert updated["results"]["qas_count"] == 150
    assert updated["results"]["clinical_protocols_count"] == 120
    assert updated["completion_percentage"] == 50


def test_get_relative_path_is_relative_to_backend_root(monkeypatch, tmp_path) -> None:
    backend_root = tmp_path / "backend"
    source_dir = backend_root / "src" / "services"
    source_dir.mkdir(parents=True)
    target_path = backend_root / "datasets" / "preprocessed" / "clinical.json"

    monkeypatch.setattr(preprocess_data, "__file__", str(source_dir / "preprocess_data.py"))

    assert preprocess_data._get_relative_path(str(target_path)) == (
        os.path.join("datasets", "preprocessed", "clinical.json")
    )


def test_mark_preprocess_document_failed_stores_error_message(monkeypatch) -> None:
    fake_collection = FakeCollection()
    monkeypatch.setattr(preprocess_collection, "get_collection", lambda _: fake_collection)

    document = preprocess_collection.create_preprocess_document()
    updated = preprocess_collection.mark_preprocess_document_failed(document["_id"], "boom")

    assert updated is not None
    assert updated["status"] == "failed"
    assert updated["error_message"] == "boom"


def test_preprocess_data_background_runs_translation_for_qa_only(monkeypatch, tmp_path) -> None:
    calls: list[tuple[str, object]] = []

    def fake_update_preprocess_document(doc_id: str, results: dict, percentage: int) -> None:
        calls.append(("update_preprocess_document", (doc_id, results, percentage)))

    def fake_update_step_status(
        doc_id: str,
        step_name: str,
        status: str,
        error_message: str | None = None,
        completion_percentage: float | None = None,
    ) -> None:
        calls.append((
            "update_step_status",
            (doc_id, step_name, status, error_message, completion_percentage),
        ))

    def fake_download_datasets(doc_id: str) -> dict:
        calls.append(("download_datasets", doc_id))
        fake_update_step_status(doc_id, "one_download_datasets", "in_progress", None, 50)
        fake_update_step_status(doc_id, "one_download_datasets", "completed", None, 100)
        return {
            "qas": {"pubmedqa": str(tmp_path / "qa_repo")},
            "clinical_protocols": (tmp_path / "protocols.json", tmp_path / "pdfs"),
        }

    def fake_extract_data(
        doc_id: str,
        qas_paths: dict,
        clinical_protocols_paths: tuple,
    ) -> tuple[str, int, str, int]:
        train_qa = tmp_path / "qas_train.json"
        clinical_rag = tmp_path / "clinical_protocols_rag.json"
        for path in (train_qa, clinical_rag):
            path.write_text("[]", encoding="utf-8")
        return str(train_qa), 100, str(clinical_rag), 80

    def fake_translate(doc_id: str, qa_train_path: str) -> object:
        calls.append(("translate", doc_id, qa_train_path))
        return tmp_path / "qas_train_pt_br.json"

    monkeypatch.setattr(preprocess_data, "update_preprocess_document", fake_update_preprocess_document)
    monkeypatch.setattr(preprocess_data, "update_step_status", fake_update_step_status)
    monkeypatch.setattr(preprocess_data.step_one, "download_datasets", fake_download_datasets)
    monkeypatch.setattr(preprocess_data.step_two, "extract_data", fake_extract_data)
    monkeypatch.setattr(preprocess_data.step_three, "translate", fake_translate)

    preprocess_data.preprocess_data_background("doc-123")

    assert any(call[0] == "translate" for call in calls)
    assert any(
        call[0] == "update_step_status"
        and call[1][1] == "three_translating"
        and call[1][2] == "completed"
        and call[1][4] == 100
        for call in calls
    )
    assert any(
        call[0] == "update_step_status"
        and call[1][1] == "one_download_datasets"
        and call[1][4] == 100
        for call in calls
    )
    assert any(
        call[0] == "update_step_status"
        and call[1][1] == "two_data_extraction"
        and call[1][4] == 100
        for call in calls
    )


def test_preprocess_data_background_reuses_valid_preprocessed_cache(monkeypatch, tmp_path) -> None:
    calls: list[tuple[str, object]] = []

    qas_path = tmp_path / "qas_train.json"
    clinical_path = tmp_path / "clinical_protocols_rag.json"
    qas_path.write_text(json.dumps([{"question": "Pergunta", "answer": "Resposta"}]), encoding="utf-8")
    clinical_path.write_text(json.dumps([{"name": "protocolo", "content_text": "conteudo"}]), encoding="utf-8")

    monkeypatch.setattr(
        preprocess_data,
        "_get_preprocessed_paths",
        lambda: {"qas": str(qas_path), "clinical": str(clinical_path)},
    )

    def fake_update_preprocess_document(doc_id: str, results: dict, percentage: int) -> None:
        calls.append(("update_preprocess_document", (doc_id, results, percentage)))

    def fake_update_step_status(
        doc_id: str,
        step_name: str,
        status: str,
        error_message: str | None = None,
        completion_percentage: float | None = None,
    ) -> None:
        calls.append((
            "update_step_status",
            (doc_id, step_name, status, error_message, completion_percentage),
        ))

    def fake_download_datasets(doc_id: str) -> dict:
        return {
            "qas": {"pubmedqa": str(tmp_path / "qa_repo")},
            "clinical_protocols": (tmp_path / "protocols.json", tmp_path / "pdfs"),
        }

    def fake_extract_data(*args, **kwargs):
        raise AssertionError("extract_data should not run when cache is valid")

    def fake_translate(doc_id: str, qa_train_path: str) -> object:
        calls.append(("translate", doc_id, qa_train_path))
        return tmp_path / "qas_train_pt_br.json"

    monkeypatch.setattr(preprocess_data, "update_preprocess_document", fake_update_preprocess_document)
    monkeypatch.setattr(preprocess_data, "update_step_status", fake_update_step_status)
    monkeypatch.setattr(preprocess_data.step_one, "download_datasets", fake_download_datasets)
    monkeypatch.setattr(preprocess_data.step_two, "extract_data", fake_extract_data)
    monkeypatch.setattr(preprocess_data.step_three, "translate", fake_translate)

    preprocess_data.preprocess_data_background("doc-cache")

    result_updates = [call for call in calls if call[0] == "update_preprocess_document"]
    assert result_updates
    assert all("laudos_medicos_path" not in call[1][1] for call in result_updates)
    assert all("laudos_medicos_count" not in call[1][1] for call in result_updates)
    assert any(call[0] == "translate" for call in calls)
    assert any(
        call[0] == "update_step_status"
        and call[1][1] == "two_data_extraction"
        and call[1][2] == "completed"
        for call in calls
    )


def test_preprocess_data_background_rebuilds_when_cache_is_incomplete(monkeypatch, tmp_path) -> None:
    qas_path = tmp_path / "qas_train.json"
    qas_path.write_text(json.dumps([{"question": "Pergunta", "answer": "Resposta"}]), encoding="utf-8")
    clinical_path = tmp_path / "clinical_protocols_rag.json"

    monkeypatch.setattr(
        preprocess_data,
        "_get_preprocessed_paths",
        lambda: {"qas": str(qas_path), "clinical": str(clinical_path)},
    )

    def fake_download_datasets(doc_id: str) -> dict:
        return {
            "qas": {"pubmedqa": str(tmp_path / "qa_repo")},
            "clinical_protocols": (tmp_path / "protocols.json", tmp_path / "pdfs"),
        }

    def fake_extract_data(*args, **kwargs):
        extracted_qas = tmp_path / "qas_train.json"
        extracted_clinical = tmp_path / "clinical_protocols_rag.json"
        extracted_qas.write_text(json.dumps([{"question": "Nova", "answer": "Resposta"}]), encoding="utf-8")
        extracted_clinical.write_text(json.dumps([{"name": "novo", "content_text": "texto"}]), encoding="utf-8")
        return {
            "qas_train_path": str(extracted_qas),
            "qas_count": 1,
            "clinical_protocols_rag_path": str(extracted_clinical),
            "clinical_protocols_count": 1,
        }

    def fake_translate(doc_id: str, qa_train_path: str):
        return tmp_path / "qas_train_pt_br.json"

    monkeypatch.setattr(preprocess_data.step_one, "download_datasets", fake_download_datasets)
    monkeypatch.setattr(preprocess_data.step_two, "extract_data", fake_extract_data)
    monkeypatch.setattr(preprocess_data.step_three, "translate", fake_translate)
    monkeypatch.setattr(preprocess_data, "update_preprocess_document", lambda *args, **kwargs: None)
    monkeypatch.setattr(preprocess_data, "update_step_status", lambda *args, **kwargs: None)

    preprocess_data.preprocess_data_background("doc-rebuild")

    assert (tmp_path / "clinical_protocols_rag.json").exists()


def test_create_fine_tunning_document_initializes_pending_status(monkeypatch) -> None:
    class FakeCollection:
        def __init__(self) -> None:
            self.documents = {}

        def insert_one(self, document: dict) -> object:
            document_id = str(uuid.uuid4())
            document["_id"] = document_id
            self.documents[document_id] = document.copy()
            return type("Result", (), {"inserted_id": document_id})()

        def find_one(self, query: dict) -> dict | None:
            return self.documents.get(query.get("_id"))

    fake_collection = FakeCollection()

    from src.infra.database.collections import fine_tunning as fine_tunning_collection

    monkeypatch.setattr(fine_tunning_collection, "get_collection", lambda _: fake_collection)

    document = fine_tunning_collection.create_fine_tunning_document({"preprocess_id": "pre-123"})

    assert document["status"] == "pending"
