from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import shlex
import tomllib
from collections.abc import Mapping


MANAGER_LOCKFILES = {
    "pnpm": ("pnpm-lock.yaml",),
    "yarn": ("yarn.lock",),
    "bun": ("bun.lockb", "bun.lock"),
    "npm": ("package-lock.json",),
}
LOCKFILE_ORDER = ("pnpm", "yarn", "bun", "npm")
SCRIPT_RUNNERS = {
    "bun": ("bun", "run"),
    "npm": ("npm", "run"),
    "pnpm": ("pnpm", "run"),
    "yarn": ("yarn", "run"),
}


@dataclass(frozen=True, slots=True)
class PackageManagerCommandSet:
    install: str
    codegen: str
    check: str


@dataclass(frozen=True, slots=True)
class PackageManagerResult:
    ok: bool
    manager: str
    source: str
    packageRoot: str
    projectRoot: str
    pathPrepend: list[str]
    executable: str | None
    executor: str
    commands: PackageManagerCommandSet | None
    diagnostics: list[str]

    def to_payload(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PackageManagerDetectionContext:
    projectRoot: Path
    packageRoot: Path
    environment: Mapping[str, str]
    diagnostics: list[str]
    packageJson: Mapping[str, object]


def detect_package_manager(
    *,
    root: Path,
    profile_path: str = ".mockapi/profile.toml",
    package_root: str | None = None,
    env: Mapping[str, str] | None = None,
) -> PackageManagerResult:
    context_or_result = build_detection_context(
        root=root,
        profile_path=profile_path,
        package_root=package_root,
        env=env,
    )
    if isinstance(context_or_result, PackageManagerResult):
        return context_or_result

    context = context_or_result
    try:
        manager, source = choose_manager(
            context.packageRoot,
            context.projectRoot,
            context.environment,
            context.diagnostics,
            context.packageJson,
        )
    except PackageManagerDetectionError as exc:
        return failure_result(
            project_root=context.projectRoot,
            package_root=exc.package_root,
            diagnostics=[*context.diagnostics, exc.message],
        )

    executable = resolve_manager_executable(manager, context.packageRoot, context.projectRoot, context.environment)
    if executable.executable is None:
        context.diagnostics.append(f"Could not find {manager!r} on PATH, through nvm, or through corepack.")
        return package_manager_result(context, manager, source, executable, commands=None, ok=False)

    return package_manager_result(context, manager, source, executable, commands=build_commands(manager, executable), ok=True)


def build_detection_context(
    *,
    root: Path,
    profile_path: str,
    package_root: str | None,
    env: Mapping[str, str] | None,
) -> PackageManagerDetectionContext | PackageManagerResult:
    resolved_root = root.resolve()
    environment = env if env is not None else os.environ

    if not resolved_root.exists():
        return failure_result(
            project_root=resolved_root,
            package_root=None,
            diagnostics=[f"Project root does not exist: {resolved_root}"],
        )
    if not resolved_root.is_dir():
        return failure_result(
            project_root=resolved_root,
            package_root=None,
            diagnostics=[f"Project root is not a directory: {resolved_root}"],
        )

    try:
        resolved_package_root = resolve_package_root(resolved_root, profile_path, package_root)
    except PackageManagerDetectionError as exc:
        return failure_result(project_root=resolved_root, package_root=exc.package_root, diagnostics=[exc.message])

    root_diagnostic = validate_package_root(resolved_package_root)
    if root_diagnostic:
        return failure_result(project_root=resolved_root, package_root=resolved_package_root, diagnostics=[root_diagnostic])

    diagnostics: list[str] = []
    package_json = load_package_json(resolved_package_root / "package.json", required=True, diagnostics=diagnostics)
    if package_json is None:
        return failure_result(project_root=resolved_root, package_root=resolved_package_root, diagnostics=diagnostics)

    return PackageManagerDetectionContext(
        projectRoot=resolved_root,
        packageRoot=resolved_package_root,
        environment=environment,
        diagnostics=diagnostics,
        packageJson=package_json,
    )


class PackageManagerDetectionError(Exception):
    def __init__(self, message: str, *, package_root: Path | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.package_root = package_root


def failure_result(
    *,
    project_root: Path,
    package_root: Path | None,
    diagnostics: list[str],
    manager: str = "",
    source: str = "error",
    executor: str = "",
) -> PackageManagerResult:
    return PackageManagerResult(
        ok=False,
        manager=manager,
        source=source,
        packageRoot=str(package_root) if package_root is not None else "",
        projectRoot=str(project_root),
        pathPrepend=[],
        executable=None,
        executor=executor,
        commands=None,
        diagnostics=diagnostics,
    )


def resolve_package_root(root: Path, profile_path: str, package_root: str | None) -> Path:
    if package_root:
        candidate = Path(package_root)
        return (root / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()

    profile_file = Path(profile_path)
    resolved_profile = (root / profile_file).resolve() if not profile_file.is_absolute() else profile_file.resolve()
    if not resolved_profile.is_file():
        raise PackageManagerDetectionError(
            f"Profile file not found: {resolved_profile}. Run the profile/generate workflow first or pass --package-root."
        )

    try:
        profile = tomllib.loads(resolved_profile.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise PackageManagerDetectionError(f"Could not parse profile TOML {resolved_profile}: {exc}") from exc
    except OSError as exc:
        raise PackageManagerDetectionError(f"Could not read profile file {resolved_profile}: {exc}") from exc

    try:
        package_path = profile["project"]["target"]["packagePath"]
    except (KeyError, TypeError) as exc:
        raise PackageManagerDetectionError(
            f"Profile file {resolved_profile} is missing project.target.packagePath."
        ) from exc

    if not isinstance(package_path, str) or not package_path.strip():
        raise PackageManagerDetectionError(
            f"Profile file {resolved_profile} has invalid project.target.packagePath; expected a non-empty string."
        )
    return (root / package_path).resolve()


def validate_package_root(package_root: Path) -> str | None:
    if not package_root.exists():
        return f"Generated package root does not exist: {package_root}. Run generate.py first or pass --package-root."
    if not package_root.is_dir():
        return f"Generated package root is not a directory: {package_root}"
    return None


def choose_manager(
    package_root: Path,
    project_root: Path,
    env: Mapping[str, str],
    diagnostics: list[str],
    package_json: Mapping[str, object],
) -> tuple[str, str]:
    package_manager = package_manager_from_generated_package_json(package_json, package_root / "package.json")
    if package_manager:
        return package_manager, "generated package.json packageManager"

    project_package_json = load_package_json(project_root / "package.json", required=False, diagnostics=diagnostics)
    project_manager = package_manager_from_project_package_json(project_package_json, project_root / "package.json")
    if project_manager:
        return project_manager, "project package.json packageManager"

    return manager_from_lockfiles_or_availability(package_root, project_root, env)


def package_manager_from_generated_package_json(package_json: Mapping[str, object], package_json_path: Path) -> str | None:
    return read_package_manager(package_json, package_json_path)


def package_manager_from_project_package_json(
    package_json: Mapping[str, object] | None,
    package_json_path: Path,
) -> str | None:
    return read_package_manager(package_json, package_json_path)


def manager_from_lockfiles_or_availability(package_root: Path, project_root: Path, env: Mapping[str, str]) -> tuple[str, str]:
    if has_lockfile("pnpm", package_root, project_root):
        return "pnpm", "pnpm lockfile"

    pnpm = resolve_manager_executable("pnpm", package_root, project_root, env, allow_corepack=False)
    if pnpm.executable is not None:
        return "pnpm", "pnpm available"

    for manager in LOCKFILE_ORDER[1:]:
        if has_lockfile(manager, package_root, project_root):
            return manager, f"{manager} lockfile"

    return "npm", "default"


def load_package_json(path: Path, *, required: bool, diagnostics: list[str]) -> Mapping[str, object] | None:
    if not path.is_file():
        if required:
            diagnostics.append(f"Generated package package.json is missing: {path}")
        return None

    try:
        package = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        diagnostics.append(f"Could not parse package.json {path}: {exc}")
        return None
    except OSError as exc:
        diagnostics.append(f"Could not read package.json {path}: {exc}")
        return None

    if not isinstance(package, Mapping):
        diagnostics.append(f"Could not use package.json {path}: expected a JSON object.")
        return None

    return package


def read_package_manager(package: Mapping[str, object] | None, package_json: Path) -> str | None:
    if package is None:
        return None

    value = package.get("packageManager")
    if not isinstance(value, str) or not value.strip():
        return None

    manager = value.split("@", 1)[0].strip()
    if manager not in MANAGER_LOCKFILES:
        supported = ", ".join(sorted(MANAGER_LOCKFILES))
        raise PackageManagerDetectionError(
            f"Unsupported packageManager {value!r} in {package_json}. Supported managers: {supported}."
        )
    return manager


def has_lockfile(manager: str, package_root: Path, project_root: Path) -> bool:
    return any((package_root / lockfile).is_file() or (project_root / lockfile).is_file() for lockfile in MANAGER_LOCKFILES[manager])


@dataclass(frozen=True, slots=True)
class ExecutableResolution:
    executable: Path | None
    executor: str
    path_prepend: list[str]


def resolve_manager_executable(
    manager: str,
    package_root: Path,
    project_root: Path,
    env: Mapping[str, str],
    *,
    allow_corepack: bool = True,
) -> ExecutableResolution:
    path_entries = path_candidates(env)
    search_entries = executable_search_paths(package_root, project_root, env, path_entries)

    direct = resolve_direct_executable(manager, search_entries)
    if direct is not None:
        return ExecutableResolution(
            executable=direct,
            executor=manager,
            path_prepend=path_prepend_for(direct.parent, path_entries),
        )

    if allow_corepack:
        corepack = resolve_corepack_executable(manager, search_entries)
        if corepack is not None:
            return ExecutableResolution(
                executable=corepack,
                executor=f"corepack {manager}",
                path_prepend=path_prepend_for(corepack.parent, path_entries),
            )

    return ExecutableResolution(executable=None, executor=manager, path_prepend=[])


def executable_search_paths(package_root: Path, project_root: Path, env: Mapping[str, str], path_entries: list[Path]) -> list[Path]:
    nvm_entries = nvm_bin_candidates(package_root, project_root, env)
    return dedupe_paths([*path_entries, *nvm_entries])


def resolve_direct_executable(manager: str, search_entries: list[Path]) -> Path | None:
    return find_executable(manager, search_entries)


def resolve_corepack_executable(manager: str, search_entries: list[Path]) -> Path | None:
    if manager not in {"pnpm", "yarn"}:
        return None
    return find_executable("corepack", search_entries)


def path_candidates(env: Mapping[str, str]) -> list[Path]:
    return [Path(entry) for entry in env.get("PATH", "").split(os.pathsep) if entry]


def nvm_bin_candidates(package_root: Path, project_root: Path, env: Mapping[str, str]) -> list[Path]:
    candidates: list[Path] = []
    nvm_bin = env.get("NVM_BIN")
    if nvm_bin:
        candidates.append(Path(nvm_bin))

    nvm_dir = Path(env.get("NVM_DIR") or Path(env.get("HOME", "~")).expanduser() / ".nvm")
    versions_root = nvm_dir / "versions/node"
    for version in node_version_candidates(package_root, project_root, nvm_dir):
        candidates.append(versions_root / version / "bin")

    if versions_root.is_dir():
        candidates.extend(path / "bin" for path in sorted(versions_root.iterdir(), reverse=True) if path.is_dir())

    return dedupe_paths(candidates)


def node_version_candidates(package_root: Path, project_root: Path, nvm_dir: Path) -> list[str]:
    versions: list[str] = []
    for root in (package_root, project_root):
        for name in (".nvmrc", ".node-version"):
            value = read_first_line(root / name)
            if value:
                versions.extend(normalize_node_versions(value))

    versions.extend(resolve_nvm_aliases(nvm_dir, "default"))
    return dedupe_strings(versions)


def read_first_line(path: Path) -> str | None:
    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped
    return None


def normalize_node_versions(version: str) -> list[str]:
    stripped = version.strip()
    if not stripped:
        return []
    if stripped.startswith("v"):
        return [stripped, stripped[1:]]
    return [stripped, f"v{stripped}"]


def resolve_nvm_aliases(nvm_dir: Path, alias: str, seen: set[str] | None = None) -> list[str]:
    seen = seen or set()
    if alias in seen:
        return []
    seen.add(alias)

    alias_path = nvm_dir / "alias" / alias
    target = read_first_line(alias_path)
    if not target:
        return []
    if target.startswith("v") or target[:1].isdigit():
        return normalize_node_versions(target)
    return resolve_nvm_aliases(nvm_dir, target, seen)


def find_executable(name: str, directories: list[Path]) -> Path | None:
    for directory in directories:
        candidate = directory / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate.resolve()
    return None


def path_prepend_for(directory: Path, inherited_path: list[Path]) -> list[str]:
    resolved_directory = directory.resolve()
    if any(path.resolve() == resolved_directory for path in inherited_path if path.exists()):
        return []
    return [str(resolved_directory)]


def build_commands(manager: str, executable: ExecutableResolution) -> PackageManagerCommandSet:
    command_prefix = shell_command_prefix(executable)
    return PackageManagerCommandSet(
        install=build_install_command(command_prefix, executable.path_prepend),
        codegen=build_script_command(manager, command_prefix, executable.path_prepend, "codegen"),
        check=build_script_command(manager, command_prefix, executable.path_prepend, "check"),
    )


def build_install_command(command_prefix: list[str], path_prepend: list[str]) -> str:
    return shell_join([*command_prefix, "install"], path_prepend)


def build_script_command(manager: str, command_prefix: list[str], path_prepend: list[str], script: str) -> str:
    runner_prefix = command_prefix_for_runner(command_prefix, SCRIPT_RUNNERS[manager])
    return shell_join([*runner_prefix, script], path_prepend)


def shell_command_prefix(executable: ExecutableResolution) -> list[str]:
    if executable.executor.startswith("corepack "):
        return ["corepack", executable.executor.split(" ", 1)[1]]
    return [executable.executor]


def command_prefix_for_runner(command_prefix: list[str], runner: tuple[str, str]) -> list[str]:
    if command_prefix[0] == "corepack":
        return [*command_prefix, runner[1]]
    return [runner[0], runner[1]]


def shell_join(command: list[str], path_prepend: list[str] | None = None) -> str:
    rendered = shlex.join(command)
    if not path_prepend:
        return rendered
    path_prefix = shlex.quote(os.pathsep.join(path_prepend))
    return f'env PATH={path_prefix}:"$PATH" {rendered}'


def dedupe_paths(paths: list[Path]) -> list[Path]:
    result: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path)
        if key not in seen:
            seen.add(key)
            result.append(path)
    return result


def dedupe_strings(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def package_manager_result(
    context: PackageManagerDetectionContext,
    manager: str,
    source: str,
    executable: ExecutableResolution,
    *,
    commands: PackageManagerCommandSet | None,
    ok: bool,
) -> PackageManagerResult:
    return PackageManagerResult(
        ok=ok,
        manager=manager,
        source=source,
        packageRoot=str(context.packageRoot),
        projectRoot=str(context.projectRoot),
        pathPrepend=executable.path_prepend,
        executable=str(executable.executable) if executable.executable is not None else None,
        executor=executable.executor,
        commands=commands,
        diagnostics=context.diagnostics,
    )
