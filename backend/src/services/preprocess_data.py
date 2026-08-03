import json
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


def _report_progress(
    doc_id: str,
    last_reported_percentage: int,
    current_percentage: int,
    results: Dict[str, Dict[str, int]],
) -> int:
    """Atualiza o progresso apenas quando houver avanço de pelo menos 5%."""
    if current_percentage >= last_reported_percentage + 5:
        update_preprocess_document(doc_id, results, current_percentage)
        return current_percentage
    return last_reported_percentage


def preprocess_data_background(rag_percent: float, doc_id: str) -> None:
    """
    Pipeline de pré-processamento executada em background.

    Etapas:
        1. Download dos datasets (step_one)
        2. Extração e geração dos arquivos JSON de treino e RAG (step_two)

    Atualiza o documento na collection preprocess conforme o progresso,
    rastreando o status de cada step individualmente.

    Args:
        rag_percent: Percentual de dados para RAG (0.0 a 1.0).
        doc_id: ID do documento na collection preprocess.
    """
    try:
        last_reported_percentage = 0
        
        # Inicializar estrutura de resultados
        results = {
            "QAs": {
                "train_data": 0,
                "rag_data": 0
            },
            "clinical_protocols": {
                "train_data": 0,
                "rag_data": 0
            }
        }

        # Marcar início do processamento
        update_preprocess_document(doc_id, results, 0)

        # ------------------------------------------------------------------
        # Step 1 — Download dos datasets
        # ------------------------------------------------------------------
        print("Step 1: Baixando datasets...")
        update_step_status(doc_id, "one_download_datasets", "in_progress")
        
        try:
            datasets = step_one.download_datasets()
            update_step_status(doc_id, "one_download_datasets", "completed")
        except Exception as e:
            error_message = f"Erro no download dos datasets: {e}"
            update_step_status(doc_id, "one_download_datasets", "error", error_message)
            raise

        last_reported_percentage = _report_progress(
            doc_id, last_reported_percentage, 20, results
        )

        qas_paths: Dict[str, str] = datasets["qas"]
        clinical_protocols_paths: Tuple[Path, Path] = datasets["clinical_protocols"]

        # ------------------------------------------------------------------
        # Step 2 — Extração e geração dos arquivos JSON
        # ------------------------------------------------------------------
        print("Step 2: Extraindo e processando dados QA...")
        update_step_status(doc_id, "step_two_data_extraction", "in_progress")
        
        try:
            train_qa_path, rag_qa_path, train_clinical_path, rag_clinical_path = step_two.extract_data(
                qas_paths=qas_paths,
                clinical_protocols_paths=clinical_protocols_paths,
                rag_percent=rag_percent,
            )

            qa_train_count = _read_json_count(train_qa_path)
            qa_rag_count = _read_json_count(rag_qa_path)
            clinical_train_count = _read_json_count(train_clinical_path)
            clinical_rag_count = _read_json_count(rag_clinical_path)
            
            # Atualizar resultados de QAs
            results["QAs"]["train_data"] = qa_train_count
            results["QAs"]["rag_data"] = qa_rag_count
            
            # Atualizar resultados de Clinical Protocols
            results["clinical_protocols"]["train_data"] = clinical_train_count
            results["clinical_protocols"]["rag_data"] = clinical_rag_count
            
            update_step_status(doc_id, "step_two_data_extraction", "completed")
            
        except Exception as e:
            error_message = f"Erro na extração de dados: {e}"
            update_step_status(doc_id, "step_two_data_extraction", "error", error_message)
            raise

        last_reported_percentage = _report_progress(
            doc_id, last_reported_percentage, 60, results
        )

        # ------------------------------------------------------------------
        # Step 3 — Tradução dos dados QA
        # ------------------------------------------------------------------
        print("Step 3: Traduzindo dados QA para português...")
        update_step_status(doc_id, "step_three_translating", "in_progress")

        try:
            translated_train_path, translated_rag_path = step_three.translate((train_qa_path, rag_qa_path))

            results["QAs"]["train_data"] = _read_json_count(translated_train_path)
            results["QAs"]["rag_data"] = _read_json_count(translated_rag_path)

            update_step_status(doc_id, "step_three_translating", "completed")
        except Exception as e:
            error_message = f"Erro na tradução de dados QA: {e}"
            update_step_status(doc_id, "step_three_translating", "error", error_message)
            raise

        last_reported_percentage = _report_progress(
            doc_id, last_reported_percentage, 90, results
        )

        # ------------------------------------------------------------------
        # Progresso final
        # ------------------------------------------------------------------
        _report_progress(doc_id, last_reported_percentage, 100, results)
        print(
            f"Pipeline concluída com sucesso! "
            f"QAs: train={results['QAs']['train_data']} | rag={results['QAs']['rag_data']} | "
            f"Clinical Protocols: train={results['clinical_protocols']['train_data']} | rag={results['clinical_protocols']['rag_data']}"
        )

    except Exception as e:
        error_message = f"Erro no processamento background: {e}"
        print(error_message)
        # Tentar identificar qual step falhou baseado no status atual
        current_doc = None
        try:
            from infra.database.collections.preprocess import get_preprocess_document
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
    rag_percent: float = 0.5,
    background_tasks: BackgroundTasks = None,
) -> Dict[str, Any]:
    """
    Inicia a pipeline de pré-processamento de dados.

    Cria um documento na collection preprocess e agenda a execução da pipeline
    em background.

    Args:
        rag_percent: Percentual de dados para RAG (0.0 a 1.0).
        background_tasks: Instância de BackgroundTasks do FastAPI para execução assíncrona.

    Returns:
        Dict com o documento criado (incluindo _id).

    Raises:
        HTTPException: Em caso de parâmetros inválidos.
    """
    if not isinstance(rag_percent, (int, float)):
        raise HTTPException(
            status_code=400,
            detail="rag_percent deve ser um número",
        )
    if not 0.0 <= rag_percent <= 1.0:
        raise HTTPException(
            status_code=400,
            detail="rag_percent deve estar entre 0.0 e 1.0",
        )

    document = create_preprocess_document(rag_percent=rag_percent)
    doc_id = document["_id"]

    if background_tasks:
        background_tasks.add_task(preprocess_data_background, rag_percent, doc_id)
    else:
        # Execução síncrona (testes / linha de comando)
        preprocess_data_background(rag_percent, doc_id)

    return document


if __name__ == "__main__":
    preprocess_data()
