"""Integration tests for sub-issue 8 of #37: the get_dictionary tool.

Several write operations need instance-specific numeric dictionary ids
(payment modes via ``GET /setup/dictionary/payment_types``, agenda event types
via ``GET /setup/dictionary/event_types``). The ``get_dictionary(name)`` tool
must list both dictionaries with code, label and id per row, so that payment
and event tools can later be driven with codes (``VIR``, ``AC_TEL``) on a fresh
instance without any raw API call.

Marked ``integration``: needs ``DOLIBARR_URL`` and ``DOLIBARR_API_KEY``
pointing at a reachable instance. The tests are read-only: they create no data
and need no cleanup.
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
async def mcp_session() -> AsyncGenerator[Tuple[ClientSession, InitializeResult], None]:
    """Start the MCP server over STDIO and yield an initialized session.

    Same pattern as tests/integration/test_mcp_server.py.
    """
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "dolibarr_mcp.dolibarr_mcp_server"],
        env={key: value for key, value in os.environ.items() if value is not None},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init_result = await session.initialize()
            yield session, init_result


def _tool_payload(result) -> dict:
    """Extract the JSON payload from a successful MCP tool result."""
    assert not result.isError, f"expected the tool call to succeed: {result.content}"
    content = result.content[0]
    assert isinstance(content, TextContent)
    return json.loads(content.text)


@pytest.mark.asyncio
async def test_get_dictionary_tool_is_listed():
    """The get_dictionary tool is exposed by the MCP server."""
    _config()  # skip early when no instance is configured
    async with mcp_session() as (session, _init_result):
        tools = await session.list_tools()
    names = [tool.name for tool in tools.tools]
    assert "get_dictionary" in names


@pytest.mark.asyncio
async def test_get_dictionary_payment_types_via_mcp():
    """get_dictionary('payment_types') lists code/label/id per row, including VIR.

    Acceptance criterion for sub-issue 8: payment tools can later be driven
    with the code ``VIR`` resolved to this instance's numeric id.
    """
    _config()
    async with mcp_session() as (session, _init_result):
        result = await session.call_tool("get_dictionary", {"name": "payment_types"})

    payload = _tool_payload(result)
    rows = payload["rows"] if isinstance(payload, dict) and "rows" in payload else payload
    assert isinstance(rows, list) and rows, f"payment_types dictionary is empty: {payload}"

    for row in rows:
        assert row.get("code"), f"row without code: {row}"
        assert row.get("label") is not None, f"row without label: {row}"
        assert isinstance(row.get("id"), int), f"row id must be numeric: {row}"

    by_code = {row["code"]: row for row in rows}
    assert "VIR" in by_code, f"VIR missing from payment_types: {sorted(by_code)}"
    assert by_code["VIR"]["label"], "VIR must carry a label"


@pytest.mark.asyncio
async def test_get_dictionary_event_types_via_mcp():
    """get_dictionary('event_types') lists code/label/id per row, including AC_TEL.

    Acceptance criterion for sub-issue 8: agenda event tools can later be
    driven with the code ``AC_TEL`` resolved to this instance's numeric id.
    """
    _config()
    async with mcp_session() as (session, _init_result):
        result = await session.call_tool("get_dictionary", {"name": "event_types"})

    payload = _tool_payload(result)
    rows = payload["rows"] if isinstance(payload, dict) and "rows" in payload else payload
    assert isinstance(rows, list) and rows, f"event_types dictionary is empty: {payload}"

    for row in rows:
        assert row.get("code"), f"row without code: {row}"
        assert row.get("label") is not None, f"row without label: {row}"
        assert isinstance(row.get("id"), int), f"row id must be numeric: {row}"

    by_code = {row["code"]: row for row in rows}
    assert "AC_TEL" in by_code, f"AC_TEL missing from event_types: {sorted(by_code)}"
    assert by_code["AC_TEL"]["label"], "AC_TEL must carry a label"


@pytest.mark.asyncio
async def test_get_dictionary_unknown_name_is_an_error():
    """An unknown dictionary name returns a structured error, not a crash."""
    _config()
    async with mcp_session() as (session, _init_result):
        result = await session.call_tool("get_dictionary", {"name": "no_such_dictionary"})

    assert result.isError
    content = result.content[0]
    assert isinstance(content, TextContent)
    payload = json.loads(content.text)
    assert "no_such_dictionary" in json.dumps(payload)


@pytest.mark.asyncio
async def test_client_get_dictionary_direct():
    """The DolibarrClient.get_dictionary method returns normalized rows."""
    config = _config()
    async with DolibarrClient(config) as client:
        rows = await client.get_dictionary("payment_types")

    assert isinstance(rows, list) and rows
    by_code = {row["code"]: row for row in rows}
    assert "VIR" in by_code
    assert isinstance(by_code["VIR"]["id"], int)
    assert by_code["VIR"]["label"]
