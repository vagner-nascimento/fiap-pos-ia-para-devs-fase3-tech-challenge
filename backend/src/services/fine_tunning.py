from __future__ import annotations

import json
import math
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import torch
from datasets import Dataset
from fastapi import BackgroundTasks, HTTPException
from peft import LoraConfig, TaskType, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainerCallback,
    TrainerControl,
    TrainerState,
    TrainingArguments,
)
from trl import SFTTrainer

from infra.database.collections.fine_tunning import (
    create_fine_tunning_document,
    get_fine_tunning_document,
    mark_fine_tunning_document_completed,
    mark_fine_tunning_document_failed,
    update_fine_tunning_document,
)
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

    cleaned_contexts: List[str] = []
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


def _validate_preprocess_id(preprocess_id: str) -> Dict[str, Any]:
    preprocess = get_preprocess_document(preprocess_id)
    if preprocess is None:
        raise HTTPException(
            status_code=404,
            detail=f"Preprocessamento com ID {preprocess_id} nao encontrado",
        )

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


def _resolve_device() -> torch.device:
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _build_training_payload(
    *,
    preprocess_id: str,
    preprocess: Dict[str, Any],
    qas_train_path: Union[str, Path],
    clinical_protocols_train_path: Union[str, Path],
    base_model_name: str,
    model_output_dir: Union[str, Path],
    tokenizer_output_dir: Union[str, Path],
    include_clinical_protocols: bool,
    use_4bit: bool,
    max_seq_length: int,
    num_train_epochs: float,
    per_device_train_batch_size: int,
    gradient_accumulation_steps: int,
    learning_rate: float,
    warmup_ratio: float,
    logging_steps: int,
    seed: int,
) -> Dict[str, Any]:
    return {
        "preprocess_id": preprocess_id,
        "preprocess_snapshot": {
            "_id": preprocess_id,
            "status": preprocess.get("status"),
            "rag_percent": preprocess.get("rag_percent"),
            "updated_date": preprocess.get("updated_date"),
        },
        "base_model_name": base_model_name,
        "qas_train_path": str(Path(qas_train_path)),
        "clinical_protocols_train_path": str(Path(clinical_protocols_train_path)),
        "model_output_dir": str(Path(model_output_dir)),
        "tokenizer_output_dir": str(Path(tokenizer_output_dir)),
        "summary_path": str(Path(model_output_dir) / "training_summary.json"),
        "include_clinical_protocols": include_clinical_protocols,
        "use_4bit_requested": use_4bit,
        "use_4bit_effective": None,
        "status": "pendding",
        "completion_percentage": 0,
        "error_message": None,
        "created_date": datetime.now(timezone.utc),
        "updated_date": datetime.now(timezone.utc),
        "started_date": None,
        "finished_date": None,
        "device": None,
        "dataset_size": 0,
        "qas_examples": 0,
        "clinical_protocol_examples": 0,
        "estimated_total_steps": 0,
        "current_step": 0,
        "current_epoch": None,
        "current_loss": None,
        "loss_history": [],
        "training_metrics": {},
        "max_seq_length": max_seq_length,
        "num_train_epochs": num_train_epochs,
        "per_device_train_batch_size": per_device_train_batch_size,
        "gradient_accumulation_steps": gradient_accumulation_steps,
        "learning_rate": learning_rate,
        "warmup_ratio": warmup_ratio,
        "logging_steps": logging_steps,
        "seed": seed,
    }


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
    elif supports_gpu:
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


def _estimate_total_steps(
    dataset_size: int,
    per_device_train_batch_size: int,
    gradient_accumulation_steps: int,
    num_train_epochs: float,
) -> int:
    if dataset_size <= 0:
        return 1

    effective_batch = max(1, per_device_train_batch_size * gradient_accumulation_steps)
    steps_per_epoch = max(1, math.ceil(dataset_size / effective_batch))
    total_epochs = max(1, math.ceil(num_train_epochs))
    return max(1, steps_per_epoch * total_epochs)


class FineTunningProgressCallback(TrainerCallback):
    def __init__(self, doc_id: str, estimated_total_steps: int) -> None:
        self.doc_id = doc_id
        self.estimated_total_steps = max(1, estimated_total_steps)
        self.last_persist_at = 0.0
        self.current_loss: Optional[float] = None
        self.current_epoch: Optional[float] = None
        self.loss_history: List[Dict[str, Any]] = []

    def _persist(self, state: TrainerState, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self.last_persist_at < 5.0:
            return

        completion = min(
            100.0,
            round((state.global_step / self.estimated_total_steps) * 100.0, 2),
        )
        update_fine_tunning_document(
            self.doc_id,
            {
                "status": "in_progress",
                "completion_percentage": completion,
                "current_step": state.global_step,
                "current_epoch": self.current_epoch,
                "current_loss": self.current_loss,
                "loss_history": list(self.loss_history),
            },
        )
        self.last_persist_at = now

    def on_train_begin(
        self,
        args: TrainingArguments,
        state: TrainerState,
        control: TrainerControl,
        **kwargs: Any,
    ) -> None:
        update_fine_tunning_document(
            self.doc_id,
            {
                "status": "in_progress",
                "started_date": datetime.now(timezone.utc),
                "completion_percentage": 0,
                "current_step": 0,
            },
        )

    def on_log(
        self,
        args: TrainingArguments,
        state: TrainerState,
        control: TrainerControl,
        logs: Dict[str, Any],
        **kwargs: Any,
    ) -> None:
        if not logs:
            return

        if logs.get("loss") is not None:
            self.current_loss = float(logs["loss"])
            self.current_epoch = float(state.epoch) if state.epoch is not None else self.current_epoch
            entry = {
                "step": state.global_step,
                "epoch": self.current_epoch,
                "loss": self.current_loss,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            if not self.loss_history or self.loss_history[-1].get("step") != state.global_step:
                self.loss_history.append(entry)
            else:
                self.loss_history[-1] = entry

        if logs.get("eval_loss") is not None:
            self.loss_history.append(
                {
                    "step": state.global_step,
                    "epoch": float(state.epoch) if state.epoch is not None else None,
                    "loss": float(logs["eval_loss"]),
                    "kind": "eval_loss",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )

        self._persist(state)

    def on_step_end(
        self,
        args: TrainingArguments,
        state: TrainerState,
        control: TrainerControl,
        **kwargs: Any,
    ) -> None:
        self._persist(state)

    def on_train_end(
        self,
        args: TrainingArguments,
        state: TrainerState,
        control: TrainerControl,
        **kwargs: Any,
    ) -> None:
        self._persist(state, force=True)


def _training_job(doc_id: str) -> None:
    document = get_fine_tunning_document(doc_id)
    if document is None:
        return

    try:
        _validate_preprocess_id(document["preprocess_id"])

        qas_path = Path(document["qas_train_path"])
        clinical_protocols_path = Path(document["clinical_protocols_train_path"])
        model_output_path = Path(document["model_output_dir"])
        tokenizer_output_path = Path(document["tokenizer_output_dir"])
        summary_path = Path(document["summary_path"])

        qas_data = _read_json_list(qas_path)
        clinical_protocols_data = _read_json_list(clinical_protocols_path)
        training_texts, stats = _build_training_texts(
            qas_data=qas_data,
            clinical_protocols_data=clinical_protocols_data,
            include_clinical_protocols=bool(document["include_clinical_protocols"]),
        )

        if not training_texts:
            raise ValueError("Nenhum exemplo valido foi encontrado para o fine tuning.")

        device = _resolve_device()
        model, tokenizer, effective_use_4bit = _load_model(
            model_name=document["base_model_name"],
            use_4bit=bool(document["use_4bit_requested"]),
            device=device,
        )
        model = _apply_lora(model)

        estimated_total_steps = _estimate_total_steps(
            dataset_size=len(training_texts),
            per_device_train_batch_size=int(document["per_device_train_batch_size"]),
            gradient_accumulation_steps=int(document["gradient_accumulation_steps"]),
            num_train_epochs=float(document["num_train_epochs"]),
        )

        update_fine_tunning_document(
            doc_id,
            {
                "device": device.type,
                "use_4bit_effective": effective_use_4bit,
                "dataset_size": len(training_texts),
                "qas_examples": stats["qas_examples"],
                "clinical_protocol_examples": stats["clinical_protocol_examples"],
                "estimated_total_steps": estimated_total_steps,
            },
        )

        precision = {
            "fp16": device.type == "cuda" and not torch.cuda.is_bf16_supported(),
            "bf16": device.type == "cuda" and torch.cuda.is_bf16_supported(),
        }

        training_args = TrainingArguments(
            output_dir=str(model_output_path / "checkpoints"),
            num_train_epochs=float(document["num_train_epochs"]),
            per_device_train_batch_size=int(document["per_device_train_batch_size"]),
            gradient_accumulation_steps=int(document["gradient_accumulation_steps"]),
            learning_rate=float(document["learning_rate"]),
            warmup_ratio=float(document["warmup_ratio"]),
            logging_steps=int(document["logging_steps"]),
            save_strategy="epoch",
            save_total_limit=1,
            report_to=[],
            seed=int(document["seed"]),
            fp16=precision["fp16"],
            bf16=precision["bf16"],
            remove_unused_columns=False,
            optim="adamw_torch",
            gradient_checkpointing=True,
        )

        trainer = SFTTrainer(
            model=model,
            tokenizer=tokenizer,
            train_dataset=Dataset.from_dict({"text": training_texts}),
            dataset_text_field="text",
            max_seq_length=int(document["max_seq_length"]),
            args=training_args,
            packing=False,
        )
        trainer.add_callback(FineTunningProgressCallback(doc_id, estimated_total_steps))

        train_output = trainer.train()

        model_output_path.mkdir(parents=True, exist_ok=True)
        tokenizer_output_path.mkdir(parents=True, exist_ok=True)

        model.save_pretrained(model_output_path)
        tokenizer.save_pretrained(tokenizer_output_path)

        training_metrics = dict(train_output.metrics or {})
        training_metrics["loss_history"] = get_fine_tunning_document(doc_id).get("loss_history", [])

        with summary_path.open("w", encoding="utf-8") as handle:
            json.dump(
                {
                    "preprocess_id": document["preprocess_id"],
                    "device": device.type,
                    "dataset_size": len(training_texts),
                    "training_metrics": training_metrics,
                },
                handle,
                ensure_ascii=False,
                indent=2,
                default=str,
            )

        mark_fine_tunning_document_completed(
            doc_id,
            {
                "training_metrics": training_metrics,
                "current_loss": training_metrics.get("train_loss"),
                "current_step": estimated_total_steps,
                "current_epoch": float(document["num_train_epochs"]),
                "device": device.type,
                "use_4bit_effective": effective_use_4bit,
                "dataset_size": len(training_texts),
                "qas_examples": stats["qas_examples"],
                "clinical_protocol_examples": stats["clinical_protocol_examples"],
                "summary_path": str(summary_path),
            },
        )

    except Exception as exc:
        mark_fine_tunning_document_failed(doc_id, str(exc))


def _prepare_training_document(
    preprocess_id: str,
    qas_train_path: Union[str, Path],
    clinical_protocols_train_path: Union[str, Path],
    *,
    base_model_name: str,
    model_output_dir: Union[str, Path],
    tokenizer_output_dir: Union[str, Path],
    include_clinical_protocols: bool,
    use_4bit: bool,
    max_seq_length: int,
    num_train_epochs: float,
    per_device_train_batch_size: int,
    gradient_accumulation_steps: int,
    learning_rate: float,
    warmup_ratio: float,
    logging_steps: int,
    seed: int,
) -> Dict[str, Any]:
    preprocess = _validate_preprocess_id(preprocess_id)
    payload = _build_training_payload(
        preprocess_id=preprocess_id,
        preprocess=preprocess,
        qas_train_path=qas_train_path,
        clinical_protocols_train_path=clinical_protocols_train_path,
        base_model_name=base_model_name,
        model_output_dir=model_output_dir,
        tokenizer_output_dir=tokenizer_output_dir,
        include_clinical_protocols=include_clinical_protocols,
        use_4bit=use_4bit,
        max_seq_length=max_seq_length,
        num_train_epochs=num_train_epochs,
        per_device_train_batch_size=per_device_train_batch_size,
        gradient_accumulation_steps=gradient_accumulation_steps,
        learning_rate=learning_rate,
        warmup_ratio=warmup_ratio,
        logging_steps=logging_steps,
        seed=seed,
    )
    return create_fine_tunning_document(payload)


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
    background_tasks: Optional[BackgroundTasks] = None,
) -> Dict[str, Any]:
    """
    Cria o documento de fine tuning e agenda o treinamento em background.
    """

    document = _prepare_training_document(
        preprocess_id,
        qas_train_path,
        clinical_protocols_train_path,
        base_model_name=base_model_name,
        model_output_dir=model_output_dir,
        tokenizer_output_dir=tokenizer_output_dir,
        include_clinical_protocols=include_clinical_protocols,
        use_4bit=use_4bit,
        max_seq_length=max_seq_length,
        num_train_epochs=num_train_epochs,
        per_device_train_batch_size=per_device_train_batch_size,
        gradient_accumulation_steps=gradient_accumulation_steps,
        learning_rate=learning_rate,
        warmup_ratio=warmup_ratio,
        logging_steps=logging_steps,
        seed=seed,
    )

    if background_tasks is not None:
        background_tasks.add_task(_training_job, document["_id"])
    else:
        _training_job(document["_id"])
        refreshed = get_fine_tunning_document(document["_id"])
        if refreshed is not None:
            return refreshed

    return document


def get_fine_tunning_status(doc_id: str) -> Dict[str, Any]:
    document = get_fine_tunning_document(doc_id)
    if document is None:
        raise HTTPException(status_code=404, detail=f"Documento com ID {doc_id} nao encontrado")
    return document
