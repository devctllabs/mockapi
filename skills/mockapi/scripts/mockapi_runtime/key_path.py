from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .filesystem import FileSystem


def json_key_path_exists(text: str, key_path: Sequence[str]) -> bool:
    try:
        value: Any = json.loads(text)
    except json.JSONDecodeError:
        return False

    return _mapping_key_path_exists(value, key_path)


def yaml_key_path_exists(text: str, key_path: Sequence[str]) -> bool:
    expected = tuple(key_path)
    if not expected:
        return True

    stack: list[tuple[int, str]] = []
    block_scalar_indent: int | None = None

    for raw_line in text.splitlines():
        indent, stripped = _split_yaml_line(raw_line)
        if indent is None or stripped is None:
            continue

        should_skip, block_scalar_indent = _advance_yaml_block_scalar(indent, block_scalar_indent)
        if should_skip:
            continue

        if _is_ignorable_yaml_line(stripped):
            continue

        parsed = _parse_yaml_key_value(stripped)
        if parsed is None:
            continue

        key, raw_value = parsed
        _prune_yaml_stack(stack, indent)

        if _current_yaml_path(stack, key) == expected:
            return True

        value = raw_value.strip()
        if value.startswith(("|", ">")):
            block_scalar_indent = indent
        elif value == "":
            stack.append((indent, key))

    return False


def document_key_path_exists(fs: FileSystem, path: Path, key_path: Sequence[str]) -> bool:
    if not fs.is_file(path):
        return False

    text = fs.read_text(path)
    suffix = path.suffix.lower()
    if suffix == ".json":
        return json_key_path_exists(text, key_path)
    if suffix in {".yaml", ".yml"}:
        return yaml_key_path_exists(text, key_path)
    return False


def _mapping_key_path_exists(value: Any, key_path: Sequence[str]) -> bool:
    for key in key_path:
        if not isinstance(value, Mapping) or key not in value:
            return False
        value = value[key]
    return True


def _leading_space_count(value: str) -> int:
    return len(value) - len(value.lstrip(" "))


def _split_yaml_line(raw_line: str) -> tuple[int | None, str | None]:
    if not raw_line.strip():
        return None, None
    indent = _leading_space_count(raw_line)
    return indent, raw_line[indent:].rstrip("\r")


def _advance_yaml_block_scalar(indent: int, block_scalar_indent: int | None) -> tuple[bool, int | None]:
    if block_scalar_indent is None:
        return False, None
    if indent > block_scalar_indent:
        return True, block_scalar_indent
    return False, None


def _is_ignorable_yaml_line(stripped: str) -> bool:
    return not stripped or stripped.startswith(("#", "---", "...", "- ", "?", "-"))


def _prune_yaml_stack(stack: list[tuple[int, str]], indent: int) -> None:
    while stack and indent <= stack[-1][0]:
        stack.pop()


def _current_yaml_path(stack: list[tuple[int, str]], key: str) -> tuple[str, ...]:
    return tuple(item_key for _, item_key in stack) + (key,)


def _parse_yaml_key_value(stripped: str) -> tuple[str, str] | None:
    if not stripped:
        return None

    index = 0
    key_chars: list[str] = []

    if stripped[0] in {"'", '"'}:
        quote = stripped[0]
        index = 1
        while index < len(stripped):
            char = stripped[index]
            if quote == "'" and char == "'":
                if stripped[index + 1 : index + 2] == "'":
                    key_chars.append("'")
                    index += 2
                    continue
                index += 1
                break
            if quote == '"' and char == "\\":
                next_char = stripped[index + 1 : index + 2]
                if not next_char:
                    return None
                key_chars.append(next_char)
                index += 2
                continue
            if quote == '"' and char == '"':
                index += 1
                break
            key_chars.append(char)
            index += 1
        else:
            return None

        while index < len(stripped) and stripped[index].isspace():
            index += 1
        if stripped[index : index + 1] != ":":
            return None
        key = "".join(key_chars)
        index += 1
    else:
        while index < len(stripped):
            char = stripped[index]
            if char == ":":
                next_char = stripped[index + 1 : index + 2]
                if next_char and not next_char.isspace() and next_char != "#":
                    key_chars.append(":")
                    index += 1
                    continue
                key = "".join(key_chars).strip()
                if not key:
                    return None
                index += 1
                break
            key_chars.append(char)
            index += 1
        else:
            return None

    value_chars: list[str] = []
    quote: str | None = None
    while index < len(stripped):
        char = stripped[index]
        if quote == "'":
            if char == "'" and stripped[index + 1 : index + 2] == "'":
                value_chars.append("''")
                index += 2
                continue
            value_chars.append(char)
            if char == "'":
                quote = None
            index += 1
            continue
        if quote == '"':
            if char == "\\":
                next_char = stripped[index + 1 : index + 2]
                if not next_char:
                    value_chars.append(char)
                    index += 1
                    continue
                value_chars.append("\\" + next_char)
                index += 2
                continue
            value_chars.append(char)
            if char == '"':
                quote = None
            index += 1
            continue
        if char in {"'", '"'}:
            quote = char
            value_chars.append(char)
            index += 1
            continue
        if char == "#" and (not value_chars or value_chars[-1].isspace()):
            break
        value_chars.append(char)
        index += 1

    return key, "".join(value_chars)
