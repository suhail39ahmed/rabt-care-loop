"""Markdown chunking shared by the API retriever and the ingestion job."""

from __future__ import annotations

import hashlib
import re

ARABIC = re.compile(r"[\u0600-\u06FF]")
HEADER = re.compile(r"^<!--.*?-->\s*", re.DOTALL)


def detect_language(text: str) -> str:
    letters = re.findall(r"[A-Za-z\u0600-\u06FF]", text)
    if not letters:
        return "en"
    ar = sum(1 for c in letters if ARABIC.match(c))
    return "ar" if ar / len(letters) > 0.3 else "en"


def title_of(text: str, fallback: str) -> str:
    for line in HEADER.sub("", text).splitlines():
        if line.startswith("#"):
            return line.lstrip("#").strip()
    return fallback


def chunk_markdown(text: str, *, max_chars: int = 1200, overlap: int = 150) -> list[str]:
    """Split on headings/paragraphs, pack paragraphs up to max_chars, carry a small overlap."""
    body = HEADER.sub("", text).strip()
    paras = [p.strip() for p in re.split(r"\n\s*\n|(?=^#{1,6}\s)", body, flags=re.MULTILINE) if p and p.strip()]
    chunks: list[str] = []
    cur = ""
    for p in paras:
        while len(p) > max_chars:
            head, p = p[:max_chars], p[max_chars - overlap :]
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.append(head)
        if cur and len(cur) + len(p) + 2 > max_chars:
            chunks.append(cur)
            cur = cur[-overlap:] + "\n\n" + p if overlap else p
        else:
            cur = f"{cur}\n\n{p}" if cur else p
    if cur:
        chunks.append(cur)
    return chunks


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


STOPWORDS = frozenset(
    ["the", "and", "for", "are", "you", "your", "can", "what", "does", "with", "this", "that", "from", "have", "has", "was", "will", "not", "but", "how", "why", "when", "who", "which", "about", "into", "after", "before", "there", "their", "our", "any", "all", "may", "might", "should", "would", "could", "get", "got", "does", "did", "its", "it's", "than", "then", "them", "they", "she", "his", "her", "him", "i'm", "don't", "can't", "is", "a", "an", "of", "to", "in", "on", "at", "by", "or", "be", "do", "my", "me", "ما", "هل", "في", "من", "على", "إلى", "عن", "مع", "هذا", "هذه", "ذلك", "التي", "الذي", "أن", "إن", "كان", "لا", "لم", "لن", "قد", "ثم", "أو", "كيف", "لماذا", "متى"]
)


def tokenize(text: str) -> list[str]:
    return [
        t for t in re.findall(r"[\w\u0600-\u06FF]+", (text or "").lower()) if len(t) > 2 and t not in STOPWORDS
    ]
