"""Thin async client for the free NHTSA public APIs.

Two API families are used (no API key required):
- vPIC (vehicle specs / VIN decoding): https://vpic.nhtsa.dot.gov/api/
- NHTSA data services (recalls, ratings, complaints): https://api.nhtsa.gov/

Responses are trimmed to the fields an LLM actually needs — raw NHTSA
payloads carry 100+ mostly-empty fields per record, which wastes context
and buries the signal.
"""

from __future__ import annotations

from typing import Any

import httpx

VPIC_BASE = "https://vpic.nhtsa.dot.gov/api/vehicles"
API_BASE = "https://api.nhtsa.gov"

_TIMEOUT = httpx.Timeout(20.0)

# Fields worth surfacing from a vPIC VIN decode (out of ~140 returned).
_VIN_FIELDS = [
    "Make",
    "Model",
    "ModelYear",
    "Trim",
    "Series",
    "BodyClass",
    "VehicleType",
    "DriveType",
    "FuelTypePrimary",
    "EngineCylinders",
    "DisplacementL",
    "EngineHP",
    "TransmissionStyle",
    "PlantCity",
    "PlantCountry",
    "Manufacturer",
    "GVWR",
    "ABS",
    "ESC",
    "ErrorText",
]

_RECALL_FIELDS = [
    "NHTSACampaignNumber",
    "ReportReceivedDate",
    "Component",
    "Summary",
    "Consequence",
    "Remedy",
]

_RATING_FIELDS = [
    "VehicleDescription",
    "OverallRating",
    "OverallFrontCrashRating",
    "OverallSideCrashRating",
    "RolloverRating",
    "NHTSAElectronicStabilityControl",
    "NHTSAForwardCollisionWarning",
    "NHTSALaneDepartureWarning",
    "ComplaintsCount",
    "RecallsCount",
    "InvestigationCount",
]


async def _get_json(url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


def _trim(record: dict[str, Any], fields: list[str]) -> dict[str, Any]:
    """Keep only the listed fields, dropping empty values."""
    return {
        k: record[k]
        for k in fields
        if record.get(k) not in (None, "", "Not Applicable", 0)
    }


async def decode_vin(vin: str, model_year: int | None = None) -> dict[str, Any]:
    """Decode a VIN (full or partial) into vehicle attributes."""
    params: dict[str, Any] = {"format": "json"}
    if model_year:
        params["modelyear"] = model_year
    data = await _get_json(f"{VPIC_BASE}/DecodeVinValues/{vin}", params)
    results = data.get("Results") or [{}]
    return _trim(results[0], _VIN_FIELDS)


async def get_recalls(make: str, model: str, model_year: int) -> dict[str, Any]:
    """Fetch recall campaigns for a make/model/year."""
    data = await _get_json(
        f"{API_BASE}/recalls/recallsByVehicle",
        {"make": make, "model": model, "modelYear": model_year},
    )
    recalls = [_trim(r, _RECALL_FIELDS) for r in data.get("results", [])]
    return {"count": data.get("Count", len(recalls)), "recalls": recalls}


async def get_safety_ratings(make: str, model: str, model_year: int) -> dict[str, Any]:
    """Fetch NCAP crash-test ratings.

    NHTSA models this as two steps: list the rated variants for a
    make/model/year, then fetch ratings per variant (VehicleId).
    """
    listing = await _get_json(
        f"{API_BASE}/SafetyRatings/modelyear/{model_year}/make/{make}/model/{model}"
    )
    variants = listing.get("Results", [])
    ratings = []
    for variant in variants[:5]:  # cap variants to keep output bounded
        vehicle_id = variant.get("VehicleId")
        if not vehicle_id:
            continue
        detail = await _get_json(f"{API_BASE}/SafetyRatings/VehicleId/{vehicle_id}")
        for record in detail.get("Results", []):
            ratings.append(_trim(record, _RATING_FIELDS))
    return {"variant_count": len(variants), "ratings": ratings}


async def get_complaints(
    make: str, model: str, model_year: int, limit: int = 10
) -> dict[str, Any]:
    """Fetch consumer complaints, summarized: totals by component plus the
    most recent narratives (truncated)."""
    data = await _get_json(
        f"{API_BASE}/complaints/complaintsByVehicle",
        {"make": make, "model": model, "modelYear": model_year},
    )
    results = data.get("results", [])

    by_component: dict[str, int] = {}
    for c in results:
        comp = c.get("components") or "UNKNOWN"
        by_component[comp] = by_component.get(comp, 0) + 1

    recent = [
        {
            "date": c.get("dateComplaintFiled"),
            "component": c.get("components"),
            "crash": c.get("crash"),
            "fire": c.get("fire"),
            "summary": (c.get("summary") or "")[:400],
        }
        for c in results[:limit]
    ]
    return {
        "total_complaints": data.get("count", len(results)),
        "complaints_by_component": dict(
            sorted(by_component.items(), key=lambda kv: -kv[1])
        ),
        "recent_complaints": recent,
    }
