#!/usr/bin/env python3
import _python_bootstrap

_python_bootstrap.ensure_python_311_or_exit()

import argparse
import json
import sys
from pathlib import Path

from mockapi_runtime.diagnostics import format_validation_result, validation_result_to_payload
from mockapi_runtime.filesystem import LocalFileSystem
from mockapi_runtime.profile import ProfileValidatorService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="validate_profile.py",
        description="Validate mockapi profile and sidecar files.",
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--profile", default=".mockapi/profile.toml")
    parser.add_argument("--behavior", default=".mockapi/behavior.md")
    parser.add_argument("--profile-only", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(
    argv=None,
    *,
    validator=None,
    stdout=None,
):
    args = build_parser().parse_args(argv)
    root = Path(args.root).resolve()
    profile_path = Path(args.profile) if Path(args.profile).is_absolute() else root / args.profile
    behavior_path = Path(args.behavior) if Path(args.behavior).is_absolute() else root / args.behavior

    result = (validator or ProfileValidatorService(LocalFileSystem())).validate(
        profile_path.resolve(),
        root=Path("."),
        behavior_path=behavior_path.resolve(),
        profile_only=args.profile_only,
        cwd=root,
    )
    output = json.dumps(validation_result_to_payload(result), indent=2) if args.json else format_validation_result(result)
    print(output, file=stdout or sys.stdout)
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
