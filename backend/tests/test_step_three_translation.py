import json

import pytest
import transformers

from src.services.preprocess import step_three_translation


def test_get_translator_uses_seq2seq_components(monkeypatch):
    class FakeTokenizer:
        def __call__(self, text, return_tensors=None, truncation=None, padding=None):
            assert isinstance(text, list)
            assert text == ["hello"]
            return {"input_ids": [[1, 2]]}

        def batch_decode(self, generated_tokens, skip_special_tokens=True):
            return ["Olá, mundo!"]

    generate_kwargs = {}

    class FakeModel:
        def to(self, device):
            return self

        def eval(self):
            return self

        def generate(self, **kwargs):
            generate_kwargs.update(kwargs)
            return [[1, 2, 3]]

    monkeypatch.setattr(step_three_translation, "_translator", None)
    monkeypatch.setattr(transformers.AutoTokenizer, "from_pretrained", staticmethod(lambda *args, **kwargs: FakeTokenizer()))
    monkeypatch.setattr(transformers.AutoModelForSeq2SeqLM, "from_pretrained", staticmethod(lambda *args, **kwargs: FakeModel()))

    translator = step_three_translation._get_translator()

    result = translator("hello")
    assert result == [{"translation_text": "Olá, mundo!"}]
    assert generate_kwargs["max_new_tokens"] == 256
    assert generate_kwargs["num_beams"] == 1
    assert generate_kwargs["do_sample"] is False


def test_translate_creates_translated_files(tmp_path, monkeypatch):
    source_data = [
        {
            "question": "What is the role of mitochondria?",
            "contexts": [
                "Mitochondria are involved in energy production.",
                "They also play roles in apoptosis.",
            ],
            "answer": "Mitochondria produce ATP.",
            "metadata": {"source": "pubmedqa", "url": "https://example.com"},
        }
    ]

    input_file = tmp_path / "qas_train.json"
    input_file.write_text(json.dumps(source_data, ensure_ascii=False), encoding="utf-8")

    translated_texts = {
        "What is the role of mitochondria?": "Qual é o papel das mitocôndrias?",
        "Mitochondria are involved in energy production.": "As mitocôndrias estão envolvidas na produção de energia.",
        "They also play roles in apoptosis.": "Elas também desempenham papéis na apoptose.",
        "Mitochondria produce ATP.": "As mitocôndrias produzem ATP.",
    }

    calls = []

    class FakePipeline:
        def __call__(self, texts):
            batch = [texts] if isinstance(texts, str) else list(texts)
            calls.append(batch)
            return [{"translation_text": translated_texts[text]} for text in batch]

    monkeypatch.setattr(step_three_translation, "_get_translator", lambda: FakePipeline())
    monkeypatch.setattr(step_three_translation, "update_step_status", lambda *args, **kwargs: None)

    output_path = step_three_translation.translate("doc-123", input_file)

    assert calls == [
        [
            source_data[0]["question"],
            source_data[0]["contexts"][0],
            source_data[0]["contexts"][1],
            source_data[0]["answer"],
        ],
    ]
    assert output_path.exists()
    assert output_path.name == "qas_train_pt_br.json"

    saved = json.loads(output_path.read_text(encoding="utf-8"))
    assert saved[0]["question"] == translated_texts[source_data[0]["question"]]
    assert saved[0]["contexts"] == [
        translated_texts[source_data[0]["contexts"][0]],
        translated_texts[source_data[0]["contexts"][1]],
    ]
    assert saved[0]["answer"] == translated_texts[source_data[0]["answer"]]
    assert saved[0]["metadata"] == source_data[0]["metadata"]


def test_translate_preserves_non_string_contexts(tmp_path, monkeypatch):
    source_data = [
        {
            "question": "What is the role of mitochondria?",
            "contexts": [
                "Mitochondria are involved in energy production.",
                {"source": "keep-me"},
                42,
            ],
            "answer": "Mitochondria produce ATP.",
        }
    ]

    input_file = tmp_path / "qas_train.json"
    input_file.write_text(json.dumps(source_data, ensure_ascii=False), encoding="utf-8")

    translated_texts = {
        "What is the role of mitochondria?": "Qual é o papel das mitocôndrias?",
        "Mitochondria are involved in energy production.": "As mitocôndrias estão envolvidas na produção de energia.",
        "Mitochondria produce ATP.": "As mitocôndrias produzem ATP.",
    }

    class FakePipeline:
        def __call__(self, texts):
            batch = [texts] if isinstance(texts, str) else list(texts)
            return [{"translation_text": translated_texts[text]} for text in batch]

    monkeypatch.setattr(step_three_translation, "_get_translator", lambda: FakePipeline())
    monkeypatch.setattr(step_three_translation, "update_step_status", lambda *args, **kwargs: None)

    output_path = step_three_translation.translate("doc-123", input_file)

    saved = json.loads(output_path.read_text(encoding="utf-8"))
    assert saved[0]["contexts"] == [
        translated_texts[source_data[0]["contexts"][0]],
        {"source": "keep-me"},
        42,
    ]


def test_translate_updates_status_at_six_second_intervals(tmp_path, monkeypatch):
    source_data = []
    translated_texts = {}

    for index in range(17):
        question = f"Question {index}?"
        context = f"Context {index}."
        answer = f"Answer {index}."
        source_data.append(
            {
                "question": question,
                "contexts": [context],
                "answer": answer,
            }
        )
        translated_texts[question] = f"Pergunta {index}?"
        translated_texts[context] = f"Contexto {index}."
        translated_texts[answer] = f"Resposta {index}."

    input_file = tmp_path / "qas_train.json"
    input_file.write_text(json.dumps(source_data, ensure_ascii=False), encoding="utf-8")

    status_calls = []

    class FakePipeline:
        def __call__(self, texts):
            batch = [texts] if isinstance(texts, str) else list(texts)
            return [{"translation_text": translated_texts[text]} for text in batch]

    monkeypatch.setattr(step_three_translation, "_get_translator", lambda: FakePipeline())
    monkeypatch.setattr(
        step_three_translation,
        "update_step_status",
        lambda doc_id, step_name, status, error_message=None, completion_percentage=None: status_calls.append(
            (status, completion_percentage)
        ),
    )

    monotonic_values = iter([0.0, 5.0, 12.0])
    monkeypatch.setattr(step_three_translation.time, "monotonic", lambda: next(monotonic_values))

    output_path = step_three_translation.translate("doc-123", input_file)

    assert status_calls == [
        ("in_progress", 0),
        ("in_progress", 94.12),
        ("in_progress", 100.0),
        ("completed", 100),
    ]


def test_translate_uses_larger_translation_batches(tmp_path, monkeypatch):
    source_data = []
    translated_texts = {}

    for index in range(17):
        question = f"Question {index}?"
        context = f"Context {index}."
        answer = f"Answer {index}."
        source_data.append(
            {
                "question": question,
                "contexts": [context],
                "answer": answer,
            }
        )
        translated_texts[question] = f"Pergunta {index}?"
        translated_texts[context] = f"Contexto {index}."
        translated_texts[answer] = f"Resposta {index}."

    input_file = tmp_path / "qas_train.json"
    input_file.write_text(json.dumps(source_data, ensure_ascii=False), encoding="utf-8")

    batches = []

    class FakePipeline:
        def __call__(self, texts):
            batch = [texts] if isinstance(texts, str) else list(texts)
            batches.append(batch)
            return [{"translation_text": translated_texts[text]} for text in batch]

    monkeypatch.setattr(step_three_translation, "_get_translator", lambda: FakePipeline())
    monkeypatch.setattr(step_three_translation, "update_step_status", lambda *args, **kwargs: None)

    output_path = step_three_translation.translate("doc-123", input_file)

    assert len(batches) == 4  # 51 items / 16 batch size = 4 batches (rounded up)
    assert len(batches[0]) == 16
    assert len(batches[1]) == 16
    assert len(batches[2]) == 16
    assert len(batches[3]) == 3


def test_translate_raises_on_missing_file(tmp_path):
    missing_file = tmp_path / "missing.json"
    with pytest.raises(FileNotFoundError):
        step_three_translation.translate("doc-123", missing_file)


def test_translate_raises_on_invalid_json(tmp_path):
    invalid_file = tmp_path / "invalid.json"
    invalid_file.write_text("{ invalid json }", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        step_three_translation.translate("doc-123", invalid_file)


def test_translate_raises_on_non_list_json(tmp_path):
    invalid_format = tmp_path / "invalid_format.json"
    invalid_format.write_text(json.dumps({"question": "x"}), encoding="utf-8")

    with pytest.raises(ValueError):
        step_three_translation.translate("doc-123", invalid_format)
