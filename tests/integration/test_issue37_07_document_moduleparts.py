"""Integration tests for sub-issue 7 of #37: get_documents / download_document
for supplier invoices, tax (social charges) and bank statements.

Verified API contract on the instance (Dolibarr 21.0.0):

- ``GET /documents`` (list) only implements a fixed set of moduleparts
  (invoice/facture, supplier_invoice, order, propal, thirdparty, ...).
  ``tax`` and ``bank`` answer 500 "Modulepart ... not implemented yet", and
  the ECM listing endpoints (ecmfiles, ecmdocuments, ecmdirectories,
  attachments) do not exist (501). So listing for ``tax`` / ``bank`` must
  degrade explicitly: return the modulepart, the path convention and the
  object refs so the agent can still locate files, not an opaque 500.
- For ``supplier_invoice`` the listing entry carries ``relativename`` (the
  bare file name, ``name`` is null) and ``level1name`` = ref only; the
  ``original_file`` that ``GET /documents/download`` expects needs the
  numeric prefix: ``{id mod 10}/{floor(id/10) mod 10}/{ref}/{filename}``
  (same derivation as upload_document).
- ``GET /documents/download`` accepts ``invoice_supplier`` (not
  ``supplier_invoice``, which gets 403) for supplier invoices, and accepts
  ``tax`` (original_file = ``{charge rowid}/{filename}``) and ``bank``
  (original_file = ``{account_id}/statement/{num}/{filename}``).
- ``GET /documents`` answers 404 "does not return any document" when the
  object has no attached file: that is an empty listing, not an error.

Acceptance criteria encoded here:

- A file attached to a supplier invoice can be listed (with the numeric-prefix
  ``original_file``) and downloaded through the tools.
- Files attached to a social charge (``tax``) and to a bank statement
  (``bank``) can be listed (explicit degradation with path convention + refs)
  and downloaded through the tools.

Marked ``integration``: needs ``DOLIBARR_URL`` and ``DOLIBARR_API_KEY``
pointing at a reachable instance. Fixtures are uniquely named and cleaned up
so sequential runs on a shared instance do not collide.
"""

import base64
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


async def _skip_if_no_social_contributions(config: Config) -> None:
    """Skip when the instance lacks the /socialcontributions API.

    The CI workflow pins DOLIBARR_TEST_REF=21.0.0, which ships no
    ``api_socialcontributions`` class, so ``GET /socialcontributions`` answers
    HTTP 501 "API not found". On instances that do ship it, this returns
    normally and the test stays active.
    """
    async with DolibarrClient(config) as client:
        try:
            await client.request("GET", "socialcontributions", params={"limit": 1})
        except DolibarrAPIError as exc:
            if exc.status_code in (404, 501):
                pytest.skip(
                    f"/socialcontributions not available on this Dolibarr instance (HTTP {exc.status_code}: {exc.message})"
                )
            raise


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


def _downloaded_blob(result) -> bytes:
    """Extract and decode the binary blob of a download_document tool result."""
    assert not result.isError, f"download failed: {result.content}"
    for block in result.content:
        resource = getattr(block, "resource", None)
        if resource is not None and getattr(resource, "blob", None):
            return base64.b64decode(resource.blob)
    raise AssertionError(f"no embedded resource in download result: {result.content}")


def _payload(tag: str) -> bytes:
    """Binary payload (stored verbatim, returned as an embedded resource)."""
    return b"\x89SUB07\n" + os.urandom(256) + tag.encode()


async def _first_bank_account_id(config: Config) -> int:
    """Look up the first bank account id through the raw client (fixture setup)."""
    async with DolibarrClient(config) as client:
        accounts = await client.request("GET", "bankaccounts", params={"limit": 5})
    assert isinstance(accounts, list) and accounts, "the bank module must be enabled with one account"
    return int(accounts[0]["id"])


async def _delete_supplier_invoice_and_thirdparty(config: Config, soc_id: int, invoice_ids: List[int]) -> None:
    """Delete the fixture invoices and third party through the raw client."""
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


async def _delete_social_contribution(config: Config, contribution_id: int) -> None:
    """Delete the fixture social charge through the raw client (best effort)."""
    async with DolibarrClient(config) as client:
        try:
            await client.request("DELETE", f"socialcontributions/{contribution_id}")
        except DolibarrAPIError:
            pass


@pytest.mark.asyncio
async def test_supplier_invoice_list_and_download_with_numeric_prefix_path():
    """Acceptance: a file attached to a supplier invoice is listed with the
    numeric-prefix ``original_file`` and downloaded through the tools."""
    config = _config()
    tag = uuid.uuid4().hex[:8]
    async with mcp_session() as (session, _init_result):
        soc_id = int(_tool_payload(await session.call_tool("create_customer", {"name": f"SUB07-{tag}", "type": 2})))
        invoice_ids: List[int] = []
        try:
            inv_id = int(
                _tool_payload(
                    await session.call_tool(
                        "create_supplier_invoice",
                        {
                            "supplier_id": soc_id,
                            "ref_supplier": f"DOC07-{tag}",
                            "date": "2026-02-10",
                            "lines": [{"description": f"sub07 line {tag}", "pu_ht": 50, "qty": 1, "tva_tx": 20}],
                        },
                    )
                )
            )
            invoice_ids.append(inv_id)
            _tool_payload(await session.call_tool("validate_supplier_invoice", {"invoice_id": inv_id}))
            listed = _tool_payload(await session.call_tool("get_supplier_invoices", {"supplier_id": soc_id}))
            inv_ref = next(i["ref"] for i in listed if i.get("id") == inv_id)

            filename = f"SUB07-{tag}.bin"
            content = _payload(tag)
            expected_path = f"{inv_id % 10}/{(inv_id // 10) % 10}/{inv_ref}/{filename}"

            # 0) An object without attached files lists as empty, not as an error.
            docs = _tool_payload(await session.call_tool("get_documents", {"modulepart": "supplier_invoice", "id": inv_id}))
            assert docs == [], docs

            # Attach the file through the sub-issue 6 tool.
            uploaded = _tool_payload(
                await session.call_tool(
                    "upload_document",
                    {
                        "modulepart": "supplier_invoice",
                        "ref": inv_ref,
                        "id": inv_id,
                        "filename": filename,
                        "filecontent": base64.b64encode(content).decode("ascii"),
                        "overwrite": True,
                    },
                )
            )
            assert uploaded["original_file"] == expected_path, uploaded

            # 1) get_documents lists the file with the numeric-prefix original_file.
            docs = _tool_payload(await session.call_tool("get_documents", {"modulepart": "supplier_invoice", "id": inv_id}))
            assert isinstance(docs, list), docs
            entry = next((d for d in docs if d.get("name") == filename), None)
            assert entry is not None, f"{filename} not listed in {docs}"
            assert entry["original_file"] == expected_path, entry

            # 2) download_document accepts modulepart 'supplier_invoice' and the listed path.
            downloaded = await session.call_tool(
                "download_document", {"modulepart": "supplier_invoice", "original_file": entry["original_file"]}
            )
            assert _downloaded_blob(downloaded) == content
        finally:
            # Clean up the attached file, then the fixtures.
            try:
                await session.call_tool("delete_document", {"modulepart": "supplier_invoice", "original_file": expected_path})
            except Exception:
                pass
            await _delete_supplier_invoice_and_thirdparty(config, soc_id, invoice_ids)


@pytest.mark.asyncio
async def test_tax_social_charge_list_degrades_and_download_works():
    """Acceptance: a file attached to a social charge can be located through
    the degraded listing (path convention + rowid) and downloaded."""
    config = _config()
    await _skip_if_no_social_contributions(config)
    tag = uuid.uuid4().hex[:8]
    async with mcp_session() as (session, _init_result):
        charge_id = int(
            _tool_payload(
                await session.call_tool(
                    "create_social_contribution",
                    {
                        "label": f"SUB07-{tag}",
                        "type": 1,
                        "amount": 75,
                        "date_ech": "2026-07-05",
                        "period": "2026-07-01",
                    },
                )
            )
        )
        assert charge_id > 0
        try:
            filename = f"SUB07-tax-{tag}.bin"
            content = _payload(tag)
            expected_path = f"{charge_id}/{filename}"

            uploaded = _tool_payload(
                await session.call_tool(
                    "upload_document",
                    {
                        "modulepart": "tax",
                        "subdir": str(charge_id),
                        "filename": filename,
                        "filecontent": base64.b64encode(content).decode("ascii"),
                        "overwrite": True,
                    },
                )
            )
            assert uploaded["original_file"] == expected_path, uploaded

            # 1) Listing degrades explicitly: no opaque 500, but the modulepart,
            #    the path convention and the object ref (social-charge rowid).
            listing = _tool_payload(await session.call_tool("get_documents", {"modulepart": "tax", "id": charge_id}))
            assert isinstance(listing, dict), listing
            assert listing.get("modulepart") == "tax", listing
            assert listing.get("listing") == "unavailable", listing
            assert listing.get("id") == charge_id, listing
            assert "rowid" in (listing.get("path_convention") or ""), listing

            # 2) download_document works with original_file = '{rowid}/{filename}'.
            downloaded = await session.call_tool("download_document", {"modulepart": "tax", "original_file": expected_path})
            assert _downloaded_blob(downloaded) == content
        finally:
            try:
                await session.call_tool("delete_document", {"modulepart": "tax", "original_file": expected_path})
            except Exception:
                pass
            await _delete_social_contribution(config, charge_id)


@pytest.mark.asyncio
async def test_bank_statement_list_degrades_and_download_works():
    """Acceptance: a file attached to a bank statement can be located through
    the degraded listing (path convention + account/statement refs) and
    downloaded."""
    config = _config()
    tag = uuid.uuid4().hex[:8]
    account_id = await _first_bank_account_id(config)
    async with mcp_session() as (session, _init_result):
        num = f"2607{tag[:2]}"  # statement number YYYYMM
        subdir = f"{account_id}/statement/{num}"
        filename = f"SUB07-bank-{tag}.bin"
        content = _payload(tag)
        expected_path = f"{subdir}/{filename}"
        try:
            uploaded = _tool_payload(
                await session.call_tool(
                    "upload_document",
                    {
                        "modulepart": "bank",
                        "subdir": subdir,
                        "filename": filename,
                        "filecontent": base64.b64encode(content).decode("ascii"),
                        "overwrite": True,
                    },
                )
            )
            assert uploaded["original_file"] == expected_path, uploaded

            # 1) Listing degrades explicitly with the bank path convention.
            listing = _tool_payload(
                await session.call_tool("get_documents", {"modulepart": "bank", "id": account_id, "subdir": subdir})
            )
            assert isinstance(listing, dict), listing
            assert listing.get("modulepart") == "bank", listing
            assert listing.get("listing") == "unavailable", listing
            assert listing.get("id") == account_id, listing
            assert listing.get("subdir") == subdir, listing
            assert "statement" in (listing.get("path_convention") or ""), listing

            # 2) download_document works with original_file = '{account}/statement/{num}/{filename}'.
            downloaded = await session.call_tool("download_document", {"modulepart": "bank", "original_file": expected_path})
            assert _downloaded_blob(downloaded) == content
        finally:
            try:
                await session.call_tool("delete_document", {"modulepart": "bank", "original_file": expected_path})
            except Exception:
                pass
