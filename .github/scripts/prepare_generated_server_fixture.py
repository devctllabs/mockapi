#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.support import default_behavior, profile_toml, seed_openapi_fixture, write_project
from mockapi_runtime.filesystem import LocalFileSystem


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="prepare_generated_server_fixture.py",
        description="Prepare the temporary generated-server fixture repository.",
    )
    parser.add_argument("--root", required=True)
    return parser


def prepare_generated_server_fixture(root: Path) -> None:
    fs = LocalFileSystem()
    seed_openapi_fixture(fs, root=root)
    write_project(
        fs,
        root=root,
        profile=profile_toml(openapi_path="openapi/openapi.yaml"),
        behavior=default_behavior(),
        openapi=None,
    )


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    prepare_generated_server_fixture(Path(args.root).resolve())
    return 0


if __name__ == "__main__":
    sys.exit(main())
