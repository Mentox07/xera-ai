import hashlib
import logging
import time
import httpx
import chromadb
from pathlib import Path

logger = logging.getLogger(__name__)

CHROMA_DIR = Path("/opt/xera-ai/data/chromadb")
COLLECTION_NAME = "homelab_docs"
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

COUCHDB_URL = "http://192.168.20.21:5984"
COUCHDB_DB = "obsidian-livesync"
COUCHDB_USER = "admin"
COUCHDB_PASS = "CouchHm!2026#Obs"

CACHE_TTL = 300

_client = None
_collection = None
_search_cache: dict[str, tuple[float, list]] = {}


def _get_collection():
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        _collection = _client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def _reset_collection():
    global _client, _collection
    _client = None
    _collection = None
    _search_cache.clear()


async def _fetch_all_docs() -> list[dict]:
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(
            f"{COUCHDB_URL}/{COUCHDB_DB}/_all_docs",
            params={"include_docs": "true"},
            auth=(COUCHDB_USER, COUCHDB_PASS),
        )
        resp.raise_for_status()
        all_rows = resp.json()["rows"]

    parents = []
    leaves = {}
    for row in all_rows:
        doc = row["doc"]
        if doc.get("type") == "plain" and "children" in doc:
            parents.append(doc)
        elif doc.get("type") == "leaf" and "data" in doc:
            leaves[doc["_id"]] = doc["data"]

    documents = []
    for parent in parents:
        path = parent.get("path", parent["_id"])
        if not path.lower().endswith(".md"):
            continue
        parts = []
        for child_id in parent.get("children", []):
            if child_id in leaves:
                parts.append(leaves[child_id])
        content = "".join(parts)
        if content.strip():
            documents.append({
                "path": path,
                "content": content,
                "size": parent.get("size", len(content)),
                "mtime": parent.get("mtime", 0),
            })

    return documents


def _chunk_text(text: str, path: str) -> list[dict]:
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            text = text[end + 3:].strip()

    if len(text) <= CHUNK_SIZE:
        return [{"text": text, "path": path, "chunk_idx": 0}]

    chunks = []
    start = 0
    idx = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        if end < len(text):
            para = text.rfind("\n\n", start, end)
            if para > start + CHUNK_SIZE // 2:
                end = para + 2
            else:
                line = text.rfind("\n", start, end)
                if line > start + CHUNK_SIZE // 2:
                    end = line + 1

        chunk_text = text[start:end].strip()
        if chunk_text:
            chunks.append({"text": chunk_text, "path": path, "chunk_idx": idx})
            idx += 1

        start = end - CHUNK_OVERLAP if end < len(text) else end

    return chunks


async def ingest() -> dict:
    _reset_collection()

    documents = await _fetch_all_docs()
    logger.info(f"Fetched {len(documents)} docs from CouchDB")

    collection = _get_collection()

    try:
        all_ids = collection.get()["ids"]
        if all_ids:
            collection.delete(ids=all_ids)
    except Exception:
        pass

    all_chunks = []
    for doc in documents:
        all_chunks.extend(_chunk_text(doc["content"], doc["path"]))

    if not all_chunks:
        return {"status": "error", "message": "No documents found"}

    BATCH = 100
    total = 0
    for i in range(0, len(all_chunks), BATCH):
        batch = all_chunks[i:i + BATCH]
        ids = [hashlib.md5(f"{c['path']}:{c['chunk_idx']}".encode()).hexdigest() for c in batch]
        texts = [c["text"] for c in batch]
        metadatas = [{"path": c["path"], "chunk_idx": c["chunk_idx"]} for c in batch]
        collection.add(documents=texts, ids=ids, metadatas=metadatas)
        total += len(batch)

    logger.info(f"Ingested {total} chunks from {len(documents)} documents")
    return {"status": "ok", "documents": len(documents), "chunks": total}


def search(query: str, n_results: int = 5) -> list[dict]:
    cache_key = f"{query}::{n_results}"
    now = time.time()

    cached = _search_cache.get(cache_key)
    if cached and (now - cached[0]) < CACHE_TTL:
        return cached[1]

    collection = _get_collection()
    count = collection.count()
    if count == 0:
        return []

    results = collection.query(
        query_texts=[query],
        n_results=min(n_results, count),
    )

    hits = []
    for i in range(len(results["ids"][0])):
        hits.append({
            "text": results["documents"][0][i],
            "path": results["metadatas"][0][i]["path"],
            "distance": results["distances"][0][i] if results.get("distances") else None,
        })

    _search_cache[cache_key] = (now, hits)

    if len(_search_cache) > 200:
        oldest = sorted(_search_cache, key=lambda k: _search_cache[k][0])[:100]
        for k in oldest:
            del _search_cache[k]

    return hits


def get_status() -> dict:
    try:
        collection = _get_collection()
        return {"status": "ok", "chunks": collection.count()}
    except Exception as e:
        return {"status": "error", "message": str(e)}
