# GitHub API：拉取仓库列表（公共仓库）

import json
import urllib.error
import urllib.request
from typing import Dict, List, Optional, Tuple


def fetch_public_repos(
    owner: str,
    token: Optional[str] = None,
    timeout: int = 10
) -> Tuple[bool, List[Dict[str, object]], str]:
    repos: List[Dict[str, object]] = []
    page = 1
    per_page = 100

    while True:
        url = f"https://api.github.com/users/{owner}/repos?per_page={per_page}&page={page}"
        headers = {
            "User-Agent": "gh-repos-gui",
            "Accept": "application/vnd.github+json",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"

        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return False, [], f"未找到用户: {owner}"
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
            repos.append({
                "name": repo.get("name") or "",
                "description": repo.get("description") or "",
                "language": repo.get("language") or "",
                "topics": repo.get("topics") or [],
                "html_url": repo.get("html_url") or "",
            })

        if len(data) < per_page:
            break

        page += 1

    return True, repos, ""
