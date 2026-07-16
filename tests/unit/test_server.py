"""Unit tests for the MCP server layer — mocked, deterministic, no network.

Focus on the composite `check_vin_recalls` tool, which chains a VIN decode
into a recall lookup and has branching logic worth pinning down.
"""

from vehicle_safety_mcp import nhtsa, server


async def test_check_vin_recalls_happy_path(monkeypatch):
    async def fake_decode(vin, model_year=None):
        return {"Make": "BMW", "Model": "X3", "ModelYear": "2011"}

    async def fake_recalls(make, model, model_year):
        assert (make, model, model_year) == ("BMW", "X3", 2011)
        return {"count": 1, "recalls": [{"NHTSACampaignNumber": "11V123000"}]}

    monkeypatch.setattr(nhtsa, "decode_vin", fake_decode)
    monkeypatch.setattr(nhtsa, "get_recalls", fake_recalls)

    result = await server.check_vin_recalls("5UXWX7C5XBA000000")

    assert result["vehicle"]["Make"] == "BMW"
    assert result["count"] == 1
    assert result["recalls"][0]["NHTSACampaignNumber"] == "11V123000"
    assert "error" not in result


async def test_check_vin_recalls_unresolvable_vin_skips_recall_lookup(monkeypatch):
    async def fake_decode(vin, model_year=None):
        return {"ErrorText": "invalid VIN"}  # no Make/Model/ModelYear

    called = False

    async def fake_recalls(*args, **kwargs):
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr(nhtsa, "decode_vin", fake_decode)
    monkeypatch.setattr(nhtsa, "get_recalls", fake_recalls)

    result = await server.check_vin_recalls("NOTAVIN")

    assert "error" in result
    assert result["vehicle"] == {"ErrorText": "invalid VIN"}
    assert called is False  # must not attempt a recall lookup when unresolvable
