"""
Nó 3.1: Recuperador de Contexto do Paciente (Patient Context Retriever)

Implementa o roteamento entre as jornadas do assistente médico:

- **Jornada 1 (Q&A genérico)**: `patient_name` ausente no payload → nó é um
  no-op. Retorna `patient_context_used = False` sem qualquer chamada ao backend.

- **Jornada 2 (Consulta por paciente)**: `patient_name` preenchido → busca o
  prontuário no MongoDB via endpoint do backend, extrai apenas os campos
  clínicos relevantes (sem identificação pessoal) e injeta o contexto no estado.

O nó nunca bloqueia o pipeline. Se o prontuário não for encontrado, degrada
silenciosamente para Jornada 1 com `patient_context_used = False`.
"""
import logging
import os
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://localhost:3000")
MEDICAL_RECORD_ENDPOINT = f"{BACKEND_API_URL}/medical-record"


# ---------------------------------------------------------------------------
# Extração de campos clínicos (sem dados de identificação)
# ---------------------------------------------------------------------------

def _extract_clinical_fields(record: Dict[str, Any]) -> tuple[str, List[str]]:
    """
    Extrai campos clínicos relevantes de um prontuário, omitindo completamente
    quaisquer dados de identificação do paciente (nome, telefone, etc.).

    Args:
        record: Documento de prontuário do MongoDB.

    Returns:
        Tupla (texto_clinico, lista_de_campos_usados).
    """
    parts: List[str] = []
    fields_used: List[str] = []

    # --- Avaliação (diagnósticos) ---
    avaliacao = record.get("avaliacao") or record.get("soap", {}).get("avaliacao")
    if avaliacao:
        if isinstance(avaliacao, dict):
            itens = avaliacao.get("itens") or avaliacao.get("diagnosticos", [])
            texto = "; ".join(str(i) for i in itens) if itens else str(avaliacao)
        else:
            texto = str(avaliacao)
        if texto.strip():
            parts.append(f"Diagnosticos/Avaliacao: {texto.strip()}")
            fields_used.append("avaliacao")

    # --- Plano / Prescrição (medicamentos) ---
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

    # --- Alergias ---
    alergias = record.get("alergias") or record.get("soap", {}).get("alergias")
    if alergias:
        texto = ", ".join(str(a) for a in alergias) if isinstance(alergias, list) else str(alergias)
        if texto.strip():
            parts.append(f"Alergias: {texto.strip()}")
            fields_used.append("alergias")

    # --- Objetivo (vitais e exames) ---
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

    clinical_text = "\n".join(parts)
    return clinical_text, fields_used


# ---------------------------------------------------------------------------
# Chamada ao backend
# ---------------------------------------------------------------------------

def _fetch_medical_record(patient_name: str) -> Optional[Dict[str, Any]]:
    """
    Busca o prontuário do paciente via endpoint do backend.

    Args:
        patient_name: Nome completo do paciente.

    Returns:
        Primeiro prontuário encontrado ou None.
    """
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
        logger.error(
            f"[PATIENT] Não foi possível conectar ao backend em {MEDICAL_RECORD_ENDPOINT}."
        )
        return None
    except requests.exceptions.Timeout:
        logger.error("[PATIENT] Timeout ao buscar prontuário.")
        return None
    except requests.exceptions.RequestException as exc:
        logger.error(f"[PATIENT] Erro ao buscar prontuário: {exc}")
        return None


# ---------------------------------------------------------------------------
# Nó LangGraph
# ---------------------------------------------------------------------------

def patient_context_retriever_node(state: dict) -> dict:
    """
    Nó LangGraph: determina a jornada e, se Jornada 2, busca o prontuário.

    Lê:
    - `state['patient_name']` — campo explícito do payload (seletor de jornada)

    Escreve:
    - `state['patient_context']` — texto clínico anonimizado (vazio se J1)
    - `state['patient_context_used']` — True se prontuário foi encontrado
    - `state['patient_fields_used']` — campos extraídos do prontuário

    Roteamento:
    - patient_name ausente/vazio → Jornada 1 (no-op)
    - patient_name preenchido + prontuário encontrado → Jornada 2
    - patient_name preenchido + não encontrado → degrada para Jornada 1

    Args:
        state: Estado atual do grafo LangGraph.

    Returns:
        Estado atualizado.
    """
    patient_name = (state.get("patient_name") or "").strip()

    if not patient_name:
        # Jornada 1 — sem paciente referenciado, nó é no-op
        logger.info("[PATIENT] Jornada 1 — patient_name ausente, nenhuma consulta ao prontuário.")
        return {
            **state,
            "patient_context": "",
            "patient_context_used": False,
            "patient_fields_used": [],
        }

    # Jornada 2 — busca prontuário
    logger.info(f"[PATIENT] Jornada 2 — buscando prontuário para: '{patient_name}'")
    record = _fetch_medical_record(patient_name)

    if not record:
        logger.warning(
            f"[PATIENT] Prontuário não encontrado para '{patient_name}'. "
            "Degradando para Jornada 1."
        )
        return {
            **state,
            "patient_context": "",
            "patient_context_used": False,
            "patient_fields_used": [],
        }

    clinical_text, fields_used = _extract_clinical_fields(record)

    if not clinical_text.strip():
        logger.warning(
            f"[PATIENT] Prontuário encontrado mas sem campos clínicos extraíveis "
            f"para '{patient_name}'. Degradando para Jornada 1."
        )
        return {
            **state,
            "patient_context": "",
            "patient_context_used": False,
            "patient_fields_used": [],
        }

    logger.info(
        f"[PATIENT] Contexto clínico extraído: {len(fields_used)} campo(s) — "
        f"{fields_used}"
    )

    return {
        **state,
        "patient_context": clinical_text,
        "patient_context_used": True,
        "patient_fields_used": fields_used,
    }
