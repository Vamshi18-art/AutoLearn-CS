from __future__ import annotations
 
import os
import json
import hashlib
import logging
import traceback
from pathlib import Path
from typing import List, Optional
 
# ─────────────────────────────────────────────
# Logger (falls back to stdlib if utils missing)
# ─────────────────────────────────────────────
try:
    from utils.logger import logger
except ImportError:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger("rag_agent")
 
# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv()
 
OPENAI_API_KEY   = os.getenv("OPENAI_API_KEY", "")
EMBEDDING_MODEL  = "text-embedding-3-small"
CHUNK_SIZE       = 500
CHUNK_OVERLAP    = 80
TOP_K            = 5
 
# Local storage paths
_BASE_DIR   = Path(__file__).resolve().parent.parent
DATA_DIR    = _BASE_DIR / "data"
FAISS_DIR   = DATA_DIR / "faiss_index"
CACHE_FILE  = DATA_DIR / "rag_cache.json"
 
DATA_DIR.mkdir(parents=True, exist_ok=True)
FAISS_DIR.mkdir(parents=True, exist_ok=True)
 
# ─────────────────────────────────────────────
# Lazy imports — only fail at call-time, not import-time
# ─────────────────────────────────────────────
def _require_langchain():
    """Import heavy LangChain deps; raise ImportError with guidance on failure."""
    try:
        from langchain_community.document_loaders import (
            PyPDFLoader,
            TextLoader,
            Docx2txtLoader,
        )
        from langchain.text_splitter import RecursiveCharacterTextSplitter
        from langchain_community.vectorstores import FAISS
        from langchain_openai import OpenAIEmbeddings
        return PyPDFLoader, TextLoader, Docx2txtLoader, RecursiveCharacterTextSplitter, FAISS, OpenAIEmbeddings
    except ImportError as exc:
        raise ImportError(
            "RAG dependencies not installed. Run:\n"
            "  pip install langchain langchain-community langchain-openai "
            "faiss-cpu pypdf docx2txt\n"
            f"Original error: {exc}"
        ) from exc
 
 
# ─────────────────────────────────────────────
# Embedding Cache (avoids re-embedding same doc)
# ─────────────────────────────────────────────
def _load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text())
        except Exception:
            return {}
    return {}
 
def _save_cache(cache: dict):
    try:
        CACHE_FILE.write_text(json.dumps(cache, indent=2))
    except Exception as e:
        logger.warning(f"Cache save failed: {e}")
 
def _file_hash(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()
 
 
# ─────────────────────────────────────────────
# Document Loader
# ─────────────────────────────────────────────
def _load_document(file_path: str):
    """Load a PDF, TXT, or DOCX file into LangChain Documents."""
    PyPDFLoader, TextLoader, Docx2txtLoader, *_ = _require_langchain()
 
    ext = Path(file_path).suffix.lower()
 
    if ext == ".pdf":
        loader = PyPDFLoader(file_path)
    elif ext in (".txt", ".md"):
        loader = TextLoader(file_path, encoding="utf-8")
    elif ext in (".docx", ".doc"):
        loader = Docx2txtLoader(file_path)
    else:
        raise ValueError(f"Unsupported file type: {ext}. Supported: PDF, TXT, DOCX")
 
    docs = loader.load()
    logger.info(f"Loaded {len(docs)} page(s) from: {file_path}")
    return docs
 
 
# ─────────────────────────────────────────────
# Core: Build / Load FAISS Index
# ─────────────────────────────────────────────
_vectorstore_cache: Optional[object] = None  # module-level singleton
 
def _get_embeddings():
    *_, OpenAIEmbeddings = _require_langchain()
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY not set in environment / .env")
    return OpenAIEmbeddings(
        model=EMBEDDING_MODEL,
        openai_api_key=OPENAI_API_KEY,
    )
 
def _load_existing_index() -> Optional[object]:
    """Load FAISS index from disk if it exists."""
    _, _, _, _, FAISS, _ = _require_langchain()
    index_file = FAISS_DIR / "index.faiss"
    if index_file.exists():
        try:
            vs = FAISS.load_local(
                str(FAISS_DIR),
                _get_embeddings(),
                allow_dangerous_deserialization=True,
            )
            logger.info("Loaded existing FAISS index from disk")
            return vs
        except Exception as e:
            logger.warning(f"Could not load existing FAISS index: {e}")
    return None
 
def _save_index(vectorstore):
    """Persist FAISS index to disk."""
    try:
        vectorstore.save_local(str(FAISS_DIR))
        logger.info(f"FAISS index saved to: {FAISS_DIR}")
    except Exception as e:
        logger.error(f"Failed to save FAISS index: {e}")
 
 
# ─────────────────────────────────────────────
# Public API: add_document
# ─────────────────────────────────────────────
def add_document(file_path: str) -> bool:
    """
    Ingest a document into the FAISS vector store.
 
    Parameters
    ----------
    file_path : str
        Absolute or relative path to a PDF / TXT / DOCX file.
 
    Returns
    -------
    bool
        True on success, False on failure.
    """
    global _vectorstore_cache
 
    try:
        _, _, _, RecursiveCharacterTextSplitter, FAISS, _ = _require_langchain()
 
        # Check embedding cache to avoid re-processing same file
        cache = _load_cache()
        file_hash = _file_hash(file_path)
        if cache.get(file_path) == file_hash:
            logger.info(f"Document already indexed (cache hit): {file_path}")
            return True
 
        # Load + split
        docs = _load_document(file_path)
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
        )
        chunks = splitter.split_documents(docs)
        logger.info(f"Split into {len(chunks)} chunks")
 
        embeddings = _get_embeddings()
 
        if _vectorstore_cache is None:
            _vectorstore_cache = _load_existing_index()
 
        if _vectorstore_cache is None:
            # Build fresh index
            _vectorstore_cache = FAISS.from_documents(chunks, embeddings)
            logger.info("Created new FAISS index")
        else:
            # Merge into existing
            _vectorstore_cache.add_documents(chunks)
            logger.info("Added documents to existing FAISS index")
 
        _save_index(_vectorstore_cache)
 
        # Update cache
        cache[file_path] = file_hash
        _save_cache(cache)
 
        logger.info(f"✅ Document indexed successfully: {file_path}")
        return True
 
    except Exception as e:
        logger.error(f"add_document failed: {e}\n{traceback.format_exc()}")
        return False
 
 
# ─────────────────────────────────────────────
# Public API: get_rag_context
# ─────────────────────────────────────────────
def get_rag_context(query: str, top_k: int = TOP_K) -> str:
    """
    Retrieve the most relevant context chunks for a given query.
 
    Parameters
    ----------
    query : str
        The topic / question to search for.
    top_k : int
        Number of top chunks to retrieve (default: 5).
 
    Returns
    -------
    str
        Concatenated context text, or empty string if no index exists.
    """
    global _vectorstore_cache
 
    if not query or not query.strip():
        logger.warning("get_rag_context called with empty query")
        return ""
 
    try:
        _require_langchain()  # validate deps
 
        # Load from disk if not in memory
        if _vectorstore_cache is None:
            _vectorstore_cache = _load_existing_index()
 
        if _vectorstore_cache is None:
            logger.info("No FAISS index found — RAG context unavailable")
            return ""
 
        docs = _vectorstore_cache.similarity_search(query, k=top_k)
 
        if not docs:
            logger.info(f"No relevant chunks found for query: '{query}'")
            return ""
 
        context_parts = []
        for i, doc in enumerate(docs, 1):
            source = doc.metadata.get("source", "document")
            page   = doc.metadata.get("page", "")
            ref    = f"{Path(source).name} p.{page}" if page != "" else Path(source).name
            context_parts.append(f"[{i}] ({ref})\n{doc.page_content.strip()}")
 
        context = "\n\n".join(context_parts)
        logger.info(f"Retrieved {len(docs)} context chunks for: '{query}'")
        return context
 
    except Exception as e:
        logger.error(f"get_rag_context failed: {e}\n{traceback.format_exc()}")
        return ""
 
 
# ─────────────────────────────────────────────
# Public API: has_index
# ─────────────────────────────────────────────
def has_index() -> bool:
    """
    Returns True if a FAISS index exists on disk (documents have been ingested).
    Used by custom_slide_agent to decide whether to use RAG mode.
    """
    return (FAISS_DIR / "index.faiss").exists()
 
 
# ─────────────────────────────────────────────
# Public API: clear_index
# ─────────────────────────────────────────────
def clear_index():
    """Delete the FAISS index and embedding cache (for testing / reset)."""
    global _vectorstore_cache
    import shutil
    try:
        if FAISS_DIR.exists():
            shutil.rmtree(FAISS_DIR)
            FAISS_DIR.mkdir(parents=True, exist_ok=True)
        if CACHE_FILE.exists():
            CACHE_FILE.unlink()
        _vectorstore_cache = None
        logger.info("FAISS index and cache cleared")
    except Exception as e:
        logger.error(f"clear_index failed: {e}")
 
 
# ─────────────────────────────────────────────
# Exports
# ─────────────────────────────────────────────
__all__ = [
    "add_document",
    "get_rag_context",
    "has_index",
    "clear_index",
]
 
 
# ─────────────────────────────────────────────
# Standalone test
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("=== RAG Agent Self-Test ===")
    print(f"FAISS dir     : {FAISS_DIR}")
    print(f"Index exists  : {has_index()}")
    print(f"Embedding model: {EMBEDDING_MODEL}")
 
    ctx = get_rag_context("Binary Search Tree operations")
    if ctx:
        print(f"\nSample context (first 300 chars):\n{ctx[:300]}")
    else:
        print("\nNo context available — add documents first via add_document(path)")