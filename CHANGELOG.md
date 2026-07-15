# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-07-15

### Added
- Initial release of the NHTSA vehicle safety MCP server.
- `decode_vin` — decode a VIN into make, model, year, engine, plant, and safety equipment.
- `check_vin_recalls` — decode a VIN and return its recall campaigns in one step.
- `get_recalls` — recall campaigns for a make/model/year (defect, consequence, remedy).
- `get_safety_ratings` — NCAP crash-test star ratings per body-style variant.
- `get_complaints` — consumer complaints grouped by component, with recent narratives.
- Responses trimmed for LLM consumption to keep tool output focused and bounded.
- Live smoke tests against the real NHTSA APIs.

[0.1.0]: https://github.com/basit-khan-abdul/vehicle-safety-mcp/releases/tag/v0.1.0
