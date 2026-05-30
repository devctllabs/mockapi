from __future__ import annotations

import json
import textwrap
import tomllib
from pathlib import Path
from typing import Iterable

from mockapi_runtime.filesystem import FileSystem
from mockapi_runtime.files import WriteService
from mockapi_runtime.generate import CommandRunner, MockServerGeneratorService, PackageManagerDetector, SkillRootService
from mockapi_runtime.models import Profile, profile_from_mapping
from mockapi_runtime.profile import ProfileValidatorService
from mockapi_runtime.render_features import FeatureRenderService
from mockapi_runtime.render_project import ProjectRenderService
from mockapi_runtime.templates import TemplateService


PROJECT_ROOT = Path("/project").resolve()
SKILL_ROOT = Path("/skill/mockapi").resolve()
RUNTIME_ROOT = Path("/runtime").resolve()
TEMPLATE_ROOT = RUNTIME_ROOT / "templates"
ADMIN_OPENAPI_TEMPLATE_PATH = RUNTIME_ROOT / "admin_openapi.yaml"
OPENAPI_FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures/openapi"


class MemoryFileSystem(FileSystem):
    def __init__(self) -> None:
        self.files: dict[str, str] = {}
        self.directories: set[str] = set()

    def read_text(self, path: Path) -> str:
        return self.files[self._key(path)]

    def write_text(self, path: Path, content: str) -> None:
        key = self._key(path)
        self._add_parent_directories(Path(key))
        self.files[key] = content

    def is_file(self, path: Path) -> bool:
        return self._key(path) in self.files

    def exists(self, path: Path) -> bool:
        key = self._key(path)
        return key in self.files or key in self.directories

    def mkdir(self, path: Path) -> None:
        self._add_directory(Path(self._key(path)))

    def iter_files(self, root: Path) -> Iterable[Path]:
        root_key = self._key(root)
        prefix = f"{root_key}/"
        return [Path(key) for key in sorted(self.files) if key.startswith(prefix)]

    def _key(self, path: Path) -> str:
        return Path(path).as_posix()

    def _add_parent_directories(self, path: Path) -> None:
        for parent in path.parents:
            self.directories.add(parent.as_posix())

    def _add_directory(self, path: Path) -> None:
        self.directories.add(path.as_posix())
        self._add_parent_directories(path)


SIMPLE_OPENAPI = """openapi: 3.1.0
info:
  title: Test API
  version: 1.0.0
paths: {}
components:
  schemas:
    Workspace:
      type: object
"""


def profile_toml(*, openapi_path: str = "openapi.yaml") -> str:
    openapi_value = json.dumps(openapi_path)
    return textwrap.dedent(
        f"""\
        schemaVersion = 1

        [generator]
        name = "mockapi"
        version = "0.1.0"

        [project]
        root = "."

        [project.target]
        packagePath = "mock-server"
        packageName = "@local/mock-server"
        serverName = "Mock API"

        [[apis]]
        name = "product-api"
        openapi = {openapi_value}
        basePath = "/api/v1"

        [[features]]
        name = "workspaces"
        stateSlices = ["workspaces"]
        operations = ["listWorkspaces"]

        [state]
        schemaVersion = 1

        [[state.slices]]
        name = "workspaces"
        recordType = "Workspace"
        array = true
        idField = "id"
        softDeleteField = "deletedAt"

        [[operations]]
        operationId = "listWorkspaces"
        api = "product-api"
        feature = "workspaces"
        method = "GET"
        path = "/workspaces"
        """
    )


def profile_model(profile_text: str | None = None) -> Profile:
    return profile_from_mapping(tomllib.loads(textwrap.dedent(profile_text or profile_toml())))


def default_behavior() -> str:
    return textwrap.dedent(
        """\
        # Mock Behavior

        ## operation:listWorkspaces
        Status: inferred
        """
    )


def seed_runtime_templates(fs: FileSystem) -> None:
    templates = {
        "app.ts.tpl": "{{STARTER_HEADER}}\nconst basePath = {{DEFAULT_BASE_PATH}}\n{{RUNTIME_IMPORTS}}\n{{ROUTE_REGISTRATIONS}}\n",
        "codegen-mock-runtime.ts.tpl": "{{GENERATED_HEADER}}\nexport const runtimeConfigs = [\n{{RUNTIME_CONFIGS}}\n]\n",
        "controllers.ts.tpl": (
            "{{STARTER_HEADER}}\n{{PRODUCT_IMPORTS}}\n{{OPERATION_IMPORTS}}\n"
            "export type MockApiDependencies = { state: unknown }\n"
            "const operationCount = {{OPERATION_COUNT}}\n"
            "export const newMockApiControllers = (deps: MockApiDependencies): {{PRODUCT_TYPES}} => ({\n"
            "{{CONTROLLER_SPREADS}}\n})\n"
        ),
        "openapi-ts.config.ts.tpl": "{{GENERATED_HEADER}}\nexport default [\n{{CONFIGS}}\n]\n",
        "operation-controller.ts.tpl": (
            "{{STARTER_HEADER}}\n"
            "export const {{FACTORY_NAME}} = (_deps: unknown): Pick<ProductMockControllers, {{PICK_KEYS}}> => ({\n"
            "{{CONTROLLER_METHODS}}\n"
            "})\n"
        ),
        "feature-seed.ts.tpl": (
            "{{STARTER_HEADER}}\n"
            "import type { SeedContext } from '../../generated/mock-admin/state/seed.ts'\n"
            "import type { MockState } from '../../generated/mock-admin/contract/index.ts'\n"
            "export const {{FUNCTION_NAME}} = (_context: SeedContext): Pick<MockState, {{PICK_KEYS}}> => ({\n"
            "{{SLICE_SEEDS}}\n"
            "})\n"
        ),
        "state-seed.ts.tpl": (
            "{{GENERATED_HEADER}}\n"
            "{{SEED_IMPORTS}}"
            "import type { MockState } from '../contract/index.ts'\n"
            "export const seedNow = {{SEED_NOW}}\n"
            "export const seedState = (): MockState => {\n"
            "  const context = { seedNow, fromSeedNow: (_days: number) => seedNow }\n"
            "  return {\n"
            "    schemaVersion: {{SCHEMA_VERSION}},\n"
            "    clock: { now: seedNow },\n"
            "{{FALLBACK_SLICE_SEEDS}}\n"
            "{{FEATURE_SEED_SPREADS}}\n"
            "  }\n"
            "}\n"
        ),
    }
    for name, content in templates.items():
        fs.write_text(TEMPLATE_ROOT / name, content)
    fs.write_text(
        ADMIN_OPENAPI_TEMPLATE_PATH,
        "openapi: 3.1.0\ninfo:\n  title: __MOCKAPI_ADMIN_API_TITLE__\npaths:\n  /__mock/health:\n    get: {}\ncomponents:\n  schemas:\n    MockClock:\n      type: object\n      required: [now]\n      properties:\n        now:\n          type: string\n          format: date-time\n__MOCKAPI_ADMIN_MOCK_STATE_SCHEMAS__\n",
    )


def seed_skill_template(fs: FileSystem) -> None:
    fs.write_text(SKILL_ROOT / "SKILL.md", "# Mockapi\n")
    fs.write_text(
        SKILL_ROOT / "assets/templates/mock-server/package.json",
        json.dumps(
            {
                "name": "__MOCKAPI_PACKAGE_NAME__",
                "scripts": {
                    "build": "node scripts/build.mjs",
                    "codegen": "tsx scripts/codegen-admin-openapi.ts && openapi-ts && tsx scripts/codegen-mock-runtime.ts",
                    "codegen:contract": "tsx scripts/codegen-admin-openapi.ts && openapi-ts",
                    "test": "vitest run",
                },
                "devDependencies": {
                    "esbuild": "^0.28.0",
                    "vitest": "^4.1.4",
                },
            },
            separators=(",", ":"),
        )
        + "\n",
    )
    fs.write_text(SKILL_ROOT / "assets/templates/mock-server/.gitignore", ".mockapi-runtime/\ndist/\n")
    fs.write_text(
        SKILL_ROOT / "assets/templates/mock-server/vitest.config.ts",
        "export default { test: { environment: 'node', globals: true } }\n",
    )
    fs.write_text(
        SKILL_ROOT / "assets/templates/mock-server/scripts/build.mjs",
        (
            "import { rm } from 'node:fs/promises'\n"
            "import path from 'node:path'\n"
            "import { fileURLToPath } from 'node:url'\n"
            "\n"
            "import { build } from 'esbuild'\n"
            "\n"
            "const packageRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')\n"
            "const distRoot = path.join(packageRoot, 'dist')\n"
            "\n"
            "await rm(distRoot, { recursive: true, force: true })\n"
            "\n"
            "await build({\n"
            "  bundle: true,\n"
            "  entryPoints: [path.join(packageRoot, 'src/server.ts')],\n"
            "  format: 'esm',\n"
            "  outfile: path.join(distRoot, 'server.js'),\n"
            "  platform: 'node',\n"
            "  sourcemap: true,\n"
            "  target: 'node20',\n"
            "})\n"
        ),
    )
    fs.write_text(
        SKILL_ROOT / "assets/templates/mock-server/scripts/codegen-admin-openapi.ts",
        (
            "// @ts-nocheck -- mockapi template source; stripped during generation\n"
            "// This file is generated by mockapi.\n"
            "// Do not edit by hand.\n"
            "\n"
            "admin codegen\n"
        ),
    )
    fs.write_text(
        SKILL_ROOT / "assets/templates/mock-server/scripts/lib/mockRuntimeCodegen.ts",
        (
            "// @ts-nocheck -- mockapi template source; stripped during generation\n"
            "// This file is generated by mockapi.\n"
            "// Do not edit by hand.\n"
            "\n"
            "runtime codegen\n"
        ),
    )
    for path, body in {
        "src/generated/mock-admin/state/controller.ts": "admin controller\n",
        "src/generated/mock-admin/state/repository.ts": "admin repository\n",
        "src/generated/mock-admin/state/service.ts": "admin service\n",
    }.items():
        fs.write_text(
            SKILL_ROOT / f"assets/templates/mock-server/{path}",
            (
                "// @ts-nocheck -- mockapi template source; stripped during generation\n"
                "// This file is generated by mockapi.\n"
                "// Do not edit by hand.\n"
                "\n"
                f"{body}"
            ),
        )
    fs.write_text(
        SKILL_ROOT / "assets/templates/mock-server/src/server.ts",
        "// @ts-nocheck -- mockapi template source; stripped during generation\nserver\n",
    )


def write_project(
    fs: FileSystem,
    *,
    root: Path = PROJECT_ROOT,
    profile: str | None = None,
    behavior: str | None = None,
    openapi: str | None = SIMPLE_OPENAPI,
) -> Path:
    if openapi is not None:
        fs.write_text(root / "openapi.yaml", openapi)
    profile_path = root / ".mockapi/profile.toml"
    fs.write_text(profile_path, profile or profile_toml())
    fs.write_text(root / ".mockapi/behavior.md", behavior or default_behavior())
    return profile_path


def seed_openapi_fixture(fs: FileSystem, *, root: Path = PROJECT_ROOT, fixture_root: Path = OPENAPI_FIXTURE_ROOT) -> Path:
    target_root = root / "openapi"
    for source_path in sorted(fixture_root.rglob("*")):
        if source_path.is_file():
            relative_path = source_path.relative_to(fixture_root)
            fs.write_text(target_root / relative_path, source_path.read_text(encoding="utf-8"))
    return target_root / "openapi.yaml"


def create_generator(
    fs: FileSystem,
    *,
    command_runner: CommandRunner | None = None,
    env: dict[str, str] | None = None,
    package_manager_detector: PackageManagerDetector | None = None,
) -> MockServerGeneratorService:
    seed_runtime_templates(fs)
    seed_skill_template(fs)
    template_service = TemplateService(fs, TEMPLATE_ROOT)
    return MockServerGeneratorService(
        fs,
        ProfileValidatorService(fs),
        WriteService(fs),
        ProjectRenderService(fs, template_service, ADMIN_OPENAPI_TEMPLATE_PATH),
        FeatureRenderService(fs, template_service),
        SkillRootService(fs, env=env if env is not None else {}, cwd=Path("/workspace"), script_root=SKILL_ROOT),
        command_runner=command_runner,
        package_manager_detector=package_manager_detector,
        env=env if env is not None else {},
    )
