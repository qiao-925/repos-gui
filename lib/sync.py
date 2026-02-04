# GitHub 公共仓库同步模块：从 GitHub 拉取公共仓库列表并更新 REPO-GROUPS.md
#
# 主要功能：
#   - sync_repos()：同步新增仓库到“未分类”分组
#   - 只处理新增仓库，不处理删除/改名/转移

import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import List, Optional, Tuple

from lib.config import CONFIG_FILE
from lib.logger import log_error, log_info, log_success
from lib.paths import SCRIPT_DIR


OWNER_PATTERN = re.compile(r'^仓库所有者:\s*(.+)$', re.MULTILINE)
GROUP_HEADER_PATTERN = re.compile(r'^##\s+(.+?)(?:\s*<!--\s*(.+?)\s*-->)?\s*$')
REPO_LINE_PATTERN = re.compile(r'^-\s+(\S+)')


def _resolve_config_path(config_file: str) -> Path:
    config_path = Path(config_file)
    if not config_path.is_absolute():
        if not re.match(r'^[A-Za-z]:', str(config_path)):
            config_path = SCRIPT_DIR / config_path
    return config_path


def _read_text_preserve_encoding(path: Path) -> Tuple[str, str, str, bool]:
    raw = path.read_bytes()
    encoding = 'utf-8'
    if raw.startswith(b'\xef\xbb\xbf'):
        encoding = 'utf-8-sig'
    text = raw.decode(encoding)
    newline = '\r\n' if '\r\n' in text else '\n'
    has_trailing_newline = text.endswith('\n')
    return text, encoding, newline, has_trailing_newline


def _write_text_preserve_encoding(
    path: Path,
    text: str,
    encoding: str,
    newline: str,
    has_trailing_newline: bool
) -> None:
    if has_trailing_newline and not text.endswith(newline):
        text += newline
    with path.open('w', encoding=encoding, newline='') as handle:
        handle.write(text)


def _extract_owner(content: str) -> str:
    match = OWNER_PATTERN.search(content)
    if not match:
        raise ValueError("未找到仓库所有者信息")
    owner = match.group(1).strip()
    if not owner:
        raise ValueError("仓库所有者信息为空")
    return owner


def _extract_existing_repos(content: str) -> List[str]:
    repos = []
    for match in REPO_LINE_PATTERN.finditer(content):
        repo_name = match.group(1).strip()
        if repo_name:
            repos.append(repo_name)
    return repos


def _fetch_public_repo_names(
    owner: str,
    timeout: int = 10,
    token: Optional[str] = None
) -> List[str]:
    repos: List[str] = []
    page = 1
    per_page = 100

    while True:
        url = f"https://api.github.com/users/{owner}/repos?per_page={per_page}&page={page}"
        headers = {"User-Agent": "repos-sync"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
            headers["Accept"] = "application/vnd.github+json"
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise ValueError(f"未找到用户: {owner}")
            if e.code == 403:
                raise ValueError("GitHub API 访问受限（可能触发了频率限制）")
            raise ValueError(f"GitHub API 请求失败: HTTP {e.code}")
        except urllib.error.URLError as e:
            raise ValueError(f"无法连接 GitHub API: {e}")
        except Exception as e:
            raise ValueError(f"解析 GitHub API 响应失败: {e}")

        if not isinstance(data, list):
            message = data.get("message") if isinstance(data, dict) else "未知错误"
            raise ValueError(f"GitHub API 返回异常: {message}")

        if not data:
            break

        for repo in data:
            name = repo.get("name")
            if name:
                repos.append(name)

        if len(data) < per_page:
            break

        page += 1

    return repos


def read_owner(config_file: str = CONFIG_FILE) -> Tuple[bool, str, str]:
    """读取仓库所有者（不抛异常）。"""
    config_path = _resolve_config_path(config_file)
    if not config_path.exists():
        return False, "", f"配置文件不存在: {config_path}"
    if not config_path.is_file():
        return False, "", f"不是有效的文件: {config_path}"

    try:
        content, _, _, _ = _read_text_preserve_encoding(config_path)
    except Exception as e:
        return False, "", f"读取配置文件失败: {e}"

    try:
        owner = _extract_owner(content)
    except ValueError as e:
        return False, "", str(e)
    return True, owner, ""


def write_owner(config_file: str, owner: str) -> Tuple[bool, str]:
    """写入或更新仓库所有者（保持编码/换行）。"""
    config_path = _resolve_config_path(config_file)
    if not config_path.exists():
        return False, f"配置文件不存在: {config_path}"
    if not config_path.is_file():
        return False, f"不是有效的文件: {config_path}"

    try:
        content, encoding, newline, has_trailing_newline = _read_text_preserve_encoding(config_path)
    except Exception as e:
        return False, f"读取配置文件失败: {e}"

    lines = content.splitlines()
    updated = False

    for i, line in enumerate(lines):
        if OWNER_PATTERN.match(line):
            lines[i] = f"仓库所有者: {owner}"
            updated = True
            break

    if not updated:
        insert_at = 0
        if lines:
            insert_at = 1
            if len(lines) > 1 and lines[1].strip() == "":
                insert_at = 2
        lines.insert(insert_at, f"仓库所有者: {owner}")
        # 确保与后续内容有空行间隔
        if insert_at + 1 < len(lines) and lines[insert_at + 1].strip() != "":
            lines.insert(insert_at + 1, "")

    updated_text = newline.join(lines)
    try:
        _write_text_preserve_encoding(
            config_path,
            updated_text,
            encoding,
            newline,
            has_trailing_newline
        )
    except Exception as e:
        return False, f"写入配置文件失败: {e}"

    return True, ""


def _add_repos_to_unclassified(
    lines: List[str],
    new_repos: List[str]
) -> Tuple[List[str], int]:
    if not new_repos:
        return lines, 0

    group_indices = []
    for index, line in enumerate(lines):
        match = GROUP_HEADER_PATTERN.match(line)
        if match:
            group_indices.append((index, match.group(1).strip()))

    sections = []
    unclassified_section = None
    for i, (start, group_name) in enumerate(group_indices):
        end = group_indices[i + 1][0] if i + 1 < len(group_indices) else len(lines)
        sections.append((start, end, group_name))
        if group_name == "未分类":
            unclassified_section = (start, end, group_name)

    # 不存在“未分类”分组：追加到末尾
    if unclassified_section is None:
        if lines and lines[-1].strip() != "":
            lines.append("")
        lines.append("## 未分类 <!-- 未分类 -->")
        for repo in new_repos:
            lines.append(f"- {repo}")
        return lines, len(new_repos)

    start, end, _ = unclassified_section
    existing_in_section = set()
    for line in lines[start + 1:end]:
        match = REPO_LINE_PATTERN.match(line)
        if match:
            existing_in_section.add(match.group(1).strip())

    to_add = [repo for repo in new_repos if repo not in existing_in_section]
    if not to_add:
        return lines, 0

    insert_at = end
    while insert_at > start + 1 and lines[insert_at - 1].strip() == "":
        insert_at -= 1

    for offset, repo in enumerate(to_add):
        lines.insert(insert_at + offset, f"- {repo}")

    return lines, len(to_add)


def preview_sync(
    config_file: str = CONFIG_FILE,
    owner_override: Optional[str] = None,
    token: Optional[str] = None
) -> Tuple[bool, str, List[str], str]:
    """预览同步：获取新增仓库列表但不写入文件。

    Args:
        config_file: REPO-GROUPS.md 路径

    Returns:
        (成功标志, owner, 新增仓库列表, 错误信息)
    """
    config_path = _resolve_config_path(config_file)
    if not config_path.exists():
        return False, "", [], f"配置文件不存在: {config_path}"
    if not config_path.is_file():
        return False, "", [], f"不是有效的文件: {config_path}"

    try:
        content, _, _, _ = _read_text_preserve_encoding(config_path)
    except Exception as e:
        return False, "", [], f"读取配置文件失败: {e}"

    owner = ""
    if owner_override:
        owner = owner_override.strip()
    else:
        try:
            owner = _extract_owner(content)
        except ValueError as e:
            return False, "", [], str(e)

    if not owner:
        return False, "", [], "仓库所有者信息为空"

    existing_repos = set(_extract_existing_repos(content))

    try:
        remote_repos = _fetch_public_repo_names(owner, token=token)
    except ValueError as e:
        return False, owner, [], str(e)

    new_repos = sorted([repo for repo in remote_repos if repo not in existing_repos])
    return True, owner, new_repos, ""


def apply_sync(config_file: str, new_repos: List[str]) -> Tuple[bool, str]:
    """应用同步：将新增仓库写入"未分类"分组。

    Args:
        config_file: REPO-GROUPS.md 路径
        new_repos: 新增仓库列表

    Returns:
        (成功标志, 错误信息)
    """
    config_path = _resolve_config_path(config_file)
    if not config_path.exists():
        return False, f"配置文件不存在: {config_path}"

    try:
        content, encoding, newline, has_trailing_newline = _read_text_preserve_encoding(config_path)
    except Exception as e:
        return False, f"读取配置文件失败: {e}"

    lines = content.splitlines()
    updated_lines, added_count = _add_repos_to_unclassified(lines, new_repos)
    if added_count == 0:
        return True, ""

    updated_text = newline.join(updated_lines)
    try:
        _write_text_preserve_encoding(
            config_path,
            updated_text,
            encoding,
            newline,
            has_trailing_newline
        )
    except Exception as e:
        return False, f"写入配置文件失败: {e}"

    return True, ""


def sync_repos(config_file: str = CONFIG_FILE) -> int:
    """同步新增仓库到"未分类"分组。

    Args:
        config_file: REPO-GROUPS.md 路径

    Returns:
        0 表示成功，1 表示失败
    """
    config_path = _resolve_config_path(config_file)
    if not config_path.exists():
        log_error(f"配置文件不存在: {config_path}")
        return 1
    if not config_path.is_file():
        log_error(f"不是有效的文件: {config_path}")
        return 1

    try:
        content, encoding, newline, has_trailing_newline = _read_text_preserve_encoding(config_path)
    except Exception as e:
        log_error(f"读取配置文件失败: {config_path} - {e}")
        return 1

    try:
        owner = _extract_owner(content)
    except ValueError as e:
        log_error(str(e))
        return 1

    existing_repos = set(_extract_existing_repos(content))

    log_info(f"开始同步公共仓库（owner: {owner}）")
    try:
        remote_repos = _fetch_public_repo_names(owner)
    except ValueError as e:
        log_error(str(e))
        return 1

    new_repos = sorted([repo for repo in remote_repos if repo not in existing_repos])
    if not new_repos:
        log_info("没有新增仓库，REPO-GROUPS.md 已是最新")
        return 0

    lines = content.splitlines()
    updated_lines, added_count = _add_repos_to_unclassified(lines, new_repos)
    if added_count == 0:
        log_info("未分类分组已包含新增仓库，无需更新")
        return 0

    updated_text = newline.join(updated_lines)
    try:
        _write_text_preserve_encoding(
            config_path,
            updated_text,
            encoding,
            newline,
            has_trailing_newline
        )
    except Exception as e:
        log_error(f"写入配置文件失败: {config_path} - {e}")
        return 1

    log_success(f"同步完成，新增 {added_count} 个仓库已写入\"未分类\"")
    for repo in new_repos:
        log_info(f"+ {repo}")

    return 0
