import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.services.preprocess import step_two_data_extraction as step_two


def test_extract_clinical_protocols_data_creates_rag_file(monkeypatch):
    base_tmp_dir = Path(__file__).resolve().parents[1] / ".tmp-tests"
    base_tmp_dir.mkdir(parents=True, exist_ok=True)

    tmp_root = base_tmp_dir / f"pytest-{uuid.uuid4().hex}"
    tmp_root.mkdir(parents=True, exist_ok=True)
    datasets_dir = tmp_root / "datasets"
    input_dir = tmp_root / "input"
    pdfs_dir = input_dir / "pdfs"
    pdfs_dir.mkdir(parents=True)

    protocols = [
        {"name": "protocol-1.pdf", "url": "https://example.com/protocol-1.pdf", "source": "Test"},
        {"name": "protocol-2.pdf", "url": "https://example.com/protocol-2.pdf", "source": "Test"},
    ]

    json_path = input_dir / "clinical_protocols.json"
    json_path.write_text(json.dumps(protocols), encoding="utf-8")

    for protocol in protocols:
        (pdfs_dir / protocol["name"]).write_bytes(b"%PDF-1.4")

    monkeypatch.setattr(step_two, "_datasets_dir", str(datasets_dir))
    monkeypatch.setattr(
        step_two,
        "_extract_text_from_pdf",
        lambda pdf_path: f"content for {Path(pdf_path).name}",
    )

    rag_path, count = step_two._extract_clinical_protocols_data("doc-123", (json_path, pdfs_dir))

    rag_file = Path(rag_path)

    assert rag_file.exists()
    assert count == 2

    rag_data = json.loads(rag_file.read_text(encoding="utf-8"))

    assert len(rag_data) == 2
    assert "content_text" in rag_data[0]
    assert "content_text" in rag_data[1]
    assert rag_data[0]["content_text"].startswith("content for")
    assert rag_data[1]["content_text"].startswith("content for")
