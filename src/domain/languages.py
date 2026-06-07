from pathlib import Path
import re
from typing import Optional

from src.utils.mapping import load_mapping

COUNTRY_TO_LANGUAGE = load_mapping((Path(__file__).parent / 'data' / 'country_to_language.json'))


def country_to_language(country: str) -> Optional[str]:
    """Страна → язык (case-insensitive)"""
    if not country:
        return None

    normalized = country.strip()

    # Точное совпадение
    if normalized in COUNTRY_TO_LANGUAGE:
        return COUNTRY_TO_LANGUAGE[normalized]

    # Без регистра
    normalized_lower = normalized.lower()
    for country_name, lang in COUNTRY_TO_LANGUAGE.items():
        if country_name.lower() == normalized_lower:
            return lang

    return None


def get_languages(languages):
    lang_list = re.split(r', |/', languages)
    return [part.split(' ',1)[0] if ' ' in part else part for part in lang_list]