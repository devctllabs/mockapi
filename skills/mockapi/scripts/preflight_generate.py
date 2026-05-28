#!/usr/bin/env python3
import _python_bootstrap

_python_bootstrap.ensure_python_311_or_exit()

import argparse
import json
import sys
from pathlib import Path
from typing import Literal

from mockapi_runtime.diagnostics import validation_result_to_payload
from mockapi_runtime.filesystem import LocalFileSystem
from mockapi_runtime.profile import ProfileValidatorService


Classification = Literal["missing", "repair", "valid"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="preflight_generate.py",
        description="Classify mockapi sidecars before running mockapi generate.",
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--profile", default=".mockapi/profile.toml")
    parser.add_argument("--behavior", default=".mockapi/behavior.md")
    return parser


def _resolve_path(root: Path, path: str) -> Path:
    raw_path = Path(path)
    return raw_path if raw_path.is_absolute() else root / raw_path


def _payload(
    *,
    classification: Classification,
    root: Path,
    profile_path: Path,
    behavior_path: Path,
    message: str,
    validation: dict[str, object] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "ok": True,
        "classification": classification,
        "root": str(root),
        "profile": str(profile_path),
        "behavior": str(behavior_path),
        "message": message,
    }
    if validation is not None:
        payload["validation"] = validation
    return payload


def classify_sidecars(
    *,
    root: Path,
    profile_path: Path,
    behavior_path: Path,
    fs=None,
    validator=None,
) -> dict[str, object]:
    filesystem = fs or LocalFileSystem()
    resolved_root = root.resolve()
    resolved_profile_path = _resolve_path(resolved_root, str(profile_path)).resolve()
    resolved_behavior_path = _resolve_path(resolved_root, str(behavior_path)).resolve()

    if not filesystem.is_file(resolved_profile_path):
        return _payload(
            classification="missing",
            root=resolved_root,
            profile_path=resolved_profile_path,
            behavior_path=resolved_behavior_path,
            message=".mockapi/profile.toml is missing; run the profile workflow before generation.",
        )

    result = (validator or ProfileValidatorService(filesystem)).validate(
        resolved_profile_path,
        root=Path("."),
        behavior_path=resolved_behavior_path,
        cwd=resolved_root,
    )
    validation = validation_result_to_payload(result)
    if not result.ok:
        return _payload(
            classification="repair",
            root=resolved_root,
            profile_path=resolved_profile_path,
            behavior_path=resolved_behavior_path,
            message="Existing mockapi sidecars need repair before generation.",
            validation=validation,
        )

    return _payload(
        classification="valid",
        root=resolved_root,
        profile_path=resolved_profile_path,
        behavior_path=resolved_behavior_path,
        message="Existing mockapi sidecars are valid; reuse them for generation.",
        validation=validation,
    )


def main(
    argv=None,
    *,
    fs=None,
    validator=None,
    stdout=None,
):
    args = build_parser().parse_args(argv)
    root = Path(args.root).resolve()
    payload = classify_sidecars(
        root=root,
        profile_path=Path(args.profile),
        behavior_path=Path(args.behavior),
        fs=fs,
        validator=validator,
    )
    print(json.dumps(payload, indent=2), file=stdout or sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
