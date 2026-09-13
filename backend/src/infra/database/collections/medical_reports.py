import copy
import json
import re
from pathlib import Path
from typing import Any, Dict, Final, List

from infra.database.mongodb import get_collection, get_db


MEDICAL_REPORTS_COLLECTION: Final[str] = "medical_reports"
PATIENT_NAME_FIELD: Final[str] = "cabecalho_identificador.nome_paciente"
DATASET_PATH: Final[Path] = (
    Path(__file__).resolve().parents[4]
    / "datasets"
    / "files"
    / "laudos_medicos"
    / "dataset_laudos_medicos.json"
)


def _serialize_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _serialize_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    if hasattr(value, "__str__") and value.__class__.__name__ == "ObjectId":
        return str(value)
    return value


def _read_dataset(dataset_path: Path | None = None) -> List[Dict[str, Any]]:
    dataset_path = dataset_path or DATASET_PATH
    with dataset_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
        raise ValueError("O dataset de laudos médicos deve ser uma lista de objetos JSON.")

    return data


def initialize_medical_reports_collection() -> Dict[str, Any]:
    """Importa os laudos somente quando a collection não possui documentos."""
    database = get_db()
    collection = get_collection(MEDICAL_REPORTS_COLLECTION)
    collection_exists = MEDICAL_REPORTS_COLLECTION in database.list_collection_names()

    if collection_exists and collection.count_documents({}) > 0:
        return {"collection": MEDICAL_REPORTS_COLLECTION, "imported": False, "count": 0}

    documents = _read_dataset()
    if documents:
        collection.insert_many(copy.deepcopy(documents))
    collection.create_index(PATIENT_NAME_FIELD, name="patient_name_idx")
    return {
        "collection": MEDICAL_REPORTS_COLLECTION,
        "imported": True,
        "count": len(documents),
    }


def find_medical_reports_by_patient_name(patient_name: str) -> List[Dict[str, Any]]:
    """Busca laudos cujo nome completo coincide, ignorando maiúsculas/minúsculas."""
    escaped_name = re.escape(patient_name)
    cursor = get_collection(MEDICAL_REPORTS_COLLECTION).find(
        {
            PATIENT_NAME_FIELD: {
                "$regex": f"^{escaped_name}$",
                "$options": "i",
            }
        }
    )
    return [_serialize_value(copy.deepcopy(document)) for document in cursor]
