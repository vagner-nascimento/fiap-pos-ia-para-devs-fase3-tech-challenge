"""
Nó 3.1: Recuperador de Contexto do Paciente (Patient Context Retriever)

Implementa o roteamento entre as jornadas do assistente médico:

- **Jornada 1 (Q&A genérico)**: `patient_name` ausente no payload → nó é um
  no-op. Retorna `patient_context_used = False` sem qualquer chamada ao backend.

- **Jornada 2 (Consulta por paciente)**: `patient_name` preenchido → busca o
  prontuário e os laudos do paciente no backend, extrai apenas os campos
  clínicos relevantes (sem identificação pessoal) e injeta o contexto no estado.

O nó nunca bloqueia o pipeline. Se o prontuário/laudo não forem encontrados,
  degrada silenciosamente para Jornada 1 com `patient_context_used = False`.
"""
import logging
import os
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://localhost:3000")
MEDICAL_RECORD_ENDPOINT = f"{BACKEND_API_URL}/medical-record"
MEDICAL_REPORTS_ENDPOINT = f"{BACKEND_API_URL}/medical-reports"


# ---------------------------------------------------------------------------
# Extração de campos clínicos (sem dados de identificação)
# ---------------------------------------------------------------------------

def _flatten_dict_text(value: Any, parent_key: str = "") -> List[str]:
    """Converte estruturas aninhadas em texto clínico legível, sem expor dicionários brutos."""
    if value is None:
        return []
    if isinstance(value, dict):
        items: List[str] = []
        for key, child in value.items():
            if child is None or child == "":
                continue
            label = key.replace("_", " ").strip()
            if isinstance(child, (dict, list)):
                nested = _flatten_dict_text(child, label)
                items.extend(nested)
            else:
                if parent_key and parent_key.lower() in {"diagnostico_principal", "cid_10", "impressao_clinica"}:
                    items.append(f"{key.replace('_', ' ').title()}: {str(child).strip()}")
                else:
                    items.append(f"{label.title()}: {str(child).strip()}")
        return items
    if isinstance(value, list):
        items: List[str] = []
        for item in value:
            if isinstance(item, (dict, list)):
                items.extend(_flatten_dict_text(item, parent_key))
            elif item not in (None, ""):
                items.append(str(item).strip())
        return items
    if value != "":
        return [str(value).strip()]
    return []


def _extract_clinical_fields(record: Dict[str, Any]) -> tuple[str, List[str]]:
    """Extrai campos clínicos relevantes do prontuário anonimizando o paciente."""
    parts: List[str] = []
    fields_used: List[str] = []

    avaliacao = record.get("avaliacao") or record.get("soap", {}).get("avaliacao")
    if avaliacao:
        if isinstance(avaliacao, dict):
            flattened: List[str] = []
            for key, value in avaliacao.items():
                if key in {"itens", "diagnosticos"}:
                    flattened.extend(_flatten_dict_text(value, key))
                elif isinstance(value, (dict, list)):
                    flattened.extend(_flatten_dict_text({key: value}, key))
                elif value not in (None, ""):
                    flattened.append(f"{key.replace('_', ' ').title()}: {str(value).strip()}")
            texto = "; ".join(part for part in flattened if str(part).strip())
        else:
            texto = str(avaliacao)
        if texto.strip():
            parts.append(f"Diagnosticos/Avaliacao: {texto.strip()}")
            fields_used.append("avaliacao")

    plano = record.get("plano") or record.get("soap", {}).get("plano")
    if plano:
        if isinstance(plano, dict):
            prescricao = plano.get("prescricao") or plano.get("medicamentos", "")
            orientacoes = plano.get("orientacoes", "")
            if prescricao:
                parts.append(f"Medicamentos/Prescricao: {str(prescricao).strip()}")
                fields_used.append("plano.prescricao")
            if orientacoes:
                parts.append(f"Orientacoes: {str(orientacoes).strip()}")
                fields_used.append("plano.orientacoes")
        else:
            parts.append(f"Plano: {str(plano).strip()}")
            fields_used.append("plano")

    alergias = record.get("alergias") or record.get("soap", {}).get("alergias")
    if alergias:
        texto = ", ".join(str(a) for a in alergias) if isinstance(alergias, list) else str(alergias)
        if texto.strip():
            parts.append(f"Alergias: {texto.strip()}")
            fields_used.append("alergias")

    objetivo = record.get("objetivo") or record.get("soap", {}).get("objetivo")
    if objetivo:
        if isinstance(objetivo, dict):
            vitais = []
            for campo in ["pressao_arterial", "frequencia_cardiaca", "saturacao", "temperatura"]:
                valor = objetivo.get(campo)
                if valor:
                    vitais.append(f"{campo.replace('_', ' ')}: {valor}")
            exame_fisico = objetivo.get("exame_fisico", "")
            if vitais:
                parts.append(f"Sinais vitais: {'; '.join(vitais)}")
                fields_used.append("objetivo.vitais")
            if exame_fisico:
                parts.append(f"Exame fisico: {str(exame_fisico).strip()}")
                fields_used.append("objetivo.exame_fisico")
        else:
            parts.append(f"Objetivo: {str(objetivo).strip()}")
            fields_used.append("objetivo")

    return "\n".join(parts), fields_used


def _extract_medical_report_context(reports: List[Dict[str, Any]]) -> tuple[str, List[str]]:
    """Concatena os laudos em um texto único, preservando apenas campos clínicos úteis."""
    parts: List[str] = []
    fields_used: List[str] = []

    for index, report in enumerate(reports, start=1):
        if not isinstance(report, dict):
            continue

        corpo = report.get("corpo_tecnico") or {}
        conclusao = report.get("conclusao") or {}

        chunks: List[str] = []
        tipo_exame = corpo.get("tipo_exame")
        descricao = corpo.get("descricao_tecnica")
        evolucao = corpo.get("evolucao_clinica")
        diagnostico = conclusao.get("impressao_diagnostica")
        cid_10 = conclusao.get("cid_10")
        conduta = conclusao.get("conduta_terapeutica")

        if tipo_exame:
            chunks.append(f"Tipo de exame: {str(tipo_exame).strip()}")
            fields_used.append("laudos.tipo_exame")
        if descricao:
            chunks.append(f"Descricao tecnica: {str(descricao).strip()}")
            fields_used.append("laudos.descricao_tecnica")
        if evolucao:
            chunks.append(f"Evolucao: {str(evolucao).strip()}")
            fields_used.append("laudos.evolucao_clinica")
        if diagnostico:
            chunks.append(f"Impressao diagnostica: {str(diagnostico).strip()}")
            fields_used.append("laudos.impressao_diagnostica")
        if cid_10:
            chunks.append(f"CID-10: {str(cid_10).strip()}")
            fields_used.append("laudos.cid_10")
        if conduta:
            chunks.append(f"Conduta: {str(conduta).strip()}")
            fields_used.append("laudos.conduta_terapeutica")

        if chunks:
            parts.append(f"Laudo {index}: {'; '.join(chunks)}")

    unique_fields = []
    seen = set()
    for field in fields_used:
        if field not in seen:
            seen.add(field)
            unique_fields.append(field)

    return "\n\n".join(parts), unique_fields


# ---------------------------------------------------------------------------
# Chamada ao backend
# ---------------------------------------------------------------------------

def _fetch_medical_record(patient_name: str) -> Optional[Dict[str, Any]]:
    """Busca o prontuário do paciente via endpoint do backend."""
    try:
        response = requests.get(
            MEDICAL_RECORD_ENDPOINT,
            params={"patient_name": patient_name},
            timeout=10,
        )
        response.raise_for_status()
        records = response.json()
        if records and isinstance(records, list):
            logger.info(
                f"[PATIENT] Prontuário encontrado para '{patient_name}': "
                f"{len(records)} registro(s)."
            )
            return records[0]
        logger.warning(f"[PATIENT] Nenhum prontuário encontrado para '{patient_name}'.")
        return None
    except requests.exceptions.ConnectionError:
        logger.error(f"[PATIENT] Não foi possível conectar ao backend em {MEDICAL_RECORD_ENDPOINT}.")
        return None
    except requests.exceptions.Timeout:
        logger.error("[PATIENT] Timeout ao buscar prontuário.")
        return None
    except requests.exceptions.RequestException as exc:
        logger.error(f"[PATIENT] Erro ao buscar prontuário: {exc}")
        return None


def _fetch_medical_reports(patient_name: str) -> List[Dict[str, Any]]:
    """Busca os laudos médicos do paciente via endpoint do backend."""
    try:
        response = requests.get(
            MEDICAL_REPORTS_ENDPOINT,
            params={"patient_name": patient_name},
            timeout=10,
        )
        response.raise_for_status()
        records = response.json()
        if isinstance(records, list):
            logger.info(
                f"[PATIENT] Laudos encontrados para '{patient_name}': {len(records)} registro(s)."
            )
            logger.info(
                f"[PATIENT] Informações do primeiro laudo: {records[0] if records else {}}."
            )
            return records
        logger.warning(f"[PATIENT] Nenhum laudo encontrado para '{patient_name}'.")
        return []
    except requests.exceptions.ConnectionError:
        logger.error(f"[PATIENT] Não foi possível conectar ao backend em {MEDICAL_REPORTS_ENDPOINT}.")
        return []
    except requests.exceptions.Timeout:
        logger.error("[PATIENT] Timeout ao buscar laudos do paciente.")
        return []
    except requests.exceptions.RequestException as exc:
        logger.error(f"[PATIENT] Erro ao buscar laudos: {exc}")
        return []


# ---------------------------------------------------------------------------
# Nó LangGraph
# ---------------------------------------------------------------------------

def patient_context_retriever_node(state: dict) -> dict:
    """Busca prontuário e laudos do paciente para compor o contexto clínico."""
    patient_name = (state.get("patient_name") or "").strip()

    if not patient_name:
        logger.info("[PATIENT] Jornada 1 — patient_name ausente, nenhuma consulta ao prontuário.")
        return {
            **state,
            "patient_context": "",
            "patient_context_used": False,
            "patient_fields_used": [],
            "medical_reports_context": "",
            "medical_reports_used": False,
            "medical_reports_fields_used": [],
        }

    logger.info(f"[PATIENT] Jornada 2 — buscando prontuário e laudos para: '{patient_name}'")
    record = _fetch_medical_record(patient_name)
    medical_reports = _fetch_medical_reports(patient_name)

    patient_parts: List[str] = []
    fields_used: List[str] = []
    medical_report_text = ""
    medical_report_fields: List[str] = []

    if record:
        clinical_text, record_fields = _extract_clinical_fields(record)
        if clinical_text.strip():
            patient_parts.append(clinical_text)
            fields_used.extend(record_fields)

    if medical_reports:
        medical_report_text, medical_report_fields = _extract_medical_report_context(medical_reports)
        if medical_report_text.strip():
            patient_parts.append(f"Laudos médicos: {medical_report_text}")
            fields_used.extend(medical_report_fields)

    if not patient_parts:
        logger.warning(f"[PATIENT] Nenhum contexto clínico útil encontrado para '{patient_name}'.")
        return {
            **state,
            "patient_context": "",
            "patient_context_used": False,
            "patient_fields_used": [],
            "medical_reports_context": "",
            "medical_reports_used": False,
            "medical_reports_fields_used": [],
        }

    unique_fields = []
    seen = set()
    for field in fields_used:
        if field not in seen:
            seen.add(field)
            unique_fields.append(field)

    logger.info(
        "[PATIENT] Contexto clínico extraído: %d campo(s) — %s— %s",
        len(unique_fields),
        unique_fields,
        medical_report_fields,
    )

    return {
        **state,
        "patient_context": "\n\n".join(patient_parts),
        "patient_context_used": True,
        "patient_fields_used": unique_fields,
        "medical_reports_context": medical_report_text,
        "medical_reports_used": bool(medical_report_text.strip()),
        "medical_reports_fields_used": medical_report_fields,
    }
