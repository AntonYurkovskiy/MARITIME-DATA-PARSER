from typing import Optional

from functions import COUNTRY_TO_LANGUAGE


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