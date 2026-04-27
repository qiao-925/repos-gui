"""Generate VS Code / Cursor / Windsurf workspace files per group.

A `.code-workspace` file is a small JSON document that lists multiple
folders so the IDE can open all of them as a single multi-root workspace.

For each cloned group we drop a workspace file inside that group's local
folder, with relative paths pointing at every successfully cloned repo:

    clonex-repos/
    └─ Personal/
       ├─ typing-hub/
       ├─ mobile-typing/
       └─ Personal.code-workspace      <-- generated here

The file uses relative paths so the workspace stays valid when the parent
directory is renamed or moved across machines.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable, List, Tuple

from ..infra.logger import log_error, log_info, log_success


# Characters that would break or look ugly inside a workspace filename.
# Slashes / backslashes / colons are forbidden on Windows; the rest are
# replaced for readability (e.g. "AI / Agents" -> "AI _ Agents").
_FILENAME_REPLACEMENTS = {
    "/": "_",
    "\\": "_",
    ":": "_",
    "*": "_",
    "?": "_",
    '"': "_",
    "<": "_",
    ">": "_",
    "|": "_",
}


def sanitize_workspace_filename(group_name: str) -> str:
    """Make a filesystem-safe workspace base name from a group name.

    The result preserves whitespace and unicode, only swapping characters
    that are illegal or noisy in filenames. Multiple consecutive
    replacement characters are collapsed and trimmed.
    """

    name = (group_name or "").strip()
    if not name:
        return "workspace"

    for src, dst in _FILENAME_REPLACEMENTS.items():
        name = name.replace(src, dst)

    name = re.sub(r"_+", "_", name)
    name = name.strip(" _.")
    return name or "workspace"


def build_workspace_payload(repo_dir_names: Iterable[str]) -> dict:
    """Build the JSON payload of a .code-workspace file.

    Folders are referenced via relative paths (`./repo-name`) so the
    workspace stays valid regardless of where the parent directory ends
    up.
    """

    folders: List[dict] = []
    seen: set[str] = set()
    for name in repo_dir_names:
        cleaned = (name or "").strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        folders.append({"path": f"./{cleaned}"})

    return {"folders": folders, "settings": {}}


def write_workspace_file(group_dir: Path, group_name: str, repo_dir_names: Iterable[str]) -> Tuple[bool, str]:
    """Write `<group_dir>/<sanitized_name>.code-workspace`.

    Returns ``(ok, written_path_or_error)``. The function is best-effort:
    failures are logged but never raise.
    """

    folder = Path(group_dir)
    if not folder.exists() or not folder.is_dir():
        msg = f"workspace target is not a directory: {folder}"
        log_error(msg)
        return False, msg

    base = sanitize_workspace_filename(group_name)
    target = folder / f"{base}.code-workspace"
    payload = build_workspace_payload(repo_dir_names)

    if not payload["folders"]:
        log_info(f"skip workspace ({group_name}): no folders to reference")
        return False, "no folders"

    try:
        text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        target.write_text(text, encoding="utf-8")
    except Exception as exc:
        msg = f"write workspace failed: {target} - {exc}"
        log_error(msg)
        return False, msg

    log_success(f"workspace generated: {target}")
    return True, str(target)


__all__ = [
    "sanitize_workspace_filename",
    "build_workspace_payload",
    "write_workspace_file",
]
