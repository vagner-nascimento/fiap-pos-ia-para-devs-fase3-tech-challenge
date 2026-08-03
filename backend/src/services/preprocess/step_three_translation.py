
import json
import time
from contextlib import nullcontext
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

_translator: Optional[Any] = None

from infra.database.collections.preprocess import update_step_status

_TRANSLATION_BATCH_SIZE = 8
_STATUS_UPDATE_INTERVAL_SECONDS = 6.0
_MAX_NEW_TOKENS = 256


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

        if hasattr(model, "generation_config") and hasattr(model.generation_config, "max_length"):
            model.generation_config.max_length = None

        def translator(texts: Union[str, Sequence[str]]) -> List[Dict[str, str]]:
            batch_texts = [texts] if isinstance(texts, str) else list(texts)
            if not batch_texts:
                return []

            inputs = tokenizer(batch_texts, return_tensors="pt", truncation=True, padding=True)
            if torch is not None and device >= 0 and torch.cuda.is_available():
                inputs = {k: v.to(device) for k, v in inputs.items()}

            inference_context = torch.inference_mode() if torch is not None else nullcontext()
            with inference_context:
                generated_tokens = model.generate(**inputs, max_new_tokens=_MAX_NEW_TOKENS)

            translated_texts = tokenizer.batch_decode(generated_tokens, skip_special_tokens=True)
            return [{"translation_text": translated_text} for translated_text in translated_texts]

        _translator = translator
    return _translator


def _translate_texts(texts: Sequence[str]) -> List[str]:
    if not texts:
        return []

    result = _get_translator()(list(texts))
    translated_texts = [item.get("translation_text", "") for item in result]
    print(f"Translating batch of {len(texts)} texts")
    return translated_texts


def _translate_item(item: Dict[str, Any], translated_texts: Sequence[str]) -> Dict[str, Any]:
    translated_item = dict(item)
    translated_text_index = 0

    if "question" in translated_item:
        if isinstance(translated_item["question"], str):
            translated_item["question"] = translated_texts[translated_text_index]
            translated_text_index += 1

    if "contexts" in translated_item and isinstance(translated_item["contexts"], list):
        translated_contexts: List[Any] = []
        for context in translated_item["contexts"]:
            if isinstance(context, str):
                translated_contexts.append(translated_texts[translated_text_index])
                translated_text_index += 1
            else:
                translated_contexts.append(context)
        translated_item["contexts"] = translated_contexts

    if "answer" in translated_item:
        if isinstance(translated_item["answer"], str):
            translated_item["answer"] = translated_texts[translated_text_index]
            translated_text_index += 1

    return translated_item


def _translate_items_batch(
    items: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    translation_inputs: List[str] = []
    item_text_counts: List[int] = []

    for item in items:
        text_count = 0
        if isinstance(item.get("question"), str):
            translation_inputs.append(item["question"])
            text_count += 1

        contexts = item.get("contexts")
        if isinstance(contexts, list):
            for context in contexts:
                if isinstance(context, str):
                    translation_inputs.append(context)
                    text_count += 1

        if isinstance(item.get("answer"), str):
            translation_inputs.append(item["answer"])
            text_count += 1

        item_text_counts.append(text_count)

    translated_texts = _translate_texts(translation_inputs)

    translated_items: List[Dict[str, Any]] = []
    translated_text_index = 0
    for item, text_count in zip(items, item_text_counts):
        item_translations = translated_texts[translated_text_index: translated_text_index + text_count]
        translated_items.append(_translate_item(item, item_translations))
        translated_text_index += text_count

    return translated_items


def _maybe_update_progress(
    doc_id: str,
    processed_items: int,
    total_items: int,
    last_update_at: float,
    *,
    force: bool = False,
) -> float:
    now = time.monotonic()
    if force or now - last_update_at >= _STATUS_UPDATE_INTERVAL_SECONDS:
        completion_percentage = 100.0 if total_items == 0 else min(
            100.0,
            round(processed_items / total_items * 100.0, 2),
        )
        update_step_status(
            doc_id,
            "three_translating",
            "in_progress",
            completion_percentage=completion_percentage,
        )
        return now
    return last_update_at


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
    last_update_at = time.monotonic()
    for index, data in enumerate(loaded_data):
        input_path = Path(QA_PATHs[index]).resolve()
        translated_data: List[Dict[str, Any]] = []

        for batch_start in range(0, len(data), _TRANSLATION_BATCH_SIZE):
            batch = data[batch_start:batch_start + _TRANSLATION_BATCH_SIZE]
            translated_batch = _translate_items_batch(batch)
            translated_data.extend(translated_batch)

            processed_items += len(batch)
            last_update_at = _maybe_update_progress(
                doc_id,
                processed_items,
                total_items,
                last_update_at,
            )

        output_path = input_path.with_name(f"{input_path.stem}_pt_br{input_path.suffix}")
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(translated_data, handle, ensure_ascii=False, indent=2)

        output_paths.append(output_path)

    update_step_status(doc_id, "three_translating", "completed", completion_percentage=100)

    return tuple(output_paths)
