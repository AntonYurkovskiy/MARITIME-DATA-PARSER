from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.parsers.photo import get_photo


@dataclass
class SeafarerInput:
    soup: Any  # BeautifulSoup или mock
    name: Optional[str]
    middle_name: Optional[str]
    surname: Optional[str]
    rank_id: Optional[int]
    additional_ranks: Optional[List[int]]
    date_of_birth: Optional[str]
    place_of_birth: Optional[str]
    gender_id: Optional[int]
    marital_status_id: Optional[int]
    nationality_country_id: Optional[int]
    emails: List[str]
    resident_country_id: Optional[int]
    notes: Optional[str]
    phones_list_of_dicts: List[Dict[str, Any]]
    personal_id: Optional[str]
    language_id_by_citizenship: Optional[int]


def _build_seafarer_dict_from_input(data: SeafarerInput) -> Dict[str, Any]:
    photo = get_photo(data.soup)

    return {
        "photo": photo,
        "name": data.name,
        "middle_name": data.middle_name,
        "surname": data.surname,
        "rank_id": data.rank_id,
        "additional_ranks_id": data.additional_ranks,
        "date_of_birth": data.date_of_birth,
        "place_of_birth": data.place_of_birth,
        "gender_id": data.gender_id,
        "marital_status_id": data.marital_status_id,
        "nationality_country_id": data.nationality_country_id,
        "emails": data.emails,
        # "resident_status_id": data.resident_country_id,
        "fast_note": data.notes,
        "phone_numbers": data.phones_list_of_dicts,
        "personal_id": data.personal_id,
        "language_id": data.language_id_by_citizenship,
    }


def build_seafarer_dict(
    soup,
    name,
    middle_name,
    surname,
    rank_id,
    additional_ranks,
    date_of_birth,
    place_of_birth,
    gender_id,
    marital_status_id,
    nationality_country_id,
    emails,
    resident_country_id,
    notes,
    phones_list_of_dicts,
    personal_id,
    language_id_by_citizenship,
) -> Dict[str, Any]:
    """
    Фасад с прежней сигнатурой (как в тестах),
    внутри собирает SeafarerInput и делегирует в _build_seafarer_dict_from_input.
    """
    data = SeafarerInput(
        soup=soup,
        name=name,
        middle_name=middle_name,
        surname=surname,
        rank_id=rank_id,
        additional_ranks=additional_ranks,
        date_of_birth=date_of_birth,
        place_of_birth=place_of_birth,
        gender_id=gender_id,
        marital_status_id=marital_status_id,
        nationality_country_id=nationality_country_id,
        emails=emails,
        resident_country_id=resident_country_id,
        notes=notes,
        phones_list_of_dicts=phones_list_of_dicts,
        personal_id=personal_id,
        language_id_by_citizenship=language_id_by_citizenship,
    )

    return _build_seafarer_dict_from_input(data)


# def stringify_id_fields(data: dict) -> dict:
#     result = {}
#     for key, value in data.items():
#         if isinstance(value, dict):
#             result[key] = stringify_id_fields(value)
#         elif isinstance(value, list):
#             result[key] = [
#                 stringify_id_fields(x) if isinstance(x, dict) else x
#                 for x in value
#             ]
#         elif key.endswith("_id") and value is not None:
#             result[key] = str(value)
#         else:
#             result[key] = value
#     return result




def stringify_id_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, dict):
            # рекурсивно обрабатываем вложенные словари
            result[key] = stringify_id_fields(value)
        elif isinstance(value, list):
            # список может содержать словари и любые другие элементы
            processed_list: List[Any] = [
                stringify_id_fields(x) if isinstance(x, dict) else x
                for x in value
            ]
            result[key] = processed_list
        elif key.endswith("_id") and value is not None:
            # поля *_id приводим к строке
            result[key] = str(value)
        else:
            result[key] = value
    return result