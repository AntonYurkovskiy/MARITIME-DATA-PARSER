import logging
from pathlib import Path


from src.api.dicts import get_dict
from src.api.geo import get_resident_country, search_geo
from src.api.seafarers import add_seafarer, get_id, upload_seafarer_photo
from src.api.vessels import add_historical_contract
from src.config import INPUT_DIR
from src.domain.builder import build_seafarer_dict
from src.domain.languages import country_to_language
from src.extractors.dates import extract_date_to_iso
from src.extractors.documents import get_personal_id_by_passport, get_ranks
from src.extractors.emails import get_emails_list
from src.extractors.names import get_names
from src.extractors.phones import get_phones
from src.parsers.html import get_html_content, main_parser, parse_notes
# from src.domain.languages import (
#     get_languages,
# )



logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def load_reference_data():
    ranks = get_dict("ranks")
    gender = get_dict("gender")
    marital_statuses = get_dict("marital_statuses")
    resident_statuses = get_dict("resident_statuses")
    languages = get_dict("languages")
    vessel_types = get_dict("vessel_types")

    return ranks, gender, marital_statuses, resident_statuses, languages, vessel_types


def process_all_files(html_files, ranks, gender, marital_statuses, resident_statuses, languages, vessel_types):
    success_count = 0
    error_count = 0

    for idx, file in enumerate(html_files, 1):
        try:
            logger.info("📄 Обработка файла %d/%d: %s", idx, len(html_files), file)

            soup = get_html_content(file)
            main_info = main_parser(soup)
            notes = parse_notes(soup)

            name, middle_name, surname = get_names(main_info["Main info"]["Name / Surname:"])
            date_of_birth, place_of_birth = extract_date_to_iso(main_info["Main info"]["Birthday / Place of birth:"])
            emails = get_emails_list(main_info["Main info"]["E-mail:"])

            gender_id = get_id(gender, main_info["Biometrics"]["Sex"], "gender")
            personal_id = get_personal_id_by_passport(main_info["Passports / Smbk"])
            positions = get_ranks(main_info["Main info"]["Position applied for:"])
            rank_id = get_id(ranks, positions[0], "ranks")
            additional_ranks = [get_id(ranks, rank, "ranks") for rank in positions[1:]]

            nationality_country = search_geo(main_info["Main info"]["Citizenship:"], "countries")
            nationality_country_id = nationality_country[0]["id"] if nationality_country else ""

            # languages_list = get_languages(main_info["Additional info"]["Knowledge of other languages:"])
            # language_id = ([get_id(languages, language, "languages") for language in languages_list] if languages_list else [])[0]
            language_id_by_citizenship = get_id(languages, country_to_language(main_info["Main info"]["Citizenship:"]), "languages")

            resident_country = get_resident_country(
                main_info["Main info"]["Country of residence / City:"],
                main_info["Main info"]["Citizenship:"],
            )
            geo_resident = search_geo(resident_country, "countries")
            resident_country_id = geo_resident[0]["id"] if geo_resident else None

            next_of_kin = main_info["Additional info"]["Next of kin:"]
            marital_status = "Married" if next_of_kin == "Wife" else None
            marital_status_id = get_id(marital_statuses, marital_status, "marital_statuses")

            phones = main_info["Main info"]["Phones:"]
            phones_list_of_dicts = get_phones(phones, resident_country_id, nationality_country_id, search_geo)

            result = build_seafarer_dict(
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
                personal_id[0],
                language_id_by_citizenship,
            )

            photo = result.pop("photo", None)
            created = add_seafarer(result)
            seafarer_uuid = created["inserted"]["uuid"]
            logger.info("✅ Моряк создан: %s %s (uuid: %s)", name, surname, seafarer_uuid)

            try:
                contract_count = len(main_info["Sea service (last 5 years)"])
                logger.info("📋 Добавляем %d контрактов...", contract_count)
                for item in main_info["Sea service (last 5 years)"]:
                    add_historical_contract(item, seafarer_uuid, ranks, vessel_types)
                logger.info("✅ %d контрактов добавлено", contract_count)
            except Exception as e:
                logger.warning("⚠️ Ошибка при добавлении контрактов: %s", e)

            try:
                upload_seafarer_photo(seafarer_uuid, photo)
                logger.info("📷 Фото загружено")
            except Exception as e:
                logger.warning("⚠️ Ошибка при загрузке фото: %s", e)

            success_count += 1
        except Exception as e:
            error_count += 1
            logger.error("❌ Ошибка при обработке файла %s: %s", file, e)
            continue

    logger.info("%s", "=" * 50)
    logger.info("📊 ИТОГО: успешно %d, ошибок %d", success_count, error_count)


def main():
    ranks, gender, marital_statuses, resident_statuses, languages, vessel_types = load_reference_data()

    html_files = [str(p) for p in Path(INPUT_DIR).rglob("*.html")]

    process_all_files(html_files, ranks, gender, marital_statuses, resident_statuses, languages, vessel_types)


if __name__ == "__main__":
    main()
