from __future__ import annotations

import unittest
from pathlib import Path


TEMPLATE_ROOT = Path(__file__).resolve().parents[1] / "skills/mockapi/assets/templates/mock-server"


def read_template(relative_path: str) -> str:
    return (TEMPLATE_ROOT / relative_path).read_text(encoding="utf-8")


class TemplateContentTests(unittest.TestCase):
    def test_config_defaults_to_package_local_runtime_db(self) -> None:
        config = read_template("src/config.ts")

        self.assertIn("const packageRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')", config)
        self.assertIn("const defaultStateFile = path.join(packageRoot, '.mockapi-runtime', 'db.json')", config)
        self.assertIn("stateFile: resolveStateFile(process.env.MOCK_API_STATE_FILE)", config)
        self.assertIn("path.isAbsolute(value) ? value : path.resolve(packageRoot, value)", config)

    def test_server_logs_state_snapshot_path(self) -> None:
        server = read_template("src/server.ts")

        self.assertIn("State snapshot: ${config.stateFile}", server)

    def test_template_ignores_runtime_state_directory(self) -> None:
        gitignore = read_template(".gitignore")

        self.assertIn(".mockapi-runtime/", gitignore)
        self.assertIn("dist/", gitignore)

    def test_id_allocator_uses_new_constructor_name(self) -> None:
        ids = read_template("src/lib/ids.ts")

        self.assertIn("export const newIdAllocator", ids)

    def test_admin_codegen_reads_source_and_writes_final_admin_yaml(self) -> None:
        script = read_template("scripts/codegen-admin-openapi.ts")

        self.assertIn("openapi/admin.source.yaml", script)
        self.assertIn("openapi/admin.yaml", script)
        self.assertIn("await readYaml(adminSourcePath)", script)
        self.assertIn("await writeFile(adminPath", script)

    def test_runtime_passes_path_parameters_using_openapi_ts_shape(self) -> None:
        runtime = read_template("src/lib/honoMockRuntime.ts")

        self.assertIn("path: context.req.param()", runtime)
        self.assertNotIn("params: context.req.param()", runtime)


if __name__ == "__main__":
    unittest.main()
