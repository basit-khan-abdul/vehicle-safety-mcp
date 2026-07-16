"""Unit tests for the NHTSA client — mocked, deterministic, no network.

Each test replaces `nhtsa._get_json` (the single HTTP seam) with canned
payloads shaped like the real API responses, then asserts the trimming and
shaping logic. These run on every push/PR.
"""

from vehicle_safety_mcp import nhtsa


def _patch_get_json(monkeypatch, handler):
    """Replace the HTTP seam with an async handler(url, params) -> dict."""

    async def fake_get_json(url, params=None):
        return handler(url, params)

    monkeypatch.setattr(nhtsa, "_get_json", fake_get_json)


async def test_decode_vin_trims_empty_and_na_fields(monkeypatch):
    payload = {
        "Results": [
            {
                "Make": "BMW",
                "Model": "X3",
                "ModelYear": "2011",
                "Trim": "",  # empty -> dropped
                "ABS": "Not Applicable",  # NA -> dropped
                "EngineCylinders": "6",
                "ErrorText": "0 - VIN decoded clean.",
            }
        ]
    }
    _patch_get_json(monkeypatch, lambda url, params: payload)

    result = await nhtsa.decode_vin("5UXWX7C5XBA000000", model_year=2011)

    assert result["Make"] == "BMW"
    assert result["Model"] == "X3"
    assert result["ModelYear"] == "2011"
    assert result["EngineCylinders"] == "6"
    assert "Trim" not in result  # empty string trimmed away
    assert "ABS" not in result  # "Not Applicable" trimmed away


async def test_decode_vin_handles_empty_results(monkeypatch):
    _patch_get_json(monkeypatch, lambda url, params: {"Results": []})
    result = await nhtsa.decode_vin("BADVIN")
    assert result == {}


async def test_get_recalls_shapes_count_and_records(monkeypatch):
    payload = {
        "Count": 2,
        "results": [
            {
                "NHTSACampaignNumber": "11V123000",
                "Component": "ENGINE",
                "Summary": "s1",
                "Consequence": "c1",
                "Remedy": "r1",
                "ReportReceivedDate": "2011-03-01",
            },
            {
                "NHTSACampaignNumber": "12V456000",
                "Component": "BRAKES",
                "Summary": "s2",
                "Consequence": "c2",
                "Remedy": "r2",
                "ReportReceivedDate": "2012-06-01",
            },
        ],
    }
    _patch_get_json(monkeypatch, lambda url, params: payload)

    result = await nhtsa.get_recalls("Honda", "Civic", 2020)

    assert result["count"] == 2
    assert len(result["recalls"]) == 2
    assert result["recalls"][0]["NHTSACampaignNumber"] == "11V123000"
    assert result["recalls"][1]["Component"] == "BRAKES"


async def test_get_recalls_empty(monkeypatch):
    _patch_get_json(monkeypatch, lambda url, params: {"Count": 0, "results": []})
    result = await nhtsa.get_recalls("Honda", "Civic", 1990)
    assert result == {"count": 0, "recalls": []}


async def test_get_safety_ratings_is_two_step_and_caps_variants(monkeypatch):
    # Seven variants returned, but the client should only fetch details for 5.
    listing = {
        "Results": [
            {"VehicleId": i, "VehicleDescription": f"var{i}"} for i in range(1, 8)
        ]
    }
    detail_calls = []

    def handler(url, params):
        if "/SafetyRatings/VehicleId/" in url:
            vid = url.rsplit("/", 1)[-1]
            detail_calls.append(vid)
            return {"Results": [{"VehicleDescription": f"var{vid}", "OverallRating": "5"}]}
        if "/SafetyRatings/modelyear/" in url:
            return listing
        raise AssertionError(f"unexpected url: {url}")

    _patch_get_json(monkeypatch, handler)

    result = await nhtsa.get_safety_ratings("Honda", "Civic", 2020)

    assert result["variant_count"] == 7  # reports the full count...
    assert len(detail_calls) == 5  # ...but only fetches 5 detail records
    assert len(result["ratings"]) == 5
    assert all(r["OverallRating"] == "5" for r in result["ratings"])


async def test_get_complaints_groups_sorts_and_truncates(monkeypatch):
    payload = {
        "count": 3,
        "results": [
            {
                "components": "ENGINE",
                "dateComplaintFiled": "2020-01-01",
                "crash": "No",
                "fire": "No",
                "summary": "x" * 500,
            },
            {
                "components": "ENGINE",
                "dateComplaintFiled": "2020-02-01",
                "crash": "No",
                "fire": "No",
                "summary": "short",
            },
            {
                "components": "BRAKES",
                "dateComplaintFiled": "2020-03-01",
                "crash": "Yes",
                "fire": "No",
                "summary": "brake issue",
            },
        ],
    }
    _patch_get_json(monkeypatch, lambda url, params: payload)

    result = await nhtsa.get_complaints("Honda", "Civic", 2020, limit=2)

    assert result["total_complaints"] == 3
    # grouped by component, sorted most-frequent first
    assert list(result["complaints_by_component"].items()) == [("ENGINE", 2), ("BRAKES", 1)]
    # limit respected
    assert len(result["recent_complaints"]) == 2
    # narrative truncated to 400 chars
    assert len(result["recent_complaints"][0]["summary"]) == 400
