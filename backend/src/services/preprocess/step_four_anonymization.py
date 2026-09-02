import json
from pathlib import Path
from typing import Any, Dict, List

from infra.database.collections.preprocess import update_step_status

OUTPUT_PATH = (
    Path(__file__).resolve().parents[3]
    / "datasets"
    / "preprocessed"
    / "medical_reports"
    / "anonymizated_medical_reports.json"
)


def anonymization(doc_id: str, medical_reports_path: Path) -> Path:
    input_path = Path(medical_reports_path).resolve()

    if not input_path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {input_path}")

    with input_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, list):
        raise ValueError(f"Formato inválido para {input_path}: esperado uma lista de objetos JSON.")

    output_path = OUTPUT_PATH
    output_path.parent.mkdir(parents=True, exist_ok=True)
    total_items = len(data)
    anonymized_data: List[Dict[str, Any]] = []

    update_step_status(doc_id, "four_anonymization", "in_progress", completion_percentage=0)

    for index, report in enumerate(data, start=1):
        if not isinstance(report, dict):
            raise ValueError(f"Registro inválido na posição {index}: esperado um objeto JSON.")

        anonymized_report = dict(report)
        header = report.get("cabecalho_identificador")
        if isinstance(header, dict):
            anonymized_header = dict(header)
            patient_name = anonymized_header.get("nome_paciente")
            requesting_physician = anonymized_header.get("medico_solicitante")
            if isinstance(patient_name, str):
                anonymized_header["nome_paciente"] = "*" * len(patient_name)
            if isinstance(requesting_physician, str):
                anonymized_header["medico_solicitante"] = "Dr(a). " + "*" * len(requesting_physician)
            anonymized_report["cabecalho_identificador"] = anonymized_header

        anonymized_data.append(anonymized_report)
        completion_percentage = 100.0 if total_items == 0 else round(index / total_items * 100.0, 2)
        update_step_status(
            doc_id,
            "four_anonymization",
            "in_progress",
            completion_percentage=completion_percentage,
        )

    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(anonymized_data, handle, ensure_ascii=False, indent=2)

    update_step_status(doc_id, "four_anonymization", "completed", completion_percentage=100)
    return output_path
