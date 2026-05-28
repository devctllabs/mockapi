"""Guard bundled mockapi scripts before loading runtime code."""

import sys


MIN_VERSION = (3, 11)


def ensure_python_311_or_exit():
    current_version = tuple(sys.version_info[:3])
    if _is_supported_version(current_version):
        return

    active_executable = sys.executable or "python"
    _fail(
        sys.stderr,
        "mockapi requires Python {required}+ for bundled scripts. "
        "Current interpreter: {executable} (Python {current}). "
        "Run this script with a Python {required}+ executable.".format(
            required=_format_version(MIN_VERSION),
            executable=active_executable,
            current=_format_version(current_version),
        ),
    )


def _is_supported_version(version):
    normalized = tuple(version[:2])
    return normalized >= MIN_VERSION


def _format_version(version):
    if len(version) >= 3:
        return "{0}.{1}.{2}".format(version[0], version[1], version[2])
    return "{0}.{1}".format(version[0], version[1])


def _fail(stderr, message):
    print(message, file=stderr)
    raise SystemExit(1)
