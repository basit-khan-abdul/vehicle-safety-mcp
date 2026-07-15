# vehicle-safety-mcp

An [MCP](https://modelcontextprotocol.io) server that connects Claude to **NHTSA vehicle safety data** — VIN decoding, safety recalls, NCAP crash-test ratings, and consumer complaints. Ask Claude *"does my car have any open recalls?"* and get a real answer from the US government's own data.

Built on the free [NHTSA public APIs](https://www.nhtsa.gov/nhtsa-datasets-and-apis) — no API key required.

## Why

Vehicle safety data is public but painful: it lives across several government APIs, each response carries 100+ mostly-empty fields, and safety ratings require a two-step lookup nobody remembers. This server does the plumbing so the conversation stays natural:

> **You:** Is a 2020 Honda Civic safe? Anything I should know before buying one?
>
> **Claude:** *(calls `get_safety_ratings` + `get_recalls` + `get_complaints`)* The 2020 Civic scored 5 stars overall in NCAP testing… it has 5 recall campaigns, most notably the fuel pump recall… the most complained-about component is…

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

## Tests

Live smoke tests against the real APIs (the upstream contract *is* the product):

```bash
uv run pytest
```

## Design notes

- **Trimmed responses over raw passthrough.** Each NHTSA record is filtered to a curated field list (`nhtsa.py`). An LLM doesn't need 140 vPIC fields to say "it's a BMW X3".
- **Composite tool for the common question.** `check_vin_recalls` chains decode → recall lookup because "does *my car* have recalls?" is the question real people ask — one tool call instead of two round trips.
- **Bounded output everywhere.** Ratings capped at 5 variants, complaint narratives truncated at 400 chars, complaint list limited — tool output that scrolls forever helps nobody.

## Data source & disclaimer

Data comes from the [US National Highway Traffic Safety Administration](https://www.nhtsa.gov/) public APIs and covers vehicles sold in the United States. This project is not affiliated with or endorsed by NHTSA. Always verify safety-critical information with official sources.

## License

MIT © [Basit Khan](https://www.linkedin.com/in/basit-khan-abdul/)
