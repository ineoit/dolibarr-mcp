"""Integration tests for sub-issue 3 of #37: social contributions tools.

Verified API contract on the instance (Dolibarr 21.0.0 + the upstream
``api_socialcontributions`` class):

- ``GET /socialcontributions`` returns large objects; the tool maps them to a
  compact summary (id, label, type, amount, period, paid flag).
- ``POST /socialcontributions`` accepts the server-side field names ``fk_type``
  and ``period`` only; sending the raw ``type`` / French-period fields fails with a 400
  ("fk_type field missing" / "period field missing"). ``date_ech`` and
  ``period`` are integer Unix timestamps (midnight UTC convention).
- ``paye`` cannot be set by POST or PUT; it flips only when a payment is
  recorded: ``POST /socialcontributions/{id}/payments`` with ``datepaye``,
  ``amount``, ``paiementtype`` (numeric mode id, required), ``accountid``
  (creates the linked bank line, required while the bank module is on), plus
  optional ``num_payment``, ``note``, ``closepaidcontrib``.

Acceptance criteria encoded here:

- A charge can be created, paid, and listed per period without the raw API.
- The tool never sends the raw ``type`` / French-period fields to the endpoint (friendly names
  are accepted and translated to ``fk_type`` / ``period``).
- The compact list keeps the response small for dozens of charges.

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
import pytest_asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import InitializeResult, TextContent

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from dolibarr_mcp import Config, DolibarrClient  # noqa: E402
from dolibarr_mcp.dolibarr_client import DolibarrAPIError  # noqa: E402

pytestmark = pytest.mark.integration


async def _skip_if_no_social_contributions(config: Config) -> None:
    """Skip when the instance lacks the /socialcontributions API.

    The CI workflow pins DOLIBARR_TEST_REF=21.0.0, which ships no
    ``api_socialcontributions`` class, so ``GET /socialcontributions`` answers
    HTTP 501 "API not found". On instances that do ship it, this returns
    normally and the tests stay active.
    """
    async with DolibarrClient(config) as client:
        try:
            await client.request("GET", "socialcontributions", params={"limit": 1})
        except DolibarrAPIError as exc:
            if exc.status_code in (404, 501):
                pytest.skip(
                    f"/socialcontributions not available on this Dolibarr instance " f"(HTTP {exc.status_code}: {exc.message})"
                )
            raise


@pytest_asyncio.fixture(autouse=True)
async def _require_social_contributions_endpoint():
    await _skip_if_no_social_contributions(_config())


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


async def _delete_contribution(config: Config, contribution_id: int, payment_ids: List[int]) -> None:
    """Delete the fixture payments and contribution (best effort)."""
    async with DolibarrClient(config) as client:
        for payment_id in payment_ids:
            try:
                await client.request("DELETE", f"socialcontributions/payments/{payment_id}")
            except DolibarrAPIError:
                pass
        try:
            await client.request("DELETE", f"socialcontributions/{contribution_id}")
        except DolibarrAPIError:
            pass


@pytest.mark.asyncio
async def test_create_pay_and_list_social_contribution_per_period():
    """A charge is created, paid, and listed per period without the raw API.

    - ``create_social_contribution`` accepts friendly ``type`` / ``period``
      (YYYY-MM-DD dates) and returns the new id,
    - the created charge reads back unpaid,
    - ``add_social_contribution_payment`` records the payment (mode code VIR,
      bank account, num_payment, note) and the charge flips to paid,
    - ``get_social_contributions`` lists it as a compact summary filtered by
      period and paid state.
    """
    config = _config()
    tag = uuid.uuid4().hex[:8]
    account_id = await _first_bank_account_id(config)
    async with mcp_session() as (session, _init_result):
        created: List[int] = []
        payment_ids: List[int] = []
        try:
            contrib_id = int(
                _tool_payload(
                    await session.call_tool(
                        "create_social_contribution",
                        {
                            "label": f"SUB03-{tag}",
                            "type": 1,
                            "amount": 150,
                            "date_ech": "2026-08-05",
                            "period": "2026-08-01",
                        },
                    )
                )
            )
            created.append(contrib_id)
            assert contrib_id > 0, contrib_id

            # Unpaid right after creation: paye follows the payments, not POST.
            listed = _tool_payload(await session.call_tool("get_social_contributions", {"period": "2026-08-01", "paid": False}))
            mine = [c for c in listed if int(c["id"]) == contrib_id]
            assert len(mine) == 1, f"new charge must be listed unpaid: {listed}"
            assert mine[0]["paid"] is False, mine[0]
            assert mine[0]["label"] == f"SUB03-{tag}", mine[0]
            assert int(mine[0]["type"]) == 1, mine[0]
            assert float(mine[0]["amount"]) == pytest.approx(150.0), mine[0]
            # Compact summary: exactly the documented keys, no raw API fields.
            assert set(mine[0].keys()) == {"id", "label", "type", "amount", "period", "paid"}, mine[0]

            payment_id = int(
                _tool_payload(
                    await session.call_tool(
                        "add_social_contribution_payment",
                        {
                            "contribution_id": contrib_id,
                            "amount": 150,
                            "payment_mode": "VIR",
                            "accountid": account_id,
                            "payment_date": "2026-08-05",
                            "num_payment": f"SC-{tag}",
                            "note": f"payment {tag}",
                            "closepaidcontrib": True,
                        },
                    )
                )
            )
            payment_ids.append(payment_id)
            assert payment_id > 0, payment_id

            # paye follows the payments: full payment closes the charge.
            listed_paid = _tool_payload(
                await session.call_tool("get_social_contributions", {"period": "2026-08-01", "paid": True})
            )
            mine_paid = [c for c in listed_paid if int(c["id"]) == contrib_id]
            assert len(mine_paid) == 1 and mine_paid[0]["paid"] is True, listed_paid

            # The other period filter must not return this charge.
            listed_other = _tool_payload(await session.call_tool("get_social_contributions", {"period": "2026-09-01"}))
            assert all(int(c["id"]) != contrib_id for c in listed_other), listed_other

            # Type filter works too.
            listed_type = _tool_payload(await session.call_tool("get_social_contributions", {"type": 1, "paid": True}))
            assert any(int(c["id"]) == contrib_id for c in listed_type), listed_type
        finally:
            await _delete_contribution(config, contrib_id, payment_ids)


@pytest.mark.asyncio
async def test_update_social_contribution_never_sends_raw_field_names():
    """``update_social_contribution`` accepts friendly names and translates them.

    - updating with friendly ``type`` / ``period`` succeeds (a raw ``type`` or
      French-period field would be rejected by the server with a 400),
    - the update is visible in the compact list.
    """
    config = _config()
    async with mcp_session() as (session, _init_result):
        tag = uuid.uuid4().hex[:8]
        contrib_id = int(
            _tool_payload(
                await session.call_tool(
                    "create_social_contribution",
                    {
                        "label": f"SUB03U-{tag}",
                        "type": 10,
                        "amount": 42,
                        "date_ech": "2026-07-05",
                        "period": "2026-07-01",
                    },
                )
            )
        )
        try:
            _tool_payload(
                await session.call_tool(
                    "update_social_contribution",
                    {
                        "contribution_id": contrib_id,
                        "label": f"SUB03U-{tag}-renamed",
                        "type": 1,
                        "period": "2026-08-01",
                        "amount": 43,
                    },
                )
            )
            listed = _tool_payload(await session.call_tool("get_social_contributions", {"period": "2026-08-01", "type": 1}))
            mine = [c for c in listed if int(c["id"]) == contrib_id]
            assert len(mine) == 1, f"updated charge must be listed under its new period/type: {listed}"
            assert mine[0]["label"] == f"SUB03U-{tag}-renamed", mine[0]
            assert float(mine[0]["amount"]) == pytest.approx(43.0), mine[0]
        finally:
            await _delete_contribution(config, contrib_id, [])


@pytest.mark.asyncio
async def test_compact_list_stays_small_for_many_charges():
    """The compact list keeps responses small even with charges across periods."""
    config = _config()
    async with mcp_session() as (session, _init_result):
        tag = uuid.uuid4().hex[:8]
        created: List[int] = []
        try:
            for month in ("2026-01-01", "2026-02-01", "2026-03-01"):
                contrib_id = int(
                    _tool_payload(
                        await session.call_tool(
                            "create_social_contribution",
                            {
                                "label": f"SUB03S-{tag}-{month}",
                                "type": 1,
                                "amount": 10,
                                "date_ech": month,
                                "period": month,
                            },
                        )
                    )
                )
                created.append(contrib_id)
            result = await session.call_tool("get_social_contributions", {"limit": 100})
            assert not result.isError, result.content
            payload = _tool_payload(result)
            assert isinstance(payload, list) and len(payload) >= 3, payload
            for row in payload:
                assert set(row.keys()) == {"id", "label", "type", "amount", "period", "paid"}, row
            # A raw row is ~10 KB; 100 compact rows must stay well below that total.
            assert len(json.dumps(payload)) < 20 * 1024, "compact list must stay small"
        finally:
            for contrib_id in created:
                await _delete_contribution(config, contrib_id, [])
