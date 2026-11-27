"""Integration tests for sub-issue 5 of #37: surface Dolibarr's real error bodies.

A deliberate 4xx from Dolibarr (e.g. ``POST /tasks`` without ``ref``) must
produce a tool result / exception payload that carries Dolibarr's own error
JSON (status, code, message, details) verbatim, plus the ``correlation_id``
and ``endpoint`` — instead of the old normalized
``{"message": "Validation failed", "missing_fields": [], "invalid_fields": []}``
which dropped the server's message.

Marked ``integration``: needs ``DOLIBARR_URL`` and ``DOLIBARR_API_KEY``
pointing at a reachable instance. The tests only trigger error paths, so they
create no data and need no cleanup.
"""

import json
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Tuple

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import InitializeResult, TextContent

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from dolibarr_mcp import Config, DolibarrClient  # noqa: E402
from dolibarr_mcp.dolibarr_client import DolibarrAPIError  # noqa: E402

pytestmark = pytest.mark.integration


def _config() -> Config:
    """Build the config from the environment, skipping when incomplete."""
    try:
        config = Config.from_env()
        config.validate_config()
    except ValueError:
        pytest.skip("No valid Dolibarr configuration available")
    return config


@asynccontextmanager
async def mcp_session(extra_env: dict | None = None) -> AsyncGenerator[Tuple[ClientSession, InitializeResult], None]:
    """Start the MCP server over STDIO and yield an initialized session.

    Same pattern as tests/integration/test_mcp_server.py; ``extra_env`` is
    merged into the server environment (used to enable the raw API tool).
    """
    env = {key: value for key, value in os.environ.items() if value is not None}
    env.update(extra_env or {})
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "dolibarr_mcp.dolibarr_mcp_server"],
        env=env,
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init_result = await session.initialize()
            yield session, init_result


def _error_payload(result) -> dict:
    """Extract the JSON error payload from a failed MCP tool result."""
    assert result.isError, "expected the tool call to fail"
    content = result.content[0]
    assert isinstance(content, TextContent)
    return json.loads(content.text)


@pytest.mark.asyncio
async def test_client_400_carries_dolibarr_error_body_verbatim():
    """A deliberate 400 from Dolibarr surfaces its own message, not "Validation failed".

    ``POST /tasks`` with an empty body makes Dolibarr answer HTTP 400 with
    ``{"error": {"code": 400, "message": "Bad Request: ref field missing"}, ...}``.
    """
    config = _config()
    async with DolibarrClient(config) as client:
        with pytest.raises(DolibarrAPIError) as exc_info:
            await client.request("POST", "tasks", data={})

    exc = exc_info.value
    assert exc.status_code == 400
    payload = exc.response_data or {}

    # Dolibarr's raw error JSON must be present verbatim (error.code/message + debug details).
    assert isinstance(payload.get("error"), dict), f"raw Dolibarr error body dropped: {payload}"
    assert payload["error"].get("code") == 400
    assert "ref field missing" in str(payload["error"].get("message"))
    assert "debug" in payload, "Dolibarr's debug details were dropped"

    # The normalized wrapper must keep Dolibarr's message text and the correlation info.
    assert "ref field missing" in str(payload.get("message"))
    assert payload.get("message") != "Validation failed"
    assert payload.get("status") == 400
    assert payload.get("endpoint") == "/tasks"
    assert payload.get("correlation_id")


@pytest.mark.asyncio
async def test_client_404_carries_dolibarr_error_body_verbatim():
    """Other 4xx statuses (here 404) keep Dolibarr's own message and body too."""
    config = _config()
    async with DolibarrClient(config) as client:
        with pytest.raises(DolibarrAPIError) as exc_info:
            await client.request("GET", "thirdparties/999999999")

    exc = exc_info.value
    assert exc.status_code == 404
    payload = exc.response_data or {}
    assert isinstance(payload.get("error"), dict), f"raw Dolibarr error body dropped: {payload}"
    assert "Thirdparty not found" in str(payload["error"].get("message"))
    assert "Thirdparty not found" in str(payload.get("message"))
    assert payload.get("endpoint") == "/thirdparties/999999999"
    assert payload.get("correlation_id")


@pytest.mark.asyncio
async def test_mcp_tool_400_result_contains_dolibarr_message():
    """Acceptance criterion: a deliberate 400 through an MCP tool returns Dolibarr's own text.

    Uses ``dolibarr_raw_api`` (enabled via MCP_ENABLE_RAW_API) to send
    ``POST /tasks`` with an empty body, which Dolibarr rejects with HTTP 400.
    """
    _config()  # skip early when no instance is configured
    async with mcp_session({"MCP_ENABLE_RAW_API": "true"}) as (session, _init_result):
        result = await session.call_tool(
            "dolibarr_raw_api",
            {"method": "POST", "endpoint": "tasks", "data": {}},
        )

    payload = _error_payload(result)
    assert payload.get("status") == 400
    # Dolibarr's own message text must reach the agent.
    assert "ref field missing" in json.dumps(payload)
    assert payload.get("message") != "Validation failed"
    # Raw error body preserved verbatim, with correlation info.
    assert isinstance(payload.get("error"), dict)
    assert "ref field missing" in str(payload["error"].get("message"))
    assert payload.get("endpoint") == "/tasks"
    assert payload.get("correlation_id")
