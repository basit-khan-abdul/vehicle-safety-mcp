# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Resilient HTTP layer for the NHTSA client: explicit connect/read timeouts,
  bounded retry (max 3 attempts) with exponential backoff + full jitter for
  transient failures only (5xx and connection/timeout errors — never 4xx), and
  graceful degradation to a structured `{"error", "detail", "source",
  "available": false}` payload an LLM can relay honestly instead of raising a
  traceback into the MCP layer.
- Env knobs: `NHTSA_CONNECT_TIMEOUT`, `NHTSA_READ_TIMEOUT`, `NHTSA_MAX_ATTEMPTS`,
  `NHTSA_BACKOFF_BASE`, `NHTSA_BACKOFF_CAP`.
- `tests/unit/test_resilience.py` — injects an `httpx.MockTransport` beneath the
  client to exercise the real retry loop (500-then-200 recovery, no-retry-on-4xx,
  capped attempts) and the timeout → degradation payload shape.

## [0.1.0] — 2026-07-15

### Added
- Initial release of the NHTSA vehicle safety MCP server.
- `decode_vin` — decode a VIN into make, model, year, engine, plant, and safety equipment.
- `check_vin_recalls` — decode a VIN and return its recall campaigns in one step.
- `get_recalls` — recall campaigns for a make/model/year (defect, consequence, remedy).
- `get_safety_ratings` — NCAP crash-test star ratings per body-style variant.
- `get_complaints` — consumer complaints grouped by component, with recent narratives.
- Responses trimmed for LLM consumption to keep tool output focused and bounded.
- Test suite split into deterministic unit tests (mocked, offline) and live contract smoke tests (`tests/unit/`, `tests/live/`).
- GitHub Actions: CI runs the unit tests on Python 3.11 and 3.12 on every push/PR; a weekly `contract-drift` job runs the live tests and opens an issue if the NHTSA APIs change.

[0.1.0]: https://github.com/basit-khan-abdul/vehicle-safety-mcp/releases/tag/v0.1.0
