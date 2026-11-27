"""Integration tests for sub-issue 6 of #37: upload_document and delete_document.

Verified API contract on the instance (Dolibarr 21.0.0):

- ``POST /documents/upload`` takes ALL fields in the JSON body: ``modulepart``,
  ``ref`` (or ``subdir``), ``filename``, ``filecontent`` (base64),
  ``fileencoding='base64'``, ``overwriteifexists=1``. It returns the created
  file name (a plain string). A ~1 MB file (1.4 MB of base64) goes through
  the JSON body; the query string would fail beyond ~8 KB.
- Re-uploading an existing file without ``overwriteifexists=1`` does not
  replace it (400 "already exists" here; a silent no-op elsewhere), so
  ``overwrite=True`` must map to ``overwriteifexists=1``.
- Supplier invoice paths carry a numeric prefix derived from the Dolibarr
  id: ``{id mod 10}/{floor(id/10) mod 10}/{ref}/{filename}``. On 21.0.0,
  ``GET /documents/download`` and ``DELETE /documents`` accept
  ``invoice_supplier`` for that module (``supplier_invoice`` is only valid
  for the list/upload endpoints), so delete_document normalizes it.
- ``tax`` uses ``subdir`` = social-charge rowid, ``bank`` uses
  ``subdir`` = ``{account_id}/statement/{num}`` (statement number YYYYMM).
- ``DELETE /documents`` with ``modulepart`` + ``original_file`` returns 404
  "File not found" for an already-deleted file; the tool treats that as
  success.

Acceptance criteria encoded here:

- A ~1 MB PDF is attached to a supplier invoice through the tool (JSON body,
  no query-string transport).
- Re-upload with ``overwrite=True`` replaces the file instead of a no-op.
- The computed ``original_file`` matches what ``GET /documents/download``
  expects, verified by downloading and comparing bytes.
- ``delete_document`` succeeds, and succeeds again on the already-deleted
  file (404 treated as success).

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


async def _cleanup(config: Config, soc_id: int, invoice_ids: List[int]) -> None:
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


def _make_pdf(size_bytes: int = 1024 * 1024) -> bytes:
    """A ~1 MB PDF-flavoured payload (the API stores bytes verbatim)."""
    return b"%PDF-1.4\n" + os.urandom(size_bytes) + b"\n%%EOF\n"


@pytest.mark.asyncio
async def test_upload_replace_download_delete_supplier_invoice_pdf():
    """Acceptance: 1 MB PDF on a supplier invoice, replace on re-upload, path
    matches download, delete is idempotent (404 == success)."""
    config = _config()
    tag = uuid.uuid4().hex[:8]
    async with mcp_session() as (session, _init_result):
        soc_id = int(_tool_payload(await session.call_tool("create_customer", {"name": f"SUB06-{tag}", "type": 2})))
        invoice_ids: List[int] = []
        try:
            inv_id = int(
                _tool_payload(
                    await session.call_tool(
                        "create_supplier_invoice",
                        {
                            "supplier_id": soc_id,
                            "ref_supplier": f"DOC-{tag}",
                            "date": "2026-01-15",
                            "lines": [{"description": f"doc line {tag}", "pu_ht": 100, "qty": 1, "tva_tx": 20}],
                        },
                    )
                )
            )
            invoice_ids.append(inv_id)
            _tool_payload(await session.call_tool("validate_supplier_invoice", {"invoice_id": inv_id}))
            listed = _tool_payload(await session.call_tool("get_supplier_invoices", {"supplier_id": soc_id}))
            inv = next(i for i in listed if i.get("id") == inv_id)
            inv_ref = inv["ref"]
            assert inv_ref.startswith("SI"), inv

            filename = f"SUB06-{tag}.pdf"
            pdf_v1 = _make_pdf()
            expected_path = f"{inv_id % 10}/{(inv_id // 10) % 10}/{inv_ref}/{filename}"

            # 1) Upload the ~1 MB PDF through the tool (JSON body, no query string).
            uploaded = _tool_payload(
                await session.call_tool(
                    "upload_document",
                    {
                        "modulepart": "supplier_invoice",
                        "ref": inv_ref,
                        "id": inv_id,
                        "filename": filename,
                        "filecontent": base64.b64encode(pdf_v1).decode("ascii"),
                        "overwrite": True,
                    },
                )
            )
            assert uploaded["filename"] == filename, uploaded
            assert uploaded["original_file"] == expected_path, uploaded

            # 2) The computed path is what GET /documents/download expects.
            #    (On 21.0.0 the download endpoint names the module 'invoice_supplier'.)
            downloaded = await session.call_tool(
                "download_document", {"modulepart": "invoice_supplier", "original_file": expected_path}
            )
            assert base64.b64encode(_downloaded_blob(downloaded)).decode() == base64.b64encode(pdf_v1).decode()

            # 3) Re-upload with overwrite=True replaces instead of a silent no-op.
            pdf_v2 = b"%PDF-1.4\n" + os.urandom(1024 * 1024) + b"\n%%EOF\n"
            reuploaded = _tool_payload(
                await session.call_tool(
                    "upload_document",
                    {
                        "modulepart": "supplier_invoice",
                        "ref": inv_ref,
                        "id": inv_id,
                        "filename": filename,
                        "filecontent": base64.b64encode(pdf_v2).decode("ascii"),
                        "overwrite": True,
                    },
                )
            )
            assert reuploaded["original_file"] == expected_path, reuploaded
            downloaded = await session.call_tool(
                "download_document", {"modulepart": "invoice_supplier", "original_file": expected_path}
            )
            assert _downloaded_blob(downloaded) == pdf_v2, "re-upload must replace the stored file"

            # 4) delete_document succeeds; deleting again (404) is success too.
            deleted = _tool_payload(
                await session.call_tool("delete_document", {"modulepart": "supplier_invoice", "original_file": expected_path})
            )
            assert "success" in deleted, deleted
            deleted_again = _tool_payload(
                await session.call_tool("delete_document", {"modulepart": "supplier_invoice", "original_file": expected_path})
            )
            assert "success" in deleted_again, deleted_again
        finally:
            await _cleanup(config, soc_id, invoice_ids)


@pytest.mark.asyncio
async def test_upload_document_subdir_path_conventions_and_delete():
    """``tax`` (subdir = social-charge rowid) and ``bank`` (subdir =
    ``{account_id}/statement/{num}``) path derivation, plus delete cleanup."""
    _config()
    tag = uuid.uuid4().hex[:8]
    async with mcp_session() as (session, _init_result):
        content = base64.b64encode(f"sub06 {tag}".encode()).decode("ascii")

        tax_subdir = f"9{tag[:6]}"
        tax_file = f"tax-{tag}.txt"
        uploaded_tax = _tool_payload(
            await session.call_tool(
                "upload_document",
                {
                    "modulepart": "tax",
                    "subdir": tax_subdir,
                    "filename": tax_file,
                    "filecontent": content,
                    "overwrite": True,
                },
            )
        )
        assert uploaded_tax["original_file"] == f"{tax_subdir}/{tax_file}", uploaded_tax

        bank_subdir = f"1/statement/2601{tag[:2]}"
        bank_file = f"bank-{tag}.txt"
        uploaded_bank = _tool_payload(
            await session.call_tool(
                "upload_document",
                {
                    "modulepart": "bank",
                    "subdir": bank_subdir,
                    "filename": bank_file,
                    "filecontent": content,
                    "overwrite": True,
                },
            )
        )
        assert uploaded_bank["original_file"] == f"{bank_subdir}/{bank_file}", uploaded_bank

        for modulepart, original_file in (
            ("tax", f"{tax_subdir}/{tax_file}"),
            ("bank", f"{bank_subdir}/{bank_file}"),
        ):
            deleted = _tool_payload(
                await session.call_tool("delete_document", {"modulepart": modulepart, "original_file": original_file})
            )
            assert "success" in deleted, deleted
            # 404 "File not found" on re-delete counts as success.
            again = _tool_payload(
                await session.call_tool("delete_document", {"modulepart": modulepart, "original_file": original_file})
            )
            assert "success" in again, again
