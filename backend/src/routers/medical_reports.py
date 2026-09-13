from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query

from infra.database.collections.medical_reports import find_medical_reports_by_patient_name


router = APIRouter(prefix="/medical-reports", tags=["medical-reports"])


@router.get("/", response_model=List[Dict[str, Any]])
def get_medical_reports(
    patient_name: str = Query(..., min_length=1, description="Nome completo do paciente")
) -> List[Dict[str, Any]]:
    try:
        return find_medical_reports_by_patient_name(patient_name.strip())
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao consultar laudos médicos: {str(exc)}",
        )
