# GitHub API：拉取仓库列表（公共仓库）

import json
import urllib.error
import urllib.request
from typing import Dict, List, Optional, Tuple


def _build_repo_item(repo: Dict[str, object]) -> Dict[str, object]:
    owner = repo.get("owner") if isinstance(repo, dict) else {}
    owner_login = ""
    if isinstance(owner, dict):
        owner_login = str(owner.get("login") or "")
    return {
        "name": repo.get("name") or "",
        "description": repo.get("description") or "",
        "language": repo.get("language") or "",
        "topics": repo.get("topics") or [],
        "html_url": repo.get("html_url") or "",
        "private": bool(repo.get("private", False)),
        "owner_login": owner_login,
    }


def _fetch_repo_pages(
    url_builder,
    token: Optional[str],
    timeout: int,
    not_found_message: str = "",
) -> Tuple[bool, List[Dict[str, object]], str]:
    repos: List[Dict[str, object]] = []
    page = 1
    per_page = 100

    while True:
        url = url_builder(page, per_page)
        headers = {
            "User-Agent": "CloneX",
            "Accept": "application/vnd.github+json",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"

        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 401:
                return False, [], "GitHub Token 无效或已过期"
            if e.code == 404 and not_found_message:
                return False, [], not_found_message
            if e.code == 403:
                return False, [], "GitHub API 访问受限（可能触发了频率限制）"
            return False, [], f"GitHub API 请求失败: HTTP {e.code}"
        except urllib.error.URLError as e:
            return False, [], f"无法连接 GitHub API: {e}"
        except Exception as e:
            return False, [], f"解析 GitHub API 响应失败: {e}"

        if not isinstance(data, list):
            message = data.get("message") if isinstance(data, dict) else "未知错误"
            return False, [], f"GitHub API 返回异常: {message}"

        if not data:
            break

        for repo in data:
            if isinstance(repo, dict):
                repos.append(_build_repo_item(repo))

        if len(data) < per_page:
            break

        page += 1

    return True, repos, ""


def fetch_public_repos(
    owner: str,
    token: Optional[str] = None,
    timeout: int = 10
) -> Tuple[bool, List[Dict[str, object]], str]:
    return _fetch_repo_pages(
        lambda page, per_page: f"https://api.github.com/users/{owner}/repos?per_page={per_page}&page={page}",
        token=token,
        timeout=timeout,
        not_found_message=f"未找到用户: {owner}",
    )


def fetch_owner_repos(
    owner: str,
    token: Optional[str] = None,
    timeout: int = 10,
) -> Tuple[bool, List[Dict[str, object]], str]:
    normalized_owner = owner.strip()
    if not normalized_owner:
        return False, [], "仓库所有者不能为空"

    public_success, public_repos, public_error = fetch_public_repos(normalized_owner, token=token, timeout=timeout)
    if not public_success:
        return False, [], public_error

    if not token:
        return True, public_repos, ""

    success, repos, error = _fetch_repo_pages(
        lambda page, per_page: (
            "https://api.github.com/user/repos"
            f"?visibility=all&affiliation=owner,collaborator,organization_member&per_page={per_page}&page={page}"
        ),
        token=token,
        timeout=timeout,
    )
    if not success:
        return False, [], error

    owner_key = normalized_owner.casefold()
    filtered_repos = [
        repo for repo in repos
        if str(repo.get("owner_login") or "").casefold() == owner_key
    ]

    merged_repos: Dict[str, Dict[str, object]] = {
        str(repo.get("name") or ""): repo
        for repo in public_repos
        if str(repo.get("name") or "")
    }
    for repo in filtered_repos:
        name = str(repo.get("name") or "")
        if name:
            merged_repos[name] = repo

    return True, list(merged_repos.values()), ""
