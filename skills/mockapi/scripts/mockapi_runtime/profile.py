from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping

from .behavior_policy import (
    has_explicit_slug_id_opt_in,
    mentions_counter_id_policy,
    mentions_slug_id_policy,
)
from .diagnostics import (
    Diagnostic,
    ProfileSummary,
    ValidationFailureResult,
    ValidationResult,
    ValidationSuccessResult,
)
from .filesystem import FileSystem
from .key_path import document_key_path_exists
from .models import Profile, profile_from_mapping
from .paths import is_http_url
from .schema_ref import (
    is_admin_builtin_record_type,
    is_schema_component_record_type,
    local_api_path,
    parse_schema_ref,
    schema_key_path,
    schema_ref_document_path,
)

HTTP_METHODS = {"DELETE", "GET", "PATCH", "POST", "PUT"}
OPERATION_ANCHOR_PATTERN = re.compile(r"^operation:[A-Za-z0-9_.:-]+$")
SCHEMA_REF_PATTERN = re.compile(r"^[^#:\s]+(?::[^#\s]+)?#/components/schemas/[^#\s]+$")
TS_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*$")


@dataclass(frozen=True, slots=True)
class BehaviorAnchors:
    sections: dict[str, str]
    duplicates: set[str]


@dataclass(slots=True)
class ValidationContext:
    errors: list[Diagnostic] = field(default_factory=list)
    warnings: list[Diagnostic] = field(default_factory=list)

    def error(self, diagnostic_id: str, message: str, *, path: str | None = None) -> None:
        diagnostic: Diagnostic = {"id": diagnostic_id, "message": message}
        if path is not None:
            diagnostic["path"] = path
        self.errors.append(diagnostic)

    def warn(self, diagnostic_id: str, message: str, *, path: str | None = None) -> None:
        diagnostic: Diagnostic = {"id": diagnostic_id, "message": message}
        if path is not None:
            diagnostic["path"] = path
        self.warnings.append(diagnostic)


class ProfileValidationError(Exception):
    def __init__(self, diagnostics: list[Diagnostic]) -> None:
        super().__init__("Profile validation failed.")
        self.diagnostics = diagnostics


def is_record(value: Any) -> bool:
    return isinstance(value, Mapping)


def _missing_required_id(path_name: str, key: str) -> str:
    if path_name == "profile":
        return f"profile.missing{key[:1].upper()}{key[1:]}"
    return f"profile.{path_name}.missing{key[:1].upper()}{key[1:]}"


def _required_at(
    ctx: ValidationContext,
    value: Mapping[str, Any],
    key: str,
    path_name: str,
    *,
    default: Any,
    expected: str,
    is_valid: Callable[[Any], bool],
) -> Any:
    raw = value.get(key)
    if not is_valid(raw):
        ctx.error(
            _missing_required_id(path_name, key),
            f"{path_name}.{key} must be {expected}.",
            path=f"{path_name}.{key}",
        )
        return default
    return raw


def string_at(ctx: ValidationContext, value: Mapping[str, Any], key: str, path_name: str) -> str:
    return _required_at(
        ctx,
        value,
        key,
        path_name,
        default="",
        expected="a non-empty string",
        is_valid=lambda raw: isinstance(raw, str) and raw.strip() != "",
    )


def array_at(ctx: ValidationContext, value: Mapping[str, Any], key: str, path_name: str) -> list[Any]:
    return _required_at(
        ctx,
        value,
        key,
        path_name,
        default=[],
        expected="an array",
        is_valid=lambda raw: isinstance(raw, list),
    )


def require_object(ctx: ValidationContext, value: Mapping[str, Any], key: str, path_name: str) -> Mapping[str, Any]:
    return _required_at(
        ctx,
        value,
        key,
        path_name,
        default={},
        expected="an object",
        is_valid=is_record,
    )


def parse_profile_text(text: str, profile_path: str) -> Any:
    if profile_path.endswith(".json"):
        return json.loads(text)
    if profile_path.endswith(".toml"):
        return tomllib.loads(text)
    raise ValueError("Profile must be .toml or .json.")


def operation_anchor(operation_id: str) -> str:
    return f"operation:{operation_id}"


def _validate_required_string_fields(
    ctx: ValidationContext,
    value: Mapping[str, Any],
    path_name: str,
    *keys: str,
) -> None:
    for key in keys:
        string_at(ctx, value, key, path_name)


def _validate_record_array(
    ctx: ValidationContext,
    items: list[Any],
    *,
    item_path_prefix: str,
    invalid_id: str,
    invalid_message: Callable[[str], str],
    validate_item: Callable[[Mapping[str, Any], str], None],
) -> None:
    for index, item in enumerate(items):
        item_path = f"{item_path_prefix}[{index}]"
        if not is_record(item):
            ctx.error(invalid_id, invalid_message(item_path), path=item_path)
            continue
        validate_item(item, item_path)


def _validate_generator_section(ctx: ValidationContext, value: Mapping[str, Any]) -> None:
    generator = require_object(ctx, value, "generator", "profile")
    _validate_required_string_fields(ctx, generator, "generator", "name", "version")


def _validate_project_section(ctx: ValidationContext, value: Mapping[str, Any]) -> None:
    project = require_object(ctx, value, "project", "profile")
    string_at(ctx, project, "root", "project")
    target = require_object(ctx, project, "target", "project")
    _validate_required_string_fields(ctx, target, "project.target", "packagePath", "packageName", "serverName")


def _validate_apis_section(ctx: ValidationContext, value: Mapping[str, Any]) -> None:
    apis = array_at(ctx, value, "apis", "profile")
    _validate_record_array(
        ctx,
        apis,
        item_path_prefix="apis",
        invalid_id="profile.api.invalid",
        invalid_message=lambda item_path: f"{item_path} must be an object.",
        validate_item=lambda api, item_path: _validate_required_string_fields(ctx, api, item_path, "name", "openapi"),
    )


def _validate_features_section(ctx: ValidationContext, value: Mapping[str, Any]) -> None:
    features = array_at(ctx, value, "features", "profile")
    _validate_record_array(
        ctx,
        features,
        item_path_prefix="features",
        invalid_id="profile.feature.invalid",
        invalid_message=lambda item_path: f"{item_path} must be an object.",
        validate_item=lambda feature, item_path: _validate_required_string_fields(ctx, feature, item_path, "name"),
    )


def _validate_state_section(ctx: ValidationContext, value: Mapping[str, Any]) -> None:
    state = require_object(ctx, value, "state", "profile")
    if state.get("schemaVersion") != 1:
        ctx.error("profile.state.schemaVersion.invalid", "state.schemaVersion must be 1.", path="state.schemaVersion")
    if "seed" in state and not isinstance(state["seed"], bool):
        ctx.error("profile.state.seed.invalid", "state.seed must be a boolean.", path="state.seed")
    slices = array_at(ctx, state, "slices", "state")
    _validate_record_array(
        ctx,
        slices,
        item_path_prefix="state.slices",
        invalid_id="profile.state.slice.invalid",
        invalid_message=lambda item_path: f"{item_path} must be an object.",
        validate_item=lambda state_slice, item_path: _validate_state_slice(ctx, state_slice, item_path),
    )


def _validate_state_slice(ctx: ValidationContext, state_slice: Mapping[str, Any], item_path: str) -> None:
    name = string_at(ctx, state_slice, "name", item_path)
    if name and not TS_IDENTIFIER_PATTERN.match(name):
        ctx.error(
            "profile.state.slice.invalidName",
            f"{item_path}.name must be a TypeScript identifier-safe state key.",
            path=f"{item_path}.name",
        )


def _validate_schema_ref_target(
    ctx: ValidationContext,
    *,
    fs: FileSystem,
    path: str,
    schema_name: str,
    source_path: Path,
    source_is_file_qualified: bool,
    state_slice_name: str,
    subject: str,
) -> None:
    display_ref = f"{source_path.as_posix()}#/components/schemas/{schema_name}"
    if not fs.is_file(source_path):
        if source_is_file_qualified:
            ctx.error(
                "profile.state.slice.schemaRefFileMissing",
                f"{state_slice_name} {subject} source file does not exist: {source_path.as_posix()}.",
                path=path,
            )
        return

    if document_key_path_exists(fs, source_path, schema_key_path(schema_name)):
        return

    ctx.error(
        "profile.state.slice.unresolvedSchemaRef",
        (
            f"{state_slice_name} {subject} does not resolve: {display_ref}. "
            "If the schema is defined in a domain file, use a file-qualified schemaRef "
            "or export the schema from the root OpenAPI file."
        ),
        path=path,
    )


def _validate_schema_ref(
    ctx: ValidationContext,
    *,
    state_slice: Any,
    slice_path: str,
    apis_by_name: dict[str, Any],
    fs: FileSystem | None,
    root: Path | None,
) -> None:
    schema_ref = state_slice.schemaRef
    if not SCHEMA_REF_PATTERN.match(schema_ref):
        ctx.error(
            "profile.state.slice.invalidSchemaRef",
            f"{state_slice.name} schemaRef must look like <api-name>#/components/schemas/<SchemaName> or <api-name>:<relative-file>#/components/schemas/<SchemaName>.",
            path=f"{slice_path}.schemaRef",
        )
        return

    parsed_schema_ref = parse_schema_ref(schema_ref)
    api = apis_by_name.get(parsed_schema_ref.api_name)
    if api is None:
        ctx.error(
            "profile.state.slice.unknownSchemaRefApi",
            f"{state_slice.name} schemaRef references unknown api {parsed_schema_ref.api_name}.",
            path=f"{slice_path}.schemaRef",
        )
        return

    if is_http_url(api.openapi):
        ctx.error(
            "profile.state.slice.remoteSchemaRefUnsupported",
            f"{state_slice.name} schemaRef references HTTP api {parsed_schema_ref.api_name}; admin state schema copying requires a local OpenAPI file.",
            path=f"{slice_path}.schemaRef",
        )
        return

    if fs is None or root is None:
        return

    source_path = schema_ref_document_path(parsed_schema_ref, api.openapi, root)
    _validate_schema_ref_target(
        ctx,
        fs=fs,
        path=f"{slice_path}.schemaRef",
        schema_name=parsed_schema_ref.schema_name,
        source_path=source_path,
        source_is_file_qualified=parsed_schema_ref.file_qualified,
        state_slice_name=state_slice.name,
        subject="schemaRef",
    )


def _validate_single_api_record_type(
    ctx: ValidationContext,
    *,
    state_slice: Any,
    slice_path: str,
    profile: Profile,
    fs: FileSystem | None,
    root: Path | None,
) -> None:
    if len(profile.apis) != 1:
        return

    record_type = state_slice.recordType
    if not is_schema_component_record_type(record_type) or is_admin_builtin_record_type(record_type):
        return

    api = profile.apis[0]
    if is_http_url(api.openapi):
        ctx.error(
            "profile.state.slice.remoteSchemaRefUnsupported",
            f"{state_slice.name} recordType references HTTP api {api.name}; admin state schema copying requires a local OpenAPI file.",
            path=f"{slice_path}.recordType",
        )
        return

    if fs is None or root is None:
        return

    source_path = local_api_path(api.openapi, root)
    _validate_schema_ref_target(
        ctx,
        fs=fs,
        path=f"{slice_path}.recordType",
        schema_name=str(record_type),
        source_path=source_path,
        source_is_file_qualified=False,
        state_slice_name=state_slice.name,
        subject="recordType",
    )


def _validate_multi_api_schema_ref(ctx: ValidationContext, *, state_slice: Any, slice_path: str, profile: Profile) -> None:
    record_type = state_slice.recordType
    if (
        len(profile.apis) > 1
        and is_schema_component_record_type(record_type)
        and not is_admin_builtin_record_type(record_type)
    ):
        ctx.error(
            "profile.state.slice.missingSchemaRef",
            f"{state_slice.name} must set schemaRef because multiple apis are configured.",
            path=f"{slice_path}.schemaRef",
        )


def _validate_state_schema_refs(ctx: ValidationContext, profile: Profile, fs: FileSystem | None = None, root: Path | None = None) -> None:
    apis_by_name = {api.name: api for api in profile.apis}

    for index, state_slice in enumerate(profile.state.slices):
        slice_path = f"state.slices[{index}]"

        if state_slice.schemaRef is not None:
            _validate_schema_ref(
                ctx,
                state_slice=state_slice,
                slice_path=slice_path,
                apis_by_name=apis_by_name,
                fs=fs,
                root=root,
            )
            continue

        _validate_single_api_record_type(
            ctx,
            state_slice=state_slice,
            slice_path=slice_path,
            profile=profile,
            fs=fs,
            root=root,
        )
        _validate_multi_api_schema_ref(ctx, state_slice=state_slice, slice_path=slice_path, profile=profile)


def _validate_feature_state_slice_ownership(ctx: ValidationContext, profile: Profile) -> None:
    owners: dict[str, tuple[str, str]] = {}

    for feature_index, feature in enumerate(profile.features):
        for slice_index, state_slice_name in enumerate(feature.stateSlices):
            path = f"features[{feature_index}].stateSlices[{slice_index}]"
            existing = owners.get(state_slice_name)
            if existing is not None:
                owner_name, owner_path = existing
                ctx.error(
                    "profile.feature.duplicateStateSlice",
                    f"{state_slice_name} is already owned by feature {owner_name}; stateSlices is seed ownership and each slice can have only one owner.",
                    path=path,
                )
                ctx.warn(
                    "profile.feature.duplicateStateSliceOwner",
                    f"{state_slice_name} was first listed at {owner_path}.",
                    path=owner_path,
                )
                continue

            owners[state_slice_name] = (feature.name, path)


def _validate_operations_section(ctx: ValidationContext, value: Mapping[str, Any]) -> None:
    operations = array_at(ctx, value, "operations", "profile")
    _validate_record_array(
        ctx,
        operations,
        item_path_prefix="operations",
        invalid_id="profile.operation.invalid",
        invalid_message=lambda item_path: f"{item_path} must be an object.",
        validate_item=lambda operation, item_path: _validate_operation(ctx, operation, item_path),
    )


def _validate_operation(ctx: ValidationContext, operation: Mapping[str, Any], operation_path: str) -> None:
    operation_id = string_at(ctx, operation, "operationId", operation_path)
    string_at(ctx, operation, "api", operation_path)
    string_at(ctx, operation, "feature", operation_path)
    method = string_at(ctx, operation, "method", operation_path)
    string_at(ctx, operation, "path", operation_path)

    if method and method.upper() not in HTTP_METHODS:
        ctx.error(
            "profile.operation.invalidMethod",
            f"{operation_id or operation_path} has unsupported HTTP method {method}.",
            path=f"{operation_path}.method",
        )


def parse_behavior_anchors(text: str) -> BehaviorAnchors:
    sections: dict[str, str] = {}
    duplicates: set[str] = set()
    current_anchor: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_anchor, current_lines
        if not current_anchor:
            return
        if current_anchor in sections:
            duplicates.add(current_anchor)
        else:
            sections[current_anchor] = "\n".join(current_lines)

    for line in text.splitlines():
        match = re.match(r"^##\s+(operation:[^\s#]+)\s*$", line)
        if match:
            flush()
            current_anchor = match.group(1)
            current_lines = []
        elif current_anchor:
            current_lines.append(line)

    flush()
    return BehaviorAnchors(sections=sections, duplicates=duplicates)


def summarize_profile(profile: Profile) -> ProfileSummary:
    return ProfileSummary(
        operationCount=len(profile.operations),
        schemaVersion=profile.schemaVersion,
    )


def _has_state_slice(profile: Profile, name: str) -> bool:
    return any(state_slice.name == name for state_slice in profile.state.slices)


class ProfileValidatorService:
    def __init__(self, fs: FileSystem) -> None:
        self.fs = fs

    def load_profile(self, profile_path: Path) -> Mapping[str, Any]:
        profile = parse_profile_text(self.fs.read_text(profile_path), str(profile_path))
        if not is_record(profile):
            raise ValueError("Profile must be a TOML/JSON object.")
        return profile

    def load_profile_model(self, profile_path: Path) -> Profile:
        raw_profile = self.load_profile(profile_path)
        ctx = ValidationContext()
        if raw_profile.get("schemaVersion") != 1:
            ctx.error("profile.schemaVersion.invalid", "profile.schemaVersion must be 1.", path="schemaVersion")
        _validate_generator_section(ctx, raw_profile)
        _validate_project_section(ctx, raw_profile)
        _validate_apis_section(ctx, raw_profile)
        _validate_features_section(ctx, raw_profile)
        _validate_state_section(ctx, raw_profile)
        _validate_operations_section(ctx, raw_profile)
        if ctx.errors:
            raise ProfileValidationError(ctx.errors)
        return profile_from_mapping(raw_profile)

    def validate_api_inputs(self, ctx: ValidationContext, profile: Profile, root: Path) -> None:
        for index, api in enumerate(profile.apis):
            openapi = api.openapi
            if is_http_url(openapi):
                continue
            openapi_path = Path(openapi)
            openapi_path = openapi_path if openapi_path.is_absolute() else root / openapi_path
            if not self.fs.is_file(openapi_path):
                ctx.error(
                    "profile.api.openapi.missingLocalFile",
                    f"OpenAPI input does not exist: {openapi}",
                    path=f"apis[{index}].openapi",
                )

    def validate_behavior_sidecar(self, ctx: ValidationContext, profile: Profile, behavior_path: Path) -> None:
        expected = {
            operation_anchor(operation.operationId): operation
            for operation in profile.operations
            if operation.operationId.strip()
        }

        if not self.fs.is_file(behavior_path):
            if expected:
                ctx.error("sidecar.behavior.missingFile", f"Sidecar file does not exist: {behavior_path}", path=str(behavior_path))
            return

        behavior_text = self.fs.read_text(behavior_path)
        parsed = parse_behavior_anchors(behavior_text)
        sections = parsed.sections

        for anchor in sorted(parsed.duplicates):
            ctx.error("sidecar.behavior.duplicateAnchor", f"behavior.md contains duplicate anchor {anchor}.", path=str(behavior_path))

        for anchor, operation in expected.items():
            if anchor not in sections:
                ctx.error(
                    "sidecar.behavior.missingAnchor",
                    f"behavior.md is missing {anchor} for {operation.operationId}.",
                    path=str(behavior_path),
                )

        for anchor in sections:
            if not OPERATION_ANCHOR_PATTERN.match(anchor):
                ctx.error(
                    "sidecar.behavior.invalidAnchor",
                    f"behavior.md anchor must look like operation:<stable-id>: {anchor}.",
                    path=str(behavior_path),
                )
            elif anchor not in expected:
                ctx.warn(
                    "sidecar.behavior.extraAnchor",
                    f"behavior.md contains anchor not referenced by profile.toml: {anchor}.",
                    path=str(behavior_path),
                )

        if mentions_counter_id_policy(behavior_text) and not _has_state_slice(profile, "idCounters"):
            ctx.warn(
                "sidecar.behavior.idCountersMissing",
                "behavior.md describes generated/counter IDs, but profile.toml has no idCounters state slice.",
                path=str(behavior_path),
            )

        if mentions_slug_id_policy(behavior_text) and not has_explicit_slug_id_opt_in(behavior_text):
            ctx.warn(
                "sidecar.behavior.slugIdPolicyUnconfirmed",
                "slug-style IDs are mentioned without explicit confirmation; counter IDs are the mockapi default.",
                path=str(behavior_path),
            )

    def validate_sidecars(
        self,
        ctx: ValidationContext,
        profile: Profile,
        profile_path: Path,
        behavior_path: Path | None,
        profile_only: bool,
    ) -> None:
        if profile_only:
            return
        sidecar_root = profile_path.parent
        resolved_behavior_path = behavior_path or sidecar_root / "behavior.md"
        self.validate_behavior_sidecar(ctx, profile, resolved_behavior_path)

    def validate(
        self,
        profile_path: Path,
        *,
        root: Path | None = None,
        behavior_path: Path | None = None,
        profile_only: bool = False,
        cwd: Path | None = None,
    ) -> ValidationResult:
        ctx = ValidationContext()

        try:
            profile = self.load_profile_model(profile_path)
        except ProfileValidationError as validation_error:
            return ValidationFailureResult(errors=list(validation_error.diagnostics), warnings=ctx.warnings)
        except Exception as parse_error:
            ctx.error(
                "profile.parse.failed",
                str(parse_error) if str(parse_error) else "Profile could not be parsed.",
                path=str(profile_path),
            )
            return ValidationFailureResult(errors=ctx.errors, warnings=ctx.warnings)

        summary = summarize_profile(profile)
        effective_root = self.resolve_project_root(profile, root=root, cwd=cwd)
        self.validate_operations(ctx, profile)
        self.validate_state_schema_refs(ctx, profile, effective_root)
        self.validate_feature_state_slice_ownership(ctx, profile)

        self.validate_api_inputs(ctx, profile, effective_root)
        self.validate_sidecars(ctx, profile, profile_path, behavior_path, profile_only)

        if ctx.errors:
            return ValidationFailureResult(errors=ctx.errors, warnings=ctx.warnings, profile=summary)
        return ValidationSuccessResult(errors=ctx.errors, warnings=ctx.warnings, profile=summary)

    def validate_state_schema_refs(self, ctx: ValidationContext, profile: Profile, root: Path) -> None:
        _validate_state_schema_refs(ctx, profile, self.fs, root)

    @staticmethod
    def validate_feature_state_slice_ownership(ctx: ValidationContext, profile: Profile) -> None:
        _validate_feature_state_slice_ownership(ctx, profile)

    @staticmethod
    def validate_operations(ctx: ValidationContext, profile: Profile) -> None:
        operation_ids: set[str] = set()
        api_names = {api.name for api in profile.apis}
        feature_names = {feature.name for feature in profile.features}

        for index, operation in enumerate(profile.operations):
            operation_path = f"operations[{index}]"
            operation_id = operation.operationId

            if operation_id in operation_ids:
                ctx.error(
                    "profile.operation.duplicateOperationId",
                    f"Duplicate operationId {operation_id}.",
                    path=f"{operation_path}.operationId",
                )
            operation_ids.add(operation_id)

            if operation.api not in api_names:
                ctx.error(
                    "profile.operation.unknownApi",
                    f"{operation_id} references unknown api {operation.api}.",
                    path=f"{operation_path}.api",
                )

            if operation.feature not in feature_names:
                ctx.error(
                    "profile.operation.unknownFeature",
                    f"{operation_id} references unknown feature {operation.feature}.",
                    path=f"{operation_path}.feature",
                )

    @staticmethod
    def resolve_project_root(profile: Profile, *, root: Path | None, cwd: Path | None) -> Path:
        effective_cwd = cwd or Path.cwd()
        project_root = Path(str(profile.project.root or "."))
        return (effective_cwd / (root or project_root)).resolve()
