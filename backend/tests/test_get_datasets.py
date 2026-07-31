from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "datasets"))

import get_datasets


class DummyResponse:
    def __init__(self, content: bytes):
        self.content = content

    def raise_for_status(self):
        return None


def test_download_clinical_protocol_files_writes_to_target_dir(tmp_path, monkeypatch):
    class DummyRequests:
        def get(self, url, timeout=30):
            assert url == "https://example.com/protocolo.pdf"
            return DummyResponse(b"%PDF-1.4")

    monkeypatch.setattr(get_datasets, "requests", DummyRequests())

    protocols = [{"name": "protocolo.pdf", "url": "https://example.com/protocolo.pdf", "source": "Test"}]

    downloaded = get_datasets.download_clinical_protocol_files(protocols, tmp_path)

    assert len(downloaded) == 1
    downloaded_path = Path(downloaded[0])
    assert downloaded_path.exists()
    assert downloaded_path.read_bytes() == b"%PDF-1.4"
