"""Live smoke tests against the real NHTSA APIs.

These hit the network on purpose — the point of this server is the upstream
data, so the tests validate the actual contract, not a mock of it.
Run: uv run pytest
"""

import pytest

from vehicle_safety_mcp import nhtsa

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def test_decode_vin():
    result = await nhtsa.decode_vin("5UXWX7C5*BA", model_year=2011)
    assert result["Make"] == "BMW"
    assert result["Model"] == "X3"
    assert result["ModelYear"] == "2011"


async def test_get_recalls():
    result = await nhtsa.get_recalls("Honda", "Civic", 2020)
    assert result["count"] >= 1
    first = result["recalls"][0]
    assert "Component" in first
    assert "NHTSACampaignNumber" in first


async def test_get_safety_ratings():
    result = await nhtsa.get_safety_ratings("Honda", "Civic", 2020)
    assert result["variant_count"] >= 1
    assert any("OverallRating" in r for r in result["ratings"])


async def test_get_complaints():
    result = await nhtsa.get_complaints("Honda", "Civic", 2020, limit=3)
    assert result["total_complaints"] >= 1
    assert len(result["recent_complaints"]) <= 3
    assert result["complaints_by_component"]
