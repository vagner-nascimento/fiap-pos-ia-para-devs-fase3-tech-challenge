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


def _get_dataset_root() -> str:
    """Resolve the dataset root for both local and container executions."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.abspath(os.path.join(script_dir, "..", ".."))
    candidates = [
        os.path.join(backend_dir, "datasets"),
        os.path.abspath(os.path.join(backend_dir, "..", "datasets")),
    ]
    for candidate in candidates:
        if os.path.isdir(candidate):
            return candidate
    return os.path.join(backend_dir, "datasets")


def _get_preprocessed_paths() -> Dict[str, str]:
    """Return the canonical preprocessed artifact paths used by the pipeline."""
    dataset_root = _get_dataset_root()
    return {
        "qas": os.path.join(dataset_root, "preprocessed", "qas", "qas_train.json"),
        "clinical": os.path.join(
            dataset_root,
            "preprocessed",
            "clinical_protocols",
            "clinical_protocols_rag.json",
        ),
        "laudos": os.path.join(dataset_root, "preprocessed", "laudos_medicos", "laudos_medicos.json"),
    }


def _is_valid_preprocessed_file(file_path: str | None) -> bool:
    """Return whether a preprocessed JSON artifact is present and non-empty."""
    if not file_path or not os.path.exists(file_path):
        return False

    try:
        with open(file_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception:
        return False

    if not isinstance(payload, list):
        return False

    return len(payload) > 0


def _get_valid_preprocessed_cache(expected_laudos: bool = False) -> Dict[str, Any] | None:
    """Return a valid cache snapshot only when all required preprocessed artifacts exist."""
    preprocessed_paths = _get_preprocessed_paths()
    qas_valid = _is_valid_preprocessed_file(preprocessed_paths["qas"])
    clinical_valid = _is_valid_preprocessed_file(preprocessed_paths["clinical"])
    laudos_valid = True if not expected_laudos else _is_valid_preprocessed_file(preprocessed_paths["laudos"])

    if not (qas_valid and clinical_valid and laudos_valid):
        return None

    return {
        "qas": preprocessed_paths["qas"],
        "clinical": preprocessed_paths["clinical"],
        "laudos": preprocessed_paths["laudos"],
    }


def preprocess_data_background(doc_id: str, skip_translation: bool = False) -> None:
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
            "laudos_medicos_path": None,
            "qas_count": 0,
            "clinical_protocols_count": 0,
            "laudos_medicos_count": 0
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
        pcdt_paths: Tuple[Path, Path] = datasets.get("pcdt")
        laudos_path: Path = datasets.get("laudos_medicos")

        # ------------------------------------------------------------------
        # Step 2 — Extração e geração dos arquivos JSON
        # ------------------------------------------------------------------
        print("Step 2: Extraindo e processando dados QA...")
        update_step_status(doc_id, "two_data_extraction", "in_progress", completion_percentage=0)
        
        # Verifica se a saída pré-processada já é um cache válido e reaproveita apenas quando
        # todos os artefatos críticos foram gerados corretamente.
        try:
            preprocessed_cache = _get_valid_preprocessed_cache(expected_laudos=laudos_path is not None)

            if preprocessed_cache is not None:
                qas_train_path = preprocessed_cache["qas"]
                qas_count = _read_json_count(qas_train_path)

                clinical_protocols_rag_path = preprocessed_cache["clinical"]
                clinical_protocols_count = _read_json_count(clinical_protocols_rag_path)

                laudos_medicos_path = preprocessed_cache["laudos"] if preprocessed_cache.get("laudos") else None
                laudos_medicos_count = _read_json_count(laudos_medicos_path) if laudos_medicos_path else 0

                print(
                    f"Cache pré-processado válido encontrado em {qas_train_path} e "
                    f"{clinical_protocols_rag_path}; reutilizando artefatos extraídos."
                )

                results["qas_train_path"] = _get_relative_path(qas_train_path)
                results["clinical_protocols_rag_path"] = _get_relative_path(clinical_protocols_rag_path)
                results["qas_count"] = qas_count
                results["clinical_protocols_count"] = clinical_protocols_count
                if laudos_medicos_path:
                    results["laudos_medicos_path"] = _get_relative_path(laudos_medicos_path)
                results["laudos_medicos_count"] = laudos_medicos_count

                update_step_status(
                    doc_id,
                    "two_data_extraction",
                    "completed",
                    completion_percentage=100,
                )
                update_preprocess_document(doc_id, results, _current_overall_percentage())

            else:
                # Nenhum cache válido encontrado — executar extração completa
                args = [doc_id, qas_paths, clinical_protocols_paths]
                if pcdt_paths is not None:
                    args.append(pcdt_paths)
                if laudos_path is not None:
                    args.append(laudos_path)
                extraction = step_two.extract_data(*args)

                # Suporte para duas possíveis assinaturas de retorno de extract_data:
                # - dicionário com chaves (qas_train_path, qas_count, clinical_protocols_rag_path, clinical_protocols_count, ...)
                # - tupla/lista com valores (qas_train_path, qas_count, clinical_protocols_rag_path, clinical_protocols_count[, laudos_medicos_path, laudos_medicos_count])
                if isinstance(extraction, dict):
                    qas_train_path = extraction.get("qas_train_path")
                    qas_count = extraction.get("qas_count", 0)
                    clinical_protocols_rag_path = extraction.get("clinical_protocols_rag_path")
                    clinical_protocols_count = extraction.get("clinical_protocols_count", 0)
                    laudos_medicos_path = extraction.get("laudos_medicos_path", "")
                    laudos_medicos_count = extraction.get("laudos_medicos_count", 0)
                else:
                    # seq handling
                    if len(extraction) >= 4:
                        qas_train_path, qas_count, clinical_protocols_rag_path, clinical_protocols_count = extraction[:4]
                        if len(extraction) >= 6:
                            laudos_medicos_path, laudos_medicos_count = extraction[4], extraction[5]
                        else:
                            laudos_medicos_path = ""
                            laudos_medicos_count = 0
                    else:
                        raise ValueError("Unexpected return type from step_two.extract_data")

                # Atualizar resultados com paths e counts
                results["qas_train_path"] = _get_relative_path(qas_train_path)
                results["clinical_protocols_rag_path"] = _get_relative_path(clinical_protocols_rag_path)
                results["qas_count"] = qas_count
                results["clinical_protocols_count"] = clinical_protocols_count
                if laudos_medicos_path:
                    results["laudos_medicos_path"] = _get_relative_path(laudos_medicos_path)
                results["laudos_medicos_count"] = laudos_medicos_count

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
            if skip_translation:
                print("Step 3: Pulando tradução (utilizando dados fixos)...")
                fixed_path = os.path.join("datasets", "preprocessed", "fixed", "qas", "qas_train_pt_br.json")
                results["qas_train_pt_br_path"] = fixed_path
            else:
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
            f"Clinical Protocols: count={results['clinical_protocols_count']} | "
            f"Laudos Médicos: count={results['laudos_medicos_count']}"
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
    skip_translation: bool = False,
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
        background_tasks.add_task(preprocess_data_background, doc_id, skip_translation)
    else:
        # Execução síncrona (testes / linha de comando)
        preprocess_data_background(doc_id, skip_translation)

    return document


if __name__ == "__main__":
    preprocess_data()
