"""
Photo strategy for seafarer avatar upload.
"""

import json
from typing import Dict, Any, Tuple, List

from src.parsers.photo import get_photo


def parse_photo_raw(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract photo data from parsed HTML data."""
    soup = raw_data.get("__soup") if isinstance(raw_data, dict) else None
    if soup is None:
        return {"photo": None}
    return {"photo": get_photo(soup)}


def validate_photo(photo: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate photo payload."""
    if not photo:
        return False, ["no photo found"]
    if not isinstance(photo, dict):
        return False, ["photo payload must be dict"]
    if not photo.get("file_obj"):
        return False, ["photo file_obj is missing"]
    return True, []


def normalize_photo(raw_photo: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
    """Normalize raw photo data before upload."""
    if not raw_photo:
        return {}
    photo = raw_photo.get("photo") if "photo" in raw_photo else raw_photo
    if not photo:
        return {}
    if "filename" not in photo:
        photo["filename"] = "photo.jpg"
    if "mime_type" not in photo:
        photo["mime_type"] = "image/jpeg"
    return photo


def build_photo_payload(photo: Dict[str, Any]) -> Dict[str, Any]:
    """Build photo payload for upload.

    The upload request should ultimately prepare a multipart payload with a file-like
    object and metadata such as filename and mime_type.
    """
    return {
        "data": {"data": json.dumps({"photo": {"fileRef": "A"}})},
        "files": [
            (
                "A",
                (
                    photo.get("filename", "photo.jpg"),
                    photo["file_obj"],
                    photo.get("mime_type", "image/jpeg"),
                ),
            )
        ],
    }
