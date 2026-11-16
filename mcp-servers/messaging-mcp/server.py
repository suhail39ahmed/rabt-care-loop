"""Messaging MCP — console / Mailpit adapters."""

from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

CHANNEL = os.environ.get("CHANNEL", "console")
mcp = FastMCP("rabt-messaging")


@mcp.tool()
async def send_message(to: str, text: str, channel: str | None = None) -> dict:
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root / "services" / "orchestrator"))
    from app.tools import assert_tool_allowed

    assert_tool_allowed("escalation", "send_message")
    ch = channel or CHANNEL
    if ch == "console":
        print(f"[console:{to}] {text}")
        return {"ok": True, "channel": ch, "delivered": True}
    # Mailpit / ACS would plug in here
    print(f"[{ch}:{to}] {text}")
    return {"ok": True, "channel": ch, "delivered": True, "note": "prototype adapter"}


if __name__ == "__main__":
    mcp.run()
