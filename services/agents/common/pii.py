"""PII scrubbing applied to every prompt before it leaves Rabt (#99).

What is scrubbed (in this order):
  1. Known identifiers for the case (names in English/Arabic, MRN...) passed in as tokens.
  2. Emirates ID (784-YYYY-NNNNNNN-C, with or without dashes/spaces).
  3. Singapore NRIC/FIN (S/T/F/G/M + 7 digits + letter).
  4. Email addresses.
  5. Phone numbers: UAE (+971 / 00971 / 05x), Singapore (+65 / 0065), any other "+<country>" number,
     and the 10-digit NNN-NNN-NNNN form.
  6. Medical record numbers written as "MRN: ...".
  7. Names introduced by a label: "my name is ...", "Mr./Mrs./Dr. ...", "اسمي ...", "السيد ...".

`scrub()` is one-way (placeholders such as [PHONE]). `pseudonymize()` swaps the same items for
numbered placeholders and returns the mapping, so a translation can be restored locally after the
model call without the model ever seeing the real values.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

_AR = r"[\u0621-\u064A]+"
_EN_NAME = r"[A-Z][a-z'\-]+(?:\s+[A-Z][a-z'\-]+){0,2}"

PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("EMIRATES_ID", re.compile(r"\b784[-\s]?\d{4}[-\s]?\d{7}[-\s]?\d\b")),
    ("NRIC", re.compile(r"\b[STFGM]\d{7}[A-Z]\b")),
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")),
    # UAE: +971 / 00971 / 971 then 8-9 digits (mobile 5x, landline 2/3/4/6/7/9), separators allowed
    ("PHONE", re.compile(r"(?:\+|00)?971[\s\-]?\(?0?\)?[\s\-]?[2-9](?:[\s\-]?\d){7,8}\b")),
    # UAE local mobile 05x xxx xxxx
    ("PHONE", re.compile(r"\b05\d[\s\-]?\d{3}[\s\-]?\d{4}\b")),
    # Singapore: +65 / 0065 then 8 digits starting 3/6/8/9
    ("PHONE", re.compile(r"(?:\+|00)65[\s\-]?[3689]\d{3}[\s\-]?\d{4}\b")),
    # Any other international number
    ("PHONE", re.compile(r"\+\d{1,3}[\s\-]?\(?\d{1,4}\)?(?:[\s\-]?\d){6,10}\b")),
    ("PHONE", re.compile(r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b|\b\d{10}\b")),
    ("MRN", re.compile(r"\bMRN[:#\s]*[A-Z0-9\-]{4,}\b", re.IGNORECASE)),
]

# Labelled names keep the label and replace only the name.
NAME_PATTERNS: list[re.Pattern[str]] = [
    re.compile(rf"(\b(?i:my name is|name is|name:|patient:|i am|i'm|this is)\s+)({_EN_NAME})"),
    re.compile(rf"(\b(?:Mr|Mrs|Ms|Miss|Dr)\.?\s+)({_EN_NAME})"),
    re.compile(rf"((?:اسمي|الاسم|اسم المريض|اسم المريضة|المريض|المريضة|السيد|السيدة|الأستاذ|الأستاذة|الدكتور|الدكتورة)[:\s]+)({_AR}(?:\s+(?!و){_AR}){{0,3}})"),
]


@dataclass
class ScrubResult:
    text: str
    counts: Counter = field(default_factory=Counter)
    mapping: dict[str, str] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return sum(self.counts.values())


def _run(text: str, tokens: dict[str, str] | None, numbered: bool) -> ScrubResult:
    res = ScrubResult(text=text or "")
    seq = Counter()

    def placeholder(kind: str, value: str) -> str:
        res.counts[kind] += 1
        if not numbered:
            return f"[{kind}]"
        for ph, real in res.mapping.items():
            if real == value:
                return ph
        seq[kind] += 1
        ph = f"[{kind}_{seq[kind]}]"
        res.mapping[ph] = value
        return ph

    out = res.text
    for real, token in sorted((tokens or {}).items(), key=lambda kv: -len(kv[0])):
        if real and real in out:
            n = out.count(real)
            if numbered:
                ph = placeholder("NAME", real)
                out = out.replace(real, ph)
                res.counts["NAME"] += n - 1
            else:
                out = out.replace(real, token)
                res.counts["TOKEN"] += n
    for kind, pat in PATTERNS:
        out = pat.sub(lambda m, k=kind: placeholder(k, m.group(0)), out)
    for pat in NAME_PATTERNS:
        out = pat.sub(lambda m: m.group(1) + placeholder("NAME", m.group(2)), out)
    res.text = out
    return res


def scrub(text: str, tokens: dict[str, str] | None = None) -> ScrubResult:
    """One-way scrub. Returns text plus counts per PII type (for metrics; never the values)."""
    return _run(text, tokens, numbered=False)


def pseudonymize(text: str, tokens: dict[str, str] | None = None) -> ScrubResult:
    """Reversible scrub: numbered placeholders + mapping kept locally."""
    return _run(text, tokens, numbered=True)


def restore(text: str, mapping: dict[str, str]) -> str:
    for ph, real in mapping.items():
        text = text.replace(ph, real)
    return text


def scrub_pii_uae(text: str, tokens: dict[str, str] | None = None) -> str:
    """Backwards-compatible helper."""
    return scrub(text, tokens).text
