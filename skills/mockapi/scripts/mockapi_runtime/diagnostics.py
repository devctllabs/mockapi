from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal, NotRequired, TypeAlias, TypedDict


class Diagnostic(TypedDict):
    id: str
    message: str
    path: NotRequired[str]


@dataclass(frozen=True, slots=True)
class ProfileSummary:
    operationCount: int
    schemaVersion: object


@dataclass(frozen=True, slots=True, kw_only=True)
class ValidationFailureResult:
    errors: list[Diagnostic]
    warnings: list[Diagnostic]
    profile: ProfileSummary | None = None
    ok: Literal[False] = False


@dataclass(frozen=True, slots=True, kw_only=True)
class ValidationSuccessResult:
    errors: list[Diagnostic]
    warnings: list[Diagnostic]
    profile: ProfileSummary
    ok: Literal[True] = True


ValidationResult: TypeAlias = ValidationFailureResult | ValidationSuccessResult


def _format_diagnostic(diagnostic: Diagnostic) -> str:
    path = diagnostic.get("path")
    location = f" {path}" if path else ""
    return f"- {diagnostic['id']}{location}: {diagnostic['message']}"


def format_validation_result(result: ValidationResult) -> str:
    parts = [f"ok: {str(result.ok).lower()}"]
    profile = result.profile

    if profile is None:
        parts.append("profile summary unavailable")
    else:
        parts.append(f"operationCount: {profile.operationCount}")

    error_count = len(result.errors)
    warning_count = len(result.warnings)
    parts.append("no errors" if error_count == 0 else f"errors: {error_count}")
    parts.append("no warnings" if warning_count == 0 else f"warnings: {warning_count}")

    lines = [f"Result: {', '.join(parts)}."]
    if result.errors:
        lines.append("Errors:")
        lines.extend(_format_diagnostic(diagnostic) for diagnostic in result.errors)
    if result.warnings:
        lines.append("Warnings:")
        lines.extend(_format_diagnostic(diagnostic) for diagnostic in result.warnings)

    return "\n".join(lines)


def validation_result_to_payload(result: ValidationResult) -> dict[str, Any]:
    payload = asdict(result)
    if payload.get("profile") is None:
        payload.pop("profile", None)
    return payload
