"""Azure AI Language PII detection (PiiEntityRecognition), layered after the regex scrubber (#pii).

The regex scrubber (agents.common.pii) always runs first: Emirates ID, NRIC, phones, emails, MRN and
labelled names. This layer then catches what patterns cannot, above all bare names ("Fatima is scared",
"tell Omar"), addresses and other free-text identifiers, in the text's own language.

LANGUAGE_ENDPOINT is the APIM gateway (Terraform default: `/language/:analyze-text`, PiiEntityRecognition
only, managed identity to the Language resource) or a Language resource endpoint for local testing.
Key: LANGUAGE_KEY, else LLM_API_KEY (the APIM subscription key), sent as Ocp-Apim-Subscription-Key;
without a key, an Entra ID token (managed identity) is used.

Fail closed: when LANGUAGE_PII_ENABLED is on and the call fails, `LanguagePiiError` is raised and the
caller must not send the text to a model (agents.common.llm_client returns None; templates are used).
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from agents.common import ai_metrics

log = logging.getLogger("rabt.language_pii")
API_VERSION = os.environ.get("LANGUAGE_API_VERSION", "2024-11-01")
MAX_CHARS = 5000  # synchronous analyze-text limit is 5,120 characters per document
MAX_DOCS = 5  # synchronous PII limit per request

# Languages Language PII supports that Rabt may see; others are sent as English (names in Latin script
# are still found; the regex layer still runs). Source: Language PII language support, 2026.
SUPPORTED = {"en", "ar", "hi", "ur", "ml", "ta", "bn", "fr", "es", "de", "zh-hans", "ru", "fa"}

# Language category -> Rabt placeholder kind. Everything else (dates, ages, organisations, medical terms)
# is left in place: the model needs it and it does not identify the patient on its own.
CATEGORIES = {
    "Person": "NAME",
    "PhoneNumber": "PHONE",
    "Email": "EMAIL",
    "Address": "ADDRESS",
    "IPAddress": "IP",
    "CreditCardNumber": "CARD",
    "InternationalBankingAccountNumber": "IBAN",
    "PassportNumber": "PASSPORT",
}


class LanguagePiiError(RuntimeError):
    """Language PII is enabled but the call failed: do not send the text to a model."""


def enabled() -> bool:
    flag = os.environ.get("LANGUAGE_PII_ENABLED", "false").strip().lower() in ("1", "true", "yes", "on")
    return flag and bool(os.environ.get("LANGUAGE_ENDPOINT", "").strip())


def min_confidence() -> float:
    try:
        return float(os.environ.get("LANGUAGE_PII_MIN_CONFIDENCE", "0.6"))
    except ValueError:
        return 0.6


def _lang(language: str | None) -> str:
    lang = (language or "en").lower()
    return lang if lang in SUPPORTED else "en"


def _headers() -> dict[str, str]:
    h = {"Content-Type": "application/json"}
    key = os.environ.get("LANGUAGE_KEY") or os.environ.get("LLM_API_KEY") or ""
    if key:
        h["Ocp-Apim-Subscription-Key"] = key
    else:
        from azure.identity import DefaultAzureCredential

        h["Authorization"] = "Bearer " + DefaultAzureCredential().get_token(
            "https://cognitiveservices.azure.com/.default").token
    return h


def _windows(text: str) -> list[str]:
    return [text[i : i + MAX_CHARS] for i in range(0, len(text), MAX_CHARS)] or [""]


def detect(texts: list[str], language: str | None = None) -> list[list[dict[str, Any]]]:
    """Entities per input text: [{"text", "category", "kind", "score"}]. Raises LanguagePiiError."""
    base = os.environ.get("LANGUAGE_ENDPOINT", "").strip().rstrip("/")
    url = f"{base}/language/:analyze-text?api-version={API_VERSION}"
    lang = _lang(language)
    pieces = [(i, w) for i, t in enumerate(texts) for w in _windows(t) if w.strip()]
    found: list[list[dict[str, Any]]] = [[] for _ in texts]
    threshold = min_confidence()
    for start in range(0, len(pieces), MAX_DOCS):
        batch = pieces[start : start + MAX_DOCS]
        body = {
            "kind": "PiiEntityRecognition",
            "parameters": {"modelVersion": "latest", "piiCategories": list(CATEGORIES), "domain": "none"},
            "analysisInput": {"documents": [{"id": str(n), "language": lang, "text": w}
                                            for n, (_, w) in enumerate(batch)]},
        }
        try:
            r = httpx.post(url, json=body, headers=_headers(), timeout=float(os.environ.get("LANGUAGE_TIMEOUT", "8")))
            r.raise_for_status()
            results = r.json()["results"]
            if results.get("errors"):
                raise ValueError("document errors")
        except Exception as e:  # network, 4xx/5xx, bad JSON, per-document errors
            log.warning("language_pii_failed err=%s", type(e).__name__)
            ai_metrics.incr("language_pii_errors")
            raise LanguagePiiError(type(e).__name__) from e
        for doc in results.get("documents", []):
            owner = batch[int(doc["id"])][0]
            for ent in doc.get("entities", []):
                kind = CATEGORIES.get(ent.get("category", ""))
                score = float(ent.get("confidenceScore") or 0)
                text = ent.get("text") or ""
                if kind and score >= threshold and text.strip() and "[" not in text:
                    found[owner].append({"text": text, "category": ent["category"], "kind": kind, "score": score})
    ai_metrics.incr("language_pii_calls")
    return found
