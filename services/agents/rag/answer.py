"""Grounded answers to patient questions from the approved KB (#93, #98, #100).

1. Crisis language -> urgent-help text (998 / 999) + human hand-off (deterministic, never a model).
   Personal diagnosis / medication questions -> clinician callback (deterministic, the KB never answers them).
2. Injection attempt -> refuse + hand-off.
3. App cache (scoped by language + KB index version).
4. Retrieve approved chunks. Nothing found -> "ask your care team" + a KB gap for a clinician.
5. AI on: strong model answers ONLY from the numbered sources (prompt `rag_answer`), through the APIM
   semantic cache. The answer must cite a source, use only numbers that appear in the sources and pass
   the no-diagnosis lexicon + Content Safety. Otherwise, or with AI off: extract the best approved paragraph.
"""

from __future__ import annotations

import re
from typing import Any

from agents.common import semantic_cache
from agents.common.guardrails import content_safe, has_red_flag, needs_clinician, no_diagnosis
from agents.common.injection import deny_listed
from agents.rag.kb import index_version
from agents.rag.retrieve import retrieve

TEXT = {
    "crisis": {
        "en": "Please seek urgent medical help now. In the UAE call 998 for an ambulance or 999 for police, or go to the nearest emergency department. A member of our care team will also contact you.",
        "ar": "يرجى طلب المساعدة الطبية العاجلة الآن. في الإمارات اتصل بالرقم 998 للإسعاف أو 999 للشرطة، أو توجه إلى أقرب قسم طوارئ. سيتواصل معك أيضاً أحد أعضاء فريق الرعاية.",
    },
    "clinician": {
        "en": "That needs a clinician who knows your results, so I won't guess. I have asked our care team to call you back. General information is in our approved FAQ.",
        "ar": "هذا السؤال يحتاج إلى طبيب يعرف نتائجك، لذلك لن أخمن. طلبت من فريق الرعاية الاتصال بك. المعلومات العامة موجودة في الأسئلة الشائعة المعتمدة.",
    },
    "blocked": {
        "en": "I can only use approved screening FAQs. Please ask your care team.",
        "ar": "يمكنني استخدام الأسئلة الشائعة المعتمدة فقط. يرجى سؤال فريق الرعاية.",
    },
    "none": {
        "en": "I can only answer from our approved screening FAQ. Please ask your care team, or tap Talk to a person.",
        "ar": "يمكنني الإجابة فقط من الأسئلة الشائعة المعتمدة. يرجى سؤال فريق الرعاية أو اضغط تحدث إلى شخص.",
    },
    "preface": {
        "en": "From our approved FAQ (not a diagnosis): ",
        "ar": "من الأسئلة الشائعة المعتمدة (وليس تشخيصاً): ",
    },
}


def _t(key: str, lang: str) -> str:
    return TEXT[key].get(lang) or TEXT[key]["en"]


def _extract(hit: dict[str, Any], lang: str) -> str:
    text = hit["text"]
    heading = hit.get("heading")
    if heading and text.startswith(heading):
        text = text[len(heading):]
    paras = [p.strip() for p in text.split("\n\n")
             if p.strip() and not p.strip().startswith(("#", "_Simulated", "_محتوى"))]
    body = re.sub(r"\*\*", "", " ".join(paras[:2]))[:500]
    text = _t("preface", lang) + body
    return text if no_diagnosis(text) else _t("none", lang)


def _valid_llm_answer(text: str, hits: list[dict[str, Any]]) -> bool:
    if not text or "NO_ANSWER" in text:
        return False
    cites = {int(n) for n in re.findall(r"\[(\d+)\]", text)}
    if not cites or not cites <= set(range(1, len(hits) + 1)):
        return False
    source_nums = set(re.findall(r"\d+(?:\.\d+)?", " ".join(h["text"] for h in hits)))
    nums = {n for n in re.findall(r"\d+(?:\.\d+)?", re.sub(r"\[\d+\]", "", text))}
    if not nums <= source_nums:
        return False
    return no_diagnosis(text) and content_safe(text)


async def answer(question: str, *, language: str = "en", pii_tokens: dict[str, str] | None = None) -> dict[str, Any]:
    lang = "ar" if language == "ar" else "en"
    if has_red_flag(question):
        return {"answer": _t("crisis", lang), "hand_off": True, "citations": [], "method": "crisis_rule",
                "ai_generated": False, "gap": False}
    if needs_clinician(question):
        # Never answered by the KB or a model; general approved info is attached, with a clinician callback.
        hits = await retrieve(question, language=lang, k=1)
        general = f" {_extract(hits[0], lang)}" if hits else ""
        return {"answer": _t("clinician", lang) + general, "hand_off": True, "callback": "clinician",
                "citations": [{"id": h["doc_id"], "title": h.get("title"), "chunk": h["id"], "source": h.get("source")}
                              for h in hits],
                "method": "clinician_rule", "ai_generated": False, "gap": False}
    if deny_listed(question):
        return {"answer": _t("blocked", lang), "hand_off": True, "blocked_injection": True, "citations": [],
                "method": "injection_rule", "ai_generated": False, "gap": False}

    from agents.common.llm_client import ai_enabled, chat_completion, embed
    from agents.common.pii import scrub

    cache_q = scrub(question, pii_tokens).text  # the cache never holds patient identifiers
    version = index_version()
    scope_key = semantic_cache.scope(lang, version)
    vec = None
    if ai_enabled():
        e = await embed([cache_q])
        vec = e[0] if e else None
    cached = semantic_cache.lookup(cache_q, scope_key=scope_key, embedding=vec)
    if cached:
        return cached

    hits = await retrieve(question, language=lang, k=3)
    if not hits:
        return {"answer": _t("none", lang), "hand_off_offered": True, "citations": [], "method": "no_hit",
                "ai_generated": False, "gap": True}

    citations = [{"id": h["doc_id"], "title": h.get("title"), "chunk": h["id"], "source": h.get("source")} for h in hits]
    out: dict[str, Any] | None = None
    if ai_enabled():
        from agents.common.prompts import get_prompt

        prompt = get_prompt("rag_answer")
        text = await chat_completion(
            system=f"{prompt.system}\nLanguage: {lang}.",
            user=question,
            documents=[h["text"] for h in hits],
            task="rag_answer",
            temperature=prompt.temperature or 0.1,
            max_tokens=prompt.max_tokens,
            pii_tokens=pii_tokens,
            cache_scope=scope_key,
            prompt_ref=prompt.ref,
        )
        if text and _valid_llm_answer(text, hits):
            out = {"answer": text, "citations": citations, "method": "rag_llm_grounded", "ai_generated": True,
                   "prompt": prompt.ref}
    if out is None:
        out = {"answer": _extract(hits[0], lang), "citations": citations, "method": "rag_extractive",
               "ai_generated": False}
    out |= {"hand_off_offered": True, "gap": False, "index_version": version}
    semantic_cache.store(cache_q, out, scope_key=scope_key, embedding=vec)
    return out
