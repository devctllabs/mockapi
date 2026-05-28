from __future__ import annotations

import io
import json
import os
from pathlib import Path
import tempfile
import textwrap
import unittest

import detect_package_manager as detect_package_manager_cli
from mockapi_runtime.package_manager import detect_package_manager


def write_profile(root: Path, package_path: str = "mock-server") -> None:
    profile_dir = root / ".mockapi"
    profile_dir.mkdir(parents=True)
    (profile_dir / "profile.toml").write_text(
        textwrap.dedent(
            f"""\
            schemaVersion = 1

            [generator]
            name = "mockapi"
            version = "0.1.0"

            [project]
            root = "."

            [project.target]
            packagePath = "{package_path}"
            packageName = "@local/mock-server"
            serverName = "Mock API"

            [state]
            schemaVersion = 1
            """
        ),
        encoding="utf-8",
    )


def write_package_json(root: Path, package_manager: str | None = None) -> None:
    root.mkdir(parents=True, exist_ok=True)
    package: dict[str, str] = {"name": "pkg"}
    if package_manager:
        package["packageManager"] = package_manager
    (root / "package.json").write_text(json.dumps(package) + "\n", encoding="utf-8")


def write_executable(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    path.chmod(0o755)


def isolated_env(root: Path, path: str) -> dict[str, str]:
    home = root / "home"
    home.mkdir(exist_ok=True)
    return {"HOME": str(home), "PATH": path}


class PackageManagerTests(unittest.TestCase):
    def test_missing_profile_returns_failure_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            result = detect_package_manager(root=root, env=isolated_env(root, ""))

            self.assertFalse(result.ok)
            self.assertEqual(result.source, "error")
            self.assertEqual(result.packageRoot, "")
            self.assertIn("Profile file not found", result.diagnostics[0])

    def test_malformed_profile_returns_failure_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile_dir = root / ".mockapi"
            profile_dir.mkdir()
            (profile_dir / "profile.toml").write_text("[project\n", encoding="utf-8")

            result = detect_package_manager(root=root, env=isolated_env(root, ""))

            self.assertFalse(result.ok)
            self.assertIn("Could not parse profile TOML", result.diagnostics[0])

    def test_missing_package_root_returns_failure_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_profile(root)

            result = detect_package_manager(root=root, env=isolated_env(root, ""))

            self.assertFalse(result.ok)
            self.assertTrue(result.packageRoot.endswith("/mock-server"))
            self.assertIn("Generated package root does not exist", result.diagnostics[0])

    def test_missing_generated_package_json_returns_failure_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package_root = root / "mock-server"
            write_profile(root)
            package_root.mkdir()

            result = detect_package_manager(root=root, env=isolated_env(root, ""))

            self.assertFalse(result.ok)
            self.assertEqual(result.packageRoot, str(package_root.resolve()))
            self.assertIn("Generated package package.json is missing", result.diagnostics[0])

    def test_malformed_generated_package_json_returns_failure_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package_root = root / "mock-server"
            write_profile(root)
            package_root.mkdir()
            (package_root / "package.json").write_text("{", encoding="utf-8")

            result = detect_package_manager(root=root, env=isolated_env(root, ""))

            self.assertFalse(result.ok)
            self.assertIn("Could not parse package.json", result.diagnostics[0])

    def test_unsupported_package_manager_returns_failure_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package_root = root / "mock-server"
            write_profile(root)
            write_package_json(package_root, "deno@2.0.0")

            result = detect_package_manager(root=root, env=isolated_env(root, ""))

            self.assertFalse(result.ok)
            self.assertIn("Unsupported packageManager", result.diagnostics[0])
            self.assertIn("bun, npm, pnpm, yarn", result.diagnostics[0])

    def test_generated_package_manager_wins_over_available_pnpm(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package_root = root / "mock-server"
            write_profile(root)
            write_package_json(package_root, "npm@11.0.0")
            pnpm_bin = root / "bin/pnpm"
            npm_bin = root / "bin/npm"
            write_executable(pnpm_bin)
            write_executable(npm_bin)

            result = detect_package_manager(root=root, env=isolated_env(root, str(pnpm_bin.parent)))

            self.assertTrue(result.ok)
            self.assertEqual(result.manager, "npm")
            self.assertEqual(result.source, "generated package.json packageManager")
            self.assertEqual(result.commands.install, "npm install")

    def test_project_package_manager_is_used_when_generated_package_has_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package_root = root / "mock-server"
            write_profile(root)
            write_package_json(package_root)
            write_package_json(root, "yarn@4.0.0")
            yarn_bin = root / "bin/yarn"
            write_executable(yarn_bin)

            result = detect_package_manager(root=root, env=isolated_env(root, str(yarn_bin.parent)))

            self.assertTrue(result.ok)
            self.assertEqual(result.manager, "yarn")
            self.assertEqual(result.source, "project package.json packageManager")
            self.assertEqual(result.commands.codegen, "yarn run codegen")

    def test_prefers_available_pnpm_over_other_lockfiles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package_root = root / "mock-server"
            write_profile(root)
            write_package_json(package_root)
            (root / "yarn.lock").write_text("", encoding="utf-8")
            (root / "package-lock.json").write_text("{}", encoding="utf-8")
            pnpm_bin = root / "bin/pnpm"
            write_executable(pnpm_bin)

            result = detect_package_manager(root=root, env=isolated_env(root, str(pnpm_bin.parent)))

            self.assertTrue(result.ok)
            self.assertEqual(result.manager, "pnpm")
            self.assertEqual(result.source, "pnpm available")
            self.assertEqual(result.commands.check, "pnpm run check")

    def test_uses_pnpm_lockfile_before_other_lockfiles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package_root = root / "mock-server"
            write_profile(root)
            write_package_json(package_root)
            (root / "pnpm-lock.yaml").write_text("", encoding="utf-8")
            (root / "yarn.lock").write_text("", encoding="utf-8")
            pnpm_bin = root / "bin/pnpm"
            write_executable(pnpm_bin)

            result = detect_package_manager(root=root, env=isolated_env(root, str(pnpm_bin.parent)))

            self.assertTrue(result.ok)
            self.assertEqual(result.manager, "pnpm")
            self.assertEqual(result.source, "pnpm lockfile")

    def test_falls_back_to_npm_when_no_stronger_signal_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package_root = root / "mock-server"
            write_profile(root)
            write_package_json(package_root)
            npm_bin = root / "bin/npm"
            write_executable(npm_bin)

            result = detect_package_manager(root=root, env=isolated_env(root, str(npm_bin.parent)))

            self.assertTrue(result.ok)
            self.assertEqual(result.manager, "npm")
            self.assertEqual(result.source, "default")

    def test_detects_yarn_from_lockfile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package_root = root / "mock-server"
            write_profile(root)
            write_package_json(package_root)
            (root / "yarn.lock").write_text("", encoding="utf-8")
            yarn_bin = root / "bin/yarn"
            write_executable(yarn_bin)

            result = detect_package_manager(root=root, env=isolated_env(root, str(yarn_bin.parent)))

            self.assertTrue(result.ok)
            self.assertEqual(result.manager, "yarn")
            self.assertEqual(result.source, "yarn lockfile")
            self.assertEqual(result.commands.install, "yarn install")

    def test_uses_corepack_for_yarn_lockfile_without_preferring_pnpm(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package_root = root / "mock-server"
            write_profile(root)
            write_package_json(package_root)
            (root / "yarn.lock").write_text("", encoding="utf-8")
            corepack_bin = root / "bin/corepack"
            write_executable(corepack_bin)

            result = detect_package_manager(root=root, env=isolated_env(root, str(corepack_bin.parent)))

            self.assertTrue(result.ok)
            self.assertEqual(result.manager, "yarn")
            self.assertEqual(result.executor, "corepack yarn")
            self.assertEqual(result.commands.codegen, "corepack yarn run codegen")

    def test_detects_bun_from_lockfile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package_root = root / "mock-server"
            write_profile(root)
            write_package_json(package_root)
            (root / "bun.lock").write_text("", encoding="utf-8")
            bun_bin = root / "bin/bun"
            write_executable(bun_bin)

            result = detect_package_manager(root=root, env=isolated_env(root, str(bun_bin.parent)))

            self.assertTrue(result.ok)
            self.assertEqual(result.manager, "bun")
            self.assertEqual(result.source, "bun lockfile")
            self.assertEqual(result.commands.check, "bun run check")

    def test_recovers_pnpm_installed_under_nvm(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            package_root = root / "mock-server"
            nvm_bin = home / ".nvm/versions/node/v20.0.0/bin"
            write_profile(root)
            write_package_json(package_root)
            (home / ".nvm/alias").mkdir(parents=True)
            (home / ".nvm/alias/default").write_text("v20.0.0\n", encoding="utf-8")
            write_executable(nvm_bin / "pnpm")

            result = detect_package_manager(root=root, env={"HOME": str(home), "PATH": os.pathsep.join(["/usr/bin", "/bin"])})

            self.assertTrue(result.ok)
            self.assertEqual(result.manager, "pnpm")
            self.assertEqual(result.pathPrepend, [str(nvm_bin.resolve())])
            self.assertEqual(result.commands.install, f'env PATH={nvm_bin.resolve()}:"$PATH" pnpm install')

    def test_uses_corepack_for_pnpm_when_direct_binary_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package_root = root / "mock-server"
            write_profile(root)
            write_package_json(package_root)
            (root / "pnpm-lock.yaml").write_text("", encoding="utf-8")
            corepack_bin = root / "bin/corepack"
            write_executable(corepack_bin)

            result = detect_package_manager(root=root, env=isolated_env(root, str(corepack_bin.parent)))

            self.assertTrue(result.ok)
            self.assertEqual(result.manager, "pnpm")
            self.assertEqual(result.executor, "corepack pnpm")
            self.assertEqual(result.commands.codegen, "corepack pnpm run codegen")

    def test_cli_outputs_json_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package_root = root / "mock-server"
            write_profile(root)
            write_package_json(package_root)
            npm_bin = root / "bin/npm"
            write_executable(npm_bin)
            stdout = io.StringIO()
            original_path = os.environ.get("PATH")
            original_home = os.environ.get("HOME")
            original_nvm_dir = os.environ.get("NVM_DIR")
            original_nvm_bin = os.environ.get("NVM_BIN")
            os.environ["PATH"] = str(npm_bin.parent)
            os.environ["HOME"] = str(root / "home")
            os.environ["NVM_DIR"] = str(root / "home/.nvm")
            os.environ.pop("NVM_BIN", None)
            try:
                exit_code = detect_package_manager_cli.main(["--root", str(root)], stdout=stdout)
            finally:
                if original_path is None:
                    os.environ.pop("PATH", None)
                else:
                    os.environ["PATH"] = original_path
                if original_home is None:
                    os.environ.pop("HOME", None)
                else:
                    os.environ["HOME"] = original_home
                if original_nvm_dir is None:
                    os.environ.pop("NVM_DIR", None)
                else:
                    os.environ["NVM_DIR"] = original_nvm_dir
                if original_nvm_bin is None:
                    os.environ.pop("NVM_BIN", None)
                else:
                    os.environ["NVM_BIN"] = original_nvm_bin

            payload = json.loads(stdout.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["manager"], "npm")
            self.assertEqual(payload["commands"]["check"], "npm run check")

    def test_cli_outputs_json_failure_for_missing_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stdout = io.StringIO()

            exit_code = detect_package_manager_cli.main(["--root", str(root)], stdout=stdout)

            payload = json.loads(stdout.getvalue())
            self.assertEqual(exit_code, 1)
            self.assertFalse(payload["ok"])
            self.assertIn("Profile file not found", payload["diagnostics"][0])
            self.assertIsNone(payload["commands"])


if __name__ == "__main__":
    unittest.main()
