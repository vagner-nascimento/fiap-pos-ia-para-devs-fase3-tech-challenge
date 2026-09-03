from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.rag_database import generate_rag_database, query_rag_documents


router = APIRouter(prefix="/rag-database", tags=["rag-database"])


class RagDatabaseRequest(BaseModel):
    preprocess_id: str = Field(..., min_length=1)


class RagDatabaseResponse(BaseModel):
    id: str
    batch_id: str
    preprocess_id: str
    preprocess_snapshot: Dict[str, Any]
    clinical_protocols_rag_path: str
    medical_reports_path: str
    embedding_model: str
    splitter_name: str
    splitter_chunk_size: int
    splitter_chunk_overlap: int
    status: str
    error_message: Optional[str] = None
    created_date: str
    updated_date: str
    clinical_protocol_documents: int
    medical_report_documents: int
    total_documents: int


class RagQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Texto da consulta")
    top_k: int = Field(5, ge=1, le=50, description="Quantidade maxima de documentos a retornar")
    preprocess_id: Optional[str] = Field(None, description="Filtro por ID do pre-processamento")
    similarity_threshold: Optional[float] = Field(None, ge=-1.0, le=1.0, description="Score minimo de similaridade")


class RagDocumentResult(BaseModel):
    id: str
    preprocess_id: str
    dataset: str
    source_type: str
    content: str
    similarity_score: float
    metadatas: Dict[str, Any]
    chunk_index: Optional[int] = None
    chunk_total: Optional[int] = None


class RagQueryResponse(BaseModel):
    query: str
    total_results: int
    documents: List[RagDocumentResult]


@router.post("/", response_model=RagDatabaseResponse)
def rag_database_endpoint(request: RagDatabaseRequest) -> Dict[str, Any]:
    try:
        return generate_rag_database(request.preprocess_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar base RAG: {str(exc)}")


@router.post("/query", response_model=RagQueryResponse)
def rag_query_endpoint(request: RagQueryRequest) -> Dict[str, Any]:
    try:
        return query_rag_documents(
            query=request.query,
            top_k=request.top_k,
            preprocess_id=request.preprocess_id,
            similarity_threshold=request.similarity_threshold,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao consultar base RAG: {str(exc)}")

