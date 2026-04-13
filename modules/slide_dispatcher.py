from __future__ import annotations
 
import logging
from typing import List, Optional
 
# ─────────────────────────────────────────────
# Logger
# ─────────────────────────────────────────────
try:
    from utils.logger import logger
except ImportError:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger("slide_dispatcher")
 
# ─────────────────────────────────────────────
# Internal flag: "general" | "rag"
# Default is "general". Auto-switches to "rag" when FAISS index exists.
# ─────────────────────────────────────────────
_MODE_GENERAL = "general"
_MODE_RAG     = "rag"
 
 
def _detect_mode() -> str:
    """
    Automatically detect whether RAG mode should be used.
    Returns 'rag' if a FAISS index is present, else 'general'.
    No UI interaction needed — fully automatic.
    """
    try:
        from modules.rag_agent import has_index
        if has_index():
            logger.info("RAG index detected — switching to RAG mode")
            return _MODE_RAG
    except ImportError:
        logger.debug("rag_agent not available — using general mode")
    except Exception as e:
        logger.warning(f"Mode detection failed: {e} — defaulting to general")
 
    return _MODE_GENERAL
 
 
# ─────────────────────────────────────────────
# Public API: dispatch_slides
# ─────────────────────────────────────────────
def dispatch_slides(topic: str, force_mode: Optional[str] = None) -> List[dict]:
    """
    Smart slide generation dispatcher.
 
    Parameters
    ----------
    topic : str
        The CS/programming topic to generate slides for.
    force_mode : str, optional
        Override auto-detection. Pass "general" or "rag" explicitly.
 
    Returns
    -------
    list[dict]
        Slide dicts compatible with generate_slides_and_save().
        Each dict: {"title": str, "content": list[str], "type": str}
 
    Flow
    ----
    1. Auto-detect mode (or use force_mode).
    2a. RAG mode    → get_rag_context(topic) → generate_custom_slides(topic, context)
    2b. General mode → generate_custom_slides(topic)
    3. If custom agent fails → fall back to original generate_topic_slides(topic).
    """
    mode = force_mode if force_mode in (_MODE_GENERAL, _MODE_RAG) else _detect_mode()
    logger.info(f"dispatch_slides | topic='{topic}' | mode={mode}")
 
    try:
        from modules.custom_slide_agent import generate_custom_slides
 
        context: Optional[str] = None
 
        if mode == _MODE_RAG:
            try:
                from modules.rag_agent import get_rag_context
                context = get_rag_context(topic)
                if context:
                    logger.info(f"RAG context retrieved ({len(context)} chars)")
                else:
                    logger.info("RAG returned empty context — falling back to general")
            except Exception as rag_err:
                logger.warning(f"RAG context retrieval failed: {rag_err} — using general")
                context = None
 
        slides = generate_custom_slides(topic, context)
 
        if slides:
            logger.info(f"✅ dispatch_slides success | mode={mode} | slides={len(slides)}")
            return slides
        else:
            raise ValueError("generate_custom_slides returned empty list")
 
    except Exception as e:
        logger.error(f"Custom agent failed: {e} — falling back to original generator")
 
    # ── FALLBACK: original generator (keeps existing behaviour intact) ──
    try:
        from modules.generator import generate_topic_slides
        logger.info("Using original generate_topic_slides as fallback")
        return generate_topic_slides(topic)
    except Exception as fallback_err:
        logger.error(f"Fallback generator also failed: {fallback_err}")
        return []
 
 
# ─────────────────────────────────────────────
# Convenience: expose rag_agent utilities
# so callers only need one import
# ─────────────────────────────────────────────
def ingest_document(file_path: str) -> bool:
    """
    Add a document to the RAG vector store.
    Returns True on success.
    """
    try:
        from modules.rag_agent import add_document
        return add_document(file_path)
    except Exception as e:
        logger.error(f"ingest_document failed: {e}")
        return False
 
 
def rag_available() -> bool:
    """True if RAG dependencies are installed and index exists."""
    try:
        from modules.rag_agent import has_index
        return has_index()
    except Exception:
        return False
 
 
# ─────────────────────────────────────────────
# Exports
# ─────────────────────────────────────────────
__all__ = [
    "dispatch_slides",
    "ingest_document",
    "rag_available",
]