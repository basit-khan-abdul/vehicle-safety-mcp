"""Resilience unit tests for the NHTSA client — mocked transport, no network.

These pin down the three robustness behaviours:
  1. explicit, env-configurable timeouts,
  2. bounded retry with backoff (5xx + transport errors only, never 4xx),
  3. graceful degradation to a structured payload instead of a traceback.

Unlike test_nhtsa.py (which patches the `_get_json` seam), these inject an
`httpx.MockTransport` beneath it so the *real* retry loop, backoff, and
error handling execute. Backoff sleeps are neutralised so the suite stays fast.
"""

import httpx
import pytest

from vehicle_safety_mcp import nhtsa


def _install_transport(monkeypatch, handler):
    """Route `_get_json` through an httpx.MockTransport driven by `handler`."""

    def new_client():
        return httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            timeout=nhtsa._timeout_from_env(),
        )

    monkeypatch.setattr(nhtsa, "_new_client", new_client)


def _neutralise_backoff(monkeypatch):
    """Make retries instant and record that a backoff actually happened."""
    slept: list[float] = []

    async def fake_sleep(seconds):
        slept.append(seconds)

    monkeypatch.setattr(nhtsa, "_sleep", fake_sleep)
    return slept


# ---------------------------------------------------------------------------
# 1. Timeouts
# ---------------------------------------------------------------------------


def test_timeout_defaults():
    t = nhtsa._timeout_from_env()
    assert t.connect == 5.0
    assert t.read == 20.0


def test_timeout_env_overrides(monkeypatch):
    monkeypatch.setenv("NHTSA_CONNECT_TIMEOUT", "1.5")
    monkeypatch.setenv("NHTSA_READ_TIMEOUT", "42")
    t = nhtsa._timeout_from_env()
    assert t.connect == 1.5
    assert t.read == 42.0


# ---------------------------------------------------------------------------
# 2. Retry
# ---------------------------------------------------------------------------


async def test_retry_recovers_after_500_then_200(monkeypatch):
    """A single 500 is retried and the following 200 succeeds."""
    calls = {"n": 0}
    payload = {"Results": [{"Make": "BMW"}]}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(500, text="upstream boom")
        return httpx.Response(200, json=payload)

    _install_transport(monkeypatch, handler)
    slept = _neutralise_backoff(monkeypatch)

    result = await nhtsa._get_json("https://example.test/thing")

    assert result == payload
    assert calls["n"] == 2  # failed once, retried once
    assert len(slept) == 1  # exactly one backoff between the two attempts


async def test_does_not_retry_4xx(monkeypatch):
    """4xx is a client error — fail fast, no retry, and degrade cleanly."""
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(404, text="not found")

    _install_transport(monkeypatch, handler)
    slept = _neutralise_backoff(monkeypatch)

    with pytest.raises(nhtsa.NHTSAUnavailable):
        await nhtsa._get_json("https://example.test/thing")

    assert calls["n"] == 1  # never retried
    assert slept == []  # never backed off


async def test_retries_are_capped(monkeypatch):
    """Persistent 5xx exhausts exactly _MAX_ATTEMPTS tries, then gives up."""
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(503, text="down")

    _install_transport(monkeypatch, handler)
    _neutralise_backoff(monkeypatch)

    with pytest.raises(nhtsa.NHTSAUnavailable):
        await nhtsa._get_json("https://example.test/thing")

    assert calls["n"] == nhtsa._MAX_ATTEMPTS  # bounded, not infinite


# ---------------------------------------------------------------------------
# 3. Graceful degradation
# ---------------------------------------------------------------------------


async def test_timeout_degrades_to_structured_payload(monkeypatch):
    """A timeout is retried, then a tool returns a relayable payload — not a raise."""
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        raise httpx.ConnectTimeout("simulated timeout", request=request)

    _install_transport(monkeypatch, handler)
    _neutralise_backoff(monkeypatch)

    result = await nhtsa.get_recalls("Honda", "Civic", 2020)

    assert result["available"] is False
    assert result["source"] == "NHTSA"
    assert "unreachable" in result["error"].lower()
    assert "timed out" in result["detail"].lower()
    assert calls["n"] == nhtsa._MAX_ATTEMPTS  # retried before degrading


async def test_server_error_degrades_across_all_tools(monkeypatch):
    """Every public tool degrades the same way when NHTSA is down."""

    def handler(request):
        return httpx.Response(500, text="boom")

    _install_transport(monkeypatch, handler)
    _neutralise_backoff(monkeypatch)

    for coro in (
        nhtsa.decode_vin("5UXWX7C5XBA000000"),
        nhtsa.get_recalls("Honda", "Civic", 2020),
        nhtsa.get_safety_ratings("Honda", "Civic", 2020),
        nhtsa.get_complaints("Honda", "Civic", 2020),
    ):
        result = await coro
        assert result["available"] is False
        assert result["error"].startswith("NHTSA vehicle-safety data is currently unreachable")


async def test_check_vin_recalls_propagates_degradation(monkeypatch):
    """The composite tool relays the outage instead of masking it as
    'could not resolve VIN'."""
    from vehicle_safety_mcp import server

    def handler(request):
        raise httpx.ConnectError("no route to host", request=request)

    _install_transport(monkeypatch, handler)
    _neutralise_backoff(monkeypatch)

    result = await server.check_vin_recalls("5UXWX7C5XBA000000")

    assert result["available"] is False
    assert "Could not resolve" not in result.get("error", "")
