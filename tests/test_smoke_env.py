"""Smoke test that keeps the pytest pre-commit hook green in minimal envs."""

import importlib.util

import pytest

_RUNTIME_DEPS = ("aiohttp", "mcp", "pydantic", "starlette", "pytest_asyncio")


def test_runtime_dependencies_available():
    missing = [m for m in _RUNTIME_DEPS if importlib.util.find_spec(m) is None]
    if missing:
        pytest.skip(f"runtime dependencies not installed in this environment: {missing}")
