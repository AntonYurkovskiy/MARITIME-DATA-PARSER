import os
from dotenv import load_dotenv

load_dotenv()

OFFICE_UUID = os.getenv("OFFICE_UUID", None)

API_BASE_URL = os.getenv("API_BASE_URL", "https://staffdev.360crewing.com/api/v1")
API_TIMEOUT = (30, 60)

INPUT_DIR = os.getenv("INPUT_DIR", "out/out_min")
FUZZY_THRESHOLD = 80
