#!/usr/bin/env python3
import _python_bootstrap

_python_bootstrap.ensure_python_311_or_exit()

import argparse
import json
import sys
from pathlib import Path

from mockapi_runtime.generate import MockServerGeneratorService, generate_result_to_payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="generate.py",
        description="Generate a TypeScript/Hono mock server from a mockapi profile.",
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--profile", default=".mockapi/profile.toml")
    parser.add_argument("--out")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--run-codegen", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(
    argv=None,
    *,
    generator=None,
    stdout=None,
):
    args = build_parser().parse_args(argv)
    result = (generator or MockServerGeneratorService.local()).generate(
        root=Path(args.root),
        profile_path=args.profile,
        out=args.out,
        dry_run=args.dry_run,
        run_codegen=args.run_codegen,
    )
    print(json.dumps(generate_result_to_payload(result), indent=2), file=stdout or sys.stdout)
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
