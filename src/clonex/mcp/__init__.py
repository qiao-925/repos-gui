# MCP adapter layer for CloneX.
#
# Exposes CloneX capabilities to any MCP-compatible agent
# (Claude Desktop, Cursor, Windsurf, ...).
# Runs as an independent process via `python -m clonex.mcp` and reuses
# the same auth / config files as the CLI and GUI entrypoints.
#
# Keep this module intentionally lightweight; tool registration lives in
# `clonex.mcp.server` and `clonex.mcp.tools`.

__all__ = []
