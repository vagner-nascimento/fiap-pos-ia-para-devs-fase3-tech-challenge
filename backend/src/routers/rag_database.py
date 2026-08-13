from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from services.rag_database import generate_rag_database, get_rag_generation_status


router = APIRouter(prefix="/rag-database", tags=["rag-database"])


class RagDatabaseRequest(BaseModel):
    preprocess_id: str = Field(..., min_length=1)


class RagDatabaseResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(validation_alias="_id")
    batch_id: str
    preprocess_id: str
    preprocess_snapshot: Dict[str, Any]
    qas_rag_path: str
    clinical_protocols_rag_path: str
    embedding_model: str
    splitter_name: str
    splitter_chunk_size: int
    splitter_chunk_overlap: int
    status: str
    completion_percentage: float
    error_message: Optional[str] = None
    created_date: str
    updated_date: str
    started_date: Optional[str]
    finished_date: Optional[str]
    current_step: int
    estimated_total_steps: int
    qas_documents: int
    clinical_protocol_documents: int
    total_documents: int


@router.post("/", response_model=RagDatabaseResponse)
async def rag_database_endpoint(
    request: RagDatabaseRequest,
    background_tasks: BackgroundTasks,
) -> Dict[str, Any]:
    result = await run_in_threadpool(
        generate_rag_database,
        request.preprocess_id,
        background_tasks=background_tasks,
    )
    return result


@router.get("/{doc_id}", response_model=RagDatabaseResponse)
async def get_rag_database_status_endpoint(doc_id: str) -> Dict[str, Any]:
    try:
        document = get_rag_generation_status(doc_id)
        return document
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar documento: {str(exc)}")
