import os
import sys
from pathlib import Path
from typing import Dict, Tuple, Union

from infra.database.collections.preprocess import update_step_status

# Adicionar o diretório datasets ao path para importar get_datasets
script_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(script_dir, "..", "..", ".."))
datasets_dir = os.path.join(backend_dir, "datasets")
sys.path.insert(0, datasets_dir)

# Script em datasets/get_datasets.py
# pyrefly: ignore [missing-import]
from get_datasets import (
    clone_qa_repositories,
    download_fhemig_clinical_protocols,
    prepare_pcdt_protocols,
    prepare_laudos_medicos_dataset,
)


def download_datasets(
    doc_id: str,
) -> Dict[str, Union[Dict[str, str], Tuple[Path, Path], Path]]:
    """
    Baixa/prepara todos os datasets necessários para o pré-processamento.

    Returns:
        dict com:
            "qas": dict[str, str] mapeando nome do repositório -> path local
            "clinical_protocols": tuple[Path, Path] com (json_path, pdfs_dir) (FHEMIG)
            "pcdt": tuple[Path, Path] com (json_path, pdfs_dir) (PCDT local)
            "laudos_medicos": Path para o JSON de laudos médicos (pt-BR)
    """
    update_step_status(doc_id, "one_download_datasets", "in_progress", completion_percentage=0)
    qas_paths = clone_qa_repositories()
    update_step_status(doc_id, "one_download_datasets", "in_progress", completion_percentage=40)

    clinical_protocols_paths = download_fhemig_clinical_protocols()
    update_step_status(doc_id, "one_download_datasets", "in_progress", completion_percentage=70)

    # PCDT e laudos são arquivos locais versionados no repositório; apenas validam existência
    pcdt_paths = prepare_pcdt_protocols()
    laudos_path = prepare_laudos_medicos_dataset()
    update_step_status(doc_id, "one_download_datasets", "completed", completion_percentage=100)

    return {
        "qas": qas_paths,
        "clinical_protocols": clinical_protocols_paths,
        "pcdt": pcdt_paths,
        "laudos_medicos": laudos_path,
    }
