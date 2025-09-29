"""hooks.py

Lightweight placeholder hooks for future NLP / RAG pipeline integration.

These functions are intentionally simple stubs so the ingestion pipeline can
be instrumented without pulling heavy dependencies yet.

Planned future enhancements (not implemented here):
  * Real language detection (e.g., langdetect, fasttext).
  * Sentiment analysis (e.g., transformers pipeline or rule-based model).
  * Category auto-classification using ML model.
  * Embedding generation + vector store insertion.
"""
from __future__ import annotations

from typing import List


def detect_language(text: str) -> str:
    """Heuristic placeholder for language detection.

    Strategy:
        - Very naive inspection of a few Unicode ranges / characters.
        - Returns ISO-like codes: 'en', 'ar', or 'unknown'.
    """
    if not text:
        return "unknown"
    sample = text[:400]
    # Simple heuristic for Arabic script
    for ch in sample:
        if '\u0600' <= ch <= '\u06FF':
            return "ar"
    # Default to English unless obviously something else (expand later)
    return "en"


def analyze_sentiment(text: str) -> str:
    """Placeholder sentiment analysis returning 'neutral'.

    Future:
        - Replace with a real model or API call.
    """
    return "neutral"


def auto_categorize(text: str, fallback: str = "uncategorized") -> str:
    """Placeholder category assignment.

    Simple keyword-based example. Expand with ML classifier later.
    """
    if not text:
        return fallback
    lowered = text.lower()
    if any(k in lowered for k in ("stock", "market", "finance", "bank")):
        return "finance"
    if any(k in lowered for k in ("ai", "software", "technology", "startup")):
        return "tech"
    if any(k in lowered for k in ("election", "president", "government", "war")):
        return "international"
    return fallback


def chunk_text(text: str, max_chars: int = 1500, overlap: int = 100) -> List[str]:
    """Split text into overlapping chunks suitable for embedding generation.

    Args:
        text: Full content string.
        max_chars: Maximum characters per chunk.
        overlap: Number of characters to overlap between adjacent chunks.
    """
    if not text:
        return []
    if max_chars <= 0:
        return [text]
    chunks: List[str] = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + max_chars, length)
        chunk = text[start:end]
        chunks.append(chunk)
        if end == length:
            break
        start = end - overlap if overlap > 0 else end
        if start < 0:
            start = 0
    return chunks


__all__ = [
    "detect_language",
    "analyze_sentiment",
    "auto_categorize",
    "chunk_text",
]
