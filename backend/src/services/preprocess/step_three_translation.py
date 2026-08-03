
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_translator: Optional[Any] = None


def _get_translator() -> Any:
    global _translator
    if _translator is None:
        from transformers import pipeline

        _translator = pipeline("translation", model="Helsinki-NLP/opus-mt-tc-big-en-pt")
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


def translate(QA_PATHs: Tuple[Path, Path]) -> Tuple[Path, Path]:
    """Translate two QA JSON files from English to Portuguese (pt-BR). Returns the paths of the translated files."""
    output_paths: List[Path] = []

    for input_path in QA_PATHs:
        path = Path(input_path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {path}")

        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)

        if not isinstance(data, list):
            raise ValueError(f"Formato inválido para {path}: esperado uma lista de objetos JSON.")

        translated_data = [_translate_item(item) for item in data]

        output_path = path.with_name(f"{path.stem}_pt_br{path.suffix}")
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(translated_data, handle, ensure_ascii=False, indent=2)

        output_paths.append(output_path)

    return tuple(output_paths)
