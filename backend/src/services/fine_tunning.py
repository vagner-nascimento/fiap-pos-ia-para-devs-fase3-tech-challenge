from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import torch
from datasets import Dataset
from fastapi import HTTPException
from peft import LoraConfig, TaskType, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments,
)
from trl import SFTTrainer

from infra.database.collections.preprocess import get_preprocess_document


BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_QAS_TRAIN_PATH = BACKEND_ROOT / "datasets" / "preprocessed" / "qas" / "train_pt_br.json"
DEFAULT_PROTOCOLS_TRAIN_PATH = (
    BACKEND_ROOT / "datasets" / "preprocessed" / "clinical_protocols" / "train.json"
)
DEFAULT_MODEL_DIR = BACKEND_ROOT / "models" / "hospital_helper"
DEFAULT_TOKENIZER_DIR = BACKEND_ROOT / "models" / "hospital_helper_tokenizer"
DEFAULT_BASE_MODEL = os.getenv("FINE_TUNING_BASE_MODEL", "Qwen/Qwen2.5-1.5B-Instruct")

DEFAULT_MAX_SEQ_LENGTH = 2048
DEFAULT_PROTOCOL_CHUNK_SIZE = 2400


def _normalize_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", value).strip()


def _read_json_list(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Arquivo nao encontrado: {path}")

    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, list):
        raise ValueError(f"Formato invalido em {path}: esperado uma lista de objetos JSON")

    return data


def _join_contexts(contexts: Any) -> str:
    if not isinstance(contexts, list):
        return ""

    cleaned_contexts = []
    for context in contexts:
        normalized = _normalize_text(context)
        if normalized:
            cleaned_contexts.append(normalized)

    if not cleaned_contexts:
        return ""

    if len(cleaned_contexts) == 1:
        return cleaned_contexts[0]

    return "\n".join(
        f"[Contexto {index + 1}] {text}" for index, text in enumerate(cleaned_contexts)
    )


def _chunk_text(text: str, max_chunk_size: int) -> List[str]:
    normalized = _normalize_text(text)
    if not normalized:
        return []

    if len(normalized) <= max_chunk_size:
        return [normalized]

    chunks: List[str] = []
    current_chunk = ""

    for sentence in re.split(r"(?<=[.!?])\s+", normalized):
        sentence = sentence.strip()
        if not sentence:
            continue

        candidate = sentence if not current_chunk else f"{current_chunk} {sentence}"
        if len(candidate) <= max_chunk_size:
            current_chunk = candidate
            continue

        if current_chunk:
            chunks.append(current_chunk.strip())
        current_chunk = sentence

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks or [normalized[:max_chunk_size].strip()]


def _build_qa_example(item: Dict[str, Any]) -> Optional[str]:
    question = _normalize_text(item.get("question"))
    answer = _normalize_text(item.get("answer"))
    contexts = _join_contexts(item.get("contexts"))

    if not question or not answer:
        return None

    prompt_lines = [
        "### Instrucao:",
        "Responda em pt-BR usando o contexto clinico fornecido.",
        "",
        "### Entrada:",
        f"Pergunta: {question}",
    ]

    if contexts:
        prompt_lines.extend(["Contexto:", contexts])

    prompt_lines.extend(["", "### Resposta:", answer])
    return "\n".join(prompt_lines)


def _build_protocol_examples(item: Dict[str, Any]) -> List[str]:
    content_text = _normalize_text(item.get("content_text"))
    if not content_text:
        return []

    name = _normalize_text(item.get("name")) or "protocolo_clinico"
    source = _normalize_text(item.get("source")) or "fonte_desconhecida"
    url = _normalize_text(item.get("url"))

    metadata_lines = [
        "### Protocolo clinico",
        f"Nome: {name}",
        f"Fonte: {source}",
    ]
    if url:
        metadata_lines.append(f"URL: {url}")
    metadata_lines.append("")
    metadata_lines.append("Conteudo:")

    prefix = "\n".join(metadata_lines)
    return [f"{prefix}\n{chunk}" for chunk in _chunk_text(content_text, DEFAULT_PROTOCOL_CHUNK_SIZE)]


def _build_training_texts(
    qas_data: Sequence[Dict[str, Any]],
    clinical_protocols_data: Sequence[Dict[str, Any]],
    include_clinical_protocols: bool,
) -> Tuple[List[str], Dict[str, int]]:
    texts: List[str] = []
    stats = {
        "qas_examples": 0,
        "clinical_protocol_examples": 0,
    }

    for item in qas_data:
        example = _build_qa_example(item)
        if example:
            texts.append(example)
            stats["qas_examples"] += 1

    if include_clinical_protocols:
        for item in clinical_protocols_data:
            protocol_examples = _build_protocol_examples(item)
            texts.extend(protocol_examples)
            stats["clinical_protocol_examples"] += len(protocol_examples)

    return texts, stats


def _resolve_device() -> torch.device:
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _validate_preprocess_id(preprocess_id: str) -> Dict[str, Any]:
    preprocess = get_preprocess_document(preprocess_id)
    if preprocess is None:
        raise HTTPException(status_code=404, detail=f"Preprocessamento com ID {preprocess_id} nao encontrado")

    status = preprocess.get("status")
    if status != "completed":
        error_message = preprocess.get("error_message")
        raise HTTPException(
            status_code=422,
            detail=(
                "Preprocessamento não foi concluído com sucesso. "
                f"Status atual: {status}, Error: {error_message}"
            ),
        )

    return preprocess


def _load_model(
    model_name: str,
    use_4bit: bool,
    device: torch.device,
) -> Tuple[Any, Any, bool]:
    tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    supports_gpu = device.type == "cuda"
    effective_use_4bit = bool(use_4bit and supports_gpu)

    model_kwargs: Dict[str, Any] = {
        "trust_remote_code": True,
        "low_cpu_mem_usage": True,
    }

    if supports_gpu:
        if effective_use_4bit:
            model_kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=(
                    torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
                ),
            )
            model_kwargs["device_map"] = "auto"
        else:
            model_kwargs["torch_dtype"] = (
                torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
            )
    else:
        model_kwargs["torch_dtype"] = torch.float32

    model = AutoModelForCausalLM.from_pretrained(model_name, **model_kwargs)
    model.config.use_cache = False

    if effective_use_4bit:
        model = prepare_model_for_kbit_training(model)

    if supports_gpu and not effective_use_4bit:
        model = model.to(device)

    return model, tokenizer, effective_use_4bit


def _apply_lora(model: Any) -> Any:
    lora_config = LoraConfig(
        r=16,
        lora_alpha=16,
        lora_dropout=0.05,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
    )
    return get_peft_model(model, lora_config)


def fine_tunning(
    preprocess_id: str,
    qas_train_path: Union[str, Path] = DEFAULT_QAS_TRAIN_PATH,
    clinical_protocols_train_path: Union[str, Path] = DEFAULT_PROTOCOLS_TRAIN_PATH,
    *,
    base_model_name: str = DEFAULT_BASE_MODEL,
    model_output_dir: Union[str, Path] = DEFAULT_MODEL_DIR,
    tokenizer_output_dir: Union[str, Path] = DEFAULT_TOKENIZER_DIR,
    include_clinical_protocols: bool = True,
    use_4bit: bool = False,
    max_seq_length: int = DEFAULT_MAX_SEQ_LENGTH,
    num_train_epochs: float = 1.0,
    per_device_train_batch_size: int = 1,
    gradient_accumulation_steps: int = 4,
    learning_rate: float = 2e-4,
    warmup_ratio: float = 0.03,
    logging_steps: int = 5,
    seed: int = 3407,
) -> Dict[str, Any]:
    """
    Fine tune pipeline for the hospital helper model.
    """

    _validate_preprocess_id(preprocess_id)

    qas_path = Path(qas_train_path)
    clinical_protocols_path = Path(clinical_protocols_train_path)
    model_output_path = Path(model_output_dir)
    tokenizer_output_path = Path(tokenizer_output_dir)
    summary_path = model_output_path / "training_summary.json"

    qas_data = _read_json_list(qas_path)
    clinical_protocols_data = _read_json_list(clinical_protocols_path)

    training_texts, stats = _build_training_texts(
        qas_data=qas_data,
        clinical_protocols_data=clinical_protocols_data,
        include_clinical_protocols=include_clinical_protocols,
    )

    if not training_texts:
        raise ValueError("Nenhum exemplo valido foi encontrado para o fine tuning.")

    dataset = Dataset.from_dict({"text": training_texts})
    device = _resolve_device()
    model, tokenizer, effective_use_4bit = _load_model(
        model_name=base_model_name,
        use_4bit=use_4bit,
        device=device,
    )
    model = _apply_lora(model)

    precision = {
        "fp16": device.type == "cuda" and not torch.cuda.is_bf16_supported(),
        "bf16": device.type == "cuda" and torch.cuda.is_bf16_supported(),
    }

    training_args = TrainingArguments(
        output_dir=str(model_output_path / "checkpoints"),
        num_train_epochs=num_train_epochs,
        per_device_train_batch_size=per_device_train_batch_size,
        gradient_accumulation_steps=gradient_accumulation_steps,
        learning_rate=learning_rate,
        warmup_ratio=warmup_ratio,
        logging_steps=logging_steps,
        save_strategy="epoch",
        save_total_limit=1,
        report_to=[],
        seed=seed,
        fp16=precision["fp16"],
        bf16=precision["bf16"],
        remove_unused_columns=False,
        optim="adamw_torch",
        gradient_checkpointing=True,
    )

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=max_seq_length,
        args=training_args,
        packing=False,
    )

    train_output = trainer.train()

    model_output_path.mkdir(parents=True, exist_ok=True)
    tokenizer_output_path.mkdir(parents=True, exist_ok=True)

    model.save_pretrained(model_output_path)
    tokenizer.save_pretrained(tokenizer_output_path)

    summary: Dict[str, Any] = {
        "preprocess_id": preprocess_id,
        "base_model_name": base_model_name,
        "include_clinical_protocols": include_clinical_protocols,
        "use_4bit_requested": use_4bit,
        "use_4bit_effective": effective_use_4bit,
        "device": device.type,
        "max_seq_length": max_seq_length,
        "dataset_size": len(training_texts),
        "qas_examples": stats["qas_examples"],
        "clinical_protocol_examples": stats["clinical_protocol_examples"],
        "model_output_dir": str(model_output_path),
        "tokenizer_output_dir": str(tokenizer_output_path),
        "training_metrics": train_output.metrics,
    }

    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2, default=str)

    summary["summary_path"] = str(summary_path)
    return summary
