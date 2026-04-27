# FastMCP singleton. Kept in its own module to avoid circular imports
# between `server.py` (which registers tools) and each `tools/*.py` module
# (which needs the instance to call @mcp.tool()).

from mcp.server.fastmcp import FastMCP


mcp = FastMCP("clonex-mcp")
