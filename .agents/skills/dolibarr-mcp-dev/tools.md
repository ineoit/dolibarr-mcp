# Tools — adding or modifying an MCP tool

A tool spans three places; keep all three in the same commit.

## 1. Client method — `src/dolibarr_mcp/dolibarr_client.py`

Add an `async def` on the client using the shared `request()` helper. Conventions:

- Auth is automatic (`DOLAPIKEY` header); payloads are JSON.
- List endpoints accept `limit`, `page`, `sortfield`, `sortorder`, `sqlfilters`.
- Use `_get_list()` for paginated lists.
- Return plain dicts/lists; raise on HTTP errors so the server can wrap them.

## 2. Tool definition — `src/dolibarr_mcp/dolibarr_mcp_server.py` (`_all_tools()`)

Register the tool name, description and JSON input schema. Search tools must filter server-side via
`sqlfilters` and escape values with `_escape_sqlfilter()` — never interpolate raw user input into a
filter.

## 3. Dispatch — `handle_call_tool()`

Add the branch that calls the client method and returns the result. Wrap failures with `_error_result()`
so clients get structured errors, never unhandled exceptions.

## Policy

- Write tools (create/update/delete) are automatically hidden when `MCP_READ_ONLY=true`
  (`is_write_tool()`); `dolibarr_raw_api` stays hidden unless `MCP_ENABLE_RAW_API=true`.
- After adding a tool, add a unit test in `tests/test_*.py` mocking the HTTP layer.
- Update `docs/api-reference.md` and CHANGELOG.md in the same commit.

## Issue #37 toolset — per-endpoint quirks

New groups: supplier invoices, payments, social contributions, bank, documents (upload/delete + extended
listing), tasks/time (timespent), fichinter, agenda, dictionaries, `search_thirdparties`. Quirks to
remember:

- Errors: all 4xx/5xx results include raw Dolibarr body + status + `correlation_id` + endpoint.
- `pay_supplier_invoice` takes query params (not body); VIR payment code comes from
  `get_dictionary('payment_types')`; `closepaidinvoices` is a yes/no string. `pay_invoice` rejects
  supplier ids — route them here.
- `get_bank_lines` / `get_supplier_invoices`: single-condition `sqlfilters` only, no `t.` prefix;
  multiple conditions are merged locally.
- Timespent fields map to `timespent_line_*`; totals come back as `total_duration` with fallback reads
  when absent.
- Line payloads: supplier invoice lines and fichinter lines use `description` (not `desc`), `pu_ht`;
  intervention lines take description/date/duration (integer timestamps).
- `upload_document` / `delete_document` use a JSON body with modulepart path conventions
  (supplier_invoice uses a numeric prefix, plus tax, bank); a 404 on delete is success.
- `create_agenda_event` needs `type_code` from `get_dictionary('event_types')` (e.g. AC_TEL);
  `contact_id` is accepted but not persisted upstream.
- Social contribution tools skip cleanly (version-aware) when `/socialcontributions` is absent.
