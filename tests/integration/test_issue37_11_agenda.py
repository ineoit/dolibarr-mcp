"""Integration tests for sub-issue 11 of #37: agenda event tools (create, get).

Verified API contract on the instance (Dolibarr 21.0.0, MAIN_MODULE_AGENDA=1):

- ``POST /agendaevents`` requires ``userownerid`` and ``type_code`` (the field
  name ``type`` is rejected on the wire). Working payload: ``type_code``
  (e.g. ``AC_TEL``), ``userownerid``, ``label``, ``datep``/``datef`` (integer
  Unix timestamps), ``percentage`` (100 = completed), ``socid`` (third-party
  link persists), ``note_private``. The contact link (``contact_id``) is
  accepted but NOT persisted (upstream Dolibarr behavior).
- ``GET /agendaevents/{id}`` returns the event with ``type_code``, ``label``,
  ``datep``/``datef``, ``percentage``, ``socid``, ``note_private``,
  ``userownerid``.
- Event type codes are resolved through the ``event_types`` dictionary
  (``get_dictionary``, sub-issue 8): tools accept codes like ``AC_TEL`` as well
  as the instance-specific numeric dictionary id, no raw API call needed.

Acceptance criteria encoded here: an ``AC_TEL`` event attached to a third
party can be created and read back through the tools.

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

# 2026-03-15 10:30:00 UTC and +30 min, the event window used below.
DATEP_EPOCH = 1773570600
DATEF_EPOCH = 1773572400


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


async def _first_user_id(config: Config) -> int:
    """Any valid user id to own the fixture events (fixture setup)."""
    async with DolibarrClient(config) as client:
        users = await client.request("GET", "users", params={"limit": 1})
    assert users, "no user on the instance to own agenda events"
    return int(users[0]["id"])


async def _create_thirdparty(config: Config, tag: str) -> int:
    """Create the fixture third party through the raw client (fixture setup)."""
    async with DolibarrClient(config) as client:
        socid = int(
            await client.request(
                "POST",
                "thirdparties",
                data={"name": f"SUB11 soc {tag}", "client": 1, "code_client": f"SUB11-{tag}"},
            )
        )
    assert socid > 0
    return socid


async def _cleanup(config: Config, socid: int, event_ids: List[int]) -> None:
    """Delete fixture events then the third party (best effort)."""
    async with DolibarrClient(config) as client:
        for event_id in event_ids:
            try:
                await client.request("DELETE", f"agendaevents/{event_id}")
            except DolibarrAPIError:
                pass
        try:
            await client.request("DELETE", f"thirdparties/{socid}")
        except DolibarrAPIError:
            pass


@pytest.mark.asyncio
async def test_agenda_tools_are_listed():
    """The create_agenda_event and get_agenda_event tools are exposed."""
    _config()  # skip early when no instance is configured
    async with mcp_session() as (session, _init_result):
        tools = await session.list_tools()
    names = [tool.name for tool in tools.tools]
    assert "create_agenda_event" in names
    assert "get_agenda_event" in names


@pytest.mark.asyncio
async def test_create_and_get_ac_tel_event_on_thirdparty():
    """Acceptance: an AC_TEL event attached to a third party round-trips.

    ``create_agenda_event`` with ``type_code='AC_TEL'`` (resolved through the
    event_types dictionary, no raw call), then ``get_agenda_event`` shows the
    same label, type code, third-party link, window, percentage and note.
    """
    config = _config()
    tag = uuid.uuid4().hex[:8]
    socid = await _create_thirdparty(config, tag)
    userownerid = await _first_user_id(config)
    event_ids: List[int] = []
    label = f"SUB11 call {tag}"
    note = f"SUB11 note {tag}"
    try:
        async with mcp_session() as (session, _init_result):
            event_id = int(
                _tool_payload(
                    await session.call_tool(
                        "create_agenda_event",
                        {
                            "type_code": "AC_TEL",
                            "label": label,
                            "datep": DATEP_EPOCH,
                            "datef": DATEF_EPOCH,
                            "socid": socid,
                            "userownerid": userownerid,
                            "percentage": 100,
                            "note": note,
                        },
                    )
                )
            )
            event_ids.append(event_id)
            assert event_id > 0, event_id

            event = _tool_payload(await session.call_tool("get_agenda_event", {"event_id": event_id}))
            assert int(event["id"]) == event_id, event
            assert event["type_code"] == "AC_TEL", event
            assert event["label"] == label, event
            assert int(event["socid"]) == socid, event
            assert int(event["userownerid"]) == userownerid, event
            assert int(event["datep"]) == DATEP_EPOCH, event
            assert int(event["datef"]) == DATEF_EPOCH, event
            assert int(event["percentage"]) == 100, event
            assert event["note_private"] == note, event
    finally:
        await _cleanup(config, socid, event_ids)


@pytest.mark.asyncio
async def test_create_agenda_event_accepts_numeric_type_id():
    """The numeric event-type id from the dictionary is accepted as ``type``.

    ``get_dictionary('event_types')`` resolves ``AC_TEL`` to this instance's
    id; passing it as ``type`` must create the same kind of event.
    """
    config = _config()
    tag = uuid.uuid4().hex[:8]
    socid = await _create_thirdparty(config, tag)
    userownerid = await _first_user_id(config)
    event_ids: List[int] = []
    label = f"SUB11 typed {tag}"
    try:
        async with DolibarrClient(config) as client:
            rows = await client.get_dictionary("event_types")
        by_code = {row["code"]: row for row in rows}
        assert "AC_TEL" in by_code, f"AC_TEL missing from event_types: {sorted(by_code)}"
        type_id = int(by_code["AC_TEL"]["id"])

        async with mcp_session() as (session, _init_result):
            event_id = int(
                _tool_payload(
                    await session.call_tool(
                        "create_agenda_event",
                        {
                            "type": type_id,
                            "label": label,
                            "datep": DATEP_EPOCH,
                            "datef": DATEF_EPOCH,
                            "socid": socid,
                            "userownerid": userownerid,
                        },
                    )
                )
            )
            event_ids.append(event_id)

            event = _tool_payload(await session.call_tool("get_agenda_event", {"event_id": event_id}))
            assert event["type_code"] == "AC_TEL", event
            assert event["label"] == label, event
            assert int(event["socid"]) == socid, event
    finally:
        await _cleanup(config, socid, event_ids)


@pytest.mark.asyncio
async def test_create_agenda_event_unknown_type_code_is_an_error():
    """An unknown type code returns a structured error, not a crash."""
    config = _config()
    userownerid = await _first_user_id(config)
    async with mcp_session() as (session, _init_result):
        result = await session.call_tool(
            "create_agenda_event",
            {
                "type_code": "AC_NO_SUCH_TYPE",
                "label": "SUB11 bad type",
                "datep": DATEP_EPOCH,
                "datef": DATEF_EPOCH,
                "userownerid": userownerid,
            },
        )
    assert result.isError
    content = result.content[0]
    assert isinstance(content, TextContent)
    assert "AC_NO_SUCH_TYPE" in content.text
