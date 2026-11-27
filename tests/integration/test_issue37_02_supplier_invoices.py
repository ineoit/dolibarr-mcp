"""Integration tests for sub-issue 2 of #37: the supplier invoice toolset.

Verified API contract on the instance (Dolibarr 21.0.0):

- ``GET /supplierinvoices`` needs the ``t.`` prefix in ``sqlfilters``
  (e.g. ``(t.fk_soc:=:ID)``) and only honors a single condition per call.
- ``POST /supplierinvoices/{id}/lines`` silently ignores ``desc``/``subprice``
  (empty description, price 0); only ``description``/``pu_ht`` are honored.
- Adding a line to a validated invoice is a silent no-op (response ``0``).
- ``POST /supplierinvoices/{id}/validate`` returns the final ``SI...`` ref;
  ``type=2`` creates a credit note (``SA...`` ref, negative amounts).

Acceptance criteria encoded here:

- A supplier invoice can be created, lined, validated and read back through the
  MCP tools only (no ``dolibarr_raw_api``).
- ``desc``/``subprice`` on the line tools are rejected instead of producing an
  empty 0-value line.
- Adding a line to a validated invoice returns an explicit error.
- ``get_supplier_invoices`` only ever returns compact summaries (never a raw
  unfiltered dump), with ``ref_supplier`` included, one filter per call.

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


def _error_text(result) -> str:
    """Extract the text of a failed MCP tool result."""
    assert result.isError, f"expected a tool error, got: {result.content}"
    content = result.content[0]
    assert isinstance(content, TextContent)
    return content.text


async def _cleanup(config: Config, soc_id: int, invoice_ids: List[int]) -> None:
    """Delete the fixture invoices and third party through the raw client.

    Only used for teardown; the acceptance criteria concern the MCP tools.
    """
    async with DolibarrClient(config) as client:
        for invoice_id in invoice_ids:
            try:
                await client.request("DELETE", f"supplierinvoices/{invoice_id}")
            except DolibarrAPIError:
                # A paid/validated invoice may refuse deletion: revert to draft first.
                try:
                    await client.request("PUT", f"supplierinvoices/{invoice_id}", data={"status": 0})
                    await client.request("DELETE", f"supplierinvoices/{invoice_id}")
                except DolibarrAPIError:
                    pass
        try:
            await client.request("DELETE", f"thirdparties/{soc_id}")
        except DolibarrAPIError:
            pass


@pytest.mark.asyncio
async def test_supplier_invoice_create_line_validate_readback_cycle():
    """Create + line + validate + read back, then settodraft/settopaid cycle.

    All through MCP tools, no ``dolibarr_raw_api``:
    - ``create_supplier_invoice`` with an inline line returns the draft id,
    - ``add_supplier_invoice_line`` / ``update_supplier_invoice_line`` work on the draft,
    - ``validate_supplier_invoice`` returns the final ``SI...`` ref,
    - ``get_supplier_invoices(supplier_id=...)`` reads it back as a compact summary
      including ``ref_supplier``,
    - adding a line to the validated invoice is an explicit error,
    - ``set_supplier_invoice_to_draft`` keeps the ref, re-validation keeps it too,
    - ``set_supplier_invoice_paid`` marks it paid,
    - ``update_supplier_invoice`` (label/ref_supplier) works on the paid invoice.
    """
    config = _config()
    tag = uuid.uuid4().hex[:8]
    async with mcp_session() as (session, _init_result):
        soc_id = int(_tool_payload(await session.call_tool("create_customer", {"name": f"SUB02-{tag}", "type": 2})))
        invoice_ids: List[int] = []
        try:
            inv_id = int(
                _tool_payload(
                    await session.call_tool(
                        "create_supplier_invoice",
                        {
                            "supplier_id": soc_id,
                            "ref_supplier": f"REF-{tag}",
                            "date": "2026-01-15",
                            "lines": [{"description": f"line one {tag}", "pu_ht": 100, "qty": 2, "tva_tx": 20}],
                        },
                    )
                )
            )
            invoice_ids.append(inv_id)

            line_id = int(
                _tool_payload(
                    await session.call_tool(
                        "add_supplier_invoice_line",
                        {"invoice_id": inv_id, "description": f"line two {tag}", "pu_ht": 50, "qty": 1, "tva_tx": 20},
                    )
                )
            )
            _tool_payload(
                await session.call_tool("update_supplier_invoice_line", {"invoice_id": inv_id, "line_id": line_id, "pu_ht": 60})
            )

            validated = _tool_payload(await session.call_tool("validate_supplier_invoice", {"invoice_id": inv_id}))
            assert "SI" in json.dumps(validated), f"validate should return the final SI ref: {validated}"

            async def read_back() -> dict:
                listed = _tool_payload(await session.call_tool("get_supplier_invoices", {"supplier_id": soc_id}))
                mine = [i for i in listed if i.get("id") == inv_id]
                assert len(mine) == 1, f"invoice {inv_id} not found in list: {listed}"
                return mine[0]

            inv = await read_back()
            assert inv["ref"].startswith("SI"), inv
            assert inv["ref_supplier"] == f"REF-{tag}", inv
            assert inv["status"] == "unpaid", inv
            assert float(inv["total_ht"]) == pytest.approx(260.0), inv  # 2*100 + 1*60
            assert "lines" not in inv and "array_options" not in inv, "list must be a compact summary, not raw"

            # Adding a line to a validated invoice must be an explicit error, not a silent no-op.
            error = _error_text(
                await session.call_tool(
                    "add_supplier_invoice_line",
                    {"invoice_id": inv_id, "description": f"late {tag}", "pu_ht": 5, "qty": 1},
                )
            )
            assert "draft" in error.lower(), f"error should say the invoice is not a draft: {error}"

            # Correction cycle: settodraft (ref kept), add a line, re-validate (ref kept).
            _tool_payload(await session.call_tool("set_supplier_invoice_to_draft", {"invoice_id": inv_id}))
            inv = await read_back()
            assert inv["status"] == "draft" and inv["ref"].startswith("SI"), inv
            _tool_payload(
                await session.call_tool(
                    "add_supplier_invoice_line",
                    {"invoice_id": inv_id, "description": f"line three {tag}", "pu_ht": 10, "qty": 1, "tva_tx": 20},
                )
            )
            validated_again = _tool_payload(await session.call_tool("validate_supplier_invoice", {"invoice_id": inv_id}))
            assert inv["ref"] in json.dumps(validated_again), f"re-validation should keep the SI ref: {validated_again}"
            inv = await read_back()
            assert inv["status"] == "unpaid" and float(inv["total_ht"]) == pytest.approx(270.0), inv

            # Mark paid, then update label/ref_supplier on the paid invoice (idempotent).
            _tool_payload(await session.call_tool("set_supplier_invoice_paid", {"invoice_id": inv_id}))
            inv = await read_back()
            assert inv["status"] == "paid" and inv["paid"] is True, inv
            _tool_payload(
                await session.call_tool(
                    "update_supplier_invoice",
                    {"invoice_id": inv_id, "label": f"LBL-{tag}", "ref_supplier": f"REF2-{tag}"},
                )
            )
            inv = await read_back()
            assert inv["ref_supplier"] == f"REF2-{tag}" and inv["status"] == "paid", inv
        finally:
            await _cleanup(config, soc_id, invoice_ids)


@pytest.mark.asyncio
async def test_line_tools_reject_desc_and_subprice():
    """``desc``/``subprice`` are rejected on the line tools.

    The raw API silently ignores them (empty description, price 0); the tools
    must reject them instead. The schema also forbids them
    (``additionalProperties: false``), so the client-side guard is checked
    directly too.
    """
    config = _config()
    tag = uuid.uuid4().hex[:8]
    async with mcp_session() as (session, _init_result):
        soc_id = int(_tool_payload(await session.call_tool("create_customer", {"name": f"SUB02D-{tag}", "type": 2})))
        invoice_ids: List[int] = []
        try:
            inv_id = int(
                _tool_payload(
                    await session.call_tool(
                        "create_supplier_invoice",
                        {"supplier_id": soc_id, "ref_supplier": f"RD-{tag}", "date": "2026-01-15"},
                    )
                )
            )
            invoice_ids.append(inv_id)

            for tool, extra in (
                ("add_supplier_invoice_line", {"invoice_id": inv_id}),
                ("update_supplier_invoice_line", {"invoice_id": inv_id, "line_id": 1}),
            ):
                args = {**extra, "desc": "WRONG", "subprice": 999, "description": f"ok {tag}", "pu_ht": 10, "qty": 1}
                error = _error_text(await session.call_tool(tool, args))
                assert "desc" in error and "subprice" in error, f"{tool} should name the rejected fields: {error}"

            # Client-level guard (bypasses the JSON schema): must raise, not send.
            async with DolibarrClient(config) as client:
                with pytest.raises(DolibarrAPIError) as exc_info:
                    await client.add_supplier_invoice_line(inv_id, desc="WRONG", subprice=999, description="x", pu_ht=1, qty=1)
                assert "desc" in str(exc_info.value) and "subprice" in str(exc_info.value)
        finally:
            await _cleanup(config, soc_id, invoice_ids)


@pytest.mark.asyncio
async def test_get_supplier_invoices_compact_summary_single_condition():
    """Listing is compact, filterable by one condition, and includes ref_supplier.

    - summaries carry ``ref_supplier`` and never the raw object,
    - ``supplier_id`` and ``ref_supplier`` filters work (``t.``-prefixed single
      sqlfilter condition),
    - passing several filter conditions at once is an explicit error (Dolibarr
      returns 0 rows for multi-condition sqlfilters),
    - an unfiltered call still returns compact summaries, never a raw dump.
    """
    config = _config()
    tag = uuid.uuid4().hex[:8]
    async with mcp_session() as (session, _init_result):
        soc_id = int(_tool_payload(await session.call_tool("create_customer", {"name": f"SUB02L-{tag}", "type": 2})))
        invoice_ids: List[int] = []
        try:
            for suffix in ("A", "B"):
                inv_id = int(
                    _tool_payload(
                        await session.call_tool(
                            "create_supplier_invoice",
                            {
                                "supplier_id": soc_id,
                                "ref_supplier": f"RL-{tag}-{suffix}",
                                "date": "2026-01-15",
                                "lines": [{"description": f"l {suffix}", "pu_ht": 10, "qty": 1, "tva_tx": 20}],
                            },
                        )
                    )
                )
                invoice_ids.append(inv_id)

            allowed_keys = {
                "id",
                "ref",
                "ref_supplier",
                "socid",
                "type",
                "date",
                "due_date",
                "total_ht",
                "total_tva",
                "total_ttc",
                "status",
                "paid",
                "remain_to_pay",
            }
            listed = _tool_payload(await session.call_tool("get_supplier_invoices", {"supplier_id": soc_id, "limit": 50}))
            assert isinstance(listed, list) and listed
            mine = [i for i in listed if i.get("ref_supplier", "").startswith(f"RL-{tag}-")]
            assert len(mine) == 2, f"expected the two fixture invoices: {listed}"
            for item in listed:
                assert set(item.keys()) <= allowed_keys, f"summary leaked raw fields: {sorted(item.keys())}"
                assert "lines" not in item and "array_options" not in item

            by_ref = _tool_payload(await session.call_tool("get_supplier_invoices", {"ref_supplier": f"RL-{tag}-A"}))
            assert [i["id"] for i in by_ref] == [invoice_ids[0]], by_ref

            error = _error_text(
                await session.call_tool("get_supplier_invoices", {"supplier_id": soc_id, "ref_supplier": f"RL-{tag}-A"})
            )
            assert "single" in error.lower() or "one condition" in error.lower(), error

            unfiltered = _tool_payload(await session.call_tool("get_supplier_invoices", {"limit": 5}))
            assert isinstance(unfiltered, list) and unfiltered
            for item in unfiltered:
                assert set(item.keys()) <= allowed_keys, f"unfiltered list must stay compact: {sorted(item.keys())}"
        finally:
            await _cleanup(config, soc_id, invoice_ids)


@pytest.mark.asyncio
async def test_supplier_credit_note_type_2():
    """``type=2`` creates a credit note: ``SA...`` ref and negative amounts."""
    config = _config()
    tag = uuid.uuid4().hex[:8]
    async with mcp_session() as (session, _init_result):
        soc_id = int(_tool_payload(await session.call_tool("create_customer", {"name": f"SUB02C-{tag}", "type": 2})))
        invoice_ids: List[int] = []
        try:
            cn_id = int(
                _tool_payload(
                    await session.call_tool(
                        "create_supplier_invoice",
                        {
                            "supplier_id": soc_id,
                            "ref_supplier": f"CN-{tag}",
                            "date": "2026-01-15",
                            "type": 2,
                            "lines": [{"description": f"credit {tag}", "pu_ht": 50, "qty": 1, "tva_tx": 20}],
                        },
                    )
                )
            )
            invoice_ids.append(cn_id)
            validated = _tool_payload(await session.call_tool("validate_supplier_invoice", {"invoice_id": cn_id}))
            assert "SA" in json.dumps(validated), f"credit note should get an SA ref: {validated}"

            listed = _tool_payload(await session.call_tool("get_supplier_invoices", {"supplier_id": soc_id}))
            mine = [i for i in listed if i.get("id") == cn_id]
            assert len(mine) == 1
            assert mine[0]["ref"].startswith("SA"), mine[0]
            assert mine[0]["type"] == "credit_note", mine[0]
            assert float(mine[0]["total_ht"]) == pytest.approx(-50.0), mine[0]
        finally:
            await _cleanup(config, soc_id, invoice_ids)
