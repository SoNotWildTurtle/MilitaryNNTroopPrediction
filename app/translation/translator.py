"""Neural machine translation helpers for the dashboard UI."""
from functools import lru_cache
from typing import Optional

try:
    from transformers import pipeline
except Exception:  # pragma: no cover - transformers might not be installed
    pipeline = None  # type: ignore

# Mapping of target language codes to pre-trained translation models
LANG_MODELS = {
    "uk": "Helsinki-NLP/opus-mt-en-uk",
    "ru": "Helsinki-NLP/opus-mt-en-ru",
    "pl": "Helsinki-NLP/opus-mt-en-pl",
}


@lru_cache(maxsize=None)
def _load_translator(lang: str):
    """Return a cached translation pipeline for the requested language."""
    if pipeline is None:
        return None
    model_name = LANG_MODELS.get(lang)
    if not model_name:
        return None
    try:
        return pipeline("translation", model=model_name)
    except Exception:
        return None


def translate_text(text: str, target_lang: str = "en") -> str:
    """Translate English text into ``target_lang`` using a neural model.

    Falls back to returning the original text if translation fails or the
    ``transformers`` library is unavailable.
    """
    if not text or target_lang == "en":
        return text
    translator = _load_translator(target_lang)
    if translator is None:
        return text
    try:
        result = translator(text)
        if isinstance(result, list) and result:
            return result[0]["translation_text"]
    except Exception:
        pass
    return text
