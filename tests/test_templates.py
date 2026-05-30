from __future__ import annotations

import unittest
from pathlib import Path

from tests.support import MemoryFileSystem

from mockapi_runtime.templates import TemplateService, render_inline_template


class TemplateTests(unittest.TestCase):
    def test_replaces_known_tokens(self) -> None:
        rendered = render_inline_template("hello {{NAME}}", {"NAME": "mockapi"})

        self.assertEqual(rendered, "hello mockapi")

    def test_errors_for_missing_token_values(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "missing values.*NAME"):
            render_inline_template("hello {{NAME}}", {})

    def test_errors_for_unresolved_tokens(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "unresolved tokens.*{{name}}"):
            render_inline_template("hello {{name}}", {})

    def test_allows_token_text_inside_values(self) -> None:
        rendered = render_inline_template("hello {{NAME}}", {"NAME": "literal {{USER_DATA}}"})

        self.assertEqual(rendered, "hello literal {{USER_DATA}}")

    def test_errors_for_unused_values(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "unused values.*EXTRA"):
            render_inline_template("hello {{NAME}}", {"EXTRA": "unused", "NAME": "mockapi"})

    def test_template_service_reads_named_template_from_fs(self) -> None:
        fs = MemoryFileSystem()
        template_root = Path("/templates")
        fs.write_text(template_root / "hello.tpl", "hello {{NAME}}")

        rendered = TemplateService(fs, template_root).render("hello.tpl", {"NAME": "mockapi"})

        self.assertEqual(rendered, "hello mockapi")


if __name__ == "__main__":
    unittest.main()
