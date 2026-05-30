from __future__ import annotations

import unittest
from pathlib import Path

from tests.support import MemoryFileSystem

from mockapi_runtime.key_path import document_key_path_exists, json_key_path_exists, yaml_key_path_exists


class KeyPathTests(unittest.TestCase):
    def test_yaml_key_path_exists_for_nested_mapping_key(self) -> None:
        text = """openapi: 3.1.0
components:
  schemas:
    Workspace:
      type: object
"""

        self.assertTrue(yaml_key_path_exists(text, ("components", "schemas", "Workspace")))

    def test_yaml_key_path_requires_direct_path(self) -> None:
        text = """components:
  responses:
    Workspace:
      description: wrong section
  schemas:
    Folder:
      type: object
"""

        self.assertFalse(yaml_key_path_exists(text, ("components", "schemas", "Workspace")))

    def test_yaml_key_path_supports_quoted_keys_and_comments(self) -> None:
        text = """# root comment
"components": # inline comment
  'schemas':
    "TrashItem": { type: object } # inline value
"""

        self.assertTrue(yaml_key_path_exists(text, ("components", "schemas", "TrashItem")))

    def test_yaml_key_path_supports_single_quote_doubling_in_keys(self) -> None:
        text = """'comp''onents':
  schemas:
    Workspace: {}
"""

        self.assertTrue(yaml_key_path_exists(text, ("comp'onents", "schemas", "Workspace")))

    def test_yaml_key_path_supports_double_quote_escapes_in_keys(self) -> None:
        text = """"comp\\"onents": # inline comment
  schemas:
    Workspace: {}
"""

        self.assertTrue(yaml_key_path_exists(text, ('comp"onents', "schemas", "Workspace")))

    def test_yaml_key_path_ignores_block_scalar_contents(self) -> None:
        text = """components:
  description: |
    schemas:
      TrashItem:
        type: object
  schemas:
    Workspace:
      type: object
"""

        self.assertFalse(yaml_key_path_exists(text, ("components", "schemas", "TrashItem")))
        self.assertTrue(yaml_key_path_exists(text, ("components", "schemas", "Workspace")))

    def test_json_key_path_exists_for_nested_mapping_key(self) -> None:
        self.assertTrue(
            json_key_path_exists(
                '{"components":{"schemas":{"Workspace":{"type":"object"}}}}',
                ("components", "schemas", "Workspace"),
            )
        )

    def test_document_key_path_dispatches_by_suffix(self) -> None:
        fs = MemoryFileSystem()
        yaml_path = Path("/api/openapi.yaml")
        json_path = Path("/api/openapi.json")
        fs.write_text(yaml_path, "components:\n  schemas:\n    Workspace: {}\n")
        fs.write_text(json_path, '{"components":{"schemas":{"Folder":{}}}}')

        self.assertTrue(document_key_path_exists(fs, yaml_path, ("components", "schemas", "Workspace")))
        self.assertTrue(document_key_path_exists(fs, json_path, ("components", "schemas", "Folder")))
        self.assertFalse(document_key_path_exists(fs, Path("/api/missing.yaml"), ("components",)))


if __name__ == "__main__":
    unittest.main()
