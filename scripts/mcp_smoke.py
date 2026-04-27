"""End-to-end smoke test: drive the CloneX MCP server over a real MCP session.

Unlike `tests/mcp/` (fully mocked, fast, hermetic), this script does NOT mock
anything. It exercises the server against the real keyring credentials and
the real GitHub API, but communicates through an in-memory MCP transport so
no subprocess/stdio is needed.

Run with:
    uv run --group test python scripts/mcp_smoke.py
or (if only the `mcp` extra is installed):
    uv run --extra mcp python scripts/mcp_smoke.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Mapping

# Allow running from the repo root without installing the package.
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import anyio  # noqa: E402  (after sys.path tweak)


def _pretty(label: str, payload: Any) -> None:
    separator = "=" * 60
    print(f"\n{separator}\n{label}\n{separator}")
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


async def _call(client, tool_name: str, arguments: Mapping[str, Any] | None = None) -> dict:
    result = await client.call_tool(tool_name, dict(arguments or {}))
    assert result.content, f"tool {tool_name!r} returned empty content"
    first = result.content[0]
    text = getattr(first, "text", None)
    assert isinstance(text, str), f"tool {tool_name!r} did not return TextContent"
    return json.loads(text)


async def run() -> int:
    # Importing the server module registers all 16 tools on the shared
    # FastMCP instance.
    from clonex.mcp import server as _server  # noqa: F401
    from clonex.mcp.app import mcp
    from mcp.shared.memory import create_connected_server_and_client_session

    async with create_connected_server_and_client_session(mcp) as client:
        tools = await client.list_tools()
        print(f"\nServer exposes {len(tools.tools)} tools:")
        for tool in tools.tools:
            print(f"  - {tool.name}")

        auth = await _call(client, "get_auth_status")
        _pretty("get_auth_status()", auth)

        logged_in = bool((auth.get("data") or {}).get("logged_in"))
        if not logged_in:
            print(
                "\nNot logged in; skipping list_repos. "
                "Run the CloneX GUI once to authenticate, then re-run this smoke test."
            )
        else:
            repos = await _call(client, "list_repos")
            if repos.get("success"):
                data = dict(repos["data"])
                data["repos"] = [r.get("name", "") for r in data.get("repos", [])][:10]
                data["repos_shown"] = min(10, data.get("count", 0))
                _pretty("list_repos() (first 10 names only)", {"success": True, "data": data})
            else:
                _pretty("list_repos()", repos)

        groups = await _call(client, "read_groups")
        _pretty("read_groups()", groups)

        failed = await _call(client, "list_failed")
        _pretty("list_failed()", failed)

    print("\nSmoke test finished.")
    return 0


def main() -> int:
    return anyio.run(run)


if __name__ == "__main__":
    raise SystemExit(main())
