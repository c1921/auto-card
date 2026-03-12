from __future__ import annotations

import argparse
import gettext
import os
from pathlib import Path
from typing import Final

DOMAIN: Final = "auto_card"
LOCALE_DIR: Final = Path(__file__).resolve().parents[1] / "locale"
SUPPORTED_LANGUAGES: Final[tuple[str, ...]] = ("en", "zh_CN")
ENVIRONMENT_LANGUAGE_KEYS: Final[tuple[str, ...]] = (
    "LC_ALL",
    "LC_MESSAGES",
    "LANG",
)

_current_language = "en"
_translation: gettext.NullTranslations = gettext.NullTranslations()


def normalize_language(language: str | None) -> str:
    if not language:
        return "en"

    normalized = language.strip().replace("-", "_")
    lowered = normalized.lower()
    if lowered.startswith("zh"):
        return "zh_CN"
    if lowered.startswith("en"):
        return "en"
    return "en"


def detect_environment_language() -> str:
    for key in ENVIRONMENT_LANGUAGE_KEYS:
        value = os.environ.get(key)
        if value:
            return normalize_language(value)
    return "en"


def extract_cli_language(argv: list[str]) -> str | None:
    for index, argument in enumerate(argv):
        if argument == "--lang" and index + 1 < len(argv):
            return argv[index + 1]
        if argument.startswith("--lang="):
            return argument.split("=", maxsplit=1)[1]
    return None


def set_language(language: str | None = None) -> str:
    global _current_language
    global _translation

    resolved_language = normalize_language(language) if language else detect_environment_language()
    _translation = gettext.translation(
        DOMAIN,
        localedir=LOCALE_DIR,
        languages=[resolved_language],
        fallback=True,
    )
    _current_language = resolved_language
    argparse._ = _translation.gettext
    return _current_language


def get_language() -> str:
    return _current_language


def toggle_language() -> str:
    return set_language("zh_CN" if _current_language == "en" else "en")


def gettext_message(message: str) -> str:
    return _translation.gettext(message)


def ngettext_message(singular: str, plural: str, number: int) -> str:
    return _translation.ngettext(singular, plural, number)


_: Final = gettext_message
ngettext: Final = ngettext_message

set_language()
