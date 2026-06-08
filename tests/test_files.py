from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock

from tests.support import MemoryFileSystem

from mockapi_runtime.files import TEMPLATE_TS_NOCHECK_MARKER, WriteService, planned_write
from mockapi_runtime.filesystem import LocalFileSystem


class WriteServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fs = MemoryFileSystem()
        self.writer = WriteService(self.fs)

    def test_write_planned_file_creates_updates_skips_and_detects_unchanged(self) -> None:
        path = Path("/out/file.ts")

        created = self.writer.write_planned_file(planned_write(path, "first", overwrite=False))
        unchanged = self.writer.write_planned_file(planned_write(path, "first", overwrite=False))
        skipped = self.writer.write_planned_file(planned_write(path, "second", overwrite=False))
        updated = self.writer.write_planned_file(planned_write(path, "second", overwrite=True))

        self.assertEqual(created.action, "created")
        self.assertEqual(unchanged.action, "unchanged")
        self.assertEqual(skipped.action, "skipped")
        self.assertEqual(updated.action, "updated")
        self.assertEqual(self.fs.read_text(path), "second")

    def test_copy_template_writes_strips_template_only_marker(self) -> None:
        template_root = Path("/templates")
        out_root = Path("/out")
        self.fs.write_text(template_root / "src/server.ts", f"{TEMPLATE_TS_NOCHECK_MARKER}server\n")

        writes = self.writer.copy_template_writes(template_root, out_root)

        self.assertEqual(writes[0].content, "server\n")
        self.assertFalse(writes[0].overwrite)
        self.assertEqual(writes[0].path, out_root / "src/server.ts")

    def test_copy_template_writes_overwrites_generated_scripts(self) -> None:
        template_root = Path("/templates")
        out_root = Path("/out")
        self.fs.write_text(template_root / "scripts/codegen-admin-openapi.ts", "admin script\n")
        self.fs.write_text(template_root / "scripts/lib/mockRuntimeCodegen.ts", "runtime script\n")
        self.fs.write_text(template_root / "src/generated/mock-admin/state/controller.ts", "admin controller\n")
        self.fs.write_text(template_root / "src/generated/mock-admin/state/service.ts", "admin service\n")
        self.fs.write_text(template_root / "src/lib/stateStore.ts", "state store\n")

        writes = self.writer.copy_template_writes(template_root, out_root)
        by_path = {write.path: write for write in writes}

        self.assertTrue(by_path[out_root / "scripts/codegen-admin-openapi.ts"].overwrite)
        self.assertTrue(by_path[out_root / "scripts/lib/mockRuntimeCodegen.ts"].overwrite)
        self.assertTrue(by_path[out_root / "src/generated/mock-admin/state/controller.ts"].overwrite)
        self.assertTrue(by_path[out_root / "src/generated/mock-admin/state/service.ts"].overwrite)
        self.assertFalse(by_path[out_root / "src/lib/stateStore.ts"].overwrite)


class LocalFileSystemTests(unittest.TestCase):
    def test_delegates_path_operations_without_real_fs(self) -> None:
        fs = LocalFileSystem()
        path = MagicMock()

        path.read_text.return_value = "content"
        self.assertEqual(fs.read_text(path), "content")
        path.read_text.assert_called_once_with(encoding="utf-8")

        fs.write_text(path, "new")
        path.write_text.assert_called_once_with("new", encoding="utf-8")

        fs.mkdir(path)
        path.mkdir.assert_called_once_with(parents=True, exist_ok=True)

    def test_iter_files_filters_non_files_without_real_fs(self) -> None:
        fs = LocalFileSystem()
        root = MagicMock()
        file_path = MagicMock()
        directory_path = MagicMock()
        file_path.is_file.return_value = True
        directory_path.is_file.return_value = False
        root.rglob.return_value = [directory_path, file_path]

        self.assertEqual(fs.iter_files(root), [file_path])


if __name__ == "__main__":
    unittest.main()
