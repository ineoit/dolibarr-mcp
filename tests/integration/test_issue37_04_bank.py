"""Integration tests for sub-issue 4 of #37: bank tools (statement reconciliation).

Verified API contract on the instance (Dolibarr 21.0.0 + upstream
``api_bankaccounts`` class):

- ``GET /bankaccounts`` lists the bank accounts (raw objects are huge; the
  tool maps them to id/label/bank).
- ``GET /bankaccounts/{id}/lines`` rejects the ``t.`` prefix on sqlfilters
  (5xx) and is unreliable with multi-condition filters (observed: a
  two-condition ``datev`` range returns 0 rows). Exactly one condition per
  call, without prefix, works: ``(label:like:'%...%')``,
  ``(amount:=:-372.6)``, ``(num_releve:like:'%2026/02%')``,
  ``(datev:>=:1790000000)``. The tool therefore issues one single-condition
  call per filter and merges the results locally, and never sends a
  ``t.``-prefixed or multi-condition sqlfilters to this endpoint.
- ``GET /bankaccounts/{id}/lines/{line_id}/links`` returns the objects linked
  to a line (type/label/url_id), ~1s per call, so the tool batches many line
  ids in one call.
- ``POST /bankaccounts/{id}/lines`` creates a manual line (date, type, label,
  amount, optional datev, num_releve, cheque fields) and is the only place
  ``num_releve`` (bank statement number) can be set through the API.

Acceptance criteria encoded here:

- One month of bank lines can be fetched with one tool call, filtered by
  statement number or date range.
- Links are resolved for a batch of line ids within one call.
- Combined filters still return the right rows (proving the merge is local:
  a multi-condition ``datev`` range sent to the server returns 0 rows).

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
from typing import Any, AsyncGenerator, List, Tuple

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import InitializeResult, TextContent

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from dolibarr_mcp import Config, DolibarrClient  # noqa: E402
from dolibarr_mcp.dolibarr_client import DolibarrAPIError  # noqa: E402

pytestmark = pytest.mark.integration

BANK_LINE_KEYS = {"rowid", "datev", "dateo", "label", "amount", "num_releve", "rappro"}


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


async def _first_bank_account_id(config: Config) -> int:
    """Look up the first bank account id through the raw client (fixture setup)."""
    async with DolibarrClient(config) as client:
        accounts = await client.request("GET", "bankaccounts", params={"limit": 5})
    assert isinstance(accounts, list) and accounts, "the bank module must be enabled with one account"
    return int(accounts[0]["id"])


async def _delete_bank_lines(config: Config, account_id: int, line_ids: List[int]) -> None:
    """Delete the fixture bank lines (best effort)."""
    async with DolibarrClient(config) as client:
        for line_id in line_ids:
            try:
                await client.request("DELETE", f"bankaccounts/{account_id}/lines/{line_id}")
            except DolibarrAPIError:
                pass


@pytest.mark.asyncio
async def test_get_bank_accounts_returns_id_label_bank():
    """``get_bank_accounts`` lists accounts as compact (id, label, bank) rows."""
    config = _config()
    account_id = await _first_bank_account_id(config)
    async with mcp_session() as (session, _init_result):
        payload = _tool_payload(await session.call_tool("get_bank_accounts", {}))
    assert isinstance(payload, list) and payload, payload
    for account in payload:
        assert set(account.keys()) == {"id", "label", "bank"}, account
        assert isinstance(account["id"], int), account
    assert any(account["id"] == account_id for account in payload), payload


@pytest.mark.asyncio
async def test_create_bank_line_then_filter_by_num_releve_and_date_range():
    """One month of lines fetched in one call, by statement number or date range.

    - ``create_bank_line`` creates a manual line with ``num_releve`` set (the
      only API way to set the statement number),
    - ``get_bank_lines`` filtered by ``num_releve`` returns exactly that line,
    - filtered by a date range covering its month returns it, a range in
      another month does not,
    - combined filters (from + to + label_contains + amount) in ONE call
      still return it - a multi-condition sqlfilters would return 0 rows on
      this endpoint, so this proves the single-condition local merge,
    - every returned line is compact (rowid, datev, dateo, label, amount,
      num_releve, rappro) - no raw ~10 KB API objects.
    """
    config = _config()
    tag = uuid.uuid4().hex[:8]
    account_id = await _first_bank_account_id(config)
    async with mcp_session() as (session, _init_result):
        created: List[int] = []
        try:
            rowid = int(
                _tool_payload(
                    await session.call_tool(
                        "create_bank_line",
                        {
                            "account_id": account_id,
                            "date": "2026-03-15",
                            "type": "VIR",
                            "label": f"SUB04-{tag}",
                            "amount": -1337.37,
                            "datev": "2026-03-15",
                            "num_releve": f"RELE-{tag}",
                        },
                    )
                )
            )
            created.append(rowid)
            assert rowid > 0, rowid

            # Filter by statement number.
            by_releve = _tool_payload(
                await session.call_tool("get_bank_lines", {"account_id": account_id, "num_releve": f"RELE-{tag}"})
            )
            mine = [line for line in by_releve if int(line["rowid"]) == rowid]
            assert len(mine) == 1, f"the new line must be found by num_releve: {by_releve}"
            assert set(mine[0].keys()) == BANK_LINE_KEYS, mine[0]
            assert mine[0]["label"] == f"SUB04-{tag}", mine[0]
            assert float(mine[0]["amount"]) == pytest.approx(-1337.37), mine[0]
            assert mine[0]["num_releve"] == f"RELE-{tag}", mine[0]
            assert mine[0]["rappro"] is False, mine[0]
            assert mine[0]["datev"] == "2026-03-15", mine[0]
            assert mine[0]["dateo"] == "2026-03-15", mine[0]

            # Date range covering the line's month (one tool call = one month).
            march = _tool_payload(
                await session.call_tool("get_bank_lines", {"account_id": account_id, "from": "2026-03-01", "to": "2026-03-31"})
            )
            assert all(set(line.keys()) == BANK_LINE_KEYS for line in march), march
            assert any(int(line["rowid"]) == rowid for line in march), march

            # A range in another month must not return it.
            april = _tool_payload(
                await session.call_tool("get_bank_lines", {"account_id": account_id, "from": "2026-04-01", "to": "2026-04-30"})
            )
            assert all(int(line["rowid"]) != rowid for line in april), april

            # Combined filters in one call: single-condition calls merged locally.
            combined = _tool_payload(
                await session.call_tool(
                    "get_bank_lines",
                    {
                        "account_id": account_id,
                        "from": "2026-03-01",
                        "to": "2026-03-31",
                        "label_contains": f"SUB04-{tag}",
                        "amount": -1337.37,
                    },
                )
            )
            assert [int(line["rowid"]) for line in combined] == [rowid], combined

            # label_contains alone also finds it.
            by_label = _tool_payload(
                await session.call_tool("get_bank_lines", {"account_id": account_id, "label_contains": f"SUB04-{tag}"})
            )
            assert any(int(line["rowid"]) == rowid for line in by_label), by_label
        finally:
            await _delete_bank_lines(config, account_id, created)


@pytest.mark.asyncio
async def test_get_bank_lines_unfiltered_returns_compact_lines():
    """Without filters the tool returns bounded, compact lines for the account."""
    config = _config()
    account_id = await _first_bank_account_id(config)
    async with mcp_session() as (session, _init_result):
        payload = _tool_payload(await session.call_tool("get_bank_lines", {"account_id": account_id, "limit": 5}))
    assert isinstance(payload, list) and 0 < len(payload) <= 5, payload
    for line in payload:
        assert set(line.keys()) == BANK_LINE_KEYS, line
    # A raw line is ~10 KB; 5 compact lines must stay far below that.
    assert len(json.dumps(payload)) < 5 * 1024, "compact lines must stay small"


@pytest.mark.asyncio
async def test_get_bank_line_links_resolves_a_batch_in_one_call():
    """``get_bank_line_links`` resolves the linked objects of many lines in one call.

    Two manual lines are created (raw API fixture) and each gets a link
    (e.g. the supplier payment a ``(SupplierInvoicePayment)`` line settled).
    One tool call with both line ids must return both link sets.
    """
    config = _config()
    tag = uuid.uuid4().hex[:8]
    account_id = await _first_bank_account_id(config)
    created: List[int] = []
    async with DolibarrClient(config) as client:
        for index in (1, 2):
            line_id = int(
                await client.request(
                    "POST",
                    f"bankaccounts/{account_id}/lines",
                    data={
                        "date": 1773676800,  # 2026-03-15 UTC-ish; exact day irrelevant here
                        "type": "VIR",
                        "label": f"SUB04L-{tag}-{index}",
                        "amount": -10 - index,
                        "datev": 1773676800,
                    },
                )
            )
            created.append(line_id)
            await client.request(
                "POST",
                f"bankaccounts/{account_id}/lines/{line_id}/links",
                data={
                    # The POST links endpoint validates that url is a full URL.
                    "url": "http://127.0.0.1/fourn/paiement/card.php?id=",
                    "url_id": str(999000 + index),
                    "label": f"(paiement SUB04-{tag}-{index})",
                    "type": "payment_supplier",
                },
            )
    try:
        async with mcp_session() as (session, _init_result):
            payload = _tool_payload(
                await session.call_tool("get_bank_line_links", {"account_id": account_id, "line_ids": created})
            )
        assert set(payload.keys()) == {str(line_id) for line_id in created}, payload
        for index, line_id in enumerate(created, start=1):
            links = payload[str(line_id)]
            assert isinstance(links, list) and len(links) == 1, links
            assert links[0]["type"] == "payment_supplier", links[0]
            assert links[0]["label"] == f"(paiement SUB04-{tag}-{index})", links[0]
            assert links[0]["url_id"] == str(999000 + index), links[0]
    finally:
        await _delete_bank_lines(config, account_id, created)
