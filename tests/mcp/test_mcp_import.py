"""Smoke: MCP servers import and expose tools (mcp>=1.1,<2)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2] / "mcp-servers"
SERVERS = ["fhir-mcp", "directory-mcp", "messaging-mcp"]


@pytest.mark.parametrize("name", SERVERS)
def test_mcp_server_imports_and_has_tools(name: str):
    path = ROOT / name / "server.py"
    assert path.exists(), path
    spec = importlib.util.spec_from_file_location(f"rabt_{name.replace('-', '_')}", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert hasattr(mod, "mcp")
    # FastMCP registers tools on the instance
    tools = getattr(mod.mcp, "_tool_manager", None) or getattr(mod.mcp, "tools", None)
    assert tools is not None
