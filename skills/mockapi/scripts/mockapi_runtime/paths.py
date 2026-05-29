import os
import re
from pathlib import Path


def is_http_url(value: str) -> bool:
    return re.match(r"^https?://", value, re.IGNORECASE) is not None


def posix_path(value: str) -> str:
    return value.replace("\\", "/")


def relative_file_path(from_directory: Path, target_path: Path) -> str:
    relative = posix_path(os.path.relpath(target_path, from_directory))
    return relative if relative.startswith(".") else f"./{relative}"


def to_identifier(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", " ", value).strip()
    if not cleaned:
        return "Value"
    return "".join(part[:1].upper() + part[1:] for part in cleaned.split())


def to_camel_case(value: str) -> str:
    pascal = to_identifier(value)
    return pascal[:1].lower() + pascal[1:]


to_pascal_case = to_identifier
