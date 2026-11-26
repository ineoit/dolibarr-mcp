"""Unit tests for the version-aware skip guard in the sub-issue 3 integration tests."""

from unittest.mock import AsyncMock, patch

import pytest

from dolibarr_mcp.config import Config
from dolibarr_mcp.dolibarr_client import DolibarrAPIError
from tests.integration.test_issue37_03_social_contributions import (
    _skip_if_no_social_contributions,
)


def _config() -> Config:
    return Config(dolibarr_url="https://test.dolibarr.com/api/index.php", api_key="test_key")


@pytest.mark.asyncio
async def test_skips_on_501_api_not_found():
    """A 501 'API not found' (Dolibarr without the socialcontributions class) skips."""
    client = AsyncMock()
    client.request.side_effect = DolibarrAPIError("API not found (failed to include API file)", status_code=501)
    client.__aenter__.return_value = client
    with patch("tests.integration.test_issue37_03_social_contributions.DolibarrClient", return_value=client):
        with pytest.raises(pytest.skip.Exception):
            await _skip_if_no_social_contributions(_config())


@pytest.mark.asyncio
async def test_skips_on_404():
    client = AsyncMock()
    client.request.side_effect = DolibarrAPIError("Not found", status_code=404)
    client.__aenter__.return_value = client
    with patch("tests.integration.test_issue37_03_social_contributions.DolibarrClient", return_value=client):
        with pytest.raises(pytest.skip.Exception):
            await _skip_if_no_social_contributions(_config())


@pytest.mark.asyncio
async def test_does_not_skip_when_endpoint_exists():
    """A successful probe returns normally so the tests stay active."""
    client = AsyncMock()
    client.request.return_value = []
    client.__aenter__.return_value = client
    with patch("tests.integration.test_issue37_03_social_contributions.DolibarrClient", return_value=client):
        await _skip_if_no_social_contributions(_config())  # must not raise


@pytest.mark.asyncio
async def test_other_errors_still_raise():
    """Non-404/501 errors are real failures, not skips."""
    client = AsyncMock()
    client.request.side_effect = DolibarrAPIError("Server error", status_code=500)
    client.__aenter__.return_value = client
    with patch("tests.integration.test_issue37_03_social_contributions.DolibarrClient", return_value=client):
        with pytest.raises(DolibarrAPIError):
            await _skip_if_no_social_contributions(_config())
