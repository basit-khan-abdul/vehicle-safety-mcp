"""MCP server exposing NHTSA vehicle safety data.

Run directly (stdio transport, the default for Claude Desktop / Claude Code):

    uv run vehicle-safety-mcp
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from . import nhtsa

mcp = FastMCP(
    "vehicle-safety",
    instructions=(
        "Provides US vehicle safety data from NHTSA (National Highway Traffic "
        "Safety Administration): VIN decoding, recall campaigns, NCAP "
        "crash-test ratings, and consumer complaints. Data covers vehicles "
        "sold in the United States."
    ),
)


@mcp.tool()
async def decode_vin(vin: str, model_year: int | None = None) -> dict[str, Any]:
    """Decode a VIN into vehicle details (make, model, year, engine, plant, safety equipment).

    Call this when the user provides a VIN (17 characters, or a partial VIN)
    and wants to know what vehicle it is. Passing model_year improves accuracy
    for pre-2001 VINs.
    """
    return await nhtsa.decode_vin(vin, model_year)


@mcp.tool()
async def get_recalls(make: str, model: str, model_year: int) -> dict[str, Any]:
    """Get NHTSA safety recall campaigns for a vehicle make/model/year.

    Call this when the user asks whether a vehicle has recalls, what a recall
    covers, or how a defect is remedied. Example: make="Honda", model="Civic",
    model_year=2020.
    """
    return await nhtsa.get_recalls(make, model, model_year)


@mcp.tool()
async def check_vin_recalls(vin: str) -> dict[str, Any]:
    """Decode a VIN and look up recalls for that exact vehicle in one step.

    Call this when the user gives a VIN and asks "does my car have any
    recalls?" — it chains VIN decoding into a recall search automatically.
    """
    vehicle = await nhtsa.decode_vin(vin)
    if vehicle.get("available") is False:
        return vehicle  # NHTSA was unreachable during decode — relay honestly
    make = vehicle.get("Make")
    model = vehicle.get("Model")
    year = vehicle.get("ModelYear")
    if not (make and model and year):
        return {
            "vehicle": vehicle,
            "error": "Could not resolve make/model/year from this VIN.",
        }
    recalls = await nhtsa.get_recalls(make, model, int(year))
    return {"vehicle": vehicle, **recalls}


@mcp.tool()
async def get_safety_ratings(make: str, model: str, model_year: int) -> dict[str, Any]:
    """Get NCAP crash-test star ratings (overall, frontal, side, rollover) for a vehicle.

    Call this when the user asks how safe a vehicle is or how it scored in
    crash tests. Returns ratings per body-style variant.
    """
    return await nhtsa.get_safety_ratings(make, model, model_year)


@mcp.tool()
async def get_complaints(
    make: str, model: str, model_year: int, limit: int = 10
) -> dict[str, Any]:
    """Get consumer complaints filed with NHTSA for a vehicle, grouped by component.

    Call this when the user asks about known problems, reliability issues, or
    owner-reported defects. Returns totals per component plus the most recent
    complaint narratives (truncated). Increase limit for more narratives.
    """
    return await nhtsa.get_complaints(make, model, model_year, limit)


def main() -> None:
    """Entry point: run over stdio (what Claude Desktop / Claude Code expect)."""
    mcp.run()


if __name__ == "__main__":
    main()
