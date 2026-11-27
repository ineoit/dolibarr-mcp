# tests/test_server_connection.py

- \_DummyClient · class · L10-L20 — class \_DummyClient
- __aenter__ · method · L13-L14 — async def __aenter__(self)
- __aexit__ · method · L16-L17 — async def __aexit__(self, exc_type, exc_val, exc_tb)
- get_status · method · L19-L20 — async def get_status(self)
- \_ErrorClient · class · L23-L33 — class \_ErrorClient
- __aenter__ · method · L26-L27 — async def __aenter__(self)
- __aexit__ · method · L29-L30 — async def __aexit__(self, exc_type, exc_val, exc_tb)
- get_status · method · L32-L33 — async def get_status(self)
- test_api_connection_success · function · L37-L46 — async def test_api_connection_success(monkeypatch)
- test_api_connection_missing_configuration · function · L50-L58 — async def
  test_api_connection_missing_configuration()
- test_api_connection_with_client_error · function · L62-L71 — async def
  test_api_connection_with_client_error(monkeypatch)
