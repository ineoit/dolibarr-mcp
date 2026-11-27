"""Integration tests for sub-issue 13 of #37: supplier-inclusive third-party search.

``search_customers`` does not reliably reach supplier-only third parties, so a
``search_thirdparties(query, kind=customer|supplier|any)`` tool is added. The
``sqlfilters`` built from the query must tolerate apostrophes (straight or
typographic): Dolibarr's sqlfilters cannot match a literal apostrophe, so the
query's apostrophes are replaced by the ``_`` LIKE wildcard (see
``_escape_sqlfilter``).

Acceptance criterion: a supplier-only third party is found by name through the
tool.

Marked ``integration``: needs ``DOLIBARR_URL`` and ``DOLIBARR_API_KEY``
pointing at a reachable instance. Fixtures are uniquely named and cleaned up
so sequential runs on a shared instance do not collide.
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
async def test_search_thirdparties_finds_supplier_only_by_name():
    """A supplier-only third party is found by name through search_thirdparties.

    Creates a supplier-only third party (``type=2``) whose name contains a
    straight apostrophe, then asserts:
    - ``kind="supplier"`` finds it by its unique name tag,
    - ``kind="any"`` finds it by the apostrophe-containing name part, with the
      query using a straight apostrophe,
    - the same query with a typographic apostrophe (U+2019) also finds it,
    - ``kind="customer"`` does not return the supplier-only third party.
    """
    _config()  # skip early when no instance is configured
    tag = uuid.uuid4().hex[:8]
    supplier_name = f"SUB13-{tag}-L'Huilier Frères"
    async with mcp_session() as (session, _init_result):
        soc_id = int(_tool_payload(await session.call_tool("create_customer", {"name": supplier_name, "type": 2})))
        try:
            # kind=supplier finds the supplier-only third party by unique tag.
            found = _tool_payload(await session.call_tool("search_thirdparties", {"query": f"SUB13-{tag}", "kind": "supplier"}))
            assert isinstance(found, list)
            assert any(
                int(tp["id"]) == soc_id for tp in found
            ), f"supplier-only third party {soc_id} not found with kind=supplier: {found}"

            # Apostrophe in the query (straight) is tolerated via the _ wildcard.
            found = _tool_payload(await session.call_tool("search_thirdparties", {"query": f"{tag}-L'Huilier", "kind": "any"}))
            assert any(int(tp["id"]) == soc_id for tp in found), f"apostrophe query did not match {supplier_name!r}: {found}"

            # Typographic apostrophe (U+2019) in the query is tolerated too.
            found = _tool_payload(await session.call_tool("search_thirdparties", {"query": f"{tag}-L’Huilier", "kind": "any"}))
            assert any(
                int(tp["id"]) == soc_id for tp in found
            ), f"typographic apostrophe query did not match {supplier_name!r}: {found}"

            # kind=customer excludes the supplier-only third party. Dolibarr signals an
            # empty result set as a 404, so accept either an empty list or that 404.
            result = await session.call_tool("search_thirdparties", {"query": f"SUB13-{tag}", "kind": "customer"})
            if not result.isError:
                found = _tool_payload(result)
                assert isinstance(found, list)
                assert not any(
                    int(tp["id"]) == soc_id for tp in found
                ), f"supplier-only third party {soc_id} must not appear with kind=customer: {found}"
            else:
                error_content = result.content[0]
                assert isinstance(error_content, TextContent)
                assert "404" in error_content.text, f"unexpected error: {result.content}"
        finally:
            await session.call_tool("delete_customer", {"customer_id": soc_id})
