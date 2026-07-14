import re

# функция получения названия страны по коду телефона,
# с учетом резидентства и гражданства - провеирить ее на циклические импорт 
# и при необходимости вынести в utils или создать отдельный файл для работы с гео данными
from src.api.geo import resolve_country_by_code

import phonenumbers

_RUSSIAN_TRUNK_PHONE_RE = re.compile(r"(?<!\d)8[\s().-]*\d{3}[\s().-]*\d{3}[\s().-]*\d{4}(?!\d)")
_PHONE_CANDIDATE_RE = re.compile(r"(?:\+|00)?\d[\d\s().-]{5,}\d")


def normalize_phone(raw: str) -> str:
    raw = (raw or "").strip()
    if raw.startswith("00"):
        raw = "+" + raw[2:]
    cleaned = re.sub(r"[^\d+]", "", raw)
    if cleaned.startswith("+"):
        return cleaned

    digits = re.sub(r"\D", "", cleaned)
    if len(digits) == 11 and digits.startswith("8"):
        return "+7" + digits[1:]
    if digits:
        return "+" + digits
    return ""


def _extract_phone_candidates(phones: str) -> list[str]:
    text = phones or ""
    candidates: list[str] = []
    occupied_spans: list[tuple[int, int]] = []

    for match in _RUSSIAN_TRUNK_PHONE_RE.finditer(text):
        candidates.append(match.group(0))
        occupied_spans.append(match.span())

    def overlaps_occupied(span: tuple[int, int]) -> bool:
        start, end = span
        return any(start < occupied_end and end > occupied_start for occupied_start, occupied_end in occupied_spans)

    for match in _PHONE_CANDIDATE_RE.finditer(text):
        if overlaps_occupied(match.span()):
            continue
        candidate = match.group(0).strip()
        if len(re.sub(r"\D", "", candidate)) >= 7:
            candidates.append(candidate)

    return candidates or text.split()


def parse_phone(raw_phone: str, resident_country_id, nationality_country_id, search_geo_func):
    phone = normalize_phone(raw_phone)
    if not phone:
        return None

    try:
        num = phonenumbers.parse(phone, None)
    except phonenumbers.NumberParseException:
        return None

    country_code = str(num.country_code)
    national_number = str(num.national_number)

    country = resolve_country_by_code(
        country_code,
        resident_country_id,
        nationality_country_id,
        search_geo_func
    )

    return {
        "raw_phone": raw_phone,
        "country_code": country_code,
        "dial_code": f"+{country_code}",
        "national_number": national_number,
        **country,
    }


def get_phones(phones: str, resident_country_id, nationality_country_id, search_geo_func) -> list[dict]:
    items = []
    seen_numbers = set()
    for raw_phone in _extract_phone_candidates(phones):
        row = parse_phone(raw_phone, resident_country_id, nationality_country_id, search_geo_func)
        if not row or row["country_id"] is None:
            continue

        phone_key = (row.get("country_id"), row.get("national_number"))
        if phone_key in seen_numbers:
            continue
        seen_numbers.add(phone_key)

        items.append({
            "uuid": None,
            "country_id": row["country_id"],
            "number": row["national_number"],
            "type_id": 1,
            "comment": None,
        })
    return items
