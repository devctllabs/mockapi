from __future__ import annotations

from dataclasses import asdict
import os
from pathlib import Path
import subprocess
from typing import Mapping, Protocol

from .context import create_generate_context
from .diagnostics import Diagnostic
from .filesystem import FileSystem, LocalFileSystem
from .files import WriteService
from .models import (
    CodegenRunResult,
    FileWriteResult,
    GenerateApplyResult,
    GenerateDryRunResult,
    GenerateFailureResult,
    GenerateResult,
    PlannedFile,
    PlannedWrite,
)
from .package_manager import PackageManagerResult, detect_package_manager
from .profile import ProfileValidatorService
from .render_features import FeatureRenderService
from .render_project import ProjectRenderService
from .templates import TemplateService


class CommandExecutionResult(Protocol):
    command: str
    cwd: Path
    exitCode: int
    stdout: str
    stderr: str


class CommandRunner(Protocol):
    def run(self, command: str, *, cwd: Path) -> CommandExecutionResult:
        ...


class PackageManagerDetector(Protocol):
    def detect(
        self,
        *,
        root: Path,
        profile_path: str,
        package_root: Path,
        env: Mapping[str, str],
    ) -> PackageManagerResult:
        ...


class SubprocessCommandExecutionResult:
    def __init__(self, *, command: str, cwd: Path, exit_code: int, stdout: str, stderr: str) -> None:
        self.command = command
        self.cwd = cwd
        self.exitCode = exit_code
        self.stdout = stdout
        self.stderr = stderr


class SubprocessCommandRunner:
    def run(self, command: str, *, cwd: Path) -> CommandExecutionResult:
        completed = subprocess.run(
            command,
            cwd=cwd,
            shell=True,
            capture_output=True,
            text=True,
        )
        return SubprocessCommandExecutionResult(
            command=command,
            cwd=cwd,
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )


class LocalPackageManagerDetector:
    def detect(
        self,
        *,
        root: Path,
        profile_path: str,
        package_root: Path,
        env: Mapping[str, str],
    ) -> PackageManagerResult:
        return detect_package_manager(
            root=root,
            profile_path=profile_path,
            package_root=str(package_root),
            env=env,
        )


class SkillRootService:
    def __init__(
        self,
        fs: FileSystem,
        *,
        env: Mapping[str, str] | None = None,
        cwd: Path | None = None,
        script_root: Path | None = None,
    ) -> None:
        self.fs = fs
        self.env = env if env is not None else os.environ
        self.cwd = cwd or Path.cwd()
        self.script_root = script_root or Path(__file__).resolve().parents[2]

    def discover(self) -> Path:
        env_root = self.env.get("MOCKAPI_SKILL_ROOT")
        if env_root:
            candidate = Path(env_root).resolve()
            if self.fs.is_file(candidate / "SKILL.md"):
                return candidate

        candidates = [
            self.script_root,
            self.cwd / "skills/mockapi",
        ]
        for candidate in candidates:
            if self.fs.is_file(candidate / "SKILL.md"):
                return candidate.resolve()

        raise RuntimeError("Could not locate mockapi skill root.")


def dedupe_writes(writes: list[PlannedWrite]) -> list[PlannedWrite]:
    by_path: dict[Path, PlannedWrite] = {}
    for write in writes:
        by_path[Path(write.path)] = write
    return list(by_path.values())


def planned_files(writes: list[PlannedWrite]) -> list[PlannedFile]:
    return [PlannedFile(overwrite=write.overwrite, path=str(write.path)) for write in writes]


def apply_template_replacements(writes: list[PlannedWrite], replacements: dict[str, str]) -> list[PlannedWrite]:
    result: list[PlannedWrite] = []
    for write in writes:
        content = write.content
        for placeholder, value in replacements.items():
            content = content.replace(placeholder, value)
        result.append(PlannedWrite(content=content, overwrite=write.overwrite, path=write.path))
    return result


def generate_result_to_payload(result: GenerateResult) -> dict[str, object]:
    return asdict(result)


def command_outputs(*results: CommandExecutionResult | None) -> tuple[str, str]:
    stdout = "\n".join(result.stdout for result in results if result is not None and result.stdout)
    stderr = "\n".join(result.stderr for result in results if result is not None and result.stderr)
    return stdout, stderr


def codegen_diagnostic(message: str) -> Diagnostic:
    return {"id": "package.codegen.failed", "message": message}


PNPM_WORKSPACE_YAML = "allowBuilds:\n  esbuild: true\n"


class MockServerGeneratorService:
    def __init__(
        self,
        fs: FileSystem,
        profile_validator: ProfileValidatorService,
        write_service: WriteService,
        project_renderer: ProjectRenderService,
        feature_renderer: FeatureRenderService,
        skill_root_service: SkillRootService,
        command_runner: CommandRunner | None = None,
        package_manager_detector: PackageManagerDetector | None = None,
        env: Mapping[str, str] | None = None,
    ) -> None:
        self.fs = fs
        self.profile_validator = profile_validator
        self.write_service = write_service
        self.project_renderer = project_renderer
        self.feature_renderer = feature_renderer
        self.skill_root_service = skill_root_service
        self.command_runner = command_runner or SubprocessCommandRunner()
        self.package_manager_detector = package_manager_detector or LocalPackageManagerDetector()
        self.env = env if env is not None else os.environ

    @classmethod
    def local(cls) -> "MockServerGeneratorService":
        fs = LocalFileSystem()
        template_service = TemplateService(fs)
        return cls(
            fs,
            ProfileValidatorService(fs),
            WriteService(fs),
            ProjectRenderService(fs, template_service),
            FeatureRenderService(fs, template_service),
            SkillRootService(fs),
        )

    def run_codegen(
        self,
        *,
        root: Path,
        profile_path: str,
        package_root: Path,
    ) -> tuple[dict[str, object], CodegenRunResult, list[Diagnostic], list[FileWriteResult]]:
        package_manager = self.package_manager_detector.detect(
            root=root,
            profile_path=profile_path,
            package_root=package_root,
            env=self.env,
        )
        package_manager_payload = package_manager.to_payload()
        if not package_manager.ok or package_manager.commands is None:
            diagnostics = [
                codegen_diagnostic(diagnostic)
                for diagnostic in package_manager.diagnostics
            ]
            return (
                package_manager_payload,
                CodegenRunResult(attempted=True, ok=False, diagnostics=package_manager.diagnostics),
                diagnostics,
                [],
            )

        codegen_files: list[FileWriteResult] = []
        if package_manager.manager == "pnpm":
            codegen_files.append(
                self.write_service.write_planned_file(
                    PlannedWrite(
                        content=PNPM_WORKSPACE_YAML,
                        overwrite=False,
                        path=package_root / "pnpm-workspace.yaml",
                    )
                )
            )

        install_result: CommandExecutionResult | None = None
        install_command = None
        if not self.fs.exists(package_root / "node_modules"):
            install_command = package_manager.commands.install
            install_result = self.command_runner.run(install_command, cwd=package_root)
            if install_result.exitCode != 0:
                stdout, stderr = command_outputs(install_result)
                message = f"Dependency install failed with exit code {install_result.exitCode}."
                return (
                    package_manager_payload,
                    CodegenRunResult(
                        attempted=True,
                        ok=False,
                        installCommand=install_command,
                        codegenCommand=package_manager.commands.codegen,
                        exitCode=install_result.exitCode,
                        stdout=stdout,
                        stderr=stderr,
                        diagnostics=[message],
                    ),
                    [codegen_diagnostic(message)],
                    codegen_files,
                )

        codegen_command = package_manager.commands.codegen
        codegen_result = self.command_runner.run(codegen_command, cwd=package_root)
        stdout, stderr = command_outputs(install_result, codegen_result)
        if codegen_result.exitCode != 0:
            message = f"Codegen failed with exit code {codegen_result.exitCode}."
            return (
                package_manager_payload,
                CodegenRunResult(
                    attempted=True,
                    ok=False,
                    installCommand=install_command,
                    codegenCommand=codegen_command,
                    exitCode=codegen_result.exitCode,
                    stdout=stdout,
                    stderr=stderr,
                    diagnostics=[message],
                ),
                [codegen_diagnostic(message)],
                codegen_files,
            )

        return (
            package_manager_payload,
            CodegenRunResult(
                attempted=True,
                ok=True,
                installCommand=install_command,
                codegenCommand=codegen_command,
                exitCode=codegen_result.exitCode,
                stdout=stdout,
                stderr=stderr,
            ),
            [],
            codegen_files,
        )

    def detect_codegen_commands(
        self,
        *,
        root: Path,
        profile_path: str,
        package_root: Path,
    ) -> tuple[dict[str, object], CodegenRunResult]:
        package_manager = self.package_manager_detector.detect(
            root=root,
            profile_path=profile_path,
            package_root=package_root,
            env=self.env,
        )
        package_manager_payload = package_manager.to_payload()
        codegen_command = package_manager.commands.codegen if package_manager.ok and package_manager.commands else None
        return (
            package_manager_payload,
            CodegenRunResult(
                attempted=False,
                ok=package_manager.ok,
                codegenCommand=codegen_command,
                diagnostics=package_manager.diagnostics,
            ),
        )

    def generate(
        self,
        *,
        root: Path,
        profile_path: str,
        out: str | None = None,
        dry_run: bool = False,
        skill_root: Path | None = None,
        run_codegen: bool = False,
    ) -> GenerateResult:
        resolved_root = root.resolve()
        resolved_profile_path = (resolved_root / profile_path).resolve() if not Path(profile_path).is_absolute() else Path(profile_path)
        validation = self.profile_validator.validate(resolved_profile_path, root=Path("."), cwd=resolved_root)

        if not validation.ok:
            return GenerateFailureResult(diagnostics=validation.errors, dryRun=bool(dry_run), files=[])

        profile = self.profile_validator.load_profile_model(resolved_profile_path)
        context = create_generate_context(profile, resolved_root, out)
        resolved_skill_root = skill_root or self.skill_root_service.discover()
        template_root = resolved_skill_root / "assets/templates/mock-server"
        template_writes = (
            apply_template_replacements(
                self.write_service.copy_template_writes(template_root, context.outRoot),
                {"__MOCKAPI_PACKAGE_NAME__": profile.project.target.packageName},
            )
            if self.fs.exists(template_root)
            else []
        )
        writes = dedupe_writes(
            [
                *template_writes,
                *self.project_renderer.planned_writes(context),
                *self.feature_renderer.planned_writes(context),
            ]
        )

        if dry_run:
            return GenerateDryRunResult(diagnostics=[], files=planned_files(writes), outRoot=str(context.outRoot))

        files = [self.write_service.write_planned_file(write) for write in writes]
        if run_codegen:
            package_manager, codegen, diagnostics, codegen_files = self.run_codegen(
                root=resolved_root,
                profile_path=profile_path,
                package_root=context.outRoot,
            )
            files = [*files, *codegen_files]
        else:
            package_manager, codegen = self.detect_codegen_commands(
                root=resolved_root,
                profile_path=profile_path,
                package_root=context.outRoot,
            )
            diagnostics = []
        return GenerateApplyResult(
            diagnostics=diagnostics,
            files=files,
            outRoot=str(context.outRoot),
            packageManager=package_manager,
            codegen=codegen,
            ok=not diagnostics,
        )
