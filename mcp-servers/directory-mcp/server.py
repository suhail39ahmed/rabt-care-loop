"""Directory / plans / slots MCP server."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx
from mcp.server.fastmcp import FastMCP

ORCH = os.environ.get("ORCH_BASE_URL", "http://localhost:8000")
mcp = FastMCP("rabt-directory")

# Fallback local import if API down
_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "services" / "orchestrator"))


def _scope(tool: str) -> None:
    sys.path.insert(0, str(_ROOT / "services" / "orchestrator"))
    from app.tools import assert_tool_allowed

    assert_tool_allowed("navigate", tool)


@mcp.tool()
async def list_providers(specialty: str = "") -> dict:
    _scope("list_providers")
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get(f"{ORCH}/directory/providers")
        r.raise_for_status()
        providers = r.json()
    if specialty:
        providers = [p for p in providers if p.get("specialty") == specialty]
    return {"ok": True, "providers": providers}


@mcp.tool()
async def search_slots(provider_id: str) -> dict:
    """Synthetic slots for the next 14 days."""
    _scope("search_slots")
    return {
        "ok": True,
        "provider_id": provider_id,
        "slots": [
            {"id": f"{provider_id}-d{d}", "days_from_now": d, "time": "09:00"}
            for d in range(1, 15)
        ],
    }


if __name__ == "__main__":
    mcp.run()
