import os
import json
import xml.etree.ElementTree as ET
from typing import List, Dict, Any
from fastapi import HTTPException, BackgroundTasks
import sys

# Adicionar o diretório datasets ao path para importar clone_datasets
script_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(script_dir, "..", ".."))
datasets_dir = os.path.join(backend_dir, "datasets")
sys.path.insert(0, datasets_dir)

from clone_datasets import clone_repositories
from infra.database.collections.preprocess import (
    create_preprocess_document,
    update_preprocess_document
)


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
        train_data: List[Dict[str, Any]] = []
        
        # 1. Processar PubMedQA
        if os.path.exists(pubmedqa_path):
            try:
                with open(pubmedqa_path, "r", encoding="utf-8") as f:
                    pubmed_raw = json.load(f)
            except json.JSONDecodeError as e:
                print(f"Erro ao ler arquivo PubMedQA: formato JSON inválido - {str(e)}")
                update_preprocess_document(doc_id, 0, 0, 0)
                return
            except Exception as e:
                print(f"Erro ao ler arquivo PubMedQA: {str(e)}")
                update_preprocess_document(doc_id, 0, 0, 0)
                return
                
            for pmid, entry in pubmed_raw.items():
                question = entry.get("QUESTION", "").strip()
                contexts = entry.get("CONTEXTS", [])
                answer = entry.get("LONG_ANSWER", "").strip()
                
                train_data.append({
                    "question": question,
                    "contexts": contexts,
                    "answer": answer,
                    "metadata": {
                        "source": "pubmedqa",
                        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
                    }
                })
            print(f"PubMedQA processado: {len(train_data)} registros adicionados ao train_data.")
            
            # Atualizar progresso após PubMedQA (aprox 25%)
            update_preprocess_document(doc_id, len(train_data), 0, 25)
        else:
            print(f"Aviso: Arquivo PubMedQA não encontrado em {pubmedqa_path}")
            
        # 2. Processar MedQuAD
        print("Processando dados de MedQuAD...")
        medquad_entries: List[Dict[str, Any]] = []
        
        if os.path.exists(medquad_dir):
            try:
                for root_dir, _, files in os.walk(medquad_dir):
                    for file in files:
                        if file.endswith(".xml"):
                            xml_path = os.path.join(root_dir, file)
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
            except Exception as e:
                print(f"Erro ao processar diretório MedQuAD: {str(e)}")
                update_preprocess_document(doc_id, len(train_data), 0, 25)
                return
            
            print(f"MedQuAD processado: {len(medquad_entries)} registros com respostas preenchidas encontrados.")
            
            # Atualizar progresso após MedQuAD (aprox 50%)
            update_preprocess_document(doc_id, len(train_data), 0, 50)
        else:
            print(f"Aviso: Diretório MedQuAD não encontrado em {medquad_dir}")
            
        # 3. Separar MedQuAD entre RAG e Train de acordo com o percentual informado
        num_rag = int(len(medquad_entries) * rag_percent)
        
        rag_data = medquad_entries[:num_rag]
        remaining_medquad = medquad_entries[num_rag:]
        
        # Adicionar os dados restantes ao train_data
        train_data.extend(remaining_medquad)
        
        # Atualizar progresso após separação (aprox 75%)
        update_preprocess_document(doc_id, len(train_data), len(rag_data), 75)
        
        # 4. Salvar arquivos
        print(f"Salvando {len(train_data)} registros em {train_path}...")
        try:
            with open(train_path, "w", encoding="utf-8") as f:
                json.dump(train_data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Erro ao salvar arquivo train.json: {str(e)}")
            update_preprocess_document(doc_id, len(train_data), len(rag_data), 75)
            return
            
        print(f"Salvando {len(rag_data)} registros em {rag_path}...")
        try:
            with open(rag_path, "w", encoding="utf-8") as f:
                json.dump(rag_data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Erro ao salvar arquivo rag.json: {str(e)}")
            update_preprocess_document(doc_id, len(train_data), len(rag_data), 75)
            return
            
        print("Processamento concluído com sucesso!")
        
        # Atualizar progresso final (100%)
        update_preprocess_document(doc_id, len(train_data), len(rag_data), 100)
        
    except Exception as e:
        print(f"Erro no processamento background: {str(e)}")
        # Em caso de erro, atualizar com o último progresso conhecido


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
