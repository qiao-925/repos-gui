# Shared fixtures and helpers for MCP server tests.
#
# Core idea: use `mcp.shared.memory.create_connected_server_and_client_session`
# to wire a real ClientSession to the CloneX FastMCP instance through in-memory
# streams — no subprocess, no stdio, no network. This is the same helper the
# official SDK's own test suite uses.

from __future__ import annotations

import json
from typing import Any, Mapping

import pytest
from mcp import ClientSession
from mcp.shared.memory import create_connected_server_and_client_session


# Force anyio to use asyncio only (avoid duplicate runs under trio).
@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def mcp_client():
    """Return a live MCP `ClientSession` already connected to the CloneX server.

    Importing `clonex.mcp.server` triggers registration of all 16 tools
    on the shared FastMCP instance as a side effect.
    """
    # Side-effect import: register tools.
    from clonex.mcp import server as _server  # noqa: F401
    from clonex.mcp.app import mcp

    async with create_connected_server_and_client_session(mcp) as session:
        yield session


async def call(
    client: ClientSession, tool_name: str, arguments: Mapping[str, Any] | None = None
) -> dict:
    """Invoke a CloneX MCP tool and parse the JSON payload it returned.

    CloneX tools always return a dict via `ok(...) / err(...)`. FastMCP
    serializes that dict as JSON in a single `TextContent` item.
    """
    result = await client.call_tool(tool_name, dict(arguments or {}))
    assert result.content, f"tool {tool_name!r} returned empty content"
    first = result.content[0]
    text = getattr(first, "text", None)
    assert isinstance(text, str), f"tool {tool_name!r} did not return TextContent"
    return json.loads(text)


def assert_ok(payload: dict, *, tool: str = "") -> dict:
    """Assert payload is a success envelope and return its data dict."""
    assert payload.get("success") is True, f"{tool}: expected success, got {payload}"
    return payload.get("data") or {}


def assert_err(payload: dict, expected_code: str | None = None, *, tool: str = "") -> dict:
    """Assert payload is a failure envelope and return its error dict."""
    assert payload.get("success") is False, f"{tool}: expected error, got {payload}"
    error = payload.get("error") or {}
    assert "code" in error and "message" in error, f"{tool}: malformed error {error}"
    if expected_code is not None:
        assert error["code"] == expected_code, (
            f"{tool}: expected code {expected_code}, got {error['code']}"
        )
    return error
