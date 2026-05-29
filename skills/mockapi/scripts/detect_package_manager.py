#!/usr/bin/env python3
import _python_bootstrap

_python_bootstrap.ensure_python_311_or_exit()

import argparse
import json
import sys
from pathlib import Path

from mockapi_runtime.package_manager import detect_package_manager


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="detect_package_manager.py",
        description="Detect the package manager for a generated mockapi server.",
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--profile", default=".mockapi/profile.toml")
    parser.add_argument("--package-root")
    return parser


def main(argv=None, *, stdout=None):
    args = build_parser().parse_args(argv)
    result = detect_package_manager(
        root=Path(args.root),
        profile_path=args.profile,
        package_root=args.package_root,
    )
    print(json.dumps(result.to_payload(), indent=2), file=stdout or sys.stdout)
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
