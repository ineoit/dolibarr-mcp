# src/dolibarr_mcp/dolibarr_mcp_server.py

- \_error_result · function · L49-L54 — def \_error_result(payload: dict) -> CallToolResult
- \_escape_sqlfilter · function · L60-L72 — def \_escape_sqlfilter(value: str) -> str
- \_to_iso_date · function · L81-L92 — def \_to_iso_date(value: Any) -> Optional[str]
- \_to_int · function · L95-L99 — def \_to_int(value: Any) -> Optional[int]
- \_summarize_invoice · function · L102-L121 — def \_summarize_invoice(invoice: Dict[str, Any]) ->
  Dict[str, Any]
- \_summarize_document · function · L129-L143 — def \_summarize_document(doc: dict) -> dict
- \_extract_pdf_attachments · function · L146-L169 — def \_extract_pdf_attachments(data: bytes) ->
  list[dict]
- \_document_contents · function · L172-L220 — def \_document_contents(downloaded: dict, modulepart: str,
  original_file: str, include_file: bool = True)
- is_write_tool · function · L227-L229 — def is_write_tool(name: str) -> bool
- is_tool_allowed · function · L232-L238 — def is_tool_allowed(name: str, config: Config) -> bool
- handle_list_tools · function · L242-L245 — async def handle_list_tools()
- \_all_tools · function · L248-L1618 — def \_all_tools()
- handle_call_tool · function · L1622-L1961 — async def handle_call_tool(name: str, arguments: dict)
- test_api_connection · function · L1965-L2007 — async def test_api_connection(config: Config | None =
  None)
- \_run_stdio_server · function · L2010-L2024 — async def \_run_stdio_server(\_config: Config) -> None
- BearerAuthMiddleware · class · L2027-L2052 — class BearerAuthMiddleware
- __init__ · method · L2030-L2032 — def __init__(self, app, token: str)
- __call__ · method · L2034-L2052 — async def __call__(self, scope: Scope, receive: Receive, send: Send)
- \_build_http_app · function · L2055-L2104 — def \_build_http_app(session_manager:
  StreamableHTTPSessionManager, config: Config | None = None) -> Starlette
- ASGIEndpoint · class · L2059-L2066 — class ASGIEndpoint
- __init__ · method · L2062-L2063 — def __init__(self, handler)
- __call__ · method · L2065-L2066 — async def __call__(self, scope: Scope, receive: Receive, send: Send)
- lifespan · function · L2069-L2071 — async def lifespan(app)
- asgi_handler · function · L2073-L2075 — async def asgi_handler(scope, receive, send)
- \_run_http_server · function · L2107-L2132 — async def \_run_http_server(config: Config) -> None
- main · function · L2135-L2159 — async def main()
