import json
import os
from typing import Any

_translations: dict[str, dict[str, Any]] = {}


def load_translations() -> None:
    langs = ["ru", "en", "ua"]
    for lang in langs:
        path = os.path.join(os.path.dirname(__file__), f"{lang}.json")
        with open(path, "r", encoding="utf-8") as f:
            _translations[lang] = json.load(f)


def t(key: str, lang: str = "ru", **kwargs: Any) -> str:
    trans = _translations.get(lang) or _translations.get("ru", {})
    text: str = trans.get(key) or _translations.get("ru", {}).get(key, key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
            pass
    return text
