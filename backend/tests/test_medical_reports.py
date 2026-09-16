import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from infra.database.collections import medical_reports


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
        if not self.documents:
            return iter([])

        if "id_laudo" in query and isinstance(query["id_laudo"], dict) and "$in" in query["id_laudo"]:
            ids = set(query["id_laudo"]["$in"])
            return iter([doc for doc in self.documents if doc.get("id_laudo") in ids])

        patient_filter = query.get("cabecalho_identificador.nome_paciente")
        if isinstance(patient_filter, dict) and "$regex" in patient_filter:
            regex = patient_filter["$regex"]
            flags = re.IGNORECASE if patient_filter.get("$options") == "i" else 0
            compiled = re.compile(regex, flags)
            filtered = [
                doc for doc in self.documents
                if isinstance(doc, dict)
                and isinstance(doc.get("cabecalho_identificador", {}).get("nome_paciente"), str)
                and compiled.fullmatch(doc["cabecalho_identificador"]["nome_paciente"]) is not None
            ]
            if filtered:
                return iter(filtered)
            if any(isinstance(doc, dict) and "cabecalho_identificador" not in doc for doc in self.documents):
                return iter(self.documents)
            return iter([])

        return iter(self.documents)


class FakeDatabase:
    def __init__(self, collection_names):
        self.collection_names = collection_names

    def list_collection_names(self):
        return self.collection_names


def test_initialize_imports_dataset_when_collection_does_not_exist(monkeypatch, tmp_path):
    dataset_path = tmp_path / "dataset.json"
    dataset = [{"id_laudo": "report-1", "cabecalho_identificador": {"nome_paciente": "Ana"}}]
    dataset_path.write_text(json.dumps(dataset), encoding="utf-8")
    collection = FakeCollection()

    monkeypatch.setattr(medical_reports, "DATASET_PATH", dataset_path)
    monkeypatch.setattr(medical_reports, "get_db", lambda: FakeDatabase([]))
    monkeypatch.setattr(medical_reports, "get_collection", lambda _: collection)

    result = medical_reports.initialize_medical_reports_collection()

    assert result == {"collection": "medical_reports", "imported": True, "count": 1}
    assert collection.inserted_documents == dataset
    assert collection.created_indexes == [("cabecalho_identificador.nome_paciente", "patient_name_idx")]


def test_initialize_skips_existing_collection_with_documents(monkeypatch, tmp_path):
    dataset_path = tmp_path / "dataset.json"
    dataset_path.write_text("invalid", encoding="utf-8")
    collection = FakeCollection([{"id_laudo": "existing"}])

    monkeypatch.setattr(medical_reports, "DATASET_PATH", dataset_path)
    monkeypatch.setattr(
        medical_reports,
        "get_db",
        lambda: FakeDatabase(["medical_reports"]),
    )
    monkeypatch.setattr(medical_reports, "get_collection", lambda _: collection)

    result = medical_reports.initialize_medical_reports_collection()

    assert result == {"collection": "medical_reports", "imported": False, "count": 0}
    assert collection.inserted_documents == []


def test_find_by_patient_name_uses_exact_case_insensitive_filter(monkeypatch):
    collection = FakeCollection([{"id_laudo": "report-1"}])
    monkeypatch.setattr(medical_reports, "get_collection", lambda _: collection)

    result = medical_reports.find_medical_reports_by_patient_name("Ana Silva.+")

    assert result == [{"id_laudo": "report-1"}]
    assert collection.last_filter == {
        "cabecalho_identificador.nome_paciente": {
            "$regex": r"^Ana\ Silva\.\+$",
            "$options": "i",
        }
    }


def test_find_by_patient_name_falls_back_to_raw_dataset_by_id(monkeypatch, tmp_path):
    collection = FakeCollection([])
    raw_path = tmp_path / "laudos_medicos.json"
    raw_path.write_text(
        json.dumps([
            {
                "id_laudo": "report-42",
                "cabecalho_identificador": {"nome_paciente": "Maria Santos Almeida"},
            }
        ]),
        encoding="utf-8",
    )
    monkeypatch.setattr(medical_reports, "RAW_LAUDOS_PATH", raw_path)
    monkeypatch.setattr(medical_reports, "get_collection", lambda _: collection)

    collection.documents = [{"id_laudo": "report-42", "cabecalho_identificador": {"nome_paciente": "****************"}}]
    result = medical_reports.find_medical_reports_by_patient_name("Maria Santos Almeida")

    assert result == [{"id_laudo": "report-42", "cabecalho_identificador": {"nome_paciente": "****************"}}]
    assert collection.last_filter == {"id_laudo": {"$in": ["report-42"]}}
