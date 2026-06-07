import re

# функция получения названия страны по коду телефона,
# с учетом резидентства и гражданства - провеирить ее на циклические импорт 
# и при необходимости вынести в utils или создать отдельный файл для работы с гео данными
from src.api.geo import resolve_country_by_code

import phonenumbers


def normalize_phone(raw: str) -> str:
    raw = (raw or "").strip()
    if raw.startswith("00"):
        raw = "+" + raw[2:]
    elif raw[:1].isdigit():
        raw = "+" + raw
    return re.sub(r"[^\d+]", "", raw)


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
    for raw_phone in phones.split():
        row = parse_phone(raw_phone, resident_country_id, nationality_country_id, search_geo_func)
        if not row or row["country_id"] is None:
            continue

        items.append({
            "uuid": None,
            "country_id": row["country_id"],
            "number": row["national_number"],
            "type_id": 1,
            "comment": "comment",
        })
    return items