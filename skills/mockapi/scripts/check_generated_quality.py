#!/usr/bin/env python3
import _python_bootstrap

_python_bootstrap.ensure_python_311_or_exit()

import argparse
import json
import sys
from pathlib import Path

from mockapi_runtime.filesystem import LocalFileSystem
from mockapi_runtime.quality import check_generated_quality, format_quality_result, quality_result_to_payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="check_generated_quality.py",
        description="Check completed generated mock-server quality gates.",
    )
    parser.add_argument("--package-root", required=True)
    parser.add_argument("--profile")
    parser.add_argument("--json", action="store_true")
    return parser


def main(
    argv=None,
    *,
    fs=None,
    stdout=None,
):
    args = build_parser().parse_args(argv)
    package_root = Path(args.package_root).resolve()

    result = check_generated_quality(
        fs or LocalFileSystem(),
        package_root,
        profile_path=Path(args.profile).resolve() if args.profile else None,
    )
    output = json.dumps(quality_result_to_payload(result), indent=2) if args.json else format_quality_result(result)
    print(output, file=stdout or sys.stdout)
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
