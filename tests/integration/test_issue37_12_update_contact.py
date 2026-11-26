"""Integration tests for sub-issue 12 of #37: update_contact third-party move.

Dolibarr's ``PUT /contacts/{id}`` only writes the new third party when both
``socid`` and ``fk_soc`` are present in the payload; sending just one of the
two is a silent no-op (HTTP 200, contact keeps its old company). The
``update_contact`` tool must therefore send both when either is given, and
the move must be verified by re-reading the contact.

Marked ``integration``: needs ``DOLIBARR_URL`` and ``DOLIBARR_API_KEY``
pointing at a reachable instance. Fixtures are uniquely named and cleaned
up so sequential runs on a shared instance do not collide.
"""

import json
import os
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator, Tuple

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import InitializeResult, TextContent

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from dolibarr_mcp import Config  # noqa: E402

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


def _tool_payload(result) -> Any:
    """Extract the JSON payload from a successful MCP tool result."""
    assert not result.isError, f"tool call failed: {result.content}"
    content = result.content[0]
    assert isinstance(content, TextContent)
    return json.loads(content.text)


@pytest.mark.asyncio
async def test_update_contact_moves_contact_with_single_company_param():
    """A contact moved via update_contact with one company parameter lands on it.

    Creates two third parties and a contact on the first, moves the contact
    to the second passing only ``fk_soc`` (Dolibarr silently ignores a lone
    ``fk_soc`` unless ``socid`` is sent too), then re-reads the contact and
    asserts the stored third party is the new one.
    """
    _config()  # skip early when no instance is configured
    tag = uuid.uuid4().hex[:8]
    async with mcp_session() as (session, _init_result):
        soc_a = int(_tool_payload(await session.call_tool("create_customer", {"name": f"SUB12-{tag}-A"})))
        soc_b = int(_tool_payload(await session.call_tool("create_customer", {"name": f"SUB12-{tag}-B"})))
        contact_id = int(
            _tool_payload(
                await session.call_tool(
                    "create_contact",
                    {"firstname": "Sub12", "lastname": f"Move-{tag}", "socid": soc_a},
                )
            )
        )
        try:
            initial = _tool_payload(await session.call_tool("get_contact_by_id", {"contact_id": contact_id}))
            assert int(initial["socid"]) == soc_a

            # Move with a single company parameter: fk_soc only.
            _tool_payload(await session.call_tool("update_contact", {"contact_id": contact_id, "fk_soc": soc_b}))
            moved = _tool_payload(await session.call_tool("get_contact_by_id", {"contact_id": contact_id}))
            assert int(moved["socid"]) == soc_b, f"contact still on {moved.get('socid')}, expected {soc_b}"
            assert int(moved["fk_soc"]) == soc_b

            # And back with the other single parameter: socid only.
            _tool_payload(await session.call_tool("update_contact", {"contact_id": contact_id, "socid": soc_a}))
            back = _tool_payload(await session.call_tool("get_contact_by_id", {"contact_id": contact_id}))
            assert int(back["socid"]) == soc_a, f"contact still on {back.get('socid')}, expected {soc_a}"
            assert int(back["fk_soc"]) == soc_a
        finally:
            await session.call_tool("delete_contact", {"contact_id": contact_id})
            await session.call_tool("delete_customer", {"customer_id": soc_a})
            await session.call_tool("delete_customer", {"customer_id": soc_b})
