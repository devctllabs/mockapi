from __future__ import annotations

from pathlib import Path
from typing import Iterable, Protocol


class FileSystem(Protocol):
    def read_text(self, path: Path) -> str:
        ...

    def write_text(self, path: Path, content: str) -> None:
        ...

    def is_file(self, path: Path) -> bool:
        ...

    def exists(self, path: Path) -> bool:
        ...

    def mkdir(self, path: Path) -> None:
        ...

    def iter_files(self, root: Path) -> Iterable[Path]:
        ...


class LocalFileSystem:
    def read_text(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def write_text(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def is_file(self, path: Path) -> bool:
        return path.is_file()

    def exists(self, path: Path) -> bool:
        return path.exists()

    def mkdir(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)

    def iter_files(self, root: Path) -> Iterable[Path]:
        return sorted(file_path for file_path in root.rglob("*") if file_path.is_file())
