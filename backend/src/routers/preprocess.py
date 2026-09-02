from __future__ import annotations
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, ConfigDict, Field
from typing import Dict, Any, Optional
from services.preprocess_data import preprocess_data
from infra.database.collections.preprocess import get_preprocess_document


router = APIRouter(prefix="/preprocess", tags=["preprocess"])


class PreprocessRequest(BaseModel):
    """Modelo para o request de preprocessamento."""
    skip_translation: bool = False


class StepInfo(BaseModel):
    """Informações de um step individual."""
    status: str
    error_message: Optional[str] = None
    completion_percentage: Optional[float] = None


class Results(BaseModel):
    """Resultados do preprocessamento."""
    qas_train_path: Optional[str] = None
    qas_train_pt_br_path: Optional[str] = None
    clinical_protocols_rag_path: Optional[str] = None
    qas_count: int = 0
    clinical_protocols_count: int = 0


class PreprocessResponse(BaseModel):
    """Modelo para a resposta do preprocessamento."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(validation_alias="_id")
    steps: Dict[str, StepInfo]
    results: Results
    status: str
    error_message: Optional[str] = None
    updated_date: str
    completion_percentage: float


@router.post("/", response_model=PreprocessResponse)
async def preprocess_endpoint(
    request: PreprocessRequest,
    background_tasks: BackgroundTasks,
) -> Dict[str, Any]:
    """
    Processa os dados de PubMedQA e MedQuAD.
    
    O processamento é executado em background e retorna imediatamente o documento criado.
    
    Args:
        request: Payload do preprocessamento, incluindo flag de pular tradução.
        background_tasks: Instância de BackgroundTasks do FastAPI.
        
    Returns:
        Dict com o documento criado (incluindo _id e status inicial).
        
    Raises:
        HTTPException: Em caso de erro no processamento.
    """
    try:
        document = preprocess_data(
            background_tasks=background_tasks,
            skip_translation=request.skip_translation,
        )
        return document
        
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=f"Arquivo ou diretório não encontrado: {str(e)}"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Erro de validação: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao processar dados: {str(e)}"
        )


@router.get("/{doc_id}", response_model=PreprocessResponse)
async def get_preprocess_status(doc_id: str) -> Dict[str, Any]:
    """
    Retorna o status do processamento pelo ID.
    
    Args:
        doc_id: ID do documento de preprocessamento.
        
    Returns:
        Dict com o documento completo (status, train_data, rag_data, completion_percentage, etc.).
        
    Raises:
        HTTPException: Em caso de erro ou documento não encontrado.
    """
    try:
        document = get_preprocess_document(doc_id)
        
        if document is None:
            raise HTTPException(
                status_code=404,
                detail=f"Documento com ID {doc_id} não encontrado"
            )
        
        return document
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao buscar documento: {str(e)}"
        )
