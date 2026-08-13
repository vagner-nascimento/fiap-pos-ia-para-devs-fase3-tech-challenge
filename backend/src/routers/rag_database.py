from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.rag_database import generate_rag_database


router = APIRouter(prefix="/rag-database", tags=["rag-database"])


class RagDatabaseRequest(BaseModel):
    preprocess_id: str = Field(..., min_length=1)


class RagDatabaseResponse(BaseModel):
    id: str
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
    error_message: Optional[str] = None
    created_date: str
    updated_date: str
    qas_documents: int
    clinical_protocol_documents: int
    total_documents: int


@router.post("/", response_model=RagDatabaseResponse)
def rag_database_endpoint(request: RagDatabaseRequest) -> Dict[str, Any]:
    try:
        return generate_rag_database(request.preprocess_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar base RAG: {str(exc)}")
