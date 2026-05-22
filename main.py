# import dotenv
# Работа с сервером
# import requests
from pprint import pprint
import json

# Распаковка и парсинг
import zipfile
import pandas as pd
import io
from bs4 import BeautifulSoup
from datetime import datetime


from urllib.parse import urljoin, urlparse
import os
import shutil
import base64
import importlib
import re

from pathlib import Path
from dotenv import load_dotenv
import phonenumbers


import functions
import importlib
importlib.reload(functions)

from functions import (
        get_html_content, main_parser, parse_notes, get_names, extract_date_to_iso,
        get_emails_list, get_id, get_personal_id_by_passport, get_ranks, search_geo,
        get_languages, country_to_language, get_resident_country, get_phones,
        build_seafarer_dict, add_seafarer, upload_seafarer_photo, add_historical_contract,
        get_dict
    )

def load_reference_data():
    

    ranks = get_dict("ranks")
    gender = get_dict("gender")
    marital_statuses = get_dict("marital_statuses")
    resident_statuses = get_dict("resident_statuses")
    languages = get_dict("languages")
    vessel_types = get_dict("vessel_types")

    return ranks, gender, marital_statuses, resident_statuses, languages, vessel_types


def process_all_files(html_files, ranks, gender, marital_statuses, resident_statuses, languages, vessel_types):
    

    for file in html_files:
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
        nationality_country_id = search_geo(main_info["Main info"]["Citizenship:"], "countries")[0]["id"]

        languages_list = get_languages(main_info["Additional info"]["Knowledge of other languages:"])
        language_id = ([get_id(languages, language, "languages") for language in languages_list] if languages_list else [])[0]
        language_id_by_citizenship = get_id(languages, country_to_language(main_info["Main info"]["Citizenship:"]), "languages")

        resident_country = get_resident_country(
            main_info["Main info"]["Country of residence / City:"],
            main_info["Main info"]["Citizenship:"]
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
            language_id_by_citizenship
        )

        photo = result.pop("photo", None)
        created = add_seafarer(result)
        seafarer_uuid = created["inserted"]["uuid"]

        for item in main_info["Sea service (last 5 years)"]:
            add_historical_contract(item, seafarer_uuid, ranks, vessel_types)

        upload_seafarer_photo(seafarer_uuid, photo)


def main():
    ranks, gender, marital_statuses, resident_statuses, languages, vessel_types = load_reference_data()

    PATH = "out/out_min"
    html_files = [str(p) for p in Path(PATH).rglob("*.html")]

    process_all_files(html_files, ranks, gender, marital_statuses, resident_statuses, languages, vessel_types)


if __name__ == "__main__":
    main()