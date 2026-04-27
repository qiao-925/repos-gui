# Shared helpers for MCP tools: credentials, paths, config resolution.
#
# These functions wrap `infra/` and `core/` so tool modules stay thin.

from pathlib import Path
from typing import Optional

from ..core import repo_config
from ..infra import auth
from ..infra.paths import REPOS_DIR, SCRIPT_DIR


def get_github_token() -> Optional[str]:
    """Load GitHub token from keyring (preferred) or fallback file.

    Returns None if the user has never authenticated via the GUI.
    """
    token, _source = auth.load_token()
    return token


def get_cached_owner() -> str:
    """Return the cached GitHub login from the GUI, or empty string."""
    return (auth.load_cached_login() or "").strip()


def resolve_config_path(path: Optional[str] = None) -> Path:
    """Resolve a REPO-GROUPS.md path; defaults to the CloneX config default."""
    config_file = path or repo_config.CONFIG_FILE
    return repo_config.resolve_config_path(config_file)


def default_clone_root() -> Path:
    """Return the default clone root (shared with the GUI)."""
    return REPOS_DIR


def failed_repos_path() -> Path:
    """Return the path the GUI uses for the failed-repos list."""
    return SCRIPT_DIR / "failed-repos.txt"
