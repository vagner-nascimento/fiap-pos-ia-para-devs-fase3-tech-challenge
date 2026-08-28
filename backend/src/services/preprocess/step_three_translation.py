
import json
import re
import time
from contextlib import nullcontext
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

_translator: Optional[Any] = None

from infra.database.collections.preprocess import update_step_status

_TRANSLATION_BATCH_SIZE = 16
_STATUS_UPDATE_INTERVAL_SECONDS = 10.0
# Reduzido para evitar inferência excessivamente lenta no CPU,
# que era a causa principal do "pendurado" na etapa de tradução.
_MAX_NEW_TOKENS = 256
# Limite de caracteres por chunk para segmentação de textos longos.
# Valor conservador para não exceder os 256 tokens de geração do modelo Marian.
_CHUNK_CHAR_LIMIT = 400


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
                generated_tokens = model.generate(
                    **inputs,
                    max_new_tokens=_MAX_NEW_TOKENS,
                    num_beams=1,
                    do_sample=False,
                    no_repeat_ngram_size=4,
                )

            translated_texts = tokenizer.batch_decode(generated_tokens, skip_special_tokens=True)
            return [{"translation_text": translated_text} for translated_text in translated_texts]

        _translator = translator
    return _translator


def _split_into_sentences(text: str) -> List[str]:
    """Divide texto em sentenças usando pontuação como delimitador."""
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s for s in sentences if s.strip()]


def _chunk_text(text: str) -> List[str]:
    """Segmenta texto longo em chunks que cabem no limite do modelo.

    Textos curtos (<=_CHUNK_CHAR_LIMIT) retornam como chunk único.
    Textos longos são divididos em sentenças e agrupados em chunks
    que não excedam _CHUNK_CHAR_LIMIT caracteres.
    """
    if len(text) <= _CHUNK_CHAR_LIMIT:
        return [text]

    sentences = _split_into_sentences(text)
    if not sentences:
        return [text]

    chunks: List[str] = []
    current_parts: List[str] = []
    current_len = 0

    for sentence in sentences:
        # Se adicionar esta sentença excederia o limite E já temos conteúdo, fecha o chunk
        if current_len + len(sentence) > _CHUNK_CHAR_LIMIT and current_parts:
            chunks.append(" ".join(current_parts))
            current_parts = []
            current_len = 0

        current_parts.append(sentence)
        current_len += len(sentence) + 1  # +1 para o espaço

    if current_parts:
        chunks.append(" ".join(current_parts))

    return chunks


def _translate_texts(texts: Sequence[str]) -> List[str]:
    """Traduz uma lista de textos, segmentando textos longos em chunks.

    Textos longos são divididos em chunks menores, traduzidos
    individualmente e remontados com espaço. Isso evita truncação
    silenciosa pelo modelo Marian (max 512 tokens de entrada).
    """
    if not texts:
        return []

    translator = _get_translator()

    # Mapeia cada texto original nos seus chunks
    all_chunks: List[str] = []
    chunk_map: List[Tuple[int, int]] = []  # (start_index, count) para cada texto original

    for text in texts:
        chunks = _chunk_text(text)
        chunk_map.append((len(all_chunks), len(chunks)))
        all_chunks.extend(chunks)

    # Traduz todos os chunks em sub-batches
    translated_chunks: List[str] = []
    for batch_start in range(0, len(all_chunks), _TRANSLATION_BATCH_SIZE):
        batch = all_chunks[batch_start:batch_start + _TRANSLATION_BATCH_SIZE]
        result = translator(batch)
        translated_chunks.extend(
            item.get("translation_text", "") for item in result
        )

    # Remonta cada texto original a partir dos seus chunks traduzidos
    translated_texts: List[str] = []
    for start, count in chunk_map:
        parts = translated_chunks[start:start + count]
        translated_texts.append(" ".join(parts))

    print(f"Translated {len(texts)} texts ({len(all_chunks)} chunks)")
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
        print(
            f"Tradução em progresso: {processed_items}/{total_items} "
            f"itens processados ({completion_percentage:.2f}%)"
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
    qa_train_path: Path,
) -> Path:
    """Translate a single QA JSON file from English to Portuguese (pt-BR). Returns the path of the translated file."""
    input_path = Path(qa_train_path).resolve()

    if not input_path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {input_path}")

    with input_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, list):
        raise ValueError(f"Formato inválido para {input_path}: esperado uma lista de objetos JSON.")

    total_items = len(data)
    print(f"Iniciando tradução de {total_items} itens QA...")
    update_step_status(doc_id, "three_translating", "in_progress", completion_percentage=0)

    processed_items = 0
    last_update_at = time.monotonic()
    translated_data: List[Dict[str, Any]] = []

    for batch_start in range(0, len(data), _TRANSLATION_BATCH_SIZE):
        batch = data[batch_start:batch_start + _TRANSLATION_BATCH_SIZE]
        print(
            f"Traduzindo lote {batch_start // _TRANSLATION_BATCH_SIZE + 1} "
            f"({len(batch)} itens)"
        )
        translated_batch = _translate_items_batch(batch)
        translated_data.extend(translated_batch)

        processed_items += len(batch)
        last_update_at = _maybe_update_progress(
            doc_id,
            processed_items,
            total_items,
            last_update_at,
            force=True,
        )
        print(
            f"Lote concluído: {processed_items}/{total_items} itens traduzidos "
            f"({(processed_items / total_items) * 100:.2f}%)"
        )

    # Change output filename to qas_train_pt_br.json
    output_path = input_path.parent / "qas_train_pt_br.json"
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(translated_data, handle, ensure_ascii=False, indent=2)

    update_step_status(doc_id, "three_translating", "completed", completion_percentage=100)

    return output_path
