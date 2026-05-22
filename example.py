import argparse
import hashlib
import json
import logging
import sys
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup


logger = logging.getLogger("html-importer")


def setup_logging(log_file: Path) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )


def load_processed_map(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    return json.loads(path.read_text(encoding="utf-8"))


def save_processed_map(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def calculate_file_hash(file_path: Path) -> str:
    h = hashlib.sha256()

    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)

    return h.hexdigest()


def read_html(file_path: Path) -> str:
    return file_path.read_text(encoding="utf-8")


def process_html(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")

    title = soup.title.text.strip() if soup.title else None
    text = soup.get_text(separator=" ", strip=True)

    links = [
        {
            "text": a.get_text(strip=True),
            "href": a.get("href"),
        }
        for a in soup.find_all("a")
    ]

    return {
        "title": title,
        "text_preview": text[:500],
        "links_count": len(links),
        "links": links[:10],
    }


def login(
    session: requests.Session,
    api_base_url: str,
    email: str,
    password: str,
) -> str:
    logger.info("Requesting access token")

    response = session.post(
        f"{api_base_url}/auth/login",
        json={
            "email": email,
            "password": password,
        },
        timeout=30,
    )
    response.raise_for_status()

    access_token = response.json()["access_token"]

    session.headers.update({
        "Authorization": f"Bearer {access_token}",
    })

    logger.info("Access token received")
    return access_token


def send_payload(
    session: requests.Session,
    api_base_url: str,
    payload: dict[str, Any],
    email: str,
    password: str,
) -> dict[str, Any]:
    response = session.post(
        f"{api_base_url}/html-import",
        json=payload,
        timeout=60,
    )

    if response.status_code == 401:
        logger.warning("Token expired, refreshing token and retrying")
        login(session, api_base_url, email, password)

        response = session.post(
            f"{api_base_url}/html-import",
            json=payload,
            timeout=60,
        )

    response.raise_for_status()
    return response.json()


def build_payload(
    file_path: Path,
    file_hash: str,
    processed_data: dict[str, Any],
) -> dict[str, Any]:
    return {
        "source_file": {
            "name": file_path.name,
            "path": str(file_path),
            "sha256": file_hash,
        },
        "data": processed_data,
    }


def find_html_files(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]

    return sorted(input_path.glob("*.html"))


def process_file(
    file_path: Path,
    processed_map: dict[str, Any],
    session: requests.Session,
    api_base_url: str,
    email: str,
    password: str,
) -> None:
    logger.info("Processing file: %s", file_path)

    file_hash = calculate_file_hash(file_path)

    if file_hash in processed_map:
        logger.info("Skip duplicate file: %s", file_path)
        return

    html = read_html(file_path)
    processed_data = process_html(html)

    payload = build_payload(
        file_path=file_path,
        file_hash=file_hash,
        processed_data=processed_data,
    )

    response_data = send_payload(
        session=session,
        api_base_url=api_base_url,
        payload=payload,
        email=email,
        password=password,
    )

    processed_map[file_hash] = {
        "file_path": str(file_path),
        "file_name": file_path.name,
        "remote_id": response_data.get("uuid") or response_data.get("id"),
    }

    logger.info("File processed successfully: %s", file_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import HTML files and send processed data to API"
    )

    parser.add_argument(
        "input",
        type=Path,
        help="Path to .html file or directory with .html files",
    )

    parser.add_argument("--api-base-url", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)

    parser.add_argument(
        "--processed-json",
        type=Path,
        default=Path("./runtime/processed_files.json"),
    )

    parser.add_argument(
        "--log-file",
        type=Path,
        default=Path("./runtime/importer.log"),
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    setup_logging(args.log_file)

    api_base_url = args.api_base_url.rstrip("/")

    processed_map = load_processed_map(args.processed_json)

    session = requests.Session()

    try:
        login(
            session=session,
            api_base_url=api_base_url,
            email=args.email,
            password=args.password,
        )

        files = find_html_files(args.input)

        if not files:
            logger.warning("No HTML files found: %s", args.input)
            return 0

        for file_path in files:
            try:
                process_file(
                    file_path=file_path,
                    processed_map=processed_map,
                    session=session,
                    api_base_url=api_base_url,
                    email=args.email,
                    password=args.password,
                )

                save_processed_map(args.processed_json, processed_map)

            except Exception:
                logger.exception("Failed to process file: %s", file_path)

        return 0

    finally:
        save_processed_map(args.processed_json, processed_map)
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())