from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from services.fine_tunning import fine_tunning


router = APIRouter(prefix="/fine-tunning", tags=["fine-tunning"])


class FineTunningRequest(BaseModel):
    preprocess_id: str = Field(..., min_length=1)
    base_model_name: Optional[str] = Field(
        default=None,
        description="Override do modelo base para o treino",
    )
    include_clinical_protocols: bool = Field(
        default=True,
        description="Inclui os protocolos clinicos no treino",
    )
    use_4bit: bool = Field(
        default=False,
        description="Ativa quantizacao 4-bit quando houver suporte",
    )
    max_seq_length: int = Field(default=2048, ge=256, le=8192)
    num_train_epochs: float = Field(default=1.0, gt=0)
    per_device_train_batch_size: int = Field(default=1, ge=1)
    gradient_accumulation_steps: int = Field(default=4, ge=1)
    learning_rate: float = Field(default=2e-4, gt=0)
    warmup_ratio: float = Field(default=0.03, ge=0.0, le=1.0)
    logging_steps: int = Field(default=5, ge=1)
    seed: int = Field(default=3407, ge=0)


class FineTunningResponse(BaseModel):
    preprocess_id: str
    base_model_name: str
    include_clinical_protocols: bool
    use_4bit_requested: bool
    use_4bit_effective: bool
    device: str
    max_seq_length: int
    dataset_size: int
    qas_examples: int
    clinical_protocol_examples: int
    model_output_dir: str
    tokenizer_output_dir: str
    summary_path: str
    training_metrics: Dict[str, Any]


@router.post("/", response_model=FineTunningResponse)
async def fine_tunning_endpoint(request: FineTunningRequest) -> Dict[str, Any]:
    if request.base_model_name is not None and not request.base_model_name.strip():
        raise HTTPException(status_code=400, detail="base_model_name nao pode ser vazio")

    kwargs = {
        "include_clinical_protocols": request.include_clinical_protocols,
        "use_4bit": request.use_4bit,
        "max_seq_length": request.max_seq_length,
        "num_train_epochs": request.num_train_epochs,
        "per_device_train_batch_size": request.per_device_train_batch_size,
        "gradient_accumulation_steps": request.gradient_accumulation_steps,
        "learning_rate": request.learning_rate,
        "warmup_ratio": request.warmup_ratio,
        "logging_steps": request.logging_steps,
        "seed": request.seed,
    }
    if request.base_model_name is not None:
        kwargs["base_model_name"] = request.base_model_name

    result = await run_in_threadpool(
        fine_tunning,
        request.preprocess_id,
        **kwargs,
    )

    return result
