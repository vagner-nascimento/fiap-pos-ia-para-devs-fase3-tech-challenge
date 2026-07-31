import os
import json
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Tuple
from fastapi import HTTPException, BackgroundTasks
import sys

# Adicionar o diretório datasets ao path para importar clone_datasets
script_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(script_dir, "..", ".."))
datasets_dir = os.path.join(backend_dir, "datasets")
sys.path.insert(0, datasets_dir)

# Script em datasets/clone_datasets.py
from clone_datasets import clone_repositories
from infra.database.collections.preprocess import (
    create_preprocess_document,
    mark_preprocess_document_failed,
    update_preprocess_document,
)


def split_dataset_for_rag(data: List[Dict[str, Any]], rag_percent: float) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Divide uma base de dados em porções para treino e RAG.

    O percentual informado é aplicado à base inteira, então para um valor de
    0.5, cada base recebe 50% de dados para o RAG.
    """
    if not data:
        return [], []

    num_rag = int(len(data) * rag_percent)
    rag_data = data[:num_rag]
    remaining_data = data[num_rag:]
    return rag_data, remaining_data


def _report_progress(
    doc_id: str,
    last_reported_percentage: int,
    current_percentage: int,
    train_data_count: int,
    rag_data_count: int,
) -> int:
    """Atualiza o progresso apenas quando houver avanço de pelo menos 5%."""
    if current_percentage >= last_reported_percentage + 5:
        update_preprocess_document(doc_id, train_data_count, rag_data_count, current_percentage)
        return current_percentage
    return last_reported_percentage


def preprocess_data_background(rag_percent: float, doc_id: str) -> None:
    """
    Função de background que executa o processamento de dados.
    
    Atualiza o documento na collection preprocess conforme o progresso.
    
    Args:
        rag_percent: Percentual de dados MedQuAD para RAG (0.0 a 1.0).
        doc_id: ID do documento na collection preprocess.
    """
    try:
        # Atualizar status para in_progress
        update_preprocess_document(doc_id, 0, 0, 0)
        
        # Clonar os repositórios de datasets antes de iniciar o pré-processamento
        print("Clonando repositórios de datasets...")
        clone_repositories()
        
        pubmedqa_path = os.path.join(datasets_dir, "files", "pubmedqa", "data", "ori_pqal.json")
        medquad_dir = os.path.join(datasets_dir, "files", "MedQuAD")
        preprocessed_dir = os.path.join(datasets_dir, "preprocessed")
        
        train_path = os.path.join(preprocessed_dir, "train.json")
        rag_path = os.path.join(preprocessed_dir, "rag.json")
        
        # Criar pasta de preprocessed se não existir
        os.makedirs(preprocessed_dir, exist_ok=True)
        
        print("Processando dados de PubMedQA...")
        pubmedqa_entries: List[Dict[str, Any]] = []
        last_reported_percentage = 0
        
        # 1. Processar PubMedQA
        if os.path.exists(pubmedqa_path):
            try:
                with open(pubmedqa_path, "r", encoding="utf-8") as f:
                    pubmed_raw = json.load(f)
            except json.JSONDecodeError as e:
                error_message = f"Erro ao ler arquivo PubMedQA: formato JSON inválido - {str(e)}"
                print(error_message)
                mark_preprocess_document_failed(doc_id, error_message)
                return
            except Exception as e:
                error_message = f"Erro ao ler arquivo PubMedQA: {str(e)}"
                print(error_message)
                mark_preprocess_document_failed(doc_id, error_message)
                return

            total_pubmedqa_entries = len(pubmed_raw)
            for index, (pmid, entry) in enumerate(pubmed_raw.items(), start=1):
                question = entry.get("QUESTION", "").strip()
                contexts = entry.get("CONTEXTS", [])
                answer = entry.get("LONG_ANSWER", "").strip()
                
                pubmedqa_entries.append({
                    "question": question,
                    "contexts": contexts,
                    "answer": answer,
                    "metadata": {
                        "source": "pubmedqa",
                        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
                    }
                })

                if total_pubmedqa_entries > 0:
                    progress_percentage = int((index / total_pubmedqa_entries) * 50)
                    last_reported_percentage = _report_progress(
                        doc_id,
                        last_reported_percentage,
                        progress_percentage,
                        0,
                        0,
                    )
            print(f"PubMedQA processado: {len(pubmedqa_entries)} registros adicionados ao dataset.")
            
            # Garantir que o progresso avance até a metade do fluxo
            last_reported_percentage = _report_progress(doc_id, last_reported_percentage, 50, 0, 0)
        else:
            print(f"Aviso: Arquivo PubMedQA não encontrado em {pubmedqa_path}")
            
        # 2. Processar MedQuAD
        print("Processando dados de MedQuAD...")
        medquad_entries: List[Dict[str, Any]] = []
        
        if os.path.exists(medquad_dir):
            try:
                xml_files = []
                for root_dir, _, files in os.walk(medquad_dir):
                    for file in files:
                        if file.endswith(".xml"):
                            xml_files.append(os.path.join(root_dir, file))

                total_xml_files = len(xml_files)
                processed_xml_files = 0

                for xml_path in xml_files:
                    try:
                        tree = ET.parse(xml_path)
                        root_elem = tree.getroot()
                        
                        doc_source = root_elem.attrib.get("source", "").strip()
                        doc_url = root_elem.attrib.get("url", "").strip()
                        
                        qa_pairs = root_elem.find("QAPairs")
                        if qa_pairs is not None:
                            for qa_pair in qa_pairs.findall("QAPair"):
                                question_elem = qa_pair.find("Question")
                                answer_elem = qa_pair.find("Answer")
                                
                                if question_elem is not None and answer_elem is not None:
                                    q_text = (question_elem.text or "").strip()
                                    a_text = "".join(answer_elem.itertext()).strip()
                                    
                                    # Colete dados somente das questions que contêm Answer preenchida
                                    if q_text and a_text:
                                        medquad_entries.append({
                                            "question": q_text,
                                            "contexts": [],
                                            "answer": a_text,
                                            "metadata": {
                                                "source": doc_source or "MedQuAD",
                                                "url": doc_url or ""
                                            }
                                        })
                    except ET.ParseError as e:
                        print(f"Erro ao processar arquivo XML {xml_path}: {e}")
                    except Exception as e:
                        print(f"Erro ao processar arquivo XML {xml_path}: {e}")

                    processed_xml_files += 1
                    if total_xml_files > 0:
                        progress_percentage = 50 + int((processed_xml_files / total_xml_files) * 40)
                        last_reported_percentage = _report_progress(
                            doc_id,
                            last_reported_percentage,
                            progress_percentage,
                            0,
                            0,
                        )
            except Exception as e:
                error_message = f"Erro ao processar diretório MedQuAD: {str(e)}"
                print(error_message)
                mark_preprocess_document_failed(doc_id, error_message)
                return
            
            print(f"MedQuAD processado: {len(medquad_entries)} registros com respostas preenchidas encontrados.")
            
            # Garantir que o progresso avance até 90% antes da separação e salvamento
            last_reported_percentage = _report_progress(doc_id, last_reported_percentage, 90, 0, 0)
        else:
            print(f"Aviso: Diretório MedQuAD não encontrado em {medquad_dir}")
            
        # 3. Separar os dados de PubMedQA e MedQuAD entre RAG e Train
        pubmedqa_rag, pubmedqa_train = split_dataset_for_rag(pubmedqa_entries, rag_percent)
        medquad_rag, medquad_train = split_dataset_for_rag(medquad_entries, rag_percent)
        
        rag_data = pubmedqa_rag + medquad_rag
        train_data = pubmedqa_train + medquad_train
        
        # Atualizar progresso após separação (aprox 95%)
        last_reported_percentage = _report_progress(
            doc_id,
            last_reported_percentage,
            95,
            len(train_data),
            len(rag_data),
        )
        
        # 4. Salvar arquivos
        print(f"Salvando {len(train_data)} registros em {train_path}...")
        try:
            with open(train_path, "w", encoding="utf-8") as f:
                json.dump(train_data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            error_message = f"Erro ao salvar arquivo train.json: {str(e)}"
            print(error_message)
            mark_preprocess_document_failed(doc_id, error_message)
            return
            
        print(f"Salvando {len(rag_data)} registros em {rag_path}...")
        try:
            with open(rag_path, "w", encoding="utf-8") as f:
                json.dump(rag_data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            error_message = f"Erro ao salvar arquivo rag.json: {str(e)}"
            print(error_message)
            mark_preprocess_document_failed(doc_id, error_message)
            return
            
        print("Processamento concluído com sucesso!")
        
        # Atualizar progresso final (100%)
        _report_progress(doc_id, last_reported_percentage, 100, len(train_data), len(rag_data))
        
    except Exception as e:
        error_message = f"Erro no processamento background: {str(e)}"
        print(error_message)
        mark_preprocess_document_failed(doc_id, error_message)


def preprocess_data(rag_percent: float = 0.5, background_tasks: BackgroundTasks = None) -> Dict[str, Any]:
    """
    Processa dados de PubMedQA e MedQuAD, separando em conjuntos de treino e RAG.
    
    Cria um documento na collection preprocess e inicia o processamento em background.
    
    Args:
        rag_percent: Percentual de dados MedQuAD para RAG (0.0 a 1.0).
        background_tasks: Instância de BackgroundTasks do FastAPI para execução assíncrona.
        
    Returns:
        Dict com o documento criado (incluindo _id).
        
    Raises:
        HTTPException: Em caso de erro no processamento.
    """
    # Validar rag_percent
    if not isinstance(rag_percent, (int, float)):
        raise HTTPException(
            status_code=400,
            detail="rag_percent deve ser um número"
        )
    if not 0.0 <= rag_percent <= 1.0:
        raise HTTPException(
            status_code=400,
            detail="rag_percent deve estar entre 0.0 e 1.0"
        )
    
    # Criar documento na collection preprocess
    document = create_preprocess_document()
    doc_id = document["_id"]
    
    # Adicionar tarefa de background para processamento
    if background_tasks:
        background_tasks.add_task(preprocess_data_background, rag_percent, doc_id)
    else:
        # Se não houver background_tasks, executar sincronamente (para testes)
        preprocess_data_background(rag_percent, doc_id)
    
    # Retornar o documento criado imediatamente
    return document

if __name__ == "__main__":
    preprocess_data()

# TODO chamar a func do banco de dados para atualização em caso de erros.
