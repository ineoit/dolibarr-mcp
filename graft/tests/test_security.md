# tests/test_security.py

- \_cfg · function · L12-L15 — def \_cfg(\*\*kw)
- test_write_tool_detection · function · L18-L23 — def test_write_tool_detection()
- test_raw_api_disabled_by_default · function · L26-L29 — def test_raw_api_disabled_by_default()
- test_read_only_hides_all_write_tools · function · L32-L36 — def test_read_only_hides_all_write_tools()
- test_call_tool_rejects_disabled_tool · function · L40-L47 — async def
  test_call_tool_rejects_disabled_tool(monkeypatch)
- test_defaults_are_safe · function · L50-L54 — def test_defaults_are_safe()
- \_DummySessionManager · class · L57-L69 — class \_DummySessionManager
- run · method · L58-L65 — def run(self)
- \_Ctx · class · L59-L64 — class \_Ctx
- __aenter__ · method · L60-L61 — async def __aenter__(self_inner)
- __aexit__ · method · L63-L64 — async def __aexit__(self_inner, \*exc)
- handle_request · method · L67-L69 — async def handle_request(self, scope, receive, send)
- test_http_requires_bearer_token · function · L72-L78 — def test_http_requires_bearer_token()
- test_cors_disabled_by_default · function · L81-L85 — def test_cors_disabled_by_default()
- test_cors_allowlist · function · L88-L99 — def test_cors_allowlist()
- test_refuses_public_bind_without_token · function · L103-L105 — async def
  test_refuses_public_bind_without_token()
