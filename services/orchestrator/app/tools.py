"""Tool scope enforcement for agent delegation."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from app.contracts import TOOL_SCOPES

log = logging.getLogger("rabt.tools")


class ToolScopeError(PermissionError):
    """Agent attempted a tool outside its allowed scope."""


def assert_tool_allowed(agent_step: str, tool_name: str) -> None:
    allowed = TOOL_SCOPES.get(agent_step) or []
    if tool_name not in allowed:
        log.warning("tool_refused step=%s tool=%s allowed=%s", agent_step, tool_name, allowed)
        raise ToolScopeError(f"tool {tool_name!r} not in scope for {agent_step!r}")


async def invoke_tool(
    agent_step: str,
    tool_name: str,
    fn: Callable[..., Any],
    *args: Any,
    **kwargs: Any,
) -> Any:
    assert_tool_allowed(agent_step, tool_name)
    return await fn(*args, **kwargs) if _is_awaitable_fn(fn) else fn(*args, **kwargs)


def _is_awaitable_fn(fn: Callable[..., Any]) -> bool:
    import asyncio
    import inspect

    return inspect.iscoroutinefunction(fn) or asyncio.iscoroutinefunction(fn)
