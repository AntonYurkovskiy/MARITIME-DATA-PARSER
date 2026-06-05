from src.parsers.photo import get_photo


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
    language_id_by_citizenship
):
    photo = get_photo(soup)

    return {
        "photo": photo,
        "name": name,
        "middle_name": middle_name,
        "surname": surname,
        "rank_id": rank_id,
        "additional_ranks_id": additional_ranks,
        "date_of_birth": date_of_birth,
        "place_of_birth": place_of_birth,
        "gender_id": gender_id,
        "marital_status_id": marital_status_id,
        "nationality_country_id": nationality_country_id,
        "emails": emails,
        # "resident_status_id": resident_country_id,
        "fast_note": notes,
        "phone_numbers": phones_list_of_dicts,
        "personal_id": personal_id,
        "language_id": language_id_by_citizenship
    }


def stringify_id_fields(data: dict) -> dict:
    result = {}
    for key, value in data.items():
        if isinstance(value, dict):
            result[key] = stringify_id_fields(value)
        elif isinstance(value, list):
            result[key] = [
                stringify_id_fields(x) if isinstance(x, dict) else x
                for x in value
            ]
        elif key.endswith("_id") and value is not None:
            result[key] = str(value)
        else:
            result[key] = value
    return result