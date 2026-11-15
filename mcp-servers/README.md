# Rabt MCP servers

Pinned to **`mcp>=1.1,<2`** (FastMCP import path).

```bash
# from repo root
uv sync
export ORCH_BASE_URL=http://localhost:8000
uv run python mcp-servers/fhir-mcp/server.py
uv run python mcp-servers/directory-mcp/server.py
uv run python mcp-servers/messaging-mcp/server.py
```

Connect an MCP client (Cursor / Claude Desktop) with a stdio or SSE launcher pointing at each `server.py`. Tools are **read-scoped** where possible (`read_case_bundle`, `list_providers`, `search_slots`); messaging/write tools should stay behind human review in the pilot.
