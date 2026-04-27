# CloneX MCP server entry point.
#
# Importing the tool modules triggers their @mcp.tool() registration as a
# side effect. Keep `from .tools import ...` after any setup you want to run
# before tools are registered.

from ..infra.logger import set_log_callback
from .app import mcp

# Side-effect imports: register all tools on the shared FastMCP instance.
from .tools import queries as _queries  # noqa: F401
from .tools import groups as _groups  # noqa: F401
from .tools import execution as _execution  # noqa: F401
from .tools import batch as _batch  # noqa: F401
from .tools import flows as _flows  # noqa: F401


def main() -> None:
    """Start the MCP server (stdio transport by default).

    stdio transport multiplexes JSON-RPC over ``sys.stdin``/``sys.stdout``;
    any ``print`` to stdout from the logger would corrupt the protocol and
    break the client session mid-execution. Route log output to stderr only
    (file logger stays intact) before handing control over to ``mcp.run()``.
    """
    set_log_callback(None, log_to_stdout=False, log_to_stderr=True)
    mcp.run()


if __name__ == "__main__":
    main()
