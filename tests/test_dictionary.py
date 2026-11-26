"""Unit tests for DolibarrClient.get_dictionary (sub-issue 8 of #37).

The HTTP layer is mocked; no live Dolibarr instance is needed.
"""

from unittest.mock import AsyncMock, patch

import pytest

from dolibarr_mcp.config import Config
from dolibarr_mcp.dolibarr_client import DolibarrClient, DolibarrValidationError


def _config() -> Config:
    return Config(dolibarr_url="https://test.dolibarr.com/api/index.php", api_key="test_key")


def _mock_response(status: int, body: str):
    mock_response = AsyncMock()
    mock_response.status = status
    mock_response.reason = "OK" if status == 200 else "Not Found"
    mock_response.text.return_value = body
    return mock_response


@pytest.mark.asyncio
@patch("aiohttp.ClientSession.request")
async def test_get_dictionary_normalizes_rows(mock_request):
    """Rows come back with numeric id, code and label."""
    mock_request.return_value.__aenter__.return_value = _mock_response(
        200,
        '[{"id": "2", "code": "VIR", "type": "2", "label": "Virement", "module": null}]',
    )
    async with DolibarrClient(_config()) as client:
        rows = await client.get_dictionary("payment_types")

    assert rows == [{"id": 2, "code": "VIR", "type": "2", "label": "Virement", "module": None}]
    # The dictionary endpoint must be hit.
    called_url = mock_request.call_args[0][1] if len(mock_request.call_args[0]) > 1 else mock_request.call_args[1].get("url", "")
    assert "setup/dictionary/payment_types" in str(called_url)


@pytest.mark.asyncio
@patch("aiohttp.ClientSession.request")
async def test_get_dictionary_unknown_name_raises_validation_error(mock_request):
    """A 404 from the API is turned into a validation error naming the dictionary."""
    mock_request.return_value.__aenter__.return_value = _mock_response(404, '{"error": {"code": 404, "message": "Not Found"}}')
    async with DolibarrClient(_config()) as client:
        with pytest.raises(DolibarrValidationError) as exc_info:
            await client.get_dictionary("no_such_dictionary")

    assert exc_info.value.status_code == 404
    payload = exc_info.value.response_data or {}
    assert "no_such_dictionary" in payload.get("message", "")
    assert "payment_types" in payload.get("message", "")


@pytest.mark.asyncio
async def test_get_dictionary_rejects_malformed_name_without_http_call():
    """A malformed name (path traversal attempt) fails client-side, no HTTP call."""
    client = DolibarrClient(_config())
    client.request = AsyncMock()
    with pytest.raises(DolibarrValidationError):
        await client.get_dictionary("../users")
    client.request.assert_not_called()
