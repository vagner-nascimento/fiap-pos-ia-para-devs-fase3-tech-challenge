import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.services.preprocess import step_four_anonymization as step_four


def test_anonymization_masks_report_identity_and_reports_progress(monkeypatch, tmp_path) -> None:
    source_path = tmp_path / "files" / "laudos_medicos" / "dataset.json"
    source_path.parent.mkdir(parents=True)
    source_path.write_text(
        json.dumps(
            [
                {
                    "id_laudo": "report-1",
                    "cabecalho_identificador": {
                        "nome_paciente": "Ana Silva",
                        "medico_solicitante": "Dr(a). Bruno Costa",
                        "crm_solicitante": "123-RJ",
                    },
                    "corpo_tecnico": {"tipo_exame": "EEG"},
                }
            ]
        ),
        encoding="utf-8",
    )
    status_calls = []
    monkeypatch.setattr(
        step_four,
        "update_step_status",
        lambda *args, **kwargs: status_calls.append((args, kwargs)),
    )
    output_path = tmp_path / "preprocessed" / "medical_reports" / "anonymizated_medical_reports.json"
    monkeypatch.setattr(step_four, "OUTPUT_PATH", output_path)

    generated_path = step_four.anonymization("doc-1", source_path)
    result = json.loads(generated_path.read_text(encoding="utf-8"))
    header = result[0]["cabecalho_identificador"]

    assert generated_path == output_path
    assert header["nome_paciente"] == "*********"
    assert header["medico_solicitante"] == "Dr(a). ******************"
    assert header["crm_solicitante"] == "123-RJ"
    assert result[0]["corpo_tecnico"] == {"tipo_exame": "EEG"}
    assert status_calls[-1][0] == ("doc-1", "four_anonymization", "completed")
    assert status_calls[-1][1]["completion_percentage"] == 100
