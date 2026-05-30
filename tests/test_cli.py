from __future__ import annotations

import io
import json
import unittest

from tests.support import (
    PROJECT_ROOT,
    MemoryFileSystem,
    create_generator,
    default_behavior,
    profile_toml,
    seed_openapi_fixture,
    write_project,
)

import generate as generate_cli
import check_generated_quality as quality_cli
import preflight_generate as preflight_generate_cli
import validate_profile as validate_profile_cli
from mockapi_runtime.models import GenerateApplyResult
from mockapi_runtime.profile import ProfileValidatorService


class RecordingGenerateService:
    def __init__(self) -> None:
        self.kwargs: dict[str, object] | None = None

    def generate(self, **kwargs: object) -> GenerateApplyResult:
        self.kwargs = kwargs
        return GenerateApplyResult(diagnostics=[], files=[], outRoot="/out")


class CliTests(unittest.TestCase):
    def test_generate_main_uses_injected_generator_and_writes_json(self) -> None:
        fs = MemoryFileSystem()
        generator = create_generator(fs)
        write_project(fs)
        stdout = io.StringIO()

        exit_code = generate_cli.main(
            ["--root", str(PROJECT_ROOT), "--profile", ".mockapi/profile.toml", "--dry-run"],
            generator=generator,
            stdout=stdout,
        )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["dryRun"])
        self.assertTrue(payload["ok"])

    def test_generate_main_forwards_run_codegen_flag(self) -> None:
        generator = RecordingGenerateService()
        stdout = io.StringIO()

        exit_code = generate_cli.main(
            ["--root", str(PROJECT_ROOT), "--profile", ".mockapi/profile.toml", "--run-codegen"],
            generator=generator,
            stdout=stdout,
        )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["ok"])
        self.assertIsNotNone(generator.kwargs)
        self.assertTrue(generator.kwargs["run_codegen"])

    def test_validate_profile_main_outputs_text_for_success(self) -> None:
        fs = MemoryFileSystem()
        write_project(fs)
        stdout = io.StringIO()

        exit_code = validate_profile_cli.main(
            ["--root", str(PROJECT_ROOT), "--profile", ".mockapi/profile.toml"],
            validator=ProfileValidatorService(fs),
            stdout=stdout,
        )

        self.assertEqual(exit_code, 0)
        self.assertIn("Result: ok: true", stdout.getvalue())

    def test_validate_profile_main_outputs_json_for_failure(self) -> None:
        fs = MemoryFileSystem()
        write_project(fs, behavior="# Missing\n")
        stdout = io.StringIO()

        exit_code = validate_profile_cli.main(
            ["--root", str(PROJECT_ROOT), "--profile", ".mockapi/profile.toml", "--json"],
            validator=ProfileValidatorService(fs),
            stdout=stdout,
        )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["profile"]["operationCount"], 1)
        self.assertEqual(payload["errors"][0]["id"], "sidecar.behavior.missingAnchor")

    def test_validate_profile_main_smoke_checks_ref_based_openapi_fixture(self) -> None:
        fs = MemoryFileSystem()
        seed_openapi_fixture(fs)
        profile_path = write_project(
            fs,
            openapi=None,
            profile=profile_toml(openapi_path="openapi/openapi.yaml"),
            behavior=default_behavior(),
        )
        stdout = io.StringIO()

        exit_code = validate_profile_cli.main(
            ["--root", str(PROJECT_ROOT), "--profile", ".mockapi/profile.toml", "--json"],
            validator=ProfileValidatorService(fs),
            stdout=stdout,
        )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(profile_path, PROJECT_ROOT / ".mockapi/profile.toml")
        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["profile"]["operationCount"], 1)
        self.assertEqual(payload["warnings"], [])

    def test_preflight_generate_main_classifies_missing_profile(self) -> None:
        fs = MemoryFileSystem()
        stdout = io.StringIO()

        exit_code = preflight_generate_cli.main(
            ["--root", str(PROJECT_ROOT)],
            fs=fs,
            stdout=stdout,
        )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["classification"], "missing")
        self.assertEqual(payload["profile"], str(PROJECT_ROOT / ".mockapi/profile.toml"))

    def test_preflight_generate_main_classifies_repair_for_invalid_sidecars(self) -> None:
        fs = MemoryFileSystem()
        write_project(fs, behavior="# Missing\n")
        stdout = io.StringIO()

        exit_code = preflight_generate_cli.main(
            ["--root", str(PROJECT_ROOT)],
            fs=fs,
            stdout=stdout,
        )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["classification"], "repair")
        self.assertFalse(payload["validation"]["ok"])
        self.assertEqual(payload["validation"]["errors"][0]["id"], "sidecar.behavior.missingAnchor")

    def test_preflight_generate_main_classifies_valid_sidecars(self) -> None:
        fs = MemoryFileSystem()
        write_project(fs)
        stdout = io.StringIO()

        exit_code = preflight_generate_cli.main(
            ["--root", str(PROJECT_ROOT)],
            fs=fs,
            stdout=stdout,
        )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["classification"], "valid")
        self.assertTrue(payload["validation"]["ok"])

    def test_check_generated_quality_main_outputs_json_for_failure(self) -> None:
        fs = MemoryFileSystem()
        fs.write_text(
            PROJECT_ROOT / "mock-server/src/features/workspaces/controllers/listWorkspaces.ts",
            "throw new Error('TODO mockapi: implement listWorkspaces')\n",
        )
        stdout = io.StringIO()

        exit_code = quality_cli.main(
            [
                "--package-root",
                str(PROJECT_ROOT / "mock-server"),
                "--json",
            ],
            fs=fs,
            stdout=stdout,
        )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["errors"][0]["id"], "quality.phase.incompleteImplementation")
        self.assertEqual(payload["errors"][1]["id"], "quality.todo.remaining")

    def test_check_generated_quality_main_forwards_profile_path(self) -> None:
        fs = MemoryFileSystem()
        profile_path = PROJECT_ROOT / ".mockapi/profile.toml"
        fs.write_text(
            profile_path,
            profile_toml().replace("[state]\nschemaVersion = 1", "[state]\nschemaVersion = 1\nseed = false"),
        )
        fs.write_text(
            PROJECT_ROOT / "mock-server/src/features/workspaces/seed.ts",
            "import type { MockState } from '../../generated/mock-admin/contract/index.ts'\n"
            "export const seedWorkspaces = (): Pick<MockState, 'workspaces'> => ({ workspaces: [] })\n",
        )
        stdout = io.StringIO()

        exit_code = quality_cli.main(
            [
                "--package-root",
                str(PROJECT_ROOT / "mock-server"),
                "--profile",
                str(profile_path),
                "--json",
            ],
            fs=fs,
            stdout=stdout,
        )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["ok"])


if __name__ == "__main__":
    unittest.main()
