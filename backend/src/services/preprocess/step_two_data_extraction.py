import json
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pdfplumber

from infra.database.collections.preprocess import update_step_status

_script_dir = os.path.dirname(os.path.abspath(__file__))
_backend_dir = os.path.abspath(os.path.join(_script_dir, "..", "..", ".."))
_datasets_dir = os.path.join(_backend_dir, "datasets")





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
    doc_id: str,
    qas_paths: Dict[str, str],
) -> Tuple[str, int]:
    """
    Process QA datasets (PubMedQA and MedQuAD) and persist all data as a single JSON file.
    """
    update_step_status(doc_id, "two_data_extraction", "in_progress", completion_percentage=0)

    pubmedqa_path = os.path.join(
        qas_paths.get("pubmedqa", os.path.join(_datasets_dir, "files", "qas", "pubmedqa")),
        "data",
        "ori_pqal.json",
    )
    medquad_dir = qas_paths.get("MedQuAD", os.path.join(_datasets_dir, "files", "qas", "MedQuAD"))
    preprocessed_dir = os.path.join(_datasets_dir, "preprocessed", "qas")

    train_path = os.path.join(preprocessed_dir, "qas_train.json")

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

    update_step_status(doc_id, "two_data_extraction", "in_progress", completion_percentage=25)

    print("Processando dados de MedQuAD...")
    medquad_entries: List[Dict[str, Any]] = []

    if os.path.exists(medquad_dir):
        try:
            xml_files: List[str] = []
            for root_dir, _, files in os.walk(medquad_dir):
                for file_name in files:
                    if file_name.endswith(".xml"):
                        xml_files.append(os.path.join(root_dir, file_name))

            file_progress = 0
            total_files = len(xml_files)
            per_file_progress = 25.0 / total_files if total_files > 0 else 0.0

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
        update_step_status(doc_id, "two_data_extraction", "in_progress", completion_percentage=50)
    else:
        print(f"Aviso: Diretório MedQuAD não encontrado em {medquad_dir}")
        update_step_status(doc_id, "two_data_extraction", "in_progress", completion_percentage=50)

    # Combine all data without splitting
    all_data = pubmedqa_entries + medquad_entries

    print(f"Salvando {len(all_data)} registros em {train_path}...")
    try:
        with open(train_path, "w", encoding="utf-8") as handle:
            json.dump(all_data, handle, ensure_ascii=False, indent=4)
    except Exception as exc:
        raise RuntimeError(f"Erro ao salvar arquivo qas_train.json: {exc}") from exc

    print("Extração de dados QA concluída com sucesso!")
    return train_path, len(all_data)


def _extract_clinical_protocols_data(
    doc_id: str,
    clinical_protocols_paths: Tuple[Path, Path],
) -> Tuple[str, int]:
    """
    Process clinical protocols by extracting PDF text and persist all data as a single JSON file.
    """
    json_path = Path(clinical_protocols_paths[0])
    pdfs_dir = Path(clinical_protocols_paths[1])

    preprocessed_dir = os.path.join(_datasets_dir, "preprocessed", "clinical_protocols")
    rag_path = os.path.join(preprocessed_dir, "clinical_protocols_rag.json")

    os.makedirs(preprocessed_dir, exist_ok=True)

    print("Processando dados de protocolos clínicos...")
    clinical_entries: List[Dict[str, Any]] = []

    update_step_status(doc_id, "two_data_extraction", "in_progress", completion_percentage=50)

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

        total_protocols = len(protocols_data)
        protocol_progress = 0
        per_protocol_progress = 50.0 / total_protocols if total_protocols > 0 else 0.0

        for protocol in protocols_data:
            pdf_name = (protocol.get("name") or "").strip()
            if not pdf_name:
                print("Aviso: Protocolo sem nome, pulando...")
                protocol_progress += 1
                update_step_status(
                    doc_id,
                    "two_data_extraction",
                    "in_progress",
                    completion_percentage=min(100.0, 50.0 + per_protocol_progress * protocol_progress),
                )
                continue

            safe_name = re.sub(r"[^\w.-]+", "_", pdf_name, flags=re.UNICODE).strip("._-") or pdf_name
            safe_name = safe_name.replace("__", "_").strip("._-")
            if not safe_name.lower().endswith(".pdf"):
                safe_name = f"{safe_name}.pdf"

            pdf_path = pdfs_dir / safe_name

            if not pdf_path.exists():
                print(f"Aviso: PDF não encontrado em {pdf_path}, pulando protocolo...")
                protocol_progress += 1
                update_step_status(
                    doc_id,
                    "two_data_extraction",
                    "in_progress",
                    completion_percentage=min(100.0, 50.0 + per_protocol_progress * protocol_progress),
                )
                continue

            print(f"Extraindo texto de {pdf_path.name}...")
            content_text = _extract_text_from_pdf(pdf_path)

            if not content_text:
                print(f"Aviso: Não foi possível extrair texto de {pdf_path.name}, pulando...")
                protocol_progress += 1
                update_step_status(
                    doc_id,
                    "two_data_extraction",
                    "in_progress",
                    completion_percentage=min(100.0, 50.0 + per_protocol_progress * protocol_progress),
                )
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
            protocol_progress += 1
            update_step_status(
                doc_id,
                "two_data_extraction",
                "in_progress",
                completion_percentage=min(100.0, 50.0 + per_protocol_progress * protocol_progress),
            )

        if total_protocols == 0:
            update_step_status(
                doc_id,
                "two_data_extraction",
                "in_progress",
                completion_percentage=100,
            )

        print(f"Protocolos clínicos processados: {len(clinical_entries)} registros com texto extraído.")
    else:
        print(f"Aviso: Arquivo de protocolos clínicos não encontrado em {json_path}")
        update_step_status(
            doc_id,
            "two_data_extraction",
            "in_progress",
            completion_percentage=100,
        )

    # Save all data without splitting
    print(f"Salvando {len(clinical_entries)} registros em {rag_path}...")
    try:
        with open(rag_path, "w", encoding="utf-8") as handle:
            json.dump(clinical_entries, handle, ensure_ascii=False, indent=4)
    except Exception as exc:
        raise RuntimeError(f"Erro ao salvar arquivo clinical_protocols_rag.json: {exc}") from exc

    print("Extração de dados de protocolos clínicos concluída com sucesso!")
    return rag_path, len(clinical_entries)


def extract_data(
    doc_id: str,
    qas_paths: Dict[str, str],
    clinical_protocols_paths: Tuple[Path, Path],
) -> Tuple[str, int, str, int]:
    """
    Process all datasets and generate single files for QA and clinical protocols.
    Returns (qas_train_path, qas_count, clinical_protocols_rag_path, clinical_protocols_count).
    """
    qas_train_path, qas_count = _extract_qas_data(
        doc_id,
        qas_paths,
    )
    clinical_protocols_rag_path, clinical_protocols_count = _extract_clinical_protocols_data(
        doc_id,
        clinical_protocols_paths,
    )
    return qas_train_path, qas_count, clinical_protocols_rag_path, clinical_protocols_count
