import json
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pdfplumber


_script_dir = os.path.dirname(os.path.abspath(__file__))
_backend_dir = os.path.abspath(os.path.join(_script_dir, "..", "..", ".."))
_datasets_dir = os.path.join(_backend_dir, "datasets")


def _split_dataset_for_rag(
    data: List[Dict[str, Any]], rag_percent: float
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Split a dataset into RAG and train portions.

    Returns (rag_data, train_data).
    """
    if not data:
        return [], []

    num_rag = int(len(data) * rag_percent)
    return data[:num_rag], data[num_rag:]


def _extract_text_from_pdf(pdf_path: Path) -> str:
    """
    Extract text from a PDF file using pdfplumber.

    Returns an empty string if extraction fails.
    """
    if pdfplumber is None:
        print(f"Warning: pdfplumber is not available, skipping {pdf_path}")
        return ""

    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            text_content: List[str] = []
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_content.append(page_text)
            return "\n".join(text_content)
    except Exception as exc:
        print(f"Error extracting text from PDF {pdf_path}: {exc}")
        return ""


def _extract_qas_data(
    qas_paths: Dict[str, str],
    rag_percent: float,
) -> Tuple[str, str]:
    """
    Process QA datasets (PubMedQA and MedQuAD), split them into train and RAG
    and persist the results as JSON files.
    """
    pubmedqa_path = os.path.join(
        qas_paths.get("pubmedqa", os.path.join(_datasets_dir, "files", "qas", "pubmedqa")),
        "data",
        "ori_pqal.json",
    )
    medquad_dir = qas_paths.get("MedQuAD", os.path.join(_datasets_dir, "files", "qas", "MedQuAD"))
    preprocessed_dir = os.path.join(_datasets_dir, "preprocessed", "qas")

    train_path = os.path.join(preprocessed_dir, "train.json")
    rag_path = os.path.join(preprocessed_dir, "rag.json")

    os.makedirs(preprocessed_dir, exist_ok=True)

    print("Processando dados de PubMedQA...")
    pubmedqa_entries: List[Dict[str, Any]] = []

    if os.path.exists(pubmedqa_path):
        try:
            with open(pubmedqa_path, "r", encoding="utf-8") as handle:
                pubmed_raw = json.load(handle)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Erro ao ler arquivo PubMedQA: formato JSON inválido - {exc}") from exc
        except Exception as exc:
            raise RuntimeError(f"Erro ao ler arquivo PubMedQA: {exc}") from exc

        for pmid, entry in pubmed_raw.items():
            question = entry.get("QUESTION", "").strip()
            contexts = entry.get("CONTEXTS", [])
            answer = entry.get("LONG_ANSWER", "").strip()

            pubmedqa_entries.append(
                {
                    "question": question,
                    "contexts": contexts,
                    "answer": answer,
                    "metadata": {
                        "source": "pubmedqa",
                        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                    },
                }
            )

        print(f"PubMedQA processado: {len(pubmedqa_entries)} registros adicionados ao dataset.")
    else:
        print(f"Aviso: Arquivo PubMedQA não encontrado em {pubmedqa_path}")

    print("Processando dados de MedQuAD...")
    medquad_entries: List[Dict[str, Any]] = []

    if os.path.exists(medquad_dir):
        try:
            xml_files: List[str] = []
            for root_dir, _, files in os.walk(medquad_dir):
                for file_name in files:
                    if file_name.endswith(".xml"):
                        xml_files.append(os.path.join(root_dir, file_name))

            for xml_path in xml_files:
                try:
                    tree = ET.parse(xml_path)
                    root_elem = tree.getroot()

                    doc_source = root_elem.attrib.get("source", "").strip()
                    doc_url = root_elem.attrib.get("url", "").strip()

                    qa_pairs = root_elem.find("QAPairs")
                    if qa_pairs is None:
                        continue

                    for qa_pair in qa_pairs.findall("QAPair"):
                        question_elem = qa_pair.find("Question")
                        answer_elem = qa_pair.find("Answer")

                        if question_elem is None or answer_elem is None:
                            continue

                        q_text = (question_elem.text or "").strip()
                        a_text = "".join(answer_elem.itertext()).strip()

                        if q_text and a_text:
                            medquad_entries.append(
                                {
                                    "question": q_text,
                                    "contexts": [],
                                    "answer": a_text,
                                    "metadata": {
                                        "source": doc_source or "MedQuAD",
                                        "url": doc_url or "",
                                    },
                                }
                            )
                except ET.ParseError as exc:
                    print(f"Erro ao processar arquivo XML {xml_path}: {exc}")
                except Exception as exc:
                    print(f"Erro ao processar arquivo XML {xml_path}: {exc}")
        except Exception as exc:
            raise RuntimeError(f"Erro ao processar diretório MedQuAD: {exc}") from exc

        print(
            f"MedQuAD processado: {len(medquad_entries)} registros com respostas preenchidas encontrados."
        )
    else:
        print(f"Aviso: Diretório MedQuAD não encontrado em {medquad_dir}")

    pubmedqa_rag, pubmedqa_train = _split_dataset_for_rag(pubmedqa_entries, rag_percent)
    medquad_rag, medquad_train = _split_dataset_for_rag(medquad_entries, rag_percent)

    rag_data = pubmedqa_rag + medquad_rag
    train_data = pubmedqa_train + medquad_train

    print(f"Salvando {len(train_data)} registros em {train_path}...")
    try:
        with open(train_path, "w", encoding="utf-8") as handle:
            json.dump(train_data, handle, ensure_ascii=False, indent=4)
    except Exception as exc:
        raise RuntimeError(f"Erro ao salvar arquivo train.json: {exc}") from exc

    print(f"Salvando {len(rag_data)} registros em {rag_path}...")
    try:
        with open(rag_path, "w", encoding="utf-8") as handle:
            json.dump(rag_data, handle, ensure_ascii=False, indent=4)
    except Exception as exc:
        raise RuntimeError(f"Erro ao salvar arquivo rag.json: {exc}") from exc

    print("Extração de dados QA concluída com sucesso!")
    return train_path, rag_path


def _extract_clinical_protocols_data(
    clinical_protocols_paths: Tuple[Path, Path],
    rag_percent: float,
) -> Tuple[str, str]:
    """
    Process clinical protocols by extracting PDF text and splitting into train and RAG.
    """
    json_path = Path(clinical_protocols_paths[0])
    pdfs_dir = Path(clinical_protocols_paths[1])

    preprocessed_dir = os.path.join(_datasets_dir, "preprocessed", "clinical_protocols")
    train_path = os.path.join(preprocessed_dir, "train.json")
    rag_path = os.path.join(preprocessed_dir, "rag.json")

    os.makedirs(preprocessed_dir, exist_ok=True)

    print("Processando dados de protocolos clínicos...")
    clinical_entries: List[Dict[str, Any]] = []

    if json_path.exists():
        try:
            with json_path.open("r", encoding="utf-8") as handle:
                protocols_data = json.load(handle)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Erro ao ler arquivo de protocolos clínicos: formato JSON inválido - {exc}"
            ) from exc
        except Exception as exc:
            raise RuntimeError(f"Erro ao ler arquivo de protocolos clínicos: {exc}") from exc

        if not isinstance(protocols_data, list):
            raise ValueError("Arquivo de protocolos clínicos deve conter uma lista de registros")

        for protocol in protocols_data:
            pdf_name = (protocol.get("name") or "").strip()
            if not pdf_name:
                print("Aviso: Protocolo sem nome, pulando...")
                continue

            safe_name = re.sub(r"[^\w.-]+", "_", pdf_name, flags=re.UNICODE).strip("._-") or pdf_name
            safe_name = safe_name.replace("__", "_").strip("._-")
            if not safe_name.lower().endswith(".pdf"):
                safe_name = f"{safe_name}.pdf"

            pdf_path = pdfs_dir / safe_name

            if not pdf_path.exists():
                print(f"Aviso: PDF não encontrado em {pdf_path}, pulando protocolo...")
                continue

            print(f"Extraindo texto de {pdf_path.name}...")
            content_text = _extract_text_from_pdf(pdf_path)

            if not content_text:
                print(f"Aviso: Não foi possível extrair texto de {pdf_path.name}, pulando...")
                continue

            clinical_entries.append(
                {
                    "name": protocol.get("name", ""),
                    "url": protocol.get("url", ""),
                    "source": protocol.get("source", ""),
                    "content_text": content_text,
                }
            )
            print(f"Texto extraído com sucesso: {len(content_text)} caracteres")

        print(f"Protocolos clínicos processados: {len(clinical_entries)} registros com texto extraído.")
    else:
        print(f"Aviso: Arquivo de protocolos clínicos não encontrado em {json_path}")

    clinical_rag, clinical_train = _split_dataset_for_rag(clinical_entries, rag_percent)

    print(f"Salvando {len(clinical_train)} registros em {train_path}...")
    try:
        with open(train_path, "w", encoding="utf-8") as handle:
            json.dump(clinical_train, handle, ensure_ascii=False, indent=4)
    except Exception as exc:
        raise RuntimeError(f"Erro ao salvar arquivo train.json de protocolos clínicos: {exc}") from exc

    print(f"Salvando {len(clinical_rag)} registros em {rag_path}...")
    try:
        with open(rag_path, "w", encoding="utf-8") as handle:
            json.dump(clinical_rag, handle, ensure_ascii=False, indent=4)
    except Exception as exc:
        raise RuntimeError(f"Erro ao salvar arquivo rag.json de protocolos clínicos: {exc}") from exc

    print("Extração de dados de protocolos clínicos concluída com sucesso!")
    return train_path, rag_path


def extract_data(
    qas_paths: Dict[str, str],
    clinical_protocols_paths: Tuple[Path, Path],
    rag_percent: float,
) -> Tuple[str, str, str, str]:
    """
    Process all datasets and generate train/RAG files for QA and clinical protocols.
    """
    qas_data_paths = _extract_qas_data(qas_paths, rag_percent)
    clinical_data_paths = _extract_clinical_protocols_data(clinical_protocols_paths, rag_percent)
    return (*qas_data_paths, *clinical_data_paths)
