import json
from pathlib import Path

import pytest
import transformers

from src.services.preprocess import step_three_translation


def test_get_translator_uses_seq2seq_components(monkeypatch):
    class FakeTokenizer:
        def __call__(self, text, return_tensors=None, truncation=None, max_length=None):
            return {"input_ids": [1, 2]}

        def batch_decode(self, generated_tokens, skip_special_tokens=True):
            return ["Olá, mundo!"]

    class FakeModel:
        def to(self, device):
            return self

        def eval(self):
            return self

        def generate(self, **kwargs):
            return [[1, 2, 3]]

    monkeypatch.setattr(step_three_translation, "_translator", None)
    monkeypatch.setattr(transformers, "pipeline", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("pipeline não deveria ser usado")))
    monkeypatch.setattr(transformers.AutoTokenizer, "from_pretrained", staticmethod(lambda *args, **kwargs: FakeTokenizer()))
    monkeypatch.setattr(transformers.AutoModelForSeq2SeqLM, "from_pretrained", staticmethod(lambda *args, **kwargs: FakeModel()))

    translator = step_three_translation._get_translator()

    result = translator("hello")
    assert result == [{"translation_text": "Olá, mundo!"}]


def test_translate_creates_translated_files(tmp_path, monkeypatch):
    source_data = [
        {
            "question": "What is the role of mitochondria?",
            "contexts": [
                "Mitochondria are involved in energy production.",
                "They also play roles in apoptosis."
            ],
            "answer": "Mitochondria produce ATP.",
            "metadata": {"source": "pubmedqa", "url": "https://example.com"}
        }
    ]

    input_file = tmp_path / "qa.json"
    input_file.write_text(json.dumps(source_data, ensure_ascii=False), encoding="utf-8")

    translated_texts = {
        "What is the role of mitochondria?": "Qual é o papel das mitocôndrias?",
        "Mitochondria are involved in energy production.": "As mitocôndrias estão envolvidas na produção de energia.",
        "They also play roles in apoptosis.": "Elas também desempenham papéis na apoptose.",
        "Mitochondria produce ATP.": "As mitocôndrias produzem ATP."
    }

    class FakePipeline:
        def __call__(self, text):
            return [{"translation_text": translated_texts[text]}]

    monkeypatch.setattr(step_three_translation, "_get_translator", lambda: FakePipeline())

    output_paths = step_three_translation.translate("doc-123", (input_file, input_file))

    assert len(output_paths) == 2
    for output_path in output_paths:
        assert output_path.exists()
        assert output_path.name == "qa_pt_br.json"

        saved = json.loads(output_path.read_text(encoding="utf-8"))
        assert saved[0]["question"] == translated_texts[source_data[0]["question"]]
        assert saved[0]["contexts"] == [
            translated_texts[source_data[0]["contexts"][0]],
            translated_texts[source_data[0]["contexts"][1]],
        ]
        assert saved[0]["answer"] == translated_texts[source_data[0]["answer"]]
        assert saved[0]["metadata"] == source_data[0]["metadata"]


def test_translate_raises_on_missing_file(tmp_path):
    missing_file = tmp_path / "missing.json"
    with pytest.raises(FileNotFoundError):
        step_three_translation.translate("doc-123", (missing_file, missing_file))


def test_translate_raises_on_invalid_json(tmp_path):
    invalid_file = tmp_path / "invalid.json"
    invalid_file.write_text("{ invalid json }", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        step_three_translation.translate("doc-123", (invalid_file, invalid_file))


def test_translate_raises_on_non_list_json(tmp_path):
    invalid_format = tmp_path / "invalid_format.json"
    invalid_format.write_text(json.dumps({"question": "x"}), encoding="utf-8")

    with pytest.raises(ValueError):
        step_three_translation.translate("doc-123", (invalid_format, invalid_format))
