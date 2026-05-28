from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .models import ADMIN_OPENAPI_BUILTIN_STATE_RECORD_TYPES

SCHEMA_COMPONENT_RECORD_TYPE_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")
TS_SCALAR_RECORD_TYPES = {"any", "boolean", "number", "string", "unknown"}


@dataclass(frozen=True, slots=True)
class SchemaRefParts:
    api_name: str
    fragment: str
    source_path: str | None = None
    admin_builtin: bool = False

    @property
    def file_qualified(self) -> bool:
        return self.source_path is not None

    @property
    def schema_name(self) -> str:
        return _decode_json_pointer_segment(self.fragment.rsplit("/", 1)[-1])


def is_generic_record_type(record_type: object) -> bool:
    return isinstance(record_type, str) and "<" in record_type


def is_schema_component_record_type(record_type: object) -> bool:
    record_text = str(record_type or "")
    return (
        bool(SCHEMA_COMPONENT_RECORD_TYPE_PATTERN.match(record_text))
        and record_text not in TS_SCALAR_RECORD_TYPES
        and not is_generic_record_type(record_type)
    )


def is_admin_builtin_record_type(record_type: object) -> bool:
    return isinstance(record_type, str) and record_type in ADMIN_OPENAPI_BUILTIN_STATE_RECORD_TYPES


def parse_schema_ref(schema_ref: str) -> SchemaRefParts:
    source_part, fragment = schema_ref.split("#", 1)
    api_name, separator, source_path = source_part.partition(":")
    return SchemaRefParts(
        api_name=api_name,
        fragment=fragment,
        source_path=source_path if separator else None,
    )


def local_api_path(openapi: str, root: Path) -> Path:
    openapi_path = Path(openapi)
    return openapi_path if openapi_path.is_absolute() else root / openapi_path


def schema_ref_document_path(schema_ref: SchemaRefParts, api_openapi: str, root: Path) -> Path:
    api_path = local_api_path(api_openapi, root)
    if schema_ref.source_path is None:
        return api_path

    schema_path = Path(schema_ref.source_path)
    return schema_path if schema_path.is_absolute() else api_path.parent / schema_path


def schema_key_path(schema_name: str) -> tuple[str, str, str]:
    return ("components", "schemas", schema_name)


def _decode_json_pointer_segment(value: str) -> str:
    return value.replace("~1", "/").replace("~0", "~")
