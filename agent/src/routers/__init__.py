"""
Carregamento dinâmico de routers — padrão do backend principal.
"""
import importlib
import os
from pathlib import Path
from typing import List

from fastapi import APIRouter


def get_all_routers() -> List[APIRouter]:
    """
    Descobre e carrega todos os routers do pacote `routers`.

    Varre os arquivos .py do diretório (exceto __init__.py) e importa
    o atributo `router` de cada módulo.

    Returns:
        Lista de instâncias APIRouter prontas para incluir na aplicação.
    """
    routers: List[APIRouter] = []
    routers_dir = Path(__file__).parent

    for file in sorted(routers_dir.glob("*.py")):
        if file.name.startswith("_"):
            continue
        module_name = f"routers.{file.stem}"
        try:
            module = importlib.import_module(module_name)
            if hasattr(module, "router"):
                routers.append(module.router)
        except Exception as exc:
            print(f"[ROUTERS] Falha ao carregar {module_name}: {exc}")

    return routers
