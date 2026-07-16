"""Thin async client for the free NHTSA public APIs.

Two API families are used (no API key required):
- vPIC (vehicle specs / VIN decoding): https://vpic.nhtsa.dot.gov/api/
- NHTSA data services (recalls, ratings, complaints): https://api.nhtsa.gov/

Responses are trimmed to the fields an LLM actually needs — raw NHTSA
payloads carry 100+ mostly-empty fields per record, which wastes context
and buries the signal.

Resilience: every outbound call has explicit connect/read timeouts, retries
transient failures (5xx + connection/timeout errors) with jittered backoff,
and degrades to a structured "unreachable" payload the LLM can relay honestly
instead of letting a raw traceback escape into the MCP layer. Behaviour is
tunable via environment variables (see `_timeout_from_env` and the retry
constants below).
"""

from __future__ import annotations

import asyncio
import functools
import os
import random
from typing import Any, Awaitable, Callable

import httpx

VPIC_BASE = "https://vpic.nhtsa.dot.gov/api/vehicles"
API_BASE = "https://api.nhtsa.gov"


def _timeout_from_env() -> httpx.Timeout:
    """Explicit connect + read timeouts, overridable via env.

    Split so a slow-to-accept connection fails fast (connect) while a
    legitimately slow response still gets time to arrive (read).
    """
    connect = float(os.getenv("NHTSA_CONNECT_TIMEOUT", "5.0"))
    read = float(os.getenv("NHTSA_READ_TIMEOUT", "20.0"))
    return httpx.Timeout(connect=connect, read=read, write=read, pool=connect)


# Retry policy (env-tunable). Max total attempts, base backoff, and a cap on
# any single sleep so jittered exponential growth stays bounded.
_MAX_ATTEMPTS = int(os.getenv("NHTSA_MAX_ATTEMPTS", "3"))
_BACKOFF_BASE = float(os.getenv("NHTSA_BACKOFF_BASE", "0.5"))
_BACKOFF_CAP = float(os.getenv("NHTSA_BACKOFF_CAP", "8.0"))


class NHTSAUnavailable(RuntimeError):
    """The NHTSA APIs could not be reached (after retries) or refused the request.

    Raised by `_get_json`; the `@_graceful` decorator turns it into a
    structured payload so it never surfaces as a raw traceback.
    """


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


def _new_client() -> httpx.AsyncClient:
    """Build the HTTP client. Isolated so tests can inject a mock transport."""
    return httpx.AsyncClient(timeout=_timeout_from_env(), follow_redirects=True)


async def _sleep(seconds: float) -> None:
    """Backoff sleep. Indirected so tests can neutralise the wait."""
    await asyncio.sleep(seconds)


def _is_retryable(exc: Exception) -> bool:
    """Retry only transient failures: 5xx responses and transport errors
    (connection failures + timeouts). Never retry 4xx — that's a client error
    and won't fix itself."""
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return isinstance(exc, httpx.TransportError)


def _describe(exc: Exception) -> str:
    """A short, honest reason string for the degradation payload."""
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if code >= 500:
            return f"NHTSA returned a server error (HTTP {code})."
        return f"NHTSA rejected the request (HTTP {code})."
    if isinstance(exc, httpx.TimeoutException):
        return "The request to NHTSA timed out."
    return "Could not connect to NHTSA."


async def _get_json(url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """GET JSON with timeouts + bounded retry, or raise `NHTSAUnavailable`.

    Retries transient failures (5xx, connection errors, timeouts) up to
    `_MAX_ATTEMPTS` with exponential backoff + full jitter. 4xx and any other
    error fail fast. On exhaustion the underlying error is wrapped so callers
    see one typed exception instead of raw httpx internals.
    """
    last_exc: Exception | None = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            async with _new_client() as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:  # noqa: BLE001 — re-raised as NHTSAUnavailable below
            last_exc = exc
            if not _is_retryable(exc) or attempt == _MAX_ATTEMPTS:
                break
            # Full jitter: sleep in [0, min(cap, base * 2**(attempt-1))].
            ceiling = min(_BACKOFF_CAP, _BACKOFF_BASE * 2 ** (attempt - 1))
            await _sleep(random.uniform(0, ceiling))

    assert last_exc is not None  # loop always sets it before breaking
    raise NHTSAUnavailable(_describe(last_exc)) from last_exc


def _unavailable(detail: str) -> dict[str, Any]:
    """Structured degradation payload — a short message an LLM can relay
    honestly, plus a machine-detectable `available: False` flag."""
    return {
        "error": "NHTSA vehicle-safety data is currently unreachable; please try again later.",
        "detail": detail,
        "source": "NHTSA",
        "available": False,
    }


def _graceful(
    fn: Callable[..., Awaitable[dict[str, Any]]],
) -> Callable[..., Awaitable[dict[str, Any]]]:
    """Turn an `NHTSAUnavailable` into a structured payload instead of a
    traceback, so tool callers (and the MCP layer) never see a raw crash."""

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
        try:
            return await fn(*args, **kwargs)
        except NHTSAUnavailable as exc:
            return _unavailable(str(exc))

    return wrapper


def _trim(record: dict[str, Any], fields: list[str]) -> dict[str, Any]:
    """Keep only the listed fields, dropping empty values."""
    return {
        k: record[k]
        for k in fields
        if record.get(k) not in (None, "", "Not Applicable", 0)
    }


@_graceful
async def decode_vin(vin: str, model_year: int | None = None) -> dict[str, Any]:
    """Decode a VIN (full or partial) into vehicle attributes."""
    params: dict[str, Any] = {"format": "json"}
    if model_year:
        params["modelyear"] = model_year
    data = await _get_json(f"{VPIC_BASE}/DecodeVinValues/{vin}", params)
    results = data.get("Results") or [{}]
    return _trim(results[0], _VIN_FIELDS)


@_graceful
async def get_recalls(make: str, model: str, model_year: int) -> dict[str, Any]:
    """Fetch recall campaigns for a make/model/year."""
    data = await _get_json(
        f"{API_BASE}/recalls/recallsByVehicle",
        {"make": make, "model": model, "modelYear": model_year},
    )
    recalls = [_trim(r, _RECALL_FIELDS) for r in data.get("results", [])]
    return {"count": data.get("Count", len(recalls)), "recalls": recalls}


@_graceful
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


@_graceful
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
