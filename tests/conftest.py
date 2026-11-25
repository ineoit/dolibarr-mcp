"""Shared pytest configuration for the Dolibarr MCP test suite."""

import importlib.util
import pathlib

_RUNTIME_DEPS = ("aiohttp", "mcp", "pydantic", "starlette", "pytest_asyncio")


def _missing_deps() -> list:
    return [m for m in _RUNTIME_DEPS if importlib.util.find_spec(m) is None]


if _missing_deps():
    # Minimal environments (e.g. the pre-commit pytest hook env, which only
    # installs pytest) cannot import the runtime dependencies, so the real
    # test modules would fail at collection time. Ignore them there and let
    # tests/test_smoke_env.py report the skip instead.
    _here = pathlib.Path(__file__).parent
    collect_ignore = [
        str(p) for p in sorted(_here.rglob("test_*.py")) if p.name != "test_smoke_env.py"
    ]
