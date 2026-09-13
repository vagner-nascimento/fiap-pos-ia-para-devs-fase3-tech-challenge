import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from infra.database.collections import medical_record
class FakeCollection:
    def __init__(self, documents=None):
        self.documents = list(documents or [])
        self.inserted_documents = []
        self.created_indexes = []
        self.last_filter = None

    def count_documents(self, query):
        assert query == {}
        return len(self.documents)

    def insert_many(self, documents):
        self.inserted_documents.extend(documents)
        self.documents.extend(documents)

    def create_index(self, field, name):
        self.created_indexes.append((field, name))

    def find(self, query):
        self.last_filter = query
        return iter(self.documents)


class FakeDatabase:
    def __init__(self, collection_names):
        self.collection_names = collection_names

    def list_collection_names(self):
        return self.collection_names


def test_initialize_imports_medical_record_when_collection_is_empty(monkeypatch, tmp_path):
    dataset_path = tmp_path / "medical_records.json"
    dataset = [{"id_prontuario": "record-1", "identificacao": {"nome": "Ana Silva"}}]
    dataset_path.write_text(json.dumps(dataset), encoding="utf-8")
    collection = FakeCollection()

    monkeypatch.setattr(medical_record, "DATASET_PATH", dataset_path)
    monkeypatch.setattr(medical_record, "get_db", lambda: FakeDatabase(["medical_record"]))
    monkeypatch.setattr(medical_record, "get_collection", lambda _: collection)

    result = medical_record.initialize_medical_record_collection()

    assert result == {"collection": "medical_record", "imported": True, "count": 1}
    assert collection.inserted_documents == dataset
    assert collection.created_indexes == [("identificacao.nome", "medical_record_patient_name_idx")]


def test_initialize_skips_existing_medical_record_with_documents(monkeypatch, tmp_path):
    dataset_path = tmp_path / "medical_records.json"
    dataset_path.write_text("invalid", encoding="utf-8")
    collection = FakeCollection([{"id_prontuario": "existing"}])

    monkeypatch.setattr(medical_record, "DATASET_PATH", dataset_path)
    monkeypatch.setattr(medical_record, "get_db", lambda: FakeDatabase(["medical_record"]))
    monkeypatch.setattr(medical_record, "get_collection", lambda _: collection)

    result = medical_record.initialize_medical_record_collection()

    assert result == {"collection": "medical_record", "imported": False, "count": 0}
    assert collection.inserted_documents == []


def test_find_medical_records_by_patient_name_uses_exact_case_insensitive_filter(monkeypatch):
    collection = FakeCollection([{"id_prontuario": "record-1"}])
    monkeypatch.setattr(medical_record, "get_collection", lambda _: collection)

    result = medical_record.find_medical_records_by_patient_name("Ana Silva.+")

    assert result == [{"id_prontuario": "record-1"}]
    assert collection.last_filter == {
        "identificacao.nome": {
            "$regex": r"^Ana\ Silva\.\+$",
            "$options": "i",
        }
    }
