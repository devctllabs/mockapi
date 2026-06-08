from __future__ import annotations

import json
import re
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .diagnostics import Diagnostic
from .filesystem import FileSystem
from .models import Profile, profile_from_mapping

SOURCE_EXTENSIONS = {".ts", ".tsx", ".mts", ".cts"}
TEST_FILE_PATTERN = re.compile(r"\.(?:test|spec)\.[cm]?[tj]sx?$")
TODO_PATTERN = re.compile(r"TODO mockapi|throw\s+new\s+Error\(\s*['\"]TODO mockapi", re.IGNORECASE)
ALLOCATOR_PATTERN = re.compile(r"\bnewIdAllocator\s*\(")
HARDCODED_BASE_PATH_PATTERN = re.compile(r"\bbasePath\s*:\s*['\"]/")
AS_ANY_PATTERN = re.compile(r"\bas\s+any\b")
SLUG_ID_SOURCE_PATTERN = re.compile(r"\b(?:slugify|uniqueSlug)\b", re.IGNORECASE)
DIRECT_SLICE_ACCESS_PATTERN = re.compile(r"\.(?:getSlice|setSlice)\(\s*(['\"])(?P<slice>[^'\"]+)\1")
DIRECT_ENTITY_ACCESS_PATTERN = re.compile(
    r"\.(?:findEntities|findEntity|createEntity|updateEntity|deleteEntity)\(\s*(['\"])(?P<slice>[^'\"]+)\1"
)
PICK_MOCK_STATE_PATTERN = re.compile(r"Pick<\s*MockState\s*,\s*(?P<keys>[^>]+)>", re.DOTALL)
STRING_LITERAL_PATTERN = re.compile(r"['\"](?P<value>[^'\"]+)['\"]")
EMPTY_LITERAL_CONTENT_PATTERN = r"(?:\s|//[^\n\r]*(?:\r?\n|$)|/\*.*?\*/)*"
OPENAPI_REF_PATTERN = re.compile(r"\$ref\s*:\s*['\"]?(?P<ref>[^'\"\s]+)")
OVERSIZED_DOMAIN_LINE_LIMIT = 250
INFRASTRUCTURE_STATE_SLICES = {"idCounters"}


@dataclass(frozen=True, slots=True)
class QualityCheckResult:
    errors: list[Diagnostic] = field(default_factory=list)
    warnings: list[Diagnostic] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


@dataclass(frozen=True, slots=True)
class ScannedFile:
    path: Path
    relative: str
    text: str


@dataclass(frozen=True, slots=True)
class QualityScanContext:
    fs: FileSystem
    package_root: Path
    profile: Profile | None
    source_files: list[ScannedFile]
    test_files: list[ScannedFile]
    app_text: str | None
    admin_openapi_text: str | None
    seed_product_state: bool
    product_state_slices: set[str] | None
    feature_seed_slices: dict[str, set[str]]
    feature_has_repository: set[str]


def _diagnostic(diagnostic_id: str, message: str, *, path: Path | str | None = None) -> Diagnostic:
    diagnostic: Diagnostic = {"id": diagnostic_id, "message": message}
    if path is not None:
        diagnostic["path"] = str(path)
    return diagnostic


def _relative_path(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _read_optional(fs: FileSystem, path: Path | None) -> str | None:
    if path is None or not fs.is_file(path):
        return None
    return fs.read_text(path)


def _load_profile(fs: FileSystem, profile_path: Path | None) -> Profile | None:
    if profile_path is None or not fs.is_file(profile_path):
        return None

    text = fs.read_text(profile_path)
    try:
        raw_profile = json.loads(text) if profile_path.suffix == ".json" else tomllib.loads(text)
        return profile_from_mapping(raw_profile)
    except Exception:
        return None


def _infer_profile_path(fs: FileSystem, package_root: Path) -> Path | None:
    candidate = package_root.parent / ".mockapi/profile.toml"
    return candidate if fs.is_file(candidate) else None


def _is_source(path: Path) -> bool:
    return path.suffix in SOURCE_EXTENSIONS


def _is_generated_source(package_root: Path, path: Path) -> bool:
    return _relative_path(package_root, path).startswith("src/generated/")


def _source_files(fs: FileSystem, package_root: Path) -> list[ScannedFile]:
    files: list[ScannedFile] = []
    for path in fs.iter_files(package_root):
        relative = _relative_path(package_root, path)
        if "node_modules/" in relative:
            continue
        if _is_source(path):
            files.append(ScannedFile(path=path, relative=relative, text=fs.read_text(path)))
    return files


def _declares_id_counters(fs: FileSystem, package_root: Path) -> bool:
    generated_paths = (
        package_root / "src/generated/mock-admin/contract/index.ts",
        package_root / "src/generated/mock-admin/state/seed.ts",
        package_root / "openapi/admin.yaml",
    )
    return any("idCounters" in (text or "") for text in (_read_optional(fs, path) for path in generated_paths))


def _test_files(fs: FileSystem, package_root: Path) -> list[ScannedFile]:
    tests: list[ScannedFile] = []
    for path in fs.iter_files(package_root):
        relative = _relative_path(package_root, path)
        if "node_modules/" in relative:
            continue
        if TEST_FILE_PATTERN.search(path.name):
            tests.append(ScannedFile(path=path, relative=relative, text=fs.read_text(path)))
    return tests


def _feature_scan_index(source_files: list[ScannedFile]) -> tuple[dict[str, set[str]], set[str]]:
    feature_seed_slices: dict[str, set[str]] = {}
    feature_has_repository: set[str] = set()

    for scanned_file in source_files:
        feature = _feature_name(scanned_file.relative)
        if feature is None:
            continue
        if _is_feature_seed(scanned_file.relative):
            feature_seed_slices[feature] = _feature_seed_slices(scanned_file.text)
        elif _is_feature_repository(scanned_file.relative):
            feature_has_repository.add(feature)

    return feature_seed_slices, feature_has_repository


def _feature_name(relative: str) -> str | None:
    parts = relative.split("/")
    if len(parts) < 3 or parts[0] != "src" or parts[1] != "features":
        return None
    return parts[2]


def _feature_seed_slices(text: str) -> set[str]:
    match = PICK_MOCK_STATE_PATTERN.search(text)
    if not match:
        return set()
    return {literal.group("value") for literal in STRING_LITERAL_PATTERN.finditer(match.group("keys"))}


def _empty_seed_slices(text: str, slices: set[str]) -> set[str]:
    empty: set[str] = set()
    for slice_name in slices:
        key = rf"(?<![\w$])(?:{re.escape(slice_name)}|['\"]{re.escape(slice_name)}['\"])\s*:"
        empty_array = rf"{key}\s*\[{EMPTY_LITERAL_CONTENT_PATTERN}\]"
        empty_object = rf"{key}\s*\{{{EMPTY_LITERAL_CONTENT_PATTERN}\}}(?:\s+as\s+[^,\n\r}}]+)?"
        if re.search(empty_array, text, re.DOTALL) or re.search(empty_object, text, re.DOTALL):
            empty.add(slice_name)
    return empty


def _external_openapi_refs(text: str) -> list[str]:
    return [
        match.group("ref")
        for match in OPENAPI_REF_PATTERN.finditer(text)
        if not match.group("ref").startswith("#/")
    ]


def _is_feature_repository(relative: str) -> bool:
    return relative.startswith("src/features/") and relative.endswith("/repository.ts")


def _is_feature_seed(relative: str) -> bool:
    return relative.startswith("src/features/") and relative.endswith("/seed.ts")


def _is_test_file(relative: str) -> bool:
    return TEST_FILE_PATTERN.search(Path(relative).name) is not None


def _is_feature_unit_source(relative: str) -> bool:
    if not relative.startswith("src/features/"):
        return False
    if _is_test_file(relative) or _is_feature_seed(relative) or "/controllers/" in relative:
        return False
    if relative.endswith(".d.ts"):
        return False
    if Path(relative).name in {"index.ts", "types.ts"}:
        return False
    return True


def _adjacent_unit_test_candidates(relative: str) -> list[str]:
    source_path = Path(relative)
    extensions = [source_path.suffix]
    extensions.extend(
        extension
        for extension in (".ts", ".tsx", ".mts", ".cts")
        if extension != source_path.suffix
    )
    return [
        (source_path.parent / f"{source_path.stem}{kind}{extension}").as_posix()
        for kind in (".test", ".spec")
        for extension in extensions
    ]


def _feature_has_completed_behavior(source_files: list[ScannedFile], feature: str) -> bool:
    service_relative = f"src/features/{feature}/service.ts"
    if any(scanned_file.relative == service_relative for scanned_file in source_files):
        return True

    controller_root = f"src/features/{feature}/controllers/"
    for scanned_file in source_files:
        if scanned_file.relative.startswith(controller_root) and not TODO_PATTERN.search(scanned_file.text):
            return True

    return False


def _build_quality_scan_context(
    fs: FileSystem,
    package_root: Path,
    profile_path: Path | None,
) -> QualityScanContext:
    source_files = _source_files(fs, package_root)
    test_files = _test_files(fs, package_root)
    profile = _load_profile(fs, profile_path or _infer_profile_path(fs, package_root))
    seed_product_state = True if profile is None else profile.state.seed
    product_state_slices = (
        {state_slice.name for state_slice in profile.state.slices if state_slice.name not in INFRASTRUCTURE_STATE_SLICES}
        if profile is not None
        else None
    )
    feature_seed_slices, feature_has_repository = _feature_scan_index(source_files)

    return QualityScanContext(
        fs=fs,
        package_root=package_root,
        profile=profile,
        source_files=source_files,
        test_files=test_files,
        app_text=_read_optional(fs, package_root / "src/app.ts"),
        admin_openapi_text=_read_optional(fs, package_root / "openapi/admin.yaml"),
        seed_product_state=seed_product_state,
        product_state_slices=product_state_slices,
        feature_seed_slices=feature_seed_slices,
        feature_has_repository=feature_has_repository,
    )


def _format_diagnostic(diagnostic: Diagnostic) -> str:
    path = diagnostic.get("path")
    location = f" {path}" if path else ""
    return f"- {diagnostic['id']}{location}: {diagnostic['message']}"


def _check_app_base_path(context: QualityScanContext, errors: list[Diagnostic]) -> None:
    if context.app_text and "basePath?:" in context.app_text and HARDCODED_BASE_PATH_PATTERN.search(context.app_text):
        errors.append(
            _diagnostic(
                "quality.basePath.ignoredOption",
                "src/app.ts accepts basePath but mounts at a hardcoded path.",
                path="src/app.ts",
            )
        )


def _check_admin_openapi_external_refs(context: QualityScanContext, errors: list[Diagnostic]) -> None:
    if not context.admin_openapi_text:
        return

    external_refs = _external_openapi_refs(context.admin_openapi_text)
    if external_refs:
        errors.append(
            _diagnostic(
                "quality.adminOpenapi.externalRefs",
                (
                    "openapi/admin.yaml is the final bundled admin contract and must not contain "
                    f"external $ref values ({', '.join(external_refs[:3])})."
                ),
                path="openapi/admin.yaml",
            )
        )


def _check_todo_stubs(context: QualityScanContext, errors: list[Diagnostic]) -> None:
    for scanned_file in context.source_files:
        if scanned_file.relative.startswith("src/features/") and TODO_PATTERN.search(scanned_file.text):
            errors.append(
                _diagnostic(
                    "quality.todo.remaining",
                    "Feature controller or service still contains generated mockapi TODO behavior.",
                    path=scanned_file.relative,
                )
            )


def _has_todo_stubs(context: QualityScanContext) -> bool:
    return any(
        scanned_file.relative.startswith("src/features/") and TODO_PATTERN.search(scanned_file.text)
        for scanned_file in context.source_files
    )


def _check_feature_repository_requirements(context: QualityScanContext, errors: list[Diagnostic]) -> None:
    for feature, slices in sorted(context.feature_seed_slices.items()):
        product_slices = sorted(slices - INFRASTRUCTURE_STATE_SLICES)
        if not product_slices:
            continue
        if feature in context.feature_has_repository:
            continue
        if not _feature_has_completed_behavior(context.source_files, feature):
            continue
        errors.append(
            _diagnostic(
                "quality.repository.missingFeatureRepository",
                (
                    "Stateful feature owns product state slices "
                    f"{', '.join(product_slices)} but has no feature repository."
                ),
                path=f"src/features/{feature}/repository.ts",
            )
        )


def _check_seed_empty_product(context: QualityScanContext, errors: list[Diagnostic]) -> None:
    if not context.seed_product_state:
        return

    for scanned_file in context.source_files:
        if not _is_feature_seed(scanned_file.relative):
            continue

        slices = _feature_seed_slices(scanned_file.text) - INFRASTRUCTURE_STATE_SLICES
        if context.product_state_slices is not None:
            slices &= context.product_state_slices
        empty_slices = sorted(_empty_seed_slices(scanned_file.text, slices))
        if empty_slices:
            errors.append(
                _diagnostic(
                    "quality.seed.emptyProductSeed",
                    (
                        "Feature seed leaves product state slices empty "
                        f"({', '.join(empty_slices)}); populate deterministic initial data "
                        "or set state.seed = false in .mockapi/profile.toml."
                    ),
                    path=scanned_file.relative,
                )
            )


def _has_empty_product_seed_stubs(context: QualityScanContext) -> bool:
    if not context.seed_product_state:
        return False

    for scanned_file in context.source_files:
        if not _is_feature_seed(scanned_file.relative):
            continue

        slices = _feature_seed_slices(scanned_file.text) - INFRASTRUCTURE_STATE_SLICES
        if context.product_state_slices is not None:
            slices &= context.product_state_slices
        if _empty_seed_slices(scanned_file.text, slices):
            return True

    return False


def _check_incomplete_implementation_phase(context: QualityScanContext, errors: list[Diagnostic]) -> None:
    if not (_has_todo_stubs(context) or _has_empty_product_seed_stubs(context)):
        return

    errors.append(
        _diagnostic(
            "quality.phase.incompleteImplementation",
            (
                "Generated mock server still has scaffold TODO behavior or empty product seed stubs. "
                "Implement feature behavior, dependency wiring, seed data, and smoke tests before using "
                "this final quality gate for handoff."
            ),
        )
    )


def _check_id_counters_usage(context: QualityScanContext, errors: list[Diagnostic]) -> None:
    allocator_files = [
        scanned_file
        for scanned_file in context.source_files
        if not _is_generated_source(context.package_root, scanned_file.path) and ALLOCATOR_PATTERN.search(scanned_file.text)
    ]
    if allocator_files and not _declares_id_counters(context.fs, context.package_root):
        errors.append(
            _diagnostic(
                "quality.idCounters.missingState",
                "newIdAllocator is used but idCounters is not declared in profile or generated admin state.",
                path=allocator_files[0].relative,
            )
        )


def _check_slug_helper_code(context: QualityScanContext, warnings: list[Diagnostic]) -> None:
    for scanned_file in context.source_files:
        if not (scanned_file.relative.startswith("src/features/") or scanned_file.relative.startswith("src/lib/")):
            continue
        if SLUG_ID_SOURCE_PATTERN.search(scanned_file.text):
            warnings.append(
                _diagnostic(
                    "quality.slugIdHelper.present",
                    "Slug helper code is present; ensure slug-style IDs are explicitly confirmed in behavior.md.",
                    path=scanned_file.relative,
                )
            )
            break


def _check_domain_module_size(context: QualityScanContext, warnings: list[Diagnostic]) -> None:
    domain_path = context.package_root / "src/lib/domain.ts"
    domain_text = _read_optional(context.fs, domain_path)
    if domain_text and len(domain_text.splitlines()) > OVERSIZED_DOMAIN_LINE_LIMIT:
        warnings.append(
            _diagnostic(
                "quality.domainModule.oversized",
                f"src/lib/domain.ts exceeds {OVERSIZED_DOMAIN_LINE_LIMIT} lines; prefer feature-local domain helpers.",
                path=_relative_path(context.package_root, domain_path),
            )
        )


def _check_direct_slice_access(context: QualityScanContext, errors: list[Diagnostic]) -> None:
    for scanned_file in context.source_files:
        if (
            not scanned_file.relative.startswith("src/features/")
            or _is_feature_repository(scanned_file.relative)
            or _is_feature_seed(scanned_file.relative)
        ):
            continue

        slices = sorted(
            {
                match.group("slice")
                for match in DIRECT_SLICE_ACCESS_PATTERN.finditer(scanned_file.text)
                if match.group("slice") not in INFRASTRUCTURE_STATE_SLICES
            }
            | {
                match.group("slice")
                for match in DIRECT_ENTITY_ACCESS_PATTERN.finditer(scanned_file.text)
                if match.group("slice") not in INFRASTRUCTURE_STATE_SLICES
            }
        )
        if slices:
            errors.append(
                _diagnostic(
                    "quality.stateAccess.directSliceAccess",
                    (
                        "Feature behavior accesses product state slices directly "
                        f"({', '.join(slices)}); move reads and writes behind feature repositories."
                    ),
                    path=scanned_file.relative,
                )
            )


def _check_snapshot_set_all(context: QualityScanContext, warnings: list[Diagnostic]) -> None:
    for scanned_file in context.source_files:
        if scanned_file.relative.startswith("src/features/") and ".snapshot(" in scanned_file.text and ".setAll(" in scanned_file.text:
            warnings.append(
                _diagnostic(
                    "quality.stateAccess.snapshotSetAll",
                    "Feature code mixes snapshot() and setAll(); prefer feature repositories or transactions.",
                    path=scanned_file.relative,
                )
            )


def _check_unsafe_casts(context: QualityScanContext, warnings: list[Diagnostic]) -> None:
    for scanned_file in context.source_files:
        if (scanned_file.relative.startswith("src/features/") or scanned_file.relative == "src/controllers.ts") and AS_ANY_PATTERN.search(
            scanned_file.text
        ):
            warnings.append(
                _diagnostic(
                    "quality.unsafeCast.asAny",
                    "Feature/controller code contains as any; keep casts narrow and documented.",
                    path=scanned_file.relative,
                )
            )


def _check_smoke_tests(context: QualityScanContext, warnings: list[Diagnostic]) -> None:
    if not context.test_files:
        warnings.append(
            _diagnostic(
                "quality.tests.missingSmoke",
                "Generated mock server has no test/spec files; add HTTP smoke coverage in src/app.test.ts before handoff.",
                path="src/app.test.ts",
            )
        )
    elif not any("basePath" in scanned_file.text for scanned_file in context.test_files):
        warnings.append(
            _diagnostic(
                "quality.tests.missingBasePathSmoke",
                "Smoke tests do not cover custom basePath mounting; add the HTTP basePath smoke in src/app.test.ts.",
                path="src/app.test.ts",
            )
        )


def _check_feature_unit_tests(context: QualityScanContext, warnings: list[Diagnostic]) -> None:
    test_relatives = {scanned_file.relative for scanned_file in context.test_files}

    for scanned_file in context.source_files:
        if not _is_feature_unit_source(scanned_file.relative):
            continue
        if TODO_PATTERN.search(scanned_file.text):
            continue

        candidates = _adjacent_unit_test_candidates(scanned_file.relative)
        if any(candidate in test_relatives for candidate in candidates):
            continue

        warnings.append(
            _diagnostic(
                "quality.tests.missingFeatureUnit",
                (
                    "Completed LLM-owned feature source has no adjacent unit test; "
                    f"add {candidates[0]} or report the uncovered behavior as residual risk."
                ),
                path=candidates[0],
            )
        )


def check_generated_quality(
    fs: FileSystem,
    package_root: Path,
    profile_path: Path | None = None,
) -> QualityCheckResult:
    context = _build_quality_scan_context(fs, package_root, profile_path)
    errors: list[Diagnostic] = []
    warnings: list[Diagnostic] = []

    _check_incomplete_implementation_phase(context, errors)
    _check_app_base_path(context, errors)
    _check_admin_openapi_external_refs(context, errors)
    _check_todo_stubs(context, errors)
    _check_feature_repository_requirements(context, errors)
    _check_seed_empty_product(context, errors)
    _check_id_counters_usage(context, errors)
    _check_slug_helper_code(context, warnings)
    _check_domain_module_size(context, warnings)
    _check_direct_slice_access(context, errors)
    _check_snapshot_set_all(context, warnings)
    _check_unsafe_casts(context, warnings)
    _check_smoke_tests(context, warnings)
    _check_feature_unit_tests(context, warnings)

    return QualityCheckResult(errors=errors, warnings=warnings)


def format_quality_result(result: QualityCheckResult) -> str:
    error_count = len(result.errors)
    warning_count = len(result.warnings)
    lines = [
        "Result: "
        f"ok: {str(result.ok).lower()}, "
        f"{'no errors' if error_count == 0 else f'errors: {error_count}'}, "
        f"{'no warnings' if warning_count == 0 else f'warnings: {warning_count}'}."
    ]
    if result.errors:
        lines.append("Errors:")
        lines.extend(_format_diagnostic(diagnostic) for diagnostic in result.errors)
    if result.warnings:
        lines.append("Warnings:")
        lines.extend(_format_diagnostic(diagnostic) for diagnostic in result.warnings)
    return "\n".join(lines)


def quality_result_to_payload(result: QualityCheckResult) -> dict[str, object]:
    return asdict(result) | {"ok": result.ok}
