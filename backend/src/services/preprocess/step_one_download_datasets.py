import os
import sys
from pathlib import Path
from typing import Dict, Tuple, Union

# Adicionar o diretório datasets ao path para importar get_datasets
script_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(script_dir, "..", "..", ".."))
datasets_dir = os.path.join(backend_dir, "datasets")
sys.path.insert(0, datasets_dir)

# Script em datasets/get_datasets.py
# pyrefly: ignore [missing-import]
from get_datasets import clone_qa_repositories, download_fhemig_clinical_protocols


def download_datasets() -> Dict[str, Union[Dict[str, str], Tuple[Path, Path]]]:
    """
    Baixa todos os datasets necessários para o pré-processamento.

    Returns:
        dict com:
            "qas": dict[str, str] mapeando nome do repositório -> path local
            "clinical_protocols": tuple[Path, Path] com (json_path, pdfs_dir)
    """
    qas_paths = clone_qa_repositories()
    clinical_protocols_paths = download_fhemig_clinical_protocols()

    return {
        "qas": qas_paths,
        "clinical_protocols": clinical_protocols_paths,
    }