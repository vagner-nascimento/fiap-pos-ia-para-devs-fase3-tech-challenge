import importlib
import pkgutil
from typing import List
from fastapi import APIRouter


def get_all_routers() -> List[APIRouter]:
    """
    Carrega dinamicamente todos os routers do pacote routers.
    
    Esta função descobre todos os módulos Python no pacote routers,
    importa cada um e extrai os objetos APIRouter definidos neles.
    
    Returns:
        List[APIRouter]: Lista de todos os APIRouter encontrados nos módulos.
    """
    routers: List[APIRouter] = []
    
    # Importar o próprio pacote routers
    package_name = "routers"
    package = importlib.import_module(f"{package_name}")
    
    # Descobrir todos os módulos no pacote
    for importer, module_name, ispkg in pkgutil.iter_modules(package.__path__):
        if not ispkg and not module_name.startswith("_"):
            try:
                # Importar o módulo dinamicamente
                full_module_name = f"{package_name}.{module_name}"
                module = importlib.import_module(full_module_name)
                
                # Procurar por APIRouter no módulo
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if isinstance(attr, APIRouter):
                        routers.append(attr)
                        print(f"Router carregado: {module_name}.{attr_name}")
                        
            except Exception as e:
                print(f"Erro ao carregar módulo {module_name}: {e}")
                continue
    
    return routers
