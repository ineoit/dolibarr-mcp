"""Integration tests for sub-issue 10 of #37: fichinter (intervention) tools.

Verified API contract on the instance (Dolibarr 21.0.0):

- ``GET /interventions`` / ``GET /interventions/{id}`` return large objects;
  the line read side exposes ``desc``, ``date`` (Unix timestamp) and
  ``duration`` (seconds).
- ``POST /interventions`` requires ``socid``, ``fk_project`` and
  ``description`` (project-linked creation).
- ``POST /interventions/{id}/lines`` requires ``description`` (the write side
  rejects ``desc``), ``date`` (Unix timestamp) and the duration; on the pinned
  Dolibarr 21.0.0 the mandatory wire field for the duration is ``duree``
  (``duration`` alone answers a masked 400 "duree field missing"), so the
  client sends both spellings with the same value. An open sheet accepts
  lines dated on other days.

Acceptance criteria encoded here: an intervention line can be added and read
back with the correct description, date and duration, in one tool call each
way.

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

# Compact fields kept by get_interventions / get_intervention lines.
INTERVENTION_KEYS = {"id", "ref", "socid", "fk_project", "status", "description"}
LINE_KEYS = {"id", "desc", "date", "duration"}

# 2026-03-15 10:30:00 UTC, the line date used below (lines may be dated on
# any day while the sheet is open).
LINE_EPOCH = 1773570600
LINE_DURATION = 5400


async def _skip_if_no_interventions(config: Config) -> None:
    """Skip when the instance lacks the /interventions API.

    Same version-aware pattern as _skip_if_no_social_contributions: instances
    that ship no ``api_interventions`` class answer HTTP 404/501.
    """
    async with DolibarrClient(config) as client:
        try:
            await client.request("GET", "interventions", params={"limit": 1})
        except DolibarrAPIError as exc:
            if exc.status_code in (404, 501):
                pytest.skip(f"/interventions not available on this Dolibarr instance (HTTP {exc.status_code}: {exc.message})")
            raise


@pytest_asyncio.fixture(autouse=True)
async def _require_interventions_endpoint():
    await _skip_if_no_interventions(_config())


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


async def _create_project(config: Config, tag: str) -> int:
    """Create the fixture project through the raw client (fixture setup)."""
    async with DolibarrClient(config) as client:
        project_id = int(
            await client.request(
                "POST",
                "projects",
                data={"ref": f"SUB10P-{tag}", "title": f"SUB10 project {tag}", "socid": 1},
            )
        )
    assert project_id > 0
    return project_id


async def _cleanup(config: Config, project_id: int, intervention_ids: List[int]) -> None:
    """Delete fixture interventions then the project (best effort)."""
    async with DolibarrClient(config) as client:
        for intervention_id in intervention_ids:
            try:
                await client.request("DELETE", f"interventions/{intervention_id}")
            except DolibarrAPIError:
                pass
        try:
            await client.request("DELETE", f"projects/{project_id}")
        except DolibarrAPIError:
            pass


@pytest.mark.asyncio
async def test_create_get_and_compact_list_intervention():
    """``create_intervention`` links the sheet to the project; reads are compact.

    - ``create_intervention`` requires project_id/socid/description and the
      sheet is stored with the given ``fk_project``,
    - ``get_intervention`` returns the sheet with compact lines
      (``id``/``desc``/``date``/``duration`` only),
    - ``get_interventions`` returns compact summaries with a fixed key set.
    """
    config = _config()
    tag = uuid.uuid4().hex[:8]
    project_id = await _create_project(config, tag)
    intervention_ids: List[int] = []
    try:
        async with mcp_session() as (session, _init_result):
            intervention_id = int(
                _tool_payload(
                    await session.call_tool(
                        "create_intervention",
                        {
                            "project_id": project_id,
                            "socid": 1,
                            "description": f"SUB10 sheet {tag}",
                        },
                    )
                )
            )
            intervention_ids.append(intervention_id)
            assert intervention_id > 0, intervention_id

            sheet = _tool_payload(await session.call_tool("get_intervention", {"intervention_id": intervention_id}))
            assert int(sheet["id"]) == intervention_id, sheet
            assert int(sheet["fk_project"]) == project_id, sheet
            assert sheet["ref"], sheet
            assert isinstance(sheet["lines"], list), sheet
            for line in sheet["lines"]:
                assert set(line.keys()) == LINE_KEYS, line

            listing = _tool_payload(await session.call_tool("get_interventions", {"limit": 100}))
            assert isinstance(listing, list), listing
            match = [row for row in listing if int(row["id"]) == intervention_id]
            assert len(match) == 1, listing
            assert set(match[0].keys()) == INTERVENTION_KEYS, match[0]
            assert int(match[0]["fk_project"]) == project_id, match[0]
    finally:
        await _cleanup(config, project_id, intervention_ids)


@pytest.mark.asyncio
async def test_add_intervention_line_and_read_back():
    """Acceptance: a line is added and read back with description/date/duration.

    One ``add_intervention_line`` call with ``description`` / ``date`` (Unix
    timestamp) / ``duration`` (seconds), then one ``get_intervention`` call
    shows the line with ``desc`` == description, ``date`` == timestamp and
    ``duration`` == seconds.
    """
    config = _config()
    tag = uuid.uuid4().hex[:8]
    project_id = await _create_project(config, tag)
    intervention_ids: List[int] = []
    try:
        async with mcp_session() as (session, _init_result):
            intervention_id = int(
                _tool_payload(
                    await session.call_tool(
                        "create_intervention",
                        {"project_id": project_id, "socid": 1, "description": f"SUB10 sheet {tag}"},
                    )
                )
            )
            intervention_ids.append(intervention_id)

            _tool_payload(
                await session.call_tool(
                    "add_intervention_line",
                    {
                        "intervention_id": intervention_id,
                        "description": f"SUB10 line {tag}",
                        "date": LINE_EPOCH,
                        "duration": LINE_DURATION,
                    },
                )
            )

            sheet = _tool_payload(await session.call_tool("get_intervention", {"intervention_id": intervention_id}))
            lines = [line for line in sheet["lines"] if line["desc"] == f"SUB10 line {tag}"]
            assert len(lines) == 1, sheet["lines"]
            line = lines[0]
            assert set(line.keys()) == LINE_KEYS, line
            assert int(line["date"]) == LINE_EPOCH, line
            assert int(line["duration"]) == LINE_DURATION, line
    finally:
        await _cleanup(config, project_id, intervention_ids)
