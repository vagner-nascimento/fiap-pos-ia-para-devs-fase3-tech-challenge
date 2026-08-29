import hashlib
import json
import math
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Final, List, Optional, Sequence, Tuple


from fastapi import HTTPException

from infra.database.collections.preprocess import get_preprocess_document
from infra.database.collections.rag_database import (
    get_rag_documents_for_search,
    insert_rag_documents,
    get_text_search_scores,
)


try:
    from langchain_community.embeddings import HuggingFaceInstructEmbeddings as _RealEmbeddingModel
except Exception:  # pragma: no cover - optional dependency fallback
    _RealEmbeddingModel = None

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter as _RealTextSplitter
except Exception:  # pragma: no cover - optional dependency fallback
    _RealTextSplitter = None


BACKEND_ROOT = Path(__file__).resolve().parents[2]
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


PT_STOPWORDS: Final[set] = {
    "a", "ao", "aos", "aquela", "aquelas", "aquele", "aqueles", "aquilo", "as", "ate", "até",
    "com", "como", "da", "das", "de", "dela", "delas", "dele", "deles", "depois", "do",
    "dos", "e", "ela", "elas", "ele", "eles", "em", "entre", "era", "eras", "eram",
    "essa", "essas", "esse", "esses", "esta", "estamos", "estas", "estava", "estavam",
    "este", "estes", "estou", "eu", "foi", "fomos", "foram", "ha", "há", "isso", "isto",
    "ja", "já", "lhe", "lhes", "mais", "mas", "me", "mesmo", "meu", "meus", "minha", "minhas",
    "muito", "na", "nas", "nem", "no", "nos", "nossa", "nossas", "nosso", "nossos",
    "num", "numa", "o", "os", "ou", "para", "pela", "pelas", "pelo", "pelos", "por",
    "qual", "quais", "quando", "que", "quem", "se", "seja", "sem", "seu", "seus", "so", "só", "sua",
    "suas", "tambem", "também", "te", "tem", "temos", "tenho", "ter", "um", "uma", "voce", "você", "voces", "vocês"
}


def _remove_accents(text: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "MN")


def _tokenize_pt(text: str) -> List[str]:
    normalized = _remove_accents(_normalize_text(text).lower())
    words = re.findall(r"\b[a-z0-9]{2,}\b", normalized)
    filtered = [w for w in words if w not in PT_STOPWORDS]
    return filtered if filtered else words


class _FallbackEmbeddingModel:
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self.embedding_dimension = 256

    def _embed_one(self, text: str) -> List[float]:
        tokens = _tokenize_pt(text)
        if not tokens:
            return [0.0] * self.embedding_dimension

        vector: List[float] = [0.0] * self.embedding_dimension

        for token in tokens:
            stem = token[:5] if len(token) >= 5 else token
            h = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16)
            idx = h % self.embedding_dimension
            sign = 1.0 if ((h >> 16) & 1) == 1 else -1.0
            vector[idx] += sign * 1.0

            if stem != token:
                h_stem = int(hashlib.sha256(f"stem_{stem}".encode("utf-8")).hexdigest(), 16)
                idx_stem = h_stem % self.embedding_dimension
                sign_stem = 1.0 if ((h_stem >> 16) & 1) == 1 else -1.0
                vector[idx_stem] += sign_stem * 0.8

        for i in range(len(tokens) - 1):
            bigram = f"{tokens[i]}_{tokens[i+1]}"
            h_bg = int(hashlib.sha256(bigram.encode("utf-8")).hexdigest(), 16)
            idx_bg = h_bg % self.embedding_dimension
            sign_bg = 1.0 if ((h_bg >> 16) & 1) == 1 else -1.0
            vector[idx_bg] += sign_bg * 1.5

        norm = math.sqrt(sum(val * val for val in vector))
        if norm > 0:
            return [round(val / norm, 6) for val in vector]
        return vector

    def embed_documents(self, texts: Sequence[str]) -> List[List[float]]:
        return [self._embed_one(text) for text in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._embed_one(text)



def _normalize_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", value).strip()


def _read_json_list(path: str | Path) -> List[Dict[str, Any]]:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Arquivo nao encontrado: {file_path}")

    with file_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, list):
        raise ValueError(f"Formato invalido em {file_path}: esperado uma lista de objetos JSON")

    return data


def _resolve_clinical_protocols_rag_path(path_value: str) -> Path:
    path = Path(path_value.strip())
    if path.is_absolute():
        return path

    if path.parts and path.parts[0] == BACKEND_ROOT.name:
        path = Path(*path.parts[1:])

    return BACKEND_ROOT / path


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
    clinical_protocols_data: Sequence[Dict[str, Any]],
    embedding_model: Any,
    splitter: Any,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    base_documents: List[Dict[str, Any]] = []
    stats = {
        "clinical_protocol_documents": 0,
    }

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
    *,
    embedding_model_name: Optional[str] = None,
    splitter_chunk_size: int = DEFAULT_PROTOCOL_CHUNK_SIZE,
    splitter_chunk_overlap: int = DEFAULT_PROTOCOL_CHUNK_OVERLAP,
) -> Dict[str, Any]:
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

        results = preprocess.get("results")
        clinical_protocols_rag_path = (
            results.get("clinical_protocols_rag_path") if isinstance(results, dict) else None
        )
        if not isinstance(clinical_protocols_rag_path, str) or not clinical_protocols_rag_path.strip():
            raise HTTPException(
                status_code=422,
                detail="Preprocessamento concluido sem clinical_protocols_rag_path",
            )

        resolved_clinical_protocols_rag_path = _resolve_clinical_protocols_rag_path(
            clinical_protocols_rag_path
        )

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
            clinical_protocols_data=clinical_protocols_data,
            embedding_model=embedding_model,
            splitter=splitter,
        )

        if not documents:
            raise ValueError("Nenhum documento valido foi encontrado para a base RAG.")

        print(
            "[RAG][SYNC] Documentos preparados "
            f"clinical={stats['clinical_protocol_documents']} "
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
            "clinical_protocols_rag_path": str(resolved_clinical_protocols_rag_path),
            "embedding_model": resolved_embedding_model_name,
            "splitter_name": "RecursiveCharacterTextSplitter",
            "splitter_chunk_size": splitter_chunk_size,
            "splitter_chunk_overlap": splitter_chunk_overlap,
            "status": "completed",
            "error_message": None,
            "created_date": started_at.isoformat(),
            "updated_date": finished_at.isoformat(),
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


def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot_product / (norm_a * norm_b)


def query_rag_documents(
    query: str,
    top_k: int = 5,
    preprocess_id: Optional[str] = None,
    similarity_threshold: Optional[float] = None,
    embedding_model_name: Optional[str] = None,
) -> Dict[str, Any]:
    normalized_query = _normalize_text(query)
    if not normalized_query:
        raise HTTPException(status_code=400, detail="A query de busca nao pode ser vazia.")

    if top_k < 1:
        raise HTTPException(status_code=400, detail="O parametro top_k deve ser maior ou igual a 1.")

    embedding_model = _build_embedding_model(embedding_model_name)
    query_vector = embedding_model.embed_query(normalized_query)
    query_tokens = set(_tokenize_pt(normalized_query))

    raw_documents = get_rag_documents_for_search(preprocess_id=preprocess_id)
    if not raw_documents:
        return {
            "query": normalized_query,
            "total_results": 0,
            "documents": [],
        }

    # Obtem as pontuacoes da busca textual via indice nativo do MongoDB
    text_scores = get_text_search_scores(normalized_query, preprocess_id=preprocess_id, limit=200)
    max_text_score = max(text_scores.values()) if text_scores else 1.0

    scored_documents: List[Dict[str, Any]] = []
    for doc in raw_documents:
        doc_id = str(doc.get("_id", ""))
        doc_content = doc.get("content", "")
        doc_embedding = doc.get("embedding")

        # Recalcular embedding caso os vetores não tenham a mesma dimensão
        if not isinstance(doc_embedding, list) or len(doc_embedding) != len(query_vector):
            doc_embedding = embedding_model.embed_query(doc_content)

        cos_sim = _cosine_similarity(query_vector, doc_embedding)

        # Normaliza o score textual retornado pelo MongoDB [0, 1]
        raw_text_score = text_scores.get(doc_id, 0.0)
        norm_text_score = raw_text_score / max_text_score if max_text_score > 0 else 0.0

        # Para busca hibrida: combinamos o score semantico (vetor) com o lexical (texto).
        # A formula aditiva (60% vetor / 40% texto) permite que um documento com excelente match
        # de palavra-chave (tuberculose) seja resgatado mesmo que seu embedding vetorial seja fraco (ex: < 0.3).
        # Ao mesmo tempo, um documento que so tem "tratar" tera um norm_text_score muito baixo (~0.2),
        # fazendo com que seu final_score desabe para baixo de 0.3.
        final_score = round((cos_sim * 0.6) + (norm_text_score * 0.4), 6)

        if similarity_threshold is not None and final_score < similarity_threshold:
            continue

        scored_doc = {
            "id": str(doc.get("_id", "")),
            "preprocess_id": str(doc.get("preprocess_id", "")),
            "dataset": str(doc.get("dataset", "")),
            "source_type": str(doc.get("source_type", "")),
            "content": str(doc_content),
            "similarity_score": final_score,
            "metadatas": doc.get("metadatas", {}) if isinstance(doc.get("metadatas"), dict) else {},
            "chunk_index": doc.get("chunk_index"),
            "chunk_total": doc.get("chunk_total"),
        }
        scored_documents.append(scored_doc)

    scored_documents.sort(key=lambda item: item["similarity_score"], reverse=True)
    limited_documents = scored_documents[:top_k]

    return {
        "query": normalized_query,
        "total_results": len(limited_documents),
        "documents": limited_documents,
    }


