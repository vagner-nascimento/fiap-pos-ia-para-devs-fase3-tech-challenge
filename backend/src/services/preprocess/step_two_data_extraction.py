import os
import json
import re
import xml.etree.ElementTree as ET
from typing import Any, List, Dict, Tuple
from anyio import Path
import pdfplumber

# Resolver o diretório de datasets a partir deste arquivo
_script_dir = os.path.dirname(os.path.abspath(__file__))
_backend_dir = os.path.abspath(os.path.join(_script_dir, "..", "..", ".."))
_datasets_dir = os.path.join(_backend_dir, "datasets")


def _split_dataset_for_rag(
    data: List[Dict[str, Any]], rag_percent: float
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Divide uma lista de entradas em porções para RAG e treino.

    Retorna (rag_data, train_data).
    """
    if not data:
        return [], []
    num_rag = int(len(data) * rag_percent)
    return data[:num_rag], data[num_rag:]


def _extract_text_from_pdf(pdf_path: Path) -> str:
    """
    Extrai texto de um arquivo PDF usando pdfplumber.

    Args:
        pdf_path: Caminho para o arquivo PDF.

    Returns:
        Texto extraído do PDF. Retorna string vazia em caso de erro.
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text_content = []
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_content.append(page_text)
            return "\n".join(text_content)
    except Exception as e:
        print(f"Erro ao extrair texto do PDF {pdf_path}: {e}")
        return ""


def _extract_qas_data(
    qas_paths: Dict[str, str],
    rag_percent: float,
) -> Tuple[str, str]:
    """
    Processa os datasets de QA (PubMedQA e MedQuAD), separa entre treino e RAG
    e persiste os resultados em arquivos JSON.

    Args:
        qas_paths: Dicionário com as chaves "pubmedqa" e "MedQuAD" mapeando
                   para os respectivos diretórios clonados.
        rag_percent: Fração dos dados destinada ao RAG (0.0 a 1.0).

    Returns:
        Tupla (train_path, rag_path) com os caminhos absolutos dos arquivos gerados.
    """
    pubmedqa_path = os.path.join(
        qas_paths.get("pubmedqa", os.path.join(_datasets_dir, "files", "qas", "pubmedqa")),
        "data", "ori_pqal.json",
    )
    medquad_dir = qas_paths.get(
        "MedQuAD", os.path.join(_datasets_dir, "files", "qas", "MedQuAD")
    )
    preprocessed_dir = os.path.join(_datasets_dir, "preprocessed", "qas")

    train_path = os.path.join(preprocessed_dir, "train.json")
    rag_path = os.path.join(preprocessed_dir, "rag.json")

    os.makedirs(preprocessed_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # 1. Processar PubMedQA
    # ------------------------------------------------------------------
    print("Processando dados de PubMedQA...")
    pubmedqa_entries: List[Dict[str, Any]] = []

    if os.path.exists(pubmedqa_path):
        try:
            with open(pubmedqa_path, "r", encoding="utf-8") as f:
                pubmed_raw = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Erro ao ler arquivo PubMedQA: formato JSON inválido - {e}") from e
        except Exception as e:
            raise RuntimeError(f"Erro ao ler arquivo PubMedQA: {e}") from e

        for pmid, entry in pubmed_raw.items():
            question = entry.get("QUESTION", "").strip()
            contexts = entry.get("CONTEXTS", [])
            answer = entry.get("LONG_ANSWER", "").strip()

            pubmedqa_entries.append({
                "question": question,
                "contexts": contexts,
                "answer": answer,
                "metadata": {
                    "source": "pubmedqa",
                    "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                },
            })

        print(f"PubMedQA processado: {len(pubmedqa_entries)} registros adicionados ao dataset.")
    else:
        print(f"Aviso: Arquivo PubMedQA não encontrado em {pubmedqa_path}")

    # ------------------------------------------------------------------
    # 2. Processar MedQuAD
    # ------------------------------------------------------------------
    print("Processando dados de MedQuAD...")
    medquad_entries: List[Dict[str, Any]] = []

    if os.path.exists(medquad_dir):
        try:
            xml_files: List[str] = []
            for root_dir, _, files in os.walk(medquad_dir):
                for file in files:
                    if file.endswith(".xml"):
                        xml_files.append(os.path.join(root_dir, file))

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

                                # Coletar apenas pares com resposta preenchida
                                if q_text and a_text:
                                    medquad_entries.append({
                                        "question": q_text,
                                        "contexts": [],
                                        "answer": a_text,
                                        "metadata": {
                                            "source": doc_source or "MedQuAD",
                                            "url": doc_url or "",
                                        },
                                    })
                except ET.ParseError as e:
                    print(f"Erro ao processar arquivo XML {xml_path}: {e}")
                except Exception as e:
                    print(f"Erro ao processar arquivo XML {xml_path}: {e}")

        except Exception as e:
            raise RuntimeError(f"Erro ao processar diretório MedQuAD: {e}") from e

        print(
            f"MedQuAD processado: {len(medquad_entries)} registros com respostas "
            "preenchidas encontrados."
        )
    else:
        print(f"Aviso: Diretório MedQuAD não encontrado em {medquad_dir}")

    # ------------------------------------------------------------------
    # 3. Separar entre RAG e Treino
    # ------------------------------------------------------------------
    pubmedqa_rag, pubmedqa_train = _split_dataset_for_rag(pubmedqa_entries, rag_percent)
    medquad_rag, medquad_train = _split_dataset_for_rag(medquad_entries, rag_percent)

    rag_data = pubmedqa_rag + medquad_rag
    train_data = pubmedqa_train + medquad_train

    # ------------------------------------------------------------------
    # 4. Salvar arquivos JSON
    # ------------------------------------------------------------------
    print(f"Salvando {len(train_data)} registros em {train_path}...")
    try:
        with open(train_path, "w", encoding="utf-8") as f:
            json.dump(train_data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        raise RuntimeError(f"Erro ao salvar arquivo train.json: {e}") from e

    print(f"Salvando {len(rag_data)} registros em {rag_path}...")
    try:
        with open(rag_path, "w", encoding="utf-8") as f:
            json.dump(rag_data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        raise RuntimeError(f"Erro ao salvar arquivo rag.json: {e}") from e

    print("Extração de dados QA concluída com sucesso!")
    return train_path, rag_path


def _extract_clinical_protocols_data(
    clinical_protocols_paths: Tuple[Path, Path],
    rag_percent: float,
) -> Tuple[str, str]:
    """
    Processa os protocolos clínicos, extraindo texto dos PDFs e separando entre treino e RAG.

    Args:
        clinical_protocols_paths: Tupla (json_path, pdfs_dir) onde:
            - json_path: caminho para o arquivo JSON com metadados dos protocolos
            - pdfs_dir: diretório onde os arquivos PDF estão armazenados
        rag_percent: Fração dos dados destinada ao RAG (0.0 a 1.0).

    Returns:
        Tupla (train_path, rag_path) com os caminhos absolutos dos arquivos gerados.
    """
    json_path, pdfs_dir = clinical_protocols_paths
    
    # Converter Path para string se necessário
    json_path_str = str(json_path) if isinstance(json_path, Path) else json_path
    pdfs_dir_str = str(pdfs_dir) if isinstance(pdfs_dir, Path) else pdfs_dir
    
    preprocessed_dir = os.path.join(_datasets_dir, "preprocessed", "clinical_protocols")
    train_path = os.path.join(preprocessed_dir, "train.json")
    rag_path = os.path.join(preprocessed_dir, "rag.json")

    os.makedirs(preprocessed_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # 1. Ler o JSON de metadados dos protocolos
    # ------------------------------------------------------------------
    print("Processando dados de protocolos clínicos...")
    clinical_entries: List[Dict[str, Any]] = []

    if os.path.exists(json_path_str):
        try:
            with open(json_path_str, "r", encoding="utf-8") as f:
                protocols_data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Erro ao ler arquivo de protocolos clínicos: formato JSON inválido - {e}") from e
        except Exception as e:
            raise RuntimeError(f"Erro ao ler arquivo de protocolos clínicos: {e}") from e

        # ------------------------------------------------------------------
        # 2. Extrair texto de cada PDF e criar registros com content_text
        # ------------------------------------------------------------------
        for protocol in protocols_data:
            pdf_name = protocol.get("name", "")
            if not pdf_name:
                print(f"Aviso: Protocolo sem nome, pulando...")
                continue

            # Sanitizar o nome do arquivo para corresponder ao que foi baixado
            safe_name = re.sub(r"[^\w.-]+", "_", pdf_name, flags=re.UNICODE).strip("._-") or pdf_name
            safe_name = safe_name.replace("__", "_").strip("._-")
            
            pdf_path = os.path.join(pdfs_dir_str, safe_name)
            
            if not os.path.exists(pdf_path):
                print(f"Aviso: PDF não encontrado em {pdf_path}, pulando protocolo...")
                continue

            print(f"Extraindo texto de {safe_name}...")
            content_text = _extract_text_from_pdf(pdf_path)

            if content_text:
                clinical_entries.append({
                    "name": protocol.get("name", ""),
                    "url": protocol.get("url", ""),
                    "source": protocol.get("source", ""),
                    "content_text": content_text,
                })
                print(f"Texto extraído com sucesso: {len(content_text)} caracteres")
            else:
                print(f"Aviso: Não foi possível extrair texto de {safe_name}, pulando...")

        print(f"Protocolos clínicos processados: {len(clinical_entries)} registros com texto extraído.")
    else:
        print(f"Aviso: Arquivo de protocolos clínicos não encontrado em {json_path_str}")

    # ------------------------------------------------------------------
    # 3. Separar entre RAG e Treino
    # ------------------------------------------------------------------
    clinical_rag, clinical_train = _split_dataset_for_rag(clinical_entries, rag_percent)

    # ------------------------------------------------------------------
    # 4. Salvar arquivos JSON
    # ------------------------------------------------------------------
    print(f"Salvando {len(clinical_train)} registros em {train_path}...")
    try:
        with open(train_path, "w", encoding="utf-8") as f:
            json.dump(clinical_train, f, ensure_ascii=False, indent=4)
    except Exception as e:
        raise RuntimeError(f"Erro ao salvar arquivo train.json de protocolos clínicos: {e}") from e

    print(f"Salvando {len(clinical_rag)} registros em {rag_path}...")
    try:
        with open(rag_path, "w", encoding="utf-8") as f:
            json.dump(clinical_rag, f, ensure_ascii=False, indent=4)
    except Exception as e:
        raise RuntimeError(f"Erro ao salvar arquivo rag.json de protocolos clínicos: {e}") from e

    print("Extração de dados de protocolos clínicos concluída com sucesso!")
    return train_path, rag_path


def extract_data(
    qas_paths: Dict[str, str],
    clinical_protocols_paths: Tuple[Path, Path],
    rag_percent: float,
) -> Tuple[str, str, str, str]:
    """
    Processa todos os dados (QA e protocolos clínicos) e gera arquivos para treino e RAG.

    Args:
        qas_paths: Dicionário com os caminhos para os datasets de QA.
        clinical_protocols_paths: Tupla (json_path, pdfs_dir) para os protocolos clínicos.
        rag_percent: Fração dos dados destinada ao RAG (0.0 a 1.0).

    Returns:
        Tupla (train_qa_path, rag_qa_path, train_clinical_path, rag_clinical_path).
    """
    # Processar dados QA
    qas_data_paths = _extract_qas_data(qas_paths, rag_percent)
    
    # Processar dados de protocolos clínicos
    clinical_data_paths = _extract_clinical_protocols_data(clinical_protocols_paths, rag_percent)
    
    # Retornar 4 paths: train_qa, rag_qa, train_clinical, rag_clinical
    return (*qas_data_paths, *clinical_data_paths)