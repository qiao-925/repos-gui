# Tools for writing REPO-GROUPS.md (B group).
#
# write_groups merges a `{repo_name: group_name}` mapping into the local
# REPO-GROUPS.md file. The mapping is typically produced by the agent itself
# (e.g. by reading list_repos output and applying rules) or comes from an
# external tool; CloneX no longer ships a built-in AI classifier.
#
# Tool list:
#   - write_groups : dry-run preview (default) or persist mapping to disk

from typing import Dict, List

from ...core import repo_config
from ...domain.repo_groups import parse_repo_tasks, render_repo_groups_text
from ...infra.paths import REPOS_DIR
from ..app import mcp
from ..context import (
    get_cached_owner,
    resolve_config_path,
)
from ..errors import (
    E_CONFIG_MISSING,
    E_INTERNAL,
    err,
    ok,
)


@mcp.tool()
def write_groups(
    mapping: Dict[str, str],
    owner: str = "",
    path: str = "",
    dry_run: bool = True,
) -> dict:
    """Write `mapping: {repo_name: group_name}` to REPO-GROUPS.md.

    `dry_run=True` (default) returns a preview of the file content without writing.
    Call again with `dry_run=false` to persist.
    """
    if not mapping:
        return err(E_INTERNAL, "Empty mapping")

    config_path = resolve_config_path(path or None)

    effective_owner = (owner or "").strip()
    if not effective_owner and config_path.exists():
        success, read_owner, _err = repo_config.read_owner(str(config_path))
        if success:
            effective_owner = read_owner
    if not effective_owner:
        effective_owner = get_cached_owner()
    if not effective_owner:
        return err(E_CONFIG_MISSING, "Owner not provided and could not be inferred")

    # Read existing state so write_groups acts as an *incremental* update:
    # any repo already listed is preserved, new mapping entries overwrite their
    # group, and repos absent from `mapping` keep their existing group.
    existing_assignments: Dict[str, str] = {}
    existing_groups: List[str] = []
    tags: Dict[str, str] = {}
    if config_path.exists():
        existing_groups, tags = repo_config.load_groups_from_file(str(config_path))
        try:
            content, _enc, _nl, _trail = repo_config.read_text_preserve_encoding(config_path)
            for task in parse_repo_tasks(content, effective_owner, REPOS_DIR):
                existing_assignments[task.repo_name] = task.group_name
        except Exception as exc:
            # Refuse to write when we cannot read the current file: silently
            # falling back to an empty baseline would drop every existing
            # repo on disk when persisting the merged mapping.
            return err(
                E_INTERNAL,
                f"Failed to read existing REPO-GROUPS.md: {exc}",
            )

    assignments: Dict[str, str] = dict(existing_assignments)
    updated_count = 0
    for name, group in mapping.items():
        clean_name = str(name).strip()
        if not clean_name:
            continue
        clean_group = str(group).strip() or "未分类"
        if assignments.get(clean_name) != clean_group:
            updated_count += 1
        assignments[clean_name] = clean_group

    merged_groups: List[str] = list(existing_groups)
    for group in sorted({v for v in assignments.values()}):
        if group not in merged_groups:
            merged_groups.append(group)
    if "未分类" not in merged_groups:
        merged_groups.append("未分类")

    preview_text = render_repo_groups_text(
        effective_owner, merged_groups, assignments, tags, keep_empty=True
    )

    if dry_run:
        return ok(
            {
                "dry_run": True,
                "path": str(config_path),
                "owner": effective_owner,
                "groups": merged_groups,
                "total_repos": len(assignments),
                "updated_repos": updated_count,
                "would_write_preview": preview_text,
                "hint": "Call again with dry_run=false to persist",
            }
        )

    ok_write, error_msg = repo_config.write_repo_groups(
        str(config_path),
        effective_owner,
        merged_groups,
        assignments,
        tags,
        keep_empty=True,
    )
    if not ok_write:
        return err(E_INTERNAL, error_msg)

    return ok(
        {
            "dry_run": False,
            "path": str(config_path),
            "owner": effective_owner,
            "groups": merged_groups,
            "total_repos": len(assignments),
            "updated_repos": updated_count,
            "written": True,
        }
    )
