# Unified error codes + response builders for all MCP tools.
#
# Tools never raise exceptions to the client. They return:
#   {"success": True, "data": ...}
#   {"success": False, "error": {"code": ..., "message": ..., "hint"?: ...}}

from typing import Any, Dict, Optional

E_AUTH_MISSING = "E_AUTH_MISSING"
E_CONFIG_MISSING = "E_CONFIG_MISSING"
E_GITHUB_API = "E_GITHUB_API"
E_GIT_EXEC = "E_GIT_EXEC"
E_INVALID_ARG = "E_INVALID_ARG"
E_DRY_RUN_BLOCKED = "E_DRY_RUN_BLOCKED"
E_INTERNAL = "E_INTERNAL"


def ok(data: Any = None) -> Dict[str, Any]:
    """Build a successful tool response."""
    result: Dict[str, Any] = {"success": True}
    if data is not None:
        result["data"] = data
    return result


def err(code: str, message: str, hint: Optional[str] = None) -> Dict[str, Any]:
    """Build a failure tool response."""
    payload: Dict[str, str] = {"code": code, "message": message}
    if hint:
        payload["hint"] = hint
    return {"success": False, "error": payload}
