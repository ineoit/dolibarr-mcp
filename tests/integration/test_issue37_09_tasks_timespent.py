"""Integration tests for sub-issue 9 of #37: project tasks and consumed time.

Verified API contract on the instance (Dolibarr 21.0.0):

- ``POST /tasks`` requires ``ref``, ``label`` and ``fk_project``; the given
  ``ref`` becomes the final task reference (no ``TK`` auto-generation).
- ``POST /tasks/{taskid}/addtimespent`` takes ``date`` as
  ``"YYYY-MM-DD HH:MM:SS"`` stored as UTC, ``duration`` in seconds,
  ``user_id`` and ``note``. Corrections: ``PUT /tasks/{taskid}/timespent/{id}``
  (same fields), ``DELETE`` on the same endpoint.
- Reading time spent: newer Dolibarr exposes ``GET /tasks/{id}/timespent``
  (rows whose fields are all prefixed ``timespent_line_``) and
  ``GET /projects/{id}/timespent`` (consolidated ``total_duration`` in
  element ``[0]``). Dolibarr 21 does not have those GET routes; it exposes
  the same data as ``GET /tasks/{id}?includetimespent=2`` (task object whose
  ``lines`` carry the ``timespent_line_*`` fields) and
  ``?includetimespent=1`` (summary ``timespent_total_duration``). The tools
  try the dedicated routes first and fall back to the ``includetimespent``
  reads.
- Reliability quirk: ``GET /projects/{id}/tasks`` can return an empty array
  although the task exists (observed on this instance), so project-scoped
  reads fall back to ``GET /tasks?sqlfilters=(t.fk_projet:=:<id>)`` plus
  direct per-task reads; a tool must not conclude "no task" from the
  project-scoped call alone.

Acceptance criteria encoded here: time can be added, read back and corrected
without raw calls, with the entry visible in the project's consumed time with
the intended date and duration.

Marked ``integration``: needs ``DOLIBARR_URL`` and ``DOLIBARR_API_KEY``
pointing at a reachable instance. Fixtures are uniquely named and cleaned up
so sequential runs on a shared instance do not collide.
"""

import json
import os
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
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

# Clean names exposed for every timespent line (timespent_line_* stripped).
TIMESPENT_KEYS = {"id", "ref_ext", "date", "datehour", "withhour", "duration", "fk_user", "thm", "note"}

# 2026-03-15 10:30:00 UTC, the intended entry date used below.
ENTRY_DATE = "2026-03-15 10:30:00"
ENTRY_EPOCH = 1773570600


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
                data={"ref": f"SUB09P-{tag}", "title": f"SUB09 project {tag}", "socid": 1},
            )
        )
    assert project_id > 0
    return project_id


async def _cleanup(config: Config, project_id: int, task_ids: List[int]) -> None:
    """Delete fixture tasks then the project (best effort)."""
    async with DolibarrClient(config) as client:
        for task_id in task_ids:
            try:
                await client.request("DELETE", f"tasks/{task_id}")
            except DolibarrAPIError:
                pass
        try:
            await client.request("DELETE", f"projects/{project_id}")
        except DolibarrAPIError:
            pass


@pytest.mark.asyncio
async def test_create_task_uses_given_ref_as_final_reference():
    """``create_task`` requires ref/label/fk_project and the given ref is kept as-is."""
    config = _config()
    tag = uuid.uuid4().hex[:8]
    project_id = await _create_project(config, tag)
    task_ids: List[int] = []
    try:
        async with mcp_session() as (session, _init_result):
            task_id = int(
                _tool_payload(
                    await session.call_tool(
                        "create_task",
                        {"project_id": project_id, "ref": f"SUB09-T-{tag}", "label": f"SUB09 task {tag}"},
                    )
                )
            )
            task_ids.append(task_id)
            assert task_id > 0, task_id

            # Without ref the API rejects the creation (masked 400).
            result = await session.call_tool("create_task", {"project_id": project_id, "label": f"SUB09 no-ref {tag}"})
            assert result.isError, "create_task without ref must fail"
        async with DolibarrClient(config) as client:
            task = await client.request("GET", f"tasks/{task_id}")
        assert task["ref"] == f"SUB09-T-{tag}", task
        assert task["label"] == f"SUB09 task {tag}", task
        assert int(task["fk_project"]) == project_id, task
    finally:
        await _cleanup(config, project_id, task_ids)


@pytest.mark.asyncio
async def test_add_read_correct_delete_task_time_and_project_total():
    """Time is added, read back (clean names), corrected, and seen at project level.

    - ``add_task_time`` accepts a ``"YYYY-MM-DD HH:MM:SS"`` UTC string and an
      epoch timestamp; the entry is stored with the intended date (UTC) and
      duration in seconds,
    - ``get_task_timespent`` returns clean field names (no ``timespent_line_``
      prefix) and surfaces ``total_duration``,
    - ``update_task_time`` / ``delete_task_time`` correct the entry via
      ``PUT``/``DELETE /tasks/{id}/timespent/{timespent_id}``,
    - ``get_project_timespent`` surfaces the consolidated ``total_duration``
      and the entry even though the project-scoped task list is unreliable
      (fallback to direct task reads),
    - all of this without raw API calls from the test.
    """
    config = _config()
    tag = uuid.uuid4().hex[:8]
    project_id = await _create_project(config, tag)
    task_ids: List[int] = []
    try:
        async with mcp_session() as (session, _init_result):
            task_id = int(
                _tool_payload(
                    await session.call_tool(
                        "create_task",
                        {"project_id": project_id, "ref": f"SUB09-T-{tag}", "label": f"SUB09 task {tag}"},
                    )
                )
            )
            task_ids.append(task_id)

            # Add 5400s on 2026-03-15 10:30:00 UTC (string form, stored as UTC).
            _tool_payload(
                await session.call_tool(
                    "add_task_time",
                    {
                        "task_id": task_id,
                        "date": ENTRY_DATE,
                        "duration": 5400,
                        "user_id": 1,
                        "note": f"SUB09 entry {tag}",
                    },
                )
            )
            # Add 900s via an epoch timestamp (accepted alternative input).
            _tool_payload(
                await session.call_tool(
                    "add_task_time",
                    {
                        "task_id": task_id,
                        "date": ENTRY_EPOCH + 3600,  # 2026-03-15 11:30:00 UTC
                        "duration": 900,
                        "user_id": 1,
                        "note": f"SUB09 entry2 {tag}",
                    },
                )
            )

            spent = _tool_payload(await session.call_tool("get_task_timespent", {"task_id": task_id}))
            assert int(spent["total_duration"]) == 5400 + 900, spent
            assert len(spent["entries"]) == 2, spent
            for entry in spent["entries"]:
                assert set(entry.keys()) == TIMESPENT_KEYS, entry
                assert entry["duration"] in (5400, 900), entry
                assert int(entry["fk_user"]) == 1, entry
            first = next(e for e in spent["entries"] if e["duration"] == 5400)
            assert first["note"] == f"SUB09 entry {tag}", first
            # Stored as UTC: datehour must be exactly 2026-03-15 10:30:00 UTC.
            assert first["datehour"] == ENTRY_EPOCH, first
            assert datetime.fromtimestamp(first["datehour"], timezone.utc).strftime("%Y-%m-%d %H:%M:%S") == ENTRY_DATE

            # The entry is visible in the project's consumed time.
            project_spent = _tool_payload(await session.call_tool("get_project_timespent", {"project_id": project_id}))
            assert int(project_spent["total_duration"]) == 5400 + 900, project_spent
            project_entries = [e for e in project_spent["entries"] if e["note"] == f"SUB09 entry {tag}"]
            assert len(project_entries) == 1, project_spent
            assert project_entries[0]["duration"] == 5400, project_entries[0]
            assert project_entries[0]["datehour"] == ENTRY_EPOCH, project_entries[0]

            # Correct the first entry: new date, duration 7200, new note.
            timespent_id = int(first["id"])
            _tool_payload(
                await session.call_tool(
                    "update_task_time",
                    {
                        "task_id": task_id,
                        "timespent_id": timespent_id,
                        "date": "2026-03-16 08:00:00",
                        "duration": 7200,
                        "user_id": 1,
                        "note": f"SUB09 corrected {tag}",
                    },
                )
            )
            spent = _tool_payload(await session.call_tool("get_task_timespent", {"task_id": task_id}))
            assert int(spent["total_duration"]) == 7200 + 900, spent
            corrected = next(e for e in spent["entries"] if int(e["id"]) == timespent_id)
            assert corrected["duration"] == 7200, corrected
            assert corrected["note"] == f"SUB09 corrected {tag}", corrected
            assert corrected["datehour"] == 1773648000, corrected  # 2026-03-16 08:00:00 UTC

            project_spent = _tool_payload(await session.call_tool("get_project_timespent", {"project_id": project_id}))
            assert int(project_spent["total_duration"]) == 7200 + 900, project_spent

            # Delete the corrected entry; only the 900s entry remains.
            _tool_payload(await session.call_tool("delete_task_time", {"task_id": task_id, "timespent_id": timespent_id}))
            spent = _tool_payload(await session.call_tool("get_task_timespent", {"task_id": task_id}))
            assert int(spent["total_duration"]) == 900, spent
            assert [int(e["id"]) for e in spent["entries"]] != [] and all(
                int(e["id"]) != timespent_id for e in spent["entries"]
            ), spent
            project_spent = _tool_payload(await session.call_tool("get_project_timespent", {"project_id": project_id}))
            assert int(project_spent["total_duration"]) == 900, project_spent
    finally:
        await _cleanup(config, project_id, task_ids)
