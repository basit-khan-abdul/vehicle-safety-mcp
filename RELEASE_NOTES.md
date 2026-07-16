An [MCP](https://modelcontextprotocol.io) server that connects Claude to **NHTSA
vehicle safety data** — VIN decoding, safety recalls, NCAP crash-test ratings, and
consumer complaints, straight from the US government's own APIs. No API key required.

This is the first release hardened for real-world use: every upstream call now has
explicit timeouts, bounded retries, and honest failure messages instead of raw
tracebacks.

## ✨ What's new in 0.2.0

**Resilient HTTP layer for the NHTSA client.**

- **Explicit timeouts** on every outbound call — separate connect and read timeouts,
  with sensible defaults.
- **Bounded retry** (max 3 attempts) with exponential backoff + full jitter, but only
  for transient failures — 5xx responses and connection/timeout errors. Client errors
  (4xx) fail fast and are never retried.
- **Graceful degradation.** When NHTSA is genuinely unreachable, tools return a
  structured `{"error", "detail", "source", "available": false}` payload the model can
  relay honestly ("NHTSA data is currently unreachable; try again later") instead of
  surfacing a traceback into the MCP layer.
- **Env-tunable** — timeouts, attempt count, and backoff are all configurable (see below).
- New `tests/unit/test_resilience.py` injects an `httpx.MockTransport` beneath the
  client to exercise the real retry loop: 500-then-200 recovery, no-retry-on-4xx,
  capped attempts, and the timeout → degradation payload shape.

## 🧰 Tools

| Tool | What it does |
|---|---|
| `decode_vin` | VIN → make, model, year, engine, plant, safety equipment |
| `check_vin_recalls` | VIN → decoded vehicle + its recall campaigns, in one step |
| `get_recalls` | Recall campaigns for a make/model/year (defect, consequence, remedy) |
| `get_safety_ratings` | NCAP crash-test star ratings per body-style variant |
| `get_complaints` | Consumer complaints, grouped by component, with recent narratives |

Responses are deliberately **trimmed for LLM consumption** — raw NHTSA payloads carry
100+ mostly-empty fields, so the server keeps what changes an answer and drops the rest.

## 📦 Install

**Claude Code**

```bash
claude mcp add vehicle-safety -- uv run --directory /path/to/vehicle-safety-mcp vehicle-safety-mcp
```

**Claude Desktop** — add to `claude_desktop_config.json` (Settings → Developer → Edit Config):

```json
{
  "mcpServers": {
    "vehicle-safety": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/vehicle-safety-mcp", "vehicle-safety-mcp"]
    }
  }
}
```

## ⚙️ Tuning

The HTTP behaviour is env-configurable (defaults shown):

| Variable | Default | Meaning |
|---|---|---|
| `NHTSA_CONNECT_TIMEOUT` | `5.0` | Connection timeout (seconds) |
| `NHTSA_READ_TIMEOUT` | `20.0` | Response read timeout (seconds) |
| `NHTSA_MAX_ATTEMPTS` | `3` | Total attempts per request (1 = no retry) |
| `NHTSA_BACKOFF_BASE` | `0.5` | Base backoff (seconds) before jitter |
| `NHTSA_BACKOFF_CAP` | `8.0` | Max backoff for any single retry (seconds) |

## ✅ Quality

- Unit tests run on every push/PR across Python 3.11 and 3.12.
- A weekly `contract-drift` job runs the live tests against the real NHTSA APIs and
  opens an issue if the upstream contract changes.

---

**Full changelog:** https://github.com/basit-khan-abdul/vehicle-safety-mcp/blob/main/CHANGELOG.md
**Compare:** https://github.com/basit-khan-abdul/vehicle-safety-mcp/compare/v0.1.0...v0.2.0
