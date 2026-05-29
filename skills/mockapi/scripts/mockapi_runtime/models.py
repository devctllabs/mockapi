from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Mapping

from .diagnostics import Diagnostic


ADMIN_OPENAPI_BUILTIN_STATE_RECORD_TYPES = frozenset({"MockClock"})


@dataclass(frozen=True, slots=True)
class ProfileGenerator:
    name: str
    version: str


@dataclass(frozen=True, slots=True)
class ProfileProjectTarget:
    packagePath: str
    packageName: str
    serverName: str


@dataclass(frozen=True, slots=True)
class ProfileProject:
    root: str
    target: ProfileProjectTarget


@dataclass(frozen=True, slots=True)
class ProfileApi:
    name: str
    openapi: str
    basePath: str | None = None
    contractOutput: str | None = None
    runtimeOutput: str | None = None


@dataclass(frozen=True, slots=True)
class ProfileFeature:
    name: str
    stateSlices: tuple[str, ...] = ()
    operations: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ProfileStateClock:
    seedNow: str | None = None


@dataclass(frozen=True, slots=True)
class ProfileStateSlice:
    name: str
    recordType: str | None = None
    schemaRef: str | None = None
    array: bool = True
    idField: str | None = None
    softDeleteField: str | None = None


@dataclass(frozen=True, slots=True)
class ProfileState:
    schemaVersion: int
    seed: bool = True
    slices: tuple[ProfileStateSlice, ...] = ()
    clock: ProfileStateClock | None = None


@dataclass(frozen=True, slots=True)
class ProfileOperation:
    operationId: str
    api: str
    feature: str
    method: str
    path: str


@dataclass(frozen=True, slots=True)
class Profile:
    schemaVersion: int
    generator: ProfileGenerator
    project: ProfileProject
    apis: tuple[ProfileApi, ...]
    features: tuple[ProfileFeature, ...]
    state: ProfileState
    operations: tuple[ProfileOperation, ...]


@dataclass(frozen=True, slots=True)
class GenerateContext:
    profile: Profile
    root: Path
    outRoot: Path
    operationsByFeature: dict[str, tuple[ProfileOperation, ...]]


@dataclass(frozen=True, slots=True)
class PlannedWrite:
    content: str
    overwrite: bool
    path: Path


@dataclass(frozen=True, slots=True)
class FileWriteResult:
    action: Literal["created", "skipped", "unchanged", "updated"]
    path: str


@dataclass(frozen=True, slots=True)
class PlannedFile:
    action: Literal["planned"] = "planned"
    overwrite: bool = False
    path: str = ""


@dataclass(frozen=True, slots=True, kw_only=True)
class CodegenRunResult:
    attempted: bool = False
    ok: bool = True
    installCommand: str | None = None
    codegenCommand: str | None = None
    exitCode: int | None = None
    stdout: str = ""
    stderr: str = ""
    diagnostics: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True, kw_only=True)
class GenerateFailureResult:
    diagnostics: list[Diagnostic]
    dryRun: bool
    files: list[PlannedFile | FileWriteResult]
    codegen: CodegenRunResult = field(default_factory=CodegenRunResult)
    packageManager: dict[str, object] | None = None
    ok: bool = False


@dataclass(frozen=True, slots=True, kw_only=True)
class GenerateDryRunResult:
    diagnostics: list[Diagnostic]
    dryRun: Literal[True] = True
    files: list[PlannedFile] = field(default_factory=list)
    codegen: CodegenRunResult = field(default_factory=CodegenRunResult)
    packageManager: dict[str, object] | None = None
    ok: bool = True
    outRoot: str = ""


@dataclass(frozen=True, slots=True, kw_only=True)
class GenerateApplyResult:
    diagnostics: list[Diagnostic]
    dryRun: Literal[False] = False
    files: list[FileWriteResult] = field(default_factory=list)
    codegen: CodegenRunResult = field(default_factory=CodegenRunResult)
    packageManager: dict[str, object] | None = None
    ok: bool = True
    outRoot: str = ""


GenerateResult = GenerateFailureResult | GenerateDryRunResult | GenerateApplyResult


def _mapping(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError("Expected a mapping.")
    return value


def profile_from_mapping(value: Mapping[str, Any]) -> Profile:
    profile = _mapping(value)
    generator = _mapping(profile["generator"])
    project = _mapping(profile["project"])
    target = _mapping(project["target"])
    state = _mapping(profile["state"])

    return Profile(
        schemaVersion=profile["schemaVersion"],
        generator=ProfileGenerator(name=generator["name"], version=generator["version"]),
        project=ProfileProject(
            root=project["root"],
            target=ProfileProjectTarget(
                packagePath=target["packagePath"],
                packageName=target["packageName"],
                serverName=target["serverName"],
            ),
        ),
        apis=tuple(
            ProfileApi(
                name=api["name"],
                openapi=api["openapi"],
                basePath=api.get("basePath"),
                contractOutput=api.get("contractOutput"),
                runtimeOutput=api.get("runtimeOutput"),
            )
            for api in profile.get("apis", [])
        ),
        features=tuple(
            ProfileFeature(
                name=feature["name"],
                stateSlices=tuple(feature.get("stateSlices", [])),
                operations=tuple(feature.get("operations", [])),
            )
            for feature in profile.get("features", [])
        ),
        state=ProfileState(
            schemaVersion=state["schemaVersion"],
            seed=state.get("seed", True),
            slices=tuple(
                ProfileStateSlice(
                    name=state_slice["name"],
                    recordType=state_slice.get("recordType"),
                    schemaRef=state_slice.get("schemaRef"),
                    array=bool(state_slice.get("array", True)),
                    idField=state_slice.get("idField"),
                    softDeleteField=state_slice.get("softDeleteField"),
                )
                for state_slice in state.get("slices", [])
            ),
            clock=ProfileStateClock(seedNow=state.get("clock", {}).get("seedNow")) if state.get("clock") else None,
        ),
        operations=tuple(
            ProfileOperation(
                operationId=operation["operationId"],
                api=operation["api"],
                feature=operation["feature"],
                method=operation["method"],
                path=operation["path"],
            )
            for operation in profile.get("operations", [])
        ),
    )
