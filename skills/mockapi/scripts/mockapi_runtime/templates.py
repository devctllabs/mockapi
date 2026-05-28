from __future__ import annotations

import re
from pathlib import Path
from typing import Mapping

from .filesystem import FileSystem


TEMPLATE_ROOT = Path(__file__).with_name("templates")
TOKEN_PATTERN = re.compile(r"{{([A-Z][A-Z0-9_]*)}}")
TOKEN_TEXT_PATTERN = re.compile(r"{{([^{}]+)}}")


def render_inline_template(template: str, values: Mapping[str, str], *, name: str = "<inline>") -> str:
    invalid = sorted(
        {
            f"{{{{{token}}}}}"
            for token in TOKEN_TEXT_PATTERN.findall(template)
            if not re.fullmatch(r"[A-Z][A-Z0-9_]*", token)
        }
    )
    if invalid:
        raise RuntimeError(f"Template {name} contains unresolved tokens: {', '.join(invalid)}.")

    used: set[str] = set()
    missing: set[str] = set()

    def replace_token(match: re.Match[str]) -> str:
        token = match.group(1)
        used.add(token)
        if token not in values:
            missing.add(token)
            return match.group(0)
        return values[token]

    rendered = TOKEN_PATTERN.sub(replace_token, template)
    if missing:
        raise RuntimeError(f"Template {name} is missing values for: {', '.join(sorted(missing))}.")

    unused = sorted(set(values) - used)
    if unused:
        raise RuntimeError(f"Template {name} received unused values for: {', '.join(unused)}.")

    return rendered


class TemplateService:
    def __init__(self, fs: FileSystem, template_root: Path = TEMPLATE_ROOT) -> None:
        self.fs = fs
        self.template_root = template_root

    def render(self, template_name: str, values: Mapping[str, str]) -> str:
        template_path = self.template_root / template_name
        return render_inline_template(self.fs.read_text(template_path), values, name=template_name)
