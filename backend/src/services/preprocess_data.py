import json
import os
from typing import Dict, Any, Tuple
from anyio import Path
from fastapi import HTTPException, BackgroundTasks

from infra.database.collections.preprocess import (
    create_preprocess_document,
    get_preprocess_document,
    mark_preprocess_document_failed,
    update_preprocess_document,
    update_step_status,
)
from services.preprocess import step_one_download_datasets as step_one
from services.preprocess import step_two_data_extraction as step_two
from services.preprocess import step_three_translation as step_three


def _read_json_count(file_path: str) -> int:
    """Retorna a quantidade de itens em um arquivo JSON, caso exista."""
    try:
        with open(file_path, "r", encoding="utf-8") as handle:
            return len(json.load(handle))
    except Exception:
        return 0


def _get_relative_path(absolute_path: str) -> str:
    """Convert absolute path to relative path from backend directory."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.abspath(os.path.join(script_dir, "..", ".."))
    try:
        return os.path.relpath(absolute_path, backend_dir)
    except ValueError:
        # If paths are on different drives, return absolute path
        return absolute_path


def preprocess_data_background(doc_id: str) -> None:
    """
    Pipeline de pré-processamento executada em background.

    Etapas:
        1. Download dos datasets (step_one)
        2. Extração e geração dos arquivos JSON (step_two)
        3. Tradução dos dados QA (step_three)

    Atualiza o documento na collection preprocess conforme o progresso,
    rastreando o status de cada step individualmente.

    Args:
        doc_id: ID do documento na collection preprocess.
    """
    try:
        def _current_overall_percentage() -> float:
            current_doc = get_preprocess_document(doc_id)
            if not current_doc:
                return 0.0
            return float(current_doc.get("completion_percentage", 0.0))

        # Inicializar estrutura de resultados
        results = {
            "qas_train_path": None,
            "qas_train_pt_br_path": None,
            "clinical_protocols_rag_path": None,
            "qas_count": 0,
            "clinical_protocols_count": 0
        }

        # Marcar início do processamento
        update_preprocess_document(doc_id, results, 0)

        # ------------------------------------------------------------------
        # Step 1 — Download dos datasets
        # ------------------------------------------------------------------
        print("Step 1: Baixando datasets...")
        update_step_status(doc_id, "one_download_datasets", "in_progress", completion_percentage=0)

        try:
            datasets = step_one.download_datasets(doc_id)
        except Exception as e:
            error_message = f"Erro no download dos datasets: {e}"
            update_step_status(doc_id, "one_download_datasets", "error", error_message, completion_percentage=0)
            raise

        qas_paths: Dict[str, str] = datasets["qas"]
        clinical_protocols_paths: Tuple[Path, Path] = datasets["clinical_protocols"]

        # ------------------------------------------------------------------
        # Step 2 — Extração e geração dos arquivos JSON
        # ------------------------------------------------------------------
        print("Step 2: Extraindo e processando dados QA...")
        update_step_status(doc_id, "two_data_extraction", "in_progress", completion_percentage=0)
        
        try:
            qas_train_path, qas_count, clinical_protocols_rag_path, clinical_protocols_count = step_two.extract_data(
                doc_id,
                qas_paths=qas_paths,
                clinical_protocols_paths=clinical_protocols_paths,
            )

            # Atualizar resultados com paths e counts
            results["qas_train_path"] = _get_relative_path(qas_train_path)
            results["clinical_protocols_rag_path"] = _get_relative_path(clinical_protocols_rag_path)
            results["qas_count"] = qas_count
            results["clinical_protocols_count"] = clinical_protocols_count
            
            update_step_status(
                doc_id,
                "two_data_extraction",
                "completed",
                completion_percentage=100,
            )
            update_preprocess_document(doc_id, results, _current_overall_percentage())
            
        except Exception as e:
            error_message = f"Erro na extração de dados: {e}"
            update_step_status(doc_id, "two_data_extraction", "error", error_message, completion_percentage=0)
            raise

        # ------------------------------------------------------------------
        # Step 3 — Tradução dos dados QA
        # ------------------------------------------------------------------
        print("Step 3: Traduzindo dados QA para português...")
        update_step_status(doc_id, "three_translating", "in_progress", completion_percentage=0)

        try:
            translated_train_path = step_three.translate(
                doc_id,
                qas_train_path,
            )

            results["qas_train_pt_br_path"] = _get_relative_path(str(translated_train_path))

            update_step_status(
                doc_id,
                "three_translating",
                "completed",
                completion_percentage=100,
            )
            update_preprocess_document(doc_id, results, _current_overall_percentage())
        except Exception as e:
            error_message = f"Erro na tradução de dados QA: {e}"
            update_step_status(doc_id, "three_translating", "error", error_message, completion_percentage=0)
            raise

        # ------------------------------------------------------------------
        # Progresso final
        # ------------------------------------------------------------------
        update_preprocess_document(doc_id, results, 100)
        print(
            f"Pipeline concluída com sucesso! "
            f"QAs: count={results['qas_count']} | "
            f"Clinical Protocols: count={results['clinical_protocols_count']}"
        )

    except Exception as e:
        error_message = f"Erro no processamento background: {e}"
        print(error_message)
        # Tentar identificar qual step falhou baseado no status atual
        current_doc = None
        try:
            current_doc = get_preprocess_document(doc_id)
        except Exception:
            pass
        
        if current_doc and "steps" in current_doc:
            # Encontrar o step que está em in_progress e marcar como error
            for step_name, step_info in current_doc["steps"].items():
                if step_info.get("status") == "in_progress":
                    update_step_status(doc_id, step_name, "error", error_message)
                    break
        else:
            # Fallback para método antigo se não conseguir identificar o step
            mark_preprocess_document_failed(doc_id, error_message)


def preprocess_data(
    background_tasks: BackgroundTasks = None,
) -> Dict[str, Any]:
    """
    Inicia a pipeline de pré-processamento de dados.

    Cria um documento na collection preprocess e agenda a execução da pipeline
    em background.

    Args:
        background_tasks: Instância de BackgroundTasks do FastAPI para execução assíncrona.

    Returns:
        Dict com o documento criado (incluindo _id).

    Raises:
        HTTPException: Em caso de parâmetros inválidos.
    """
    document = create_preprocess_document()
    doc_id = document["_id"]

    if background_tasks:
        background_tasks.add_task(preprocess_data_background, doc_id)
    else:
        # Execução síncrona (testes / linha de comando)
        preprocess_data_background(doc_id)

    return document


if __name__ == "__main__":
    preprocess_data()
