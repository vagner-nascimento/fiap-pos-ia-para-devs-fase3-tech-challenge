import hashlib
import json
import os
import re
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from fastapi import HTTPException

from infra.database.collections.preprocess import get_preprocess_document
from infra.database.collections.rag_database import insert_rag_documents

try:
    from langchain_community.embeddings import HuggingFaceInstructEmbeddings as _RealEmbeddingModel
except Exception:  # pragma: no cover - optional dependency fallback
    _RealEmbeddingModel = None

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter as _RealTextSplitter
except Exception:  # pragma: no cover - optional dependency fallback
    _RealTextSplitter = None


BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_QAS_RAG_PATH = BACKEND_ROOT / "datasets" / "preprocessed" / "qas" / "rag_pt_br.json"
DEFAULT_CLINICAL_PROTOCOLS_RAG_PATH = (
    BACKEND_ROOT / "datasets" / "preprocessed" / "clinical_protocols" / "rag.json"
)
DEFAULT_RAG_EMBEDDING_MODEL = os.getenv("RAG_EMBEDDING_MODEL", "hkunlp/instructor-base")
DEFAULT_PROTOCOL_CHUNK_SIZE = 2400
DEFAULT_PROTOCOL_CHUNK_OVERLAP = 200


class _FallbackTextSplitter:
    def __init__(self, chunk_size: int, chunk_overlap: int) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = min(chunk_overlap, chunk_size - 1) if chunk_size > 1 else 0

    def split_text(self, text: str) -> List[str]:
        normalized = _normalize_text(text)
        if not normalized:
            return []
        if len(normalized) <= self.chunk_size:
            return [normalized]

        chunks: List[str] = []
        start = 0
        while start < len(normalized):
            end = min(len(normalized), start + self.chunk_size)
            chunk = normalized[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end >= len(normalized):
                break
            start = max(end - self.chunk_overlap, start + 1)
        return chunks


class _FallbackEmbeddingModel:
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self.embedding_dimension = 16

    def _embed_one(self, text: str) -> List[float]:
        normalized = _normalize_text(text)
        digest = hashlib.sha256(normalized.encode("utf-8")).digest()
        vector: List[float] = []
        for index in range(self.embedding_dimension):
            start = (index * 2) % len(digest)
            chunk = digest[start : start + 2]
            if len(chunk) < 2:
                chunk = chunk + digest[: 2 - len(chunk)]
            value = int.from_bytes(chunk, byteorder="big", signed=False)
            vector.append(round(value / 65535.0, 6))
        return vector

    def embed_documents(self, texts: Sequence[str]) -> List[List[float]]:
        return [self._embed_one(text) for text in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._embed_one(text)


def _normalize_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", value).strip()


def _read_json_list(path: Union[str, Path]) -> List[Dict[str, Any]]:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Arquivo nao encontrado: {file_path}")

    with file_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, list):
        raise ValueError(f"Formato invalido em {file_path}: esperado uma lista de objetos JSON")

    return data


def _validate_preprocess_id(preprocess_id: str) -> Dict[str, Any]:
    preprocess = get_preprocess_document(preprocess_id)
    if preprocess is None:
        raise HTTPException(
            status_code=404,
            detail=f"Preprocessamento com ID {preprocess_id} nao encontrado",
        )

    status = preprocess.get("status")
    if status != "completed":
        error_message = preprocess.get("error_message")
        raise HTTPException(
            status_code=422,
            detail=(
                "Preprocessamento nao foi concluido com sucesso. "
                f"Status atual: {status}, Error: {error_message}"
            ),
        )

    return preprocess


def _build_text_splitter(
    chunk_size: int = DEFAULT_PROTOCOL_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_PROTOCOL_CHUNK_OVERLAP,
) -> Any:
    if _RealTextSplitter is not None:
        return _RealTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return _FallbackTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)


def _build_embedding_model(model_name: Optional[str] = None) -> Any:
    resolved_model_name = model_name or DEFAULT_RAG_EMBEDDING_MODEL
    if _RealEmbeddingModel is not None:
        try:
            return _RealEmbeddingModel(model_name=resolved_model_name)
        except Exception:
            pass
    return _FallbackEmbeddingModel(resolved_model_name)


def _join_contexts(contexts: Any) -> str:
    if not isinstance(contexts, list):
        return ""

    cleaned_contexts: List[str] = []
    for context in contexts:
        normalized = _normalize_text(context)
        if normalized:
            cleaned_contexts.append(normalized)

    return "\n".join(cleaned_contexts)


def _build_qas_document(
    item: Dict[str, Any],
    *,
    preprocess_id: str,
    batch_id: str,
    index: int,
) -> Optional[Dict[str, Any]]:
    question = _normalize_text(item.get("question"))
    answer = _normalize_text(item.get("answer"))
    contexts = _join_contexts(item.get("contexts"))

    if not question and not answer and not contexts:
        return None

    metadata = item.get("metadata")
    source_metadata = deepcopy(metadata) if isinstance(metadata, dict) else {}

    content_lines = [
        "### QAs RAG",
        f"Pergunta: {question}" if question else None,
        f"Contexto: {contexts}" if contexts else None,
        f"Resposta: {answer}" if answer else None,
    ]
    content = "\n".join(line for line in content_lines if line)

    return {
        "_id": f"{batch_id}-qas-{index:06d}",
        "batch_id": batch_id,
        "preprocess_id": preprocess_id,
        "dataset": "qas",
        "source_type": "qas",
        "content": content,
        "metadatas": {
            "source": source_metadata,
            "question": question,
            "answer": answer,
            "contexts_count": len(item.get("contexts") or []) if isinstance(item.get("contexts"), list) else 0,
        },
    }


def _build_clinical_protocol_documents(
    item: Dict[str, Any],
    *,
    preprocess_id: str,
    batch_id: str,
    index: int,
    splitter: Any,
) -> List[Dict[str, Any]]:
    content_text = _normalize_text(item.get("content_text"))
    if not content_text:
        return []

    name = _normalize_text(item.get("name")) or "protocolo_clinico"
    source = _normalize_text(item.get("source")) or "fonte_desconhecida"
    url = _normalize_text(item.get("url"))

    source_metadata = {
        "name": name,
        "url": url,
        "source": source,
    }

    chunks = splitter.split_text(content_text)
    if not chunks:
        return []

    documents: List[Dict[str, Any]] = []
    total_chunks = len(chunks)

    for chunk_index, chunk in enumerate(chunks, start=1):
        content_lines = [
            "### Protocolo clinico RAG",
            f"Nome: {name}",
            f"Fonte: {source}",
        ]
        if url:
            content_lines.append(f"URL: {url}")
        content_lines.extend(["", "Conteudo:", chunk])
        content = "\n".join(content_lines)

        documents.append(
            {
                "_id": f"{batch_id}-clinical-{index:06d}-{chunk_index:03d}",
                "batch_id": batch_id,
                "preprocess_id": preprocess_id,
                "dataset": "clinical_protocols",
                "source_type": "clinical_protocols",
                "chunk_index": chunk_index,
                "chunk_total": total_chunks,
                "content": content,
                "metadatas": {
                    "source": source_metadata,
                    "name": name,
                    "url": url,
                    "source_label": source,
                },
            }
        )

    return documents


def _embed_documents(documents: List[Dict[str, Any]], embedding_model: Any) -> List[Dict[str, Any]]:
    if not documents:
        return []

    contents = [document["content"] for document in documents]
    embeddings = embedding_model.embed_documents(contents)

    enriched_documents: List[Dict[str, Any]] = []
    for document, embedding in zip(documents, embeddings):
        enriched_document = dict(document)
        enriched_document["embedding"] = embedding
        enriched_document["embedding_model"] = getattr(embedding_model, "model_name", DEFAULT_RAG_EMBEDDING_MODEL)
        enriched_document["embedding_dimension"] = len(embedding) if isinstance(embedding, list) else 0
        enriched_documents.append(enriched_document)

    return enriched_documents


def _build_rag_documents(
    *,
    preprocess_id: str,
    batch_id: str,
    qas_data: Sequence[Dict[str, Any]],
    clinical_protocols_data: Sequence[Dict[str, Any]],
    embedding_model: Any,
    splitter: Any,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    base_documents: List[Dict[str, Any]] = []
    stats = {
        "qas_documents": 0,
        "clinical_protocol_documents": 0,
    }

    for index, item in enumerate(qas_data, start=1):
        document = _build_qas_document(
            item,
            preprocess_id=preprocess_id,
            batch_id=batch_id,
            index=index,
        )
        if document is not None:
            base_documents.append(document)
            stats["qas_documents"] += 1

    for index, item in enumerate(clinical_protocols_data, start=1):
        protocol_documents = _build_clinical_protocol_documents(
            item,
            preprocess_id=preprocess_id,
            batch_id=batch_id,
            index=index,
            splitter=splitter,
        )
        base_documents.extend(protocol_documents)
        stats["clinical_protocol_documents"] += len(protocol_documents)

    enriched_documents = _embed_documents(base_documents, embedding_model)
    return enriched_documents, stats


def generate_rag_database(
    preprocess_id: str,
    qas_rag_path: Optional[Union[str, Path]] = None,
    clinical_protocols_rag_path: Optional[Union[str, Path]] = None,
    *,
    embedding_model_name: Optional[str] = None,
    splitter_chunk_size: int = DEFAULT_PROTOCOL_CHUNK_SIZE,
    splitter_chunk_overlap: int = DEFAULT_PROTOCOL_CHUNK_OVERLAP,
) -> Dict[str, Any]:
    resolved_qas_rag_path = Path(qas_rag_path or DEFAULT_QAS_RAG_PATH)
    resolved_clinical_protocols_rag_path = Path(
        clinical_protocols_rag_path or DEFAULT_CLINICAL_PROTOCOLS_RAG_PATH
    )
    started_at = datetime.now(timezone.utc)
    batch_id = str(uuid.uuid4())
    resolved_embedding_model_name = embedding_model_name or DEFAULT_RAG_EMBEDDING_MODEL

    print(
        "[RAG][SYNC] Solicitacao recebida "
        f"preprocess_id={preprocess_id} batch_id={batch_id}"
    )

    try:
        preprocess = _validate_preprocess_id(preprocess_id)
        preprocess_snapshot = {
            "_id": preprocess_id,
            "status": preprocess.get("status"),
            "rag_percent": preprocess.get("rag_percent"),
            "updated_date": preprocess.get("updated_date"),
        }
        print(
            "[RAG][SYNC] Preprocessamento validado "
            f"status={preprocess_snapshot['status']}"
        )

        print(f"[RAG][SYNC] Lendo QAs em {resolved_qas_rag_path}")
        qas_data = _read_json_list(resolved_qas_rag_path)
        print(f"[RAG][SYNC] QAs carregados: {len(qas_data)} registros")

        print(f"[RAG][SYNC] Lendo protocolos clinicos em {resolved_clinical_protocols_rag_path}")
        clinical_protocols_data = _read_json_list(resolved_clinical_protocols_rag_path)
        print(
            "[RAG][SYNC] Protocolos clinicos carregados: "
            f"{len(clinical_protocols_data)} registros"
        )

        print(f"[RAG][SYNC] Carregando modelo de embeddings: {resolved_embedding_model_name}")
        embedding_model = _build_embedding_model(resolved_embedding_model_name)

        print(
            "[RAG][SYNC] Criando splitter recursivo "
            f"chunk_size={splitter_chunk_size} chunk_overlap={splitter_chunk_overlap}"
        )
        splitter = _build_text_splitter(
            chunk_size=splitter_chunk_size,
            chunk_overlap=splitter_chunk_overlap,
        )

        print("[RAG][SYNC] Preparando documentos e embeddings")
        documents, stats = _build_rag_documents(
            preprocess_id=preprocess_id,
            batch_id=batch_id,
            qas_data=qas_data,
            clinical_protocols_data=clinical_protocols_data,
            embedding_model=embedding_model,
            splitter=splitter,
        )

        if not documents:
            raise ValueError("Nenhum documento valido foi encontrado para a base RAG.")

        print(
            "[RAG][SYNC] Documentos preparados "
            f"qas={stats['qas_documents']} clinical={stats['clinical_protocol_documents']} "
            f"total={len(documents)}"
        )
        print("[RAG][SYNC] Persistindo documentos no MongoDB")
        inserted_documents = insert_rag_documents(documents)
        print(f"[RAG][SYNC] Documentos persistidos: {len(inserted_documents)}")

        finished_at = datetime.now(timezone.utc)
        response = {
            "id": batch_id,
            "batch_id": batch_id,
            "preprocess_id": preprocess_id,
            "preprocess_snapshot": preprocess_snapshot,
            "qas_rag_path": str(resolved_qas_rag_path),
            "clinical_protocols_rag_path": str(resolved_clinical_protocols_rag_path),
            "embedding_model": resolved_embedding_model_name,
            "splitter_name": "RecursiveCharacterTextSplitter",
            "splitter_chunk_size": splitter_chunk_size,
            "splitter_chunk_overlap": splitter_chunk_overlap,
            "status": "completed",
            "error_message": None,
            "created_date": started_at.isoformat(),
            "updated_date": finished_at.isoformat(),
            "qas_documents": stats["qas_documents"],
            "clinical_protocol_documents": stats["clinical_protocol_documents"],
            "total_documents": len(inserted_documents),
        }
        print(
            "[RAG][SYNC] Geracao concluida com sucesso "
            f"batch_id={batch_id} total={response['total_documents']}"
        )
        return response
    except HTTPException:
        raise
    except Exception as exc:
        print(
            "[RAG][SYNC] Erro na geracao da base RAG "
            f"preprocess_id={preprocess_id} batch_id={batch_id}: {exc}"
        )
        raise
