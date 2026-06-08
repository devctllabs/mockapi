from __future__ import annotations

from pathlib import Path

from .filesystem import FileSystem
from .models import FileWriteResult, PlannedWrite


TEMPLATE_TS_NOCHECK_MARKER = "// @ts-nocheck -- mockapi template source; stripped during generation\n"
OVERWRITABLE_TEMPLATE_PATHS = frozenset(
    {
        "scripts/codegen-admin-openapi.ts",
        "scripts/lib/mockRuntimeCodegen.ts",
        "src/generated/mock-admin/state/controller.ts",
        "src/generated/mock-admin/state/service.ts",
    }
)


def planned_write(path: Path, content: str, *, overwrite: bool) -> PlannedWrite:
    return PlannedWrite(content=content, overwrite=overwrite, path=path)


def strip_template_only_directives(content: str) -> str:
    return content[len(TEMPLATE_TS_NOCHECK_MARKER) :] if content.startswith(TEMPLATE_TS_NOCHECK_MARKER) else content


class WriteService:
    def __init__(self, fs: FileSystem) -> None:
        self.fs = fs

    def copy_template_writes(self, template_root: Path, out_root: Path) -> list[PlannedWrite]:
        writes: list[PlannedWrite] = []
        for file_path in self.fs.iter_files(template_root):
            relative_path = file_path.relative_to(template_root)
            writes.append(
                PlannedWrite(
                    content=strip_template_only_directives(self.fs.read_text(file_path)),
                    overwrite=relative_path.as_posix() in OVERWRITABLE_TEMPLATE_PATHS,
                    path=out_root / relative_path,
                )
            )
        return writes

    def write_planned_file(self, write: PlannedWrite) -> FileWriteResult:
        path = Path(write.path)
        existing = self.fs.read_text(path) if self.fs.exists(path) else None

        if existing == write.content:
            return FileWriteResult(action="unchanged", path=str(path))

        if existing is not None and not write.overwrite:
            return FileWriteResult(action="skipped", path=str(path))

        self.fs.mkdir(path.parent)
        self.fs.write_text(path, write.content)
        return FileWriteResult(action="created" if existing is None else "updated", path=str(path))
