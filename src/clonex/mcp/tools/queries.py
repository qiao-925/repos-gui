# Read-only query tools (A group).
#
# Tools:
#   - list_repos      : fetch GitHub repos for an owner
#   - read_groups     : parse local REPO-GROUPS.md
#   - list_failed     : read the failed-repos list written by previous runs
#   - get_auth_status : report GitHub login / token verification state

from typing import Dict, List, Optional

from ...core import repo_config
from ...domain.repo_groups import (
    extract_existing_repos,
    extract_owner,
    parse_groups_and_tags,
    parse_repo_tasks,
)
from ...infra import auth
from ...infra.github_api import fetch_owner_repos
from ...infra.paths import REPOS_DIR
from ..app import mcp
from ..context import (
    failed_repos_path,
    get_cached_owner,
    get_github_token,
    resolve_config_path,
)
from ..errors import (
    E_AUTH_MISSING,
    E_CONFIG_MISSING,
    E_GITHUB_API,
    E_INTERNAL,
    err,
    ok,
)


@mcp.tool()
def list_repos(owner: str = "", include_private: bool = False) -> dict:
    """List GitHub repositories for the given owner.

    If `owner` is empty, uses the cached login from the CloneX GUI.
    `include_private=True` requires a valid GitHub token (login via the CloneX
    GUI first). Defaults to public-only to minimize scope of data returned.
    """
    effective_owner = (owner or get_cached_owner()).strip()
    if not effective_owner:
        return err(
            E_CONFIG_MISSING,
            "No owner specified and no cached GitHub login found",
            "Log in via the CloneX GUI first",
        )

    token = get_github_token()
    if include_private and not token:
        return err(
            E_AUTH_MISSING,
            "Private repos requested but no GitHub token available",
            "Log in via the CloneX GUI first",
        )

    # When include_private=False, do not send the token — this keeps the API
    # response to public repos only, giving the agent the smallest useful scope.
    token_for_api = token if include_private else None
    success, repos, error_msg = fetch_owner_repos(
        effective_owner,
        token=token_for_api,
    )
    if not success:
        return err(E_GITHUB_API, error_msg or "Failed to fetch repos")

    return ok({"owner": effective_owner, "count": len(repos), "repos": repos})


@mcp.tool()
def read_groups(path: str = "") -> dict:
    """Read REPO-GROUPS.md and return the parsed owner, groups, and repo assignments.

    When `path` is empty, reads the default CloneX config.
    """
    config_path = resolve_config_path(path or None)
    if not config_path.exists():
        return err(
            E_CONFIG_MISSING,
            f"Config file not found: {config_path}",
            "Run CloneX GUI first or pass `path` explicitly",
        )

    try:
        content, _enc, _nl, _trail = repo_config.read_text_preserve_encoding(config_path)
    except Exception as exc:
        return err(E_INTERNAL, f"Read config failed: {exc}")

    try:
        owner = extract_owner(content)
    except ValueError as exc:
        return err(E_CONFIG_MISSING, str(exc))

    groups, tags = parse_groups_and_tags(content)
    tasks = parse_repo_tasks(content, owner, REPOS_DIR)

    assignments: Dict[str, List[str]] = {group: [] for group in groups}
    for task in tasks:
        assignments.setdefault(task.group_name, []).append(task.repo_name)

    return ok(
        {
            "owner": owner,
            "path": str(config_path),
            "groups": [
                {
                    "name": group,
                    "tag": tags.get(group, ""),
                    "repos": assignments.get(group, []),
                }
                for group in groups
            ],
        }
    )


@mcp.tool()
def list_failed() -> dict:
    """List repos from the most recent failed run (shared with the GUI).

    Returns an empty list if no failed-repos file exists yet.
    """
    path = failed_repos_path()
    if not path.exists():
        return ok({"path": str(path), "count": 0, "owner": "", "repos": []})

    try:
        content = path.read_text(encoding="utf-8")
    except Exception as exc:
        return err(E_INTERNAL, f"Read failed list failed: {exc}")

    try:
        owner = extract_owner(content)
    except ValueError:
        owner = ""

    repos = extract_existing_repos(content)
    return ok({"path": str(path), "owner": owner, "count": len(repos), "repos": repos})


@mcp.tool()
def get_auth_status() -> dict:
    """Return current GitHub login status.

    Verifies the token against GitHub's `/user` endpoint to confirm it's still valid.
    """
    token, token_source = auth.load_token()
    cached_login = auth.load_cached_login() or ""

    login = ""
    verified = False
    if token:
        fetched_login, _repos, _err = auth.fetch_user_profile(token)
        if fetched_login:
            login = fetched_login
            verified = True

    return ok(
        {
            "logged_in": bool(token),
            "login": login or cached_login,
            "login_verified": verified,
            "token_source": token_source,
        }
    )
