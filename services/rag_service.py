"""
RAG 서비스: rag_docs/*.txt 파일을 OpenAI 임베딩으로 벡터화하여 JSON에 저장.
파일의 수정 시간(mtime)이 변경되면 해당 파일 청크를 재인덱싱.
"""
import os
import json
import math
from pathlib import Path
from typing import List
from openai import AsyncOpenAI

DOCS_DIR = Path(__file__).parent.parent / "rag_docs"
META_FILE = Path(__file__).parent.parent / ".rag_meta.json"
VECTORS_FILE = Path(__file__).parent.parent / ".rag_vectors.json"
EMBEDDING_MODEL = "text-embedding-3-small"

_vectors: list[dict] = []


def _load_vectors() -> None:
    global _vectors
    if VECTORS_FILE.exists():
        try:
            _vectors = json.loads(VECTORS_FILE.read_text(encoding="utf-8"))
        except Exception:
            _vectors = []


def _save_vectors() -> None:
    VECTORS_FILE.write_text(
        json.dumps(_vectors, ensure_ascii=False),
        encoding="utf-8",
    )


def _load_meta() -> dict:
    if META_FILE.exists():
        try:
            return json.loads(META_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_meta(meta: dict) -> None:
    META_FILE.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def _chunk_text(text: str) -> List[str]:
    """## 헤더 기준으로 섹션 분리 후 빈 섹션 제거."""
    sections: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if line.startswith("## ") and current:
            sections.append("\n".join(current).strip())
            current = [line]
        else:
            current.append(line)
    if current:
        sections.append("\n".join(current).strip())
    return [s for s in sections if len(s) > 30]


async def _embed_batch(texts: List[str]) -> List[List[float]]:
    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))
    response = await client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [item.embedding for item in response.data]


def _cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb + 1e-10)


async def index_documents() -> dict:
    """
    rag_docs/*.txt 파일을 인덱싱.
    mtime이 저장된 값과 다르면 해당 파일 청크를 재임베딩하여 덮어씀.
    """
    global _vectors

    if not DOCS_DIR.exists():
        return {"indexed": [], "skipped": [], "total_chunks": 0}

    _load_vectors()
    meta = _load_meta()
    indexed: list[str] = []
    skipped: list[str] = []

    for txt_file in sorted(DOCS_DIR.glob("*.txt")):
        fname = txt_file.name
        mtime = str(txt_file.stat().st_mtime)

        if meta.get(fname) == mtime:
            skipped.append(fname)
            continue

        # 기존 벡터에서 해당 파일 청크 제거
        _vectors = [v for v in _vectors if v["source"] != fname]

        text = txt_file.read_text(encoding="utf-8")
        chunks = _chunk_text(text)
        if not chunks:
            meta[fname] = mtime
            continue

        embeddings = await _embed_batch(chunks)
        for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            _vectors.append({
                "text": chunk,
                "embedding": emb,
                "source": fname,
                "chunk_index": i,
            })

        meta[fname] = mtime
        indexed.append(fname)
        print(f"[RAG] '{fname}' 인덱싱 완료: {len(chunks)}개 청크")

    _save_vectors()
    _save_meta(meta)

    return {"indexed": indexed, "skipped": skipped, "total_chunks": len(_vectors)}


async def retrieve(query: str, top_k: int = 4) -> List[str]:
    """쿼리와 코사인 유사도가 높은 상위 top_k 청크를 반환."""
    global _vectors
    if not _vectors:
        _load_vectors()
    if not _vectors:
        return []

    query_emb = (await _embed_batch([query]))[0]
    scored = [
        (v["text"], _cosine(query_emb, v["embedding"]))
        for v in _vectors
    ]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [text for text, _ in scored[:top_k]]
