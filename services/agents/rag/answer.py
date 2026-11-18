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
        "hi": "कृपया अभी तुरंत चिकित्सा सहायता लें। यूएई में एम्बुलेंस के लिए 998 या पुलिस के लिए 999 पर कॉल करें, या निकटतम आपातकालीन विभाग में जाएँ। हमारी देखभाल टीम का एक सदस्य भी आपसे संपर्क करेगा।",
        "ur": "براہ کرم ابھی فوری طبی مدد حاصل کریں۔ متحدہ عرب امارات میں ایمبولینس کے لیے 998 یا پولیس کے لیے 999 پر کال کریں، یا قریبی ایمرجنسی شعبے میں جائیں۔ ہماری نگہداشت ٹیم کا ایک رکن بھی آپ سے رابطہ کرے گا۔",
        "ml": "ദയവായി ഇപ്പോൾ തന്നെ അടിയന്തര വൈദ്യസഹായം തേടുക. യുഎഇയിൽ ആംബുലൻസിനായി 998 അല്ലെങ്കിൽ പോലീസിനായി 999 വിളിക്കുക, അല്ലെങ്കിൽ ഏറ്റവും അടുത്തുള്ള അത്യാഹിത വിഭാഗത്തിലേക്ക് പോകുക. ഞങ്ങളുടെ കെയർ ടീമിലെ ഒരാളും നിങ്ങളെ ബന്ധപ്പെടും.",
        "tl": "Mangyaring humingi agad ng tulong medikal. Sa UAE, tumawag sa 998 para sa ambulansya o 999 para sa pulis, o pumunta sa pinakamalapit na emergency department. Kokontakin ka rin ng isang miyembro ng aming care team.",
        "bn": "অনুগ্রহ করে এখনই জরুরি চিকিৎসা সহায়তা নিন। সংযুক্ত আরব আমিরাতে অ্যাম্বুলেন্সের জন্য 998 বা পুলিশের জন্য 999 নম্বরে কল করুন, অথবা নিকটতম জরুরি বিভাগে যান। আমাদের কেয়ার টিমের একজন সদস্যও আপনার সাথে যোগাযোগ করবেন।",
    },
    "clinician": {
        "en": "That needs a clinician who knows your results, so I won't guess. I have asked our care team to call you back. General information is in our approved FAQ.",
        "ar": "هذا السؤال يحتاج إلى طبيب يعرف نتائجك، لذلك لن أخمن. طلبت من فريق الرعاية الاتصال بك. المعلومات العامة موجودة في الأسئلة الشائعة المعتمدة.",
        "hi": "इस प्रश्न के लिए ऐसे डॉक्टर की ज़रूरत है जो आपके परिणाम जानते हों, इसलिए मैं अनुमान नहीं लगाऊँगा। मैंने देखभाल टीम से आपको वापस कॉल करने को कहा है। सामान्य जानकारी हमारे स्वीकृत FAQ में है।",
        "ur": "اس سوال کے لیے ایسے معالج کی ضرورت ہے جو آپ کے نتائج جانتا ہو، اس لیے میں اندازہ نہیں لگاؤں گا۔ میں نے نگہداشت ٹیم سے آپ کو واپس کال کرنے کو کہا ہے۔ عمومی معلومات ہمارے منظور شدہ سوالات میں موجود ہیں۔",
        "ml": "നിങ്ങളുടെ ഫലങ്ങൾ അറിയുന്ന ഒരു ഡോക്ടർ ഇതിന് ഉത്തരം നൽകണം, അതിനാൽ ഞാൻ ഊഹിക്കില്ല. നിങ്ങളെ തിരികെ വിളിക്കാൻ കെയർ ടീമിനോട് ആവശ്യപ്പെട്ടിട്ടുണ്ട്. പൊതുവായ വിവരങ്ങൾ ഞങ്ങളുടെ അംഗീകൃത FAQ-ൽ ഉണ്ട്.",
        "tl": "Kailangan ito ng doktor na nakakaalam ng iyong resulta, kaya hindi ako manghuhula. Hiniling ko sa care team na tawagan ka. Nasa aming aprubadong FAQ ang pangkalahatang impormasyon.",
        "bn": "এই প্রশ্নের জন্য এমন একজন চিকিৎসক দরকার যিনি আপনার ফলাফল জানেন, তাই আমি অনুমান করব না। আমি কেয়ার টিমকে আপনাকে ফোন করতে বলেছি। সাধারণ তথ্য আমাদের অনুমোদিত FAQ-তে আছে।",
    },
    "blocked": {
        "en": "I can only use approved screening FAQs. Please ask your care team.",
        "ar": "يمكنني استخدام الأسئلة الشائعة المعتمدة فقط. يرجى سؤال فريق الرعاية.",
        "hi": "मैं केवल स्वीकृत स्क्रीनिंग FAQ का उपयोग कर सकता हूँ। कृपया अपनी देखभाल टीम से पूछें।",
        "ur": "میں صرف منظور شدہ اسکریننگ سوالات استعمال کر سکتا ہوں۔ براہ کرم اپنی نگہداشت ٹیم سے پوچھیں۔",
        "ml": "അംഗീകൃത സ്ക്രീനിംഗ് FAQ മാത്രമേ എനിക്ക് ഉപയോഗിക്കാൻ കഴിയൂ. ദയവായി നിങ്ങളുടെ കെയർ ടീമിനോട് ചോദിക്കുക.",
        "tl": "Ang aprubadong screening FAQ lang ang magagamit ko. Mangyaring magtanong sa iyong care team.",
        "bn": "আমি শুধু অনুমোদিত স্ক্রিনিং FAQ ব্যবহার করতে পারি। অনুগ্রহ করে আপনার কেয়ার টিমকে জিজ্ঞাসা করুন।",
    },
    "none": {
        "en": "I can only answer from our approved screening FAQ. Please ask your care team, or tap Talk to a person.",
        "ar": "يمكنني الإجابة فقط من الأسئلة الشائعة المعتمدة. يرجى سؤال فريق الرعاية أو اضغط تحدث إلى شخص.",
        "hi": "मैं केवल हमारे स्वीकृत स्क्रीनिंग FAQ से उत्तर दे सकता हूँ। कृपया अपनी देखभाल टीम से पूछें, या 'किसी व्यक्ति से बात करें' दबाएँ।",
        "ur": "میں صرف ہمارے منظور شدہ اسکریننگ سوالات سے جواب دے سکتا ہوں۔ براہ کرم اپنی نگہداشت ٹیم سے پوچھیں، یا 'کسی شخص سے بات کریں' دبائیں۔",
        "ml": "ഞങ്ങളുടെ അംഗീകൃത സ്ക്രീനിംഗ് FAQ-ൽ നിന്ന് മാത്രമേ എനിക്ക് ഉത്തരം നൽകാനാകൂ. ദയവായി കെയർ ടീമിനോട് ചോദിക്കുക, അല്ലെങ്കിൽ 'ഒരാളുമായി സംസാരിക്കുക' അമർത്തുക.",
        "tl": "Mula lang sa aming aprubadong screening FAQ ako makakasagot. Magtanong sa iyong care team, o pindutin ang 'Makipag-usap sa tao'.",
        "bn": "আমি শুধু আমাদের অনুমোদিত স্ক্রিনিং FAQ থেকে উত্তর দিতে পারি। অনুগ্রহ করে কেয়ার টিমকে জিজ্ঞাসা করুন, অথবা 'একজন মানুষের সাথে কথা বলুন' চাপুন।",
    },
    "preface": {
        "en": "From our approved FAQ (not a diagnosis): ",
        "ar": "من الأسئلة الشائعة المعتمدة (وليس تشخيصاً): ",
        "hi": "हमारे स्वीकृत FAQ से (यह निदान नहीं है): ",
        "ur": "ہمارے منظور شدہ سوالات سے (یہ تشخیص نہیں ہے): ",
        "ml": "ഞങ്ങളുടെ അംഗീകൃത FAQ-ൽ നിന്ന് (ഇത് രോഗനിർണയമല്ല): ",
        "tl": "Mula sa aming aprubadong FAQ (hindi ito diagnosis): ",
        "bn": "আমাদের অনুমোদিত FAQ থেকে (এটি রোগনির্ণয় নয়): ",
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
    from agents.common.languages import KB_LANGS, normalize

    target = normalize(language)
    if target in KB_LANGS:
        return await _answer(question, language=target, pii_tokens=pii_tokens)
    # Hindi, Urdu, Malayalam, Filipino, Bengali: fixed safety texts are reviewed strings in that language;
    # grounded answers come from the English KB and go through the guarded translation layer.
    out = await _answer(question, language="en", pii_tokens=pii_tokens, reply_language=target)
    if out.get("method") in ("rag_llm_grounded", "rag_extractive"):
        from agents.translation import translate

        tr = await translate(out["answer"], target)  # type: ignore[arg-type]
        if tr.get("text"):
            out = out | {"answer": tr["text"], "translated_from": "en", "translation": tr.get("label")}
        else:
            out = out | {"translation": "unavailable", "language_note": "English answer shown; translation unavailable."}
    return out | {"language": target}


async def _answer(question: str, *, language: str = "en", pii_tokens: dict[str, str] | None = None,
                  reply_language: str | None = None) -> dict[str, Any]:
    lang = "ar" if language == "ar" else "en"
    fixed = reply_language or lang  # language for the fixed safety texts
    if has_red_flag(question):
        return {"answer": _t("crisis", fixed), "hand_off": True, "citations": [], "method": "crisis_rule",
                "ai_generated": False, "gap": False}
    if needs_clinician(question):
        # Never answered by the KB or a model; general approved info is attached, with a clinician callback.
        hits = await retrieve(question, language=lang, k=1)
        general = f" {_extract(hits[0], lang)}" if hits and not reply_language else ""
        return {"answer": _t("clinician", fixed) + general, "hand_off": True, "callback": "clinician",
                "citations": [{"id": h["doc_id"], "title": h.get("title"), "chunk": h["id"], "source": h.get("source")}
                              for h in hits],
                "method": "clinician_rule", "ai_generated": False, "gap": False}
    if deny_listed(question):
        from agents.common import ai_metrics

        ai_metrics.incr("injection_blocks", task="rag_answer", layer="app_rule")
        return {"answer": _t("blocked", fixed), "hand_off": True, "blocked_injection": True, "citations": [],
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
        return {"answer": _t("none", fixed), "hand_off_offered": True, "citations": [], "method": "no_hit",
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
