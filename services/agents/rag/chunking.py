"""KB document parsing and chunking, shared by the API retriever and the ingestion pipeline.

Docs are markdown with a YAML front matter (id, title, language, topic, audience,
clinical_review_status, reviewer, version, last_reviewed, source). Older docs approved in the app may
carry an `<!-- approved_by: ... -->` comment instead; they count as approved.

Chunking is heading-aware and token-sized: the body is split into sections by markdown headings, each
section is packed into chunks of at most `max_tokens` (estimated) with `overlap_tokens` of trailing
sentences carried into the next chunk of the same section. Every chunk starts with its heading path
("Title > Section") so it can be read and ranked on its own.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date
from typing import Any

import yaml

ARABIC = re.compile(r"[\u0600-\u06FF]")
HEADER = re.compile(r"^<!--.*?-->\s*", re.DOTALL)
LEGACY_APPROVED = re.compile(r"<!--\s*approved_by:\s*([^\s;]+)")
HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
SENTENCE = re.compile(r"(?<=[.!?؟。])\s+")
DEMO_SOURCE = "simulated demo content, not medical advice"
APPROVED = "approved"
LANGUAGES = ("en", "ar")


def detect_language(text: str) -> str:
    letters = re.findall(r"[A-Za-z\u0600-\u06FF]", text)
    if not letters:
        return "en"
    ar = sum(1 for c in letters if ARABIC.match(c))
    return "ar" if ar / len(letters) > 0.3 else "en"


def split_front_matter(text: str) -> tuple[dict[str, Any], str]:
    """(metadata, body). Front matter must open the file with `---`."""
    text = text.lstrip("\ufeff")
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            meta = yaml.safe_load(text[4:end]) or {}
            return (meta if isinstance(meta, dict) else {}), text[end + 5 :]
    return {}, text


def title_of(text: str, fallback: str) -> str:
    meta, body = split_front_matter(text)
    if meta.get("title"):
        return str(meta["title"])
    for line in HEADER.sub("", body).splitlines():
        if line.startswith("#"):
            return line.lstrip("#").strip()
    return fallback


def parse_doc(text: str, doc_id: str) -> dict[str, Any]:
    """Normalised metadata + body for one KB doc. `approved` is the only retrieval switch."""
    meta, body = split_front_matter(text)
    legacy = LEGACY_APPROVED.search(text)
    if meta:
        status = str(meta.get("clinical_review_status", "draft")).lower()
        reviewer = meta.get("reviewer") or "unknown"
    elif legacy:
        status, reviewer = APPROVED, legacy.group(1)
    else:
        status, reviewer = "draft", "none"
    body = HEADER.sub("", body).strip()
    reviewed = meta.get("last_reviewed")
    return {
        "id": str(meta.get("id") or doc_id),
        "title": str(meta.get("title") or title_of(body, doc_id)),
        "language": str(meta.get("language") or detect_language(body)),
        "topic": str(meta.get("topic") or "general"),
        "audience": str(meta.get("audience") or "patient"),
        "clinical_review_status": status,
        "approved": status == APPROVED,
        "reviewer": str(reviewer),
        "version": str(meta.get("version") or "1"),
        "last_reviewed": reviewed.isoformat() if isinstance(reviewed, date) else str(reviewed or ""),
        "source": str(meta.get("source") or DEMO_SOURCE),
        "body": body,
    }


def estimate_tokens(text: str) -> int:
    """Rough cl100k-style estimate without a tokenizer: ~1.3 tokens per Latin word, ~2.5 per Arabic word."""
    words = re.findall(r"[\w\u0600-\u06FF]+", text)
    arabic = sum(1 for w in words if ARABIC.search(w))
    punct = len(re.findall(r"[^\w\s]", text))
    return int((len(words) - arabic) * 1.3 + arabic * 2.5 + punct * 0.5) + 1


def _sections(body: str, title: str) -> list[tuple[str, list[str]]]:
    """[(heading path, paragraphs)] in document order. The H1 is the doc title."""
    sections: list[tuple[str, list[str]]] = []
    path: list[tuple[int, str]] = []
    paras: list[str] = []
    buf: list[str] = []

    def flush_para() -> None:
        if buf:
            p = "\n".join(buf).strip()
            if p:
                paras.append(p)
            buf.clear()

    def heading_path() -> str:
        names = [h for _, h in path if h != title]
        return " > ".join([title, *names])

    current = heading_path()
    for line in body.splitlines():
        m = HEADING.match(line)
        if m:
            flush_para()
            if paras:
                sections.append((current, paras))
                paras = []
            level = len(m.group(1))
            path = [(lvl, h) for lvl, h in path if lvl < level] + [(level, m.group(2).strip())]
            current = heading_path()
        elif not line.strip():
            flush_para()
        else:
            buf.append(line)
    flush_para()
    if paras:
        sections.append((current, paras))
    return sections


def _pieces(paragraph: str, max_tokens: int) -> list[str]:
    """A paragraph, or its sentences (or hard word windows) when it is longer than max_tokens."""
    if estimate_tokens(paragraph) <= max_tokens:
        return [paragraph]
    out: list[str] = []
    for s in SENTENCE.split(paragraph):
        if estimate_tokens(s) <= max_tokens:
            out.append(s)
            continue
        words = s.split()
        step = max(1, int(max_tokens / 1.6))
        out += [" ".join(words[i : i + step]) for i in range(0, len(words), step)]
    return out


def chunk_document(body: str, *, title: str, max_tokens: int = 320, overlap_tokens: int = 48) -> list[dict[str, Any]]:
    """Heading-aware, token-sized chunks with sentence overlap inside a section."""
    chunks: list[dict[str, Any]] = []
    for heading, paras in _sections(body, title):
        prefix = f"{heading}\n\n"
        budget = max(32, max_tokens - estimate_tokens(prefix))
        pieces = [p for para in paras for p in _pieces(para, budget)]
        cur: list[str] = []
        for piece in pieces:
            if cur and estimate_tokens("\n\n".join([*cur, piece])) > budget:
                chunks.append({"heading": heading, "text": prefix + "\n\n".join(cur)})
                carry: list[str] = []
                for sent in reversed(SENTENCE.split(cur[-1])):
                    if estimate_tokens(" ".join([sent, *carry])) > overlap_tokens:
                        break
                    carry.insert(0, sent)
                cur = [" ".join(carry)] if carry and overlap_tokens else []
            cur.append(piece)
        if cur:
            chunks.append({"heading": heading, "text": prefix + "\n\n".join(cur)})
    for c in chunks:
        c["tokens"] = estimate_tokens(c["text"])
    return chunks


def chunk_markdown(text: str, *, max_tokens: int = 320, overlap_tokens: int = 48) -> list[str]:
    """Chunk texts of a raw markdown doc (front matter stripped)."""
    doc = parse_doc(text, "doc")
    return [c["text"] for c in chunk_document(doc["body"], title=doc["title"], max_tokens=max_tokens,
                                              overlap_tokens=overlap_tokens)]


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


STOPWORDS = frozenset(
    ["the", "and", "for", "are", "you", "your", "can", "what", "does", "with", "this", "that", "from", "have", "has", "was", "will", "not", "but", "how", "why", "when", "who", "which", "about", "into", "after", "before", "there", "their", "our", "any", "all", "may", "might", "should", "would", "could", "get", "got", "does", "did", "its", "it's", "than", "then", "them", "they", "she", "his", "her", "him", "i'm", "don't", "can't", "is", "a", "an", "of", "to", "in", "on", "at", "by", "or", "be", "do", "my", "me", "ما", "هل", "في", "من", "على", "إلى", "عن", "مع", "هذا", "هذه", "ذلك", "التي", "الذي", "أن", "إن", "كان", "لا", "لم", "لن", "قد", "ثم", "أو", "كيف", "لماذا", "متى"]
)


AR_DIACRITICS = re.compile(r"[\u064B-\u0652\u0640]")  # harakat + tatweel
AR_PREFIXES = ("وال", "بال", "كال", "فال", "لل", "ال", "و", "ب", "ل", "ف")
AR_SUFFIXES = ("هما", "كما", "ها", "هم", "كم", "نا", "ي", "ك", "ه")


def normalize_arabic(word: str) -> str:
    """Light Arabic normalisation + stemming for BM25: alef/ya/ta-marbuta forms, clitic prefixes, pronoun suffixes."""
    w = AR_DIACRITICS.sub("", word)
    w = re.sub("[أإآ]", "ا", w).replace("ى", "ي").replace("ة", "ه")
    for p in AR_PREFIXES:
        if w.startswith(p) and len(w) - len(p) >= 3:
            w = w[len(p):]
            break
    for sfx in AR_SUFFIXES:
        if w.endswith(sfx) and len(w) - len(sfx) >= 3:
            w = w[: -len(sfx)]
            break
    return w


def tokenize(text: str) -> list[str]:
    out = []
    for t in re.findall(r"\w+", (text or "").lower()):  # \w covers Arabic letters, not ؟ or ،
        if len(t) <= 2 or t in STOPWORDS:
            continue
        out.append(normalize_arabic(t) if ARABIC.search(t) else t)
    return out
