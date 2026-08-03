
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_translator: Optional[Any] = None

from infra.database.collections.preprocess import update_step_status


def _get_translator() -> Any:
    global _translator
    if _translator is None:
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        try:
            import torch
        except ImportError:
            torch = None

        if torch is not None and torch.cuda.is_available():
            device = 0
            backend = "GPU"
        else:
            device = -1
            backend = "CPU"

        print(f"Inicializando tradutor com {backend} (device={device})")

        tokenizer = AutoTokenizer.from_pretrained("Helsinki-NLP/opus-mt-tc-big-en-pt")
        model = AutoModelForSeq2SeqLM.from_pretrained("Helsinki-NLP/opus-mt-tc-big-en-pt")

        if torch is not None and hasattr(torch, "cuda"):
            model.to(device if device >= 0 else torch.device("cpu"))
            model.eval()

        def translator(text: str) -> List[Dict[str, str]]:
            inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
            if torch is not None and device >= 0 and torch.cuda.is_available():
                inputs = {k: v.to(device) for k, v in inputs.items()}

            with torch.no_grad():
                generated_tokens = model.generate(**inputs, max_new_tokens=512)

            translated_text = tokenizer.batch_decode(generated_tokens, skip_special_tokens=True)[0]
            return [{"translation_text": translated_text}]

        _translator = translator
    return _translator


def _translate_text(text: str) -> str:
    if not isinstance(text, str):
        return ""

    result = _get_translator()(text)
    print(f"Translating: {text} -> {result[0].get('translation_text', '')}")
    return result[0].get("translation_text", "")


def _translate_item(item: Dict[str, Any]) -> Dict[str, Any]:
    translated_item = dict(item)

    if "question" in translated_item:
        translated_item["question"] = _translate_text(translated_item["question"])

    if "contexts" in translated_item and isinstance(translated_item["contexts"], list):
        translated_item["contexts"] = [
            _translate_text(context)
            for context in translated_item["contexts"]
            if isinstance(context, str)
        ]

    if "answer" in translated_item:
        translated_item["answer"] = _translate_text(translated_item["answer"])

    return translated_item


def translate(
    doc_id: str,
    QA_PATHs: Tuple[Path, Path],
) -> Tuple[Path, Path]:
    """Translate two QA JSON files from English to Portuguese (pt-BR). Returns the paths of the translated files."""
    output_paths: List[Path] = []

    loaded_data: List[List[Dict[str, Any]]] = []
    for input_path in QA_PATHs:
        path = Path(input_path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {path}")

        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)

        if not isinstance(data, list):
            raise ValueError(f"Formato inválido para {path}: esperado uma lista de objetos JSON.")

        loaded_data.append(data)

    total_items = sum(len(items) for items in loaded_data)
    update_step_status(doc_id, "three_translating", "in_progress", completion_percentage=0)

    processed_items = 0
    for index, data in enumerate(loaded_data):
        input_path = Path(QA_PATHs[index]).resolve()
        translated_data: List[Dict[str, Any]] = []

        for item in data:
            translated_data.append(_translate_item(item))
            processed_items += 1
            if total_items > 0:
                update_step_status(
                    doc_id,
                    "three_translating",
                    "in_progress",
                    completion_percentage=min(100.0, round(processed_items / total_items * 100.0, 2)),
                )

        output_path = input_path.with_name(f"{input_path.stem}_pt_br{input_path.suffix}")
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(translated_data, handle, ensure_ascii=False, indent=2)

        output_paths.append(output_path)

    update_step_status(doc_id, "three_translating", "completed", completion_percentage=100)

    return tuple(output_paths)
