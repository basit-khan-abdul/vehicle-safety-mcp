# vehicle-safety-mcp

[![CI](https://img.shields.io/github/actions/workflow/status/basit-khan-abdul/vehicle-safety-mcp/ci.yml?branch=main&style=flat&label=CI)](https://github.com/basit-khan-abdul/vehicle-safety-mcp/actions/workflows/ci.yml)
[![License](https://img.shields.io/github/license/basit-khan-abdul/vehicle-safety-mcp?style=flat)](LICENSE)
[![Release](https://img.shields.io/github/v/release/basit-khan-abdul/vehicle-safety-mcp?style=flat)](https://github.com/basit-khan-abdul/vehicle-safety-mcp/releases)

An [MCP](https://modelcontextprotocol.io) server that connects Claude to **NHTSA vehicle safety data** — VIN decoding, safety recalls, NCAP crash-test ratings, and consumer complaints. Ask Claude *"does my car have any recalls?"* and get a real answer from the US government's own data.

Built on the free [NHTSA public APIs](https://www.nhtsa.gov/nhtsa-datasets-and-apis) — no API key required.

## Why

Vehicle safety data is public but painful: it lives across several government APIs, each response carries 100+ mostly-empty fields, and safety ratings require a two-step lookup nobody remembers. This server does the plumbing so the conversation stays natural:

> **You:** Is a 2020 Honda Civic safe? Anything I should know before buying one?
>
> **Claude:** *(calls `get_safety_ratings` + `get_recalls` + `get_complaints`)* The 2020 Civic earned a 5-star overall NCAP rating… it has a handful of recall campaigns worth knowing about… and the component owners complain about most is…

## Tools

| Tool | What it does |
|---|---|
| `decode_vin` | VIN → make, model, year, engine, plant, safety equipment |
| `check_vin_recalls` | VIN → decoded vehicle + its recall campaigns, in one step |
| `get_recalls` | Recall campaigns for a make/model/year (defect, consequence, remedy) |
| `get_safety_ratings` | NCAP crash-test star ratings per body-style variant |
| `get_complaints` | Consumer complaints, grouped by component, with recent narratives |

Responses are deliberately **trimmed for LLM consumption** — raw NHTSA payloads are noisy, so the server keeps the fields that change an answer and drops the rest. Less context burned, better answers.

## Quickstart

Requires [uv](https://docs.astral.sh/uv/) (it manages Python ≥3.11 for you).

```bash
git clone https://github.com/basit-khan-abdul/vehicle-safety-mcp.git
cd vehicle-safety-mcp
uv sync
```

### Claude Code

```bash
claude mcp add vehicle-safety -- uv run --directory /path/to/vehicle-safety-mcp vehicle-safety-mcp
```

### Claude Desktop

Add to `claude_desktop_config.json` (Settings → Developer → Edit Config):

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

Restart Claude Desktop; the tools appear under the 🔌 icon.

## Try asking

- *"Decode this VIN: 5UXWX7C5*BA"*
- *"Does the 2020 Honda Civic have any recalls?"*
- *"Compare crash-test ratings of a 2021 Toyota RAV4 and a 2021 Honda CR-V"*
- *"What do owners complain about most on the 2019 Ford F-150?"*

## Reliability

Every NHTSA call runs with explicit connect and read timeouts and retries only transient failures — 5xx responses and connection/timeout errors — up to 3 attempts with exponential backoff and full jitter; client errors (4xx) fail fast and are never retried. When the upstream is genuinely unreachable, tools return a structured `{"error", "detail", "available": false}` payload the model can relay honestly, never a raw traceback into the MCP layer. Timeouts, attempt count, and backoff are all environment-tunable (see [Tuning](#tuning)). And because the NHTSA APIs are the real contract, a weekly scheduled job runs live smoke tests against them and opens a GitHub issue the moment a field or response shape drifts — so breakage surfaces before users do.

## Tests

Two suites, split by what they prove:

- **Unit** (`tests/unit/`) — mocked, deterministic, offline. Run on every push/PR across Python 3.11 and 3.12 ([CI](.github/workflows/ci.yml)).
- **Live** (`tests/live/`) — real NHTSA API smoke tests. The upstream contract *is* the product, so a weekly scheduled job ([contract-drift](.github/workflows/contract-drift.yml)) re-runs them and opens an issue if the API drifts — instead of making every push depend on a third-party API.

```bash
uv run --extra dev pytest tests/unit     # fast, offline — what CI runs on push
uv run --extra dev pytest tests/live     # hits the real NHTSA APIs
uv run --extra dev pytest -m "not live"  # everything except live
```

## Design notes

- **Trimmed responses over raw passthrough.** Each NHTSA record is filtered to a curated field list (`nhtsa.py`). An LLM doesn't need 140 vPIC fields to say "it's a BMW X3".
- **Composite tool for the common question.** `check_vin_recalls` chains decode → recall lookup because "does *my car* have recalls?" is the question real people ask — one tool call instead of two round trips.
- **Bounded output everywhere.** Ratings capped at 5 variants, complaint narratives truncated at 400 chars, complaint list limited — tool output that scrolls forever helps nobody.
- **Resilient by default.** Every NHTSA call has explicit connect/read timeouts and retries transient failures (5xx, connection errors, timeouts) up to 3 attempts with jittered backoff — but never retries a 4xx. When the upstream is genuinely down, tools return a structured `{"error": …, "available": false}` payload the model can relay honestly ("NHTSA data is currently unreachable; try again later") instead of surfacing a raw traceback.

### Tuning

The HTTP behaviour is env-configurable (sensible defaults shown):

| Variable | Default | Meaning |
|---|---|---|
| `NHTSA_CONNECT_TIMEOUT` | `5.0` | Connection timeout (seconds) |
| `NHTSA_READ_TIMEOUT` | `20.0` | Response read timeout (seconds) |
| `NHTSA_MAX_ATTEMPTS` | `3` | Total attempts per request (1 = no retry) |
| `NHTSA_BACKOFF_BASE` | `0.5` | Base backoff (seconds) before jitter |
| `NHTSA_BACKOFF_CAP` | `8.0` | Max backoff for any single retry (seconds) |

## MCP registries

Built to the [Model Context Protocol](https://modelcontextprotocol.io) spec and installable from source (see [Quickstart](#quickstart)). Browse or publish MCP servers via the community registries:

- [Official MCP Registry](https://github.com/modelcontextprotocol/registry)
- [Glama MCP directory](https://glama.ai/mcp/servers)
- [MCP.so](https://mcp.so)
- [PulseMCP](https://www.pulsemcp.com/servers)

## Data source & disclaimer

Data comes from the [US National Highway Traffic Safety Administration](https://www.nhtsa.gov/) public APIs and covers vehicles sold in the United States. This project is not affiliated with or endorsed by NHTSA. Always verify safety-critical information with official sources.

## License

MIT © [Basit Khan](https://www.linkedin.com/in/basit-khan-abdul/)
