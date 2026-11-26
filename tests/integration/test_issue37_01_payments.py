"""Integration tests for sub-issue 1 of #37: supplier payments and payment reads.

Verified API contract on the instance (Dolibarr 21.0.0):

- ``POST /invoices/{id}/payments`` 500s on a supplier invoice id; the customer
  endpoint takes ``datepaye``, ``paymentid`` (numeric mode id), ``closepaidinvoices``
  ('yes'/'no'), ``accountid`` and pays the full remaining amount (no ``amount``).
- ``POST /supplierinvoices/{id}/payments`` accepts its fields ONLY as query
  parameters: ``datepaye`` as integer Unix timestamp, ``payment_mode_id`` numeric
  (resolved from ``GET /setup/dictionary/payment_types``), ``closepaidinvoices``
  as the strings 'yes'/'no', plus ``accountid`` and ``amount``. Returns the
  payment id.
- ``GET /invoices/{id}/payments`` and ``GET /supplierinvoices/{id}/payments``
  return rows with ``amount``, ``type`` (mode code), ``date``, ``num``, ``ref``
  and ``fk_bank_line``.

Acceptance criteria encoded here:

- A supplier invoice can be paid through ``pay_supplier_invoice`` with mode
  ``VIR`` and closes (``closepaidinvoices``) when the amount balances it.
- Calling ``pay_invoice`` on a supplier invoice fails with a clear message
  pointing to ``pay_supplier_invoice`` (and ``direction='supplier'`` succeeds).
- ``get_invoice_payments`` returns payment dates/amounts/mode/account without
  a raw API call, for both directions.
- A dictionary code (``VIR``) and a numeric ``payment_mode_id`` are both accepted.

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


async def _first_bank_account_id(config: Config) -> int:
    """Look up the first bank account id through the raw client (fixture setup)."""
    async with DolibarrClient(config) as client:
        accounts = await client.request("GET", "bankaccounts", params={"limit": 5})
    assert isinstance(accounts, list) and accounts, "the bank module must be enabled with one account"
    return int(accounts[0]["id"])


async def _is_customer_invoice(config: Config, invoice_id: int) -> bool:
    """True when the id exists in the customer invoice table (raw client check)."""
    async with DolibarrClient(config) as client:
        try:
            await client.request("GET", f"invoices/{invoice_id}")
            return True
        except DolibarrAPIError:
            return False


async def _cleanup_supplier(config: Config, soc_id: int, invoice_ids: List[int]) -> None:
    """Delete the fixture supplier invoices and third party (best effort)."""
    async with DolibarrClient(config) as client:
        for invoice_id in invoice_ids:
            try:
                await client.request("DELETE", f"supplierinvoices/{invoice_id}")
            except DolibarrAPIError:
                try:
                    await client.request("PUT", f"supplierinvoices/{invoice_id}", data={"status": 0})
                    await client.request("DELETE", f"supplierinvoices/{invoice_id}")
                except DolibarrAPIError:
                    pass
        try:
            await client.request("DELETE", f"thirdparties/{soc_id}")
        except DolibarrAPIError:
            pass


async def _cleanup_customer(config: Config, soc_id: int, invoice_ids: List[int]) -> None:
    """Delete the fixture customer invoices and third party (best effort)."""
    async with DolibarrClient(config) as client:
        for invoice_id in invoice_ids:
            try:
                await client.request("DELETE", f"invoices/{invoice_id}")
            except DolibarrAPIError:
                try:
                    await client.request("PUT", f"invoices/{invoice_id}", data={"status": 0})
                    await client.request("DELETE", f"invoices/{invoice_id}")
                except DolibarrAPIError:
                    pass
        try:
            await client.request("DELETE", f"thirdparties/{soc_id}")
        except DolibarrAPIError:
            pass


async def _make_validated_supplier_invoice(session, soc_id: int, tag: str) -> int:
    """Create + line + validate a supplier invoice through the MCP tools."""
    inv_id = int(
        _tool_payload(
            await session.call_tool(
                "create_supplier_invoice",
                {
                    "supplier_id": soc_id,
                    "ref_supplier": f"PAY-{tag}",
                    "date": "2026-01-15",
                    "lines": [{"description": f"payable {tag}", "pu_ht": 100, "qty": 1, "tva_tx": 20}],
                },
            )
        )
    )
    _tool_payload(await session.call_tool("validate_supplier_invoice", {"invoice_id": inv_id}))
    return inv_id


@pytest.mark.asyncio
async def test_pay_supplier_invoice_with_vir_closes_invoice():
    """``pay_supplier_invoice`` with mode ``VIR`` records the payment and closes the invoice.

    - payment id is returned,
    - ``get_invoice_payments(direction='supplier')`` reads back date, amount, mode,
      ``num_payment`` and bank account without a raw API call,
    - the invoice reads back as ``paid`` when the amount balances (100 HT + 20% VAT).
    """
    config = _config()
    tag = uuid.uuid4().hex[:8]
    account_id = await _first_bank_account_id(config)
    async with mcp_session() as (session, _init_result):
        soc_id = int(_tool_payload(await session.call_tool("create_customer", {"name": f"SUB01-{tag}", "type": 2})))
        invoice_ids: List[int] = []
        try:
            inv_id = await _make_validated_supplier_invoice(session, soc_id, tag)
            invoice_ids.append(inv_id)

            payment_id = _tool_payload(
                await session.call_tool(
                    "pay_supplier_invoice",
                    {
                        "invoice_id": inv_id,
                        "amount": 120,
                        "payment_mode": "VIR",
                        "accountid": account_id,
                        "payment_date": "2026-01-20",
                        "closepaidinvoices": True,
                        "comment": f"full payment {tag}",
                    },
                )
            )
            assert int(payment_id) > 0, f"expected the new payment id, got: {payment_id}"

            payments = _tool_payload(
                await session.call_tool("get_invoice_payments", {"invoice_id": inv_id, "direction": "supplier"})
            )
            assert isinstance(payments, list) and len(payments) == 1, payments
            payment = payments[0]
            assert float(payment["amount"]) == pytest.approx(120.0), payment
            assert payment["mode"] == "VIR", payment
            assert payment.get("date"), f"payment date must be returned: {payment}"
            assert "num_payment" in payment, payment
            assert int(payment["bank_account_id"]) == account_id, payment

            listed = _tool_payload(await session.call_tool("get_supplier_invoices", {"supplier_id": soc_id}))
            mine = [i for i in listed if i.get("id") == inv_id]
            assert len(mine) == 1 and mine[0]["status"] == "paid", f"invoice should be paid: {listed}"
        finally:
            await _cleanup_supplier(config, soc_id, invoice_ids)


@pytest.mark.asyncio
async def test_pay_invoice_on_supplier_invoice_fails_with_pointer():
    """``pay_invoice`` never reaches a supplier invoice.

    - calling it on a supplier invoice id fails with a message naming
      ``pay_supplier_invoice``,
    - ``pay_invoice`` with ``direction='supplier'`` succeeds instead.
    """
    config = _config()
    tag = uuid.uuid4().hex[:8]
    account_id = await _first_bank_account_id(config)
    async with mcp_session() as (session, _init_result):
        soc_id = int(_tool_payload(await session.call_tool("create_customer", {"name": f"SUB01G-{tag}", "type": 2})))
        invoice_ids: List[int] = []
        try:
            # The guard detects supplier-only ids; retry if the fresh supplier id
            # collides with an existing customer invoice id (shared instance).
            inv_id = 0
            for _attempt in range(5):
                candidate = await _make_validated_supplier_invoice(session, soc_id, f"{tag}{_attempt}")
                if not await _is_customer_invoice(config, candidate):
                    inv_id = candidate
                    invoice_ids.append(inv_id)
                    break
                invoice_ids.append(candidate)
                await _cleanup_supplier(config, soc_id, [candidate])
                invoice_ids.remove(candidate)
            assert inv_id, "could not create a supplier-only invoice id"

            error = _error_text(
                await session.call_tool(
                    "pay_invoice",
                    {"invoice_id": inv_id, "payment_mode": "VIR", "accountid": account_id, "amount": 120},
                )
            )
            assert "pay_supplier_invoice" in error, f"error must point to the supplier tool: {error}"

            payment_id = _tool_payload(
                await session.call_tool(
                    "pay_invoice",
                    {
                        "invoice_id": inv_id,
                        "direction": "supplier",
                        "amount": 120,
                        "payment_mode": "VIR",
                        "accountid": account_id,
                        "closepaidinvoices": True,
                    },
                )
            )
            assert int(payment_id) > 0, payment_id
        finally:
            await _cleanup_supplier(config, soc_id, invoice_ids)


@pytest.mark.asyncio
async def test_pay_invoice_customer_with_numeric_mode_and_payment_read():
    """``pay_invoice`` pays a customer invoice; payments are readable per direction.

    Uses a numeric ``payment_mode_id`` resolved through ``get_dictionary``
    (instance-specific ids must not be hardcoded), and checks
    ``get_invoice_payments(direction='customer')``.
    """
    config = _config()
    tag = uuid.uuid4().hex[:8]
    account_id = await _first_bank_account_id(config)
    async with mcp_session() as (session, _init_result):
        soc_id = int(_tool_payload(await session.call_tool("create_customer", {"name": f"SUB01C-{tag}", "type": 1})))
        invoice_ids: List[int] = []
        try:
            inv_id = int(
                _tool_payload(
                    await session.call_tool(
                        "create_invoice",
                        {
                            "customer_id": soc_id,
                            "date": "2026-01-15",
                            "lines": [{"desc": f"service {tag}", "qty": 1, "subprice": 100, "vat": 20}],
                        },
                    )
                )
            )
            invoice_ids.append(inv_id)
            _tool_payload(await session.call_tool("validate_invoice", {"invoice_id": inv_id}))

            dictionary = _tool_payload(await session.call_tool("get_dictionary", {"name": "payment_types"}))
            vir_id = next(int(row["id"]) for row in dictionary if row.get("code") == "VIR")

            payment_id = _tool_payload(
                await session.call_tool(
                    "pay_invoice",
                    {
                        "invoice_id": inv_id,
                        "payment_mode": vir_id,
                        "accountid": account_id,
                        "closepaidinvoices": True,
                    },
                )
            )
            assert int(payment_id) > 0, payment_id

            payments = _tool_payload(
                await session.call_tool("get_invoice_payments", {"invoice_id": inv_id, "direction": "customer"})
            )
            assert isinstance(payments, list) and len(payments) == 1, payments
            payment = payments[0]
            assert float(payment["amount"]) == pytest.approx(120.0), payment
            assert payment["mode"] == "VIR", payment
            assert payment.get("date"), payment
            assert int(payment["bank_account_id"]) == account_id, payment

            # The supplier direction on a customer-only id reads empty, not an error.
            supplier_payments = _tool_payload(
                await session.call_tool("get_invoice_payments", {"invoice_id": inv_id, "direction": "supplier"})
            )
            assert supplier_payments == [], supplier_payments
        finally:
            await _cleanup_customer(config, soc_id, invoice_ids)
