from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from services.fine_tunning import fine_tunning, get_fine_tunning_status


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
    _id: str
    preprocess_id: str
    preprocess_snapshot: Dict[str, Any]
    base_model_name: str
    qas_train_path: str
    clinical_protocols_train_path: str
    model_output_dir: str
    tokenizer_output_dir: str
    summary_path: str
    include_clinical_protocols: bool
    use_4bit_requested: bool
    use_4bit_effective: Optional[bool]
    status: str
    completion_percentage: float
    error_message: Optional[str]
    created_date: str
    updated_date: str
    started_date: Optional[str]
    finished_date: Optional[str]
    device: Optional[str]
    dataset_size: int
    qas_examples: int
    clinical_protocol_examples: int
    estimated_total_steps: int
    current_step: int
    current_epoch: Optional[float]
    current_loss: Optional[float]
    loss_history: list
    training_metrics: Dict[str, Any]
    max_seq_length: int
    num_train_epochs: float
    per_device_train_batch_size: int
    gradient_accumulation_steps: int
    learning_rate: float
    warmup_ratio: float
    logging_steps: int
    seed: int


@router.post("/", response_model=FineTunningResponse)
async def fine_tunning_endpoint(request: FineTunningRequest, background_tasks: BackgroundTasks) -> Dict[str, Any]:
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
        "background_tasks": background_tasks,
    }
    if request.base_model_name is not None:
        kwargs["base_model_name"] = request.base_model_name

    result = await run_in_threadpool(
        fine_tunning,
        request.preprocess_id,
        **kwargs,
    )

    return result


@router.get("/{doc_id}", response_model=FineTunningResponse)
async def get_fine_tunning_status_endpoint(doc_id: str) -> Dict[str, Any]:
    """
    Retorna o status do fine tuning pelo ID.

    Args:
        doc_id: ID do documento de fine tuning.

    Returns:
        Dict com o documento completo (status, completion_percentage, loss_history, etc.).

    Raises:
        HTTPException: Em caso de erro ou documento não encontrado.
    """
    try:
        document = get_fine_tunning_status(doc_id)
        return document
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao buscar documento: {str(e)}"
        )
