"""GitHub Gist configuration management for remote config storage."""

import json
import time
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple

import requests

from .auth import load_token
from .logger import log_error, log_info, log_success, log_warning
from .paths import SCRIPT_DIR


class GistConfigManager:
    """Manage configuration files stored in GitHub Gist."""

    # Reserved key inside ``config_cache`` for non-content metadata such as
    # the currently-active gist id. Pure hex gist ids never collide with
    # this name, so the same cache file can hold both shapes safely.
    META_KEY = "_meta"

    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or SCRIPT_DIR / ".gist_cache"
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_file = self.cache_dir / "gist_config.json"
        self.config_cache = self._load_cache()
    
    def _load_cache(self) -> Dict:
        """Load cached gist configuration."""
        if not self.cache_file.exists():
            return {}
        
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            log_error(f"加载 Gist 缓存失败: {e}")
            return {}
    
    def _save_cache(self) -> None:
        """Save gist configuration to cache."""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.config_cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log_error(f"保存 Gist 缓存失败: {e}")
    
    def _get_token(self, provided_token: Optional[str] = None) -> Optional[str]:
        """Get token from provided or auth module."""
        if provided_token:
            return provided_token
        token, _ = load_token()
        return token

    def _get_gist_content(self, gist_id: str, filename: str, token: Optional[str] = None) -> Tuple[bool, str, str]:
        """Download content from GitHub Gist."""
        url = f"https://api.github.com/gists/{gist_id}"
        headers = {"Accept": "application/vnd.github.v3+json"}
        
        effective_token = self._get_token(token)
        if effective_token:
            headers["Authorization"] = f"token {effective_token}"
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            gist_data = response.json()
            files = gist_data.get("files", {})
            
            if filename not in files:
                return False, "", f"Gist 中未找到文件: {filename}"
            
            content = files[filename].get("content", "")
            if not content:
                return False, "", f"文件内容为空: {filename}"
            
            return True, content, ""
            
        except requests.exceptions.RequestException as e:
            return False, "", f"网络请求失败: {e}"
        except Exception as e:
            return False, "", f"解析 Gist 数据失败: {e}"
    
    def download_config(self, gist_id: str, filename: str = "REPO-GROUPS.md", 
                       token: Optional[str] = None, force_refresh: bool = False) -> Tuple[bool, str, str]:
        """Download configuration from Gist with caching."""
        cache_key = f"{gist_id}:{filename}"
        cached = self.config_cache.get(cache_key, {})
        
        # 检查缓存是否有效（1小时内）
        if not force_refresh and cached:
            cache_time = cached.get("timestamp", 0)
            if time.time() - cache_time < 3600:  # 1小时缓存
                log_info(f"使用缓存的 Gist 配置: {filename}")
                return True, cached["content"], ""
        
        log_info(f"从 Gist 下载配置: {filename}")
        success, content, error = self._get_gist_content(gist_id, filename, token)
        
        if success:
            # 更新缓存
            self.config_cache[cache_key] = {
                "content": content,
                "timestamp": time.time(),
                "gist_id": gist_id,
                "filename": filename
            }
            self._save_cache()
            log_success(f"成功下载并缓存配置: {filename}")
        
        return success, content, error
    
    def upload_config(self, gist_id: str, content: str, filename: str = "REPO-GROUPS.md",
                     token: Optional[str] = None, description: Optional[str] = None) -> Tuple[bool, str]:
        """Upload configuration to GitHub Gist."""
        effective_token = self._get_token(token)
        if not effective_token:
            return False, "上传配置需要 GitHub Token"
        
        url = f"https://api.github.com/gists/{gist_id}"
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"token {effective_token}",
            "Content-Type": "application/json"
        }
        
        data = {
            "files": {
                filename: {
                    "content": content
                }
            }
        }
        
        if description:
            data["description"] = description
        
        try:
            response = requests.patch(url, headers=headers, json=data, timeout=10)
            response.raise_for_status()
            
            # 更新缓存
            cache_key = f"{gist_id}:{filename}"
            self.config_cache[cache_key] = {
                "content": content,
                "timestamp": time.time(),
                "gist_id": gist_id,
                "filename": filename
            }
            self._save_cache()
            
            log_success(f"成功上传配置到 Gist: {filename}")
            return True, ""
            
        except requests.exceptions.RequestException as e:
            error_msg = f"上传配置失败: {e}"
            log_error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"处理上传响应失败: {e}"
            log_error(error_msg)
            return False, error_msg
    
    def create_gist(self, content: str, filename: str = "REPO-GROUPS.md",
                   token: Optional[str] = None, description: Optional[str] = None,
                   public: bool = False) -> Tuple[bool, str, str]:
        """Create a new Gist with configuration."""
        effective_token = self._get_token(token)
        if not effective_token:
            return False, "", "创建 Gist 需要 GitHub Token"
        
        url = "https://api.github.com/gists"
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"token {effective_token}",
            "Content-Type": "application/json"
        }
        
        data = {
            "public": public,
            "files": {
                filename: {
                    "content": content
                }
            }
        }
        
        if description:
            data["description"] = description
        else:
            data["description"] = "GitHub 仓库分组配置文件"
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=10)
            response.raise_for_status()
            
            gist_data = response.json()
            gist_id = gist_data.get("id", "")
            gist_url = gist_data.get("html_url", "")
            
            if not gist_id:
                return False, "", "创建 Gist 成功但未获取 ID"
            
            # 更新缓存
            cache_key = f"{gist_id}:{filename}"
            self.config_cache[cache_key] = {
                "content": content,
                "timestamp": time.time(),
                "gist_id": gist_id,
                "filename": filename
            }
            self._save_cache()
            
            log_success(f"成功创建 Gist: {gist_url}")
            return True, gist_id, gist_url
            
        except requests.exceptions.RequestException as e:
            error_msg = f"创建 Gist 失败: {e}"
            log_error(error_msg)
            return False, "", error_msg
        except Exception as e:
            error_msg = f"处理创建响应失败: {e}"
            log_error(error_msg)
            return False, "", error_msg
    
    def get_cached_configs(self) -> Dict[str, Dict]:
        """Get all cached configurations."""
        return self.config_cache.copy()
    
    def clear_cache(self, gist_id: Optional[str] = None, filename: Optional[str] = None) -> None:
        """Clear cached configurations."""
        if gist_id and filename:
            cache_key = f"{gist_id}:{filename}"
            self.config_cache.pop(cache_key, None)
        elif gist_id:
            keys_to_remove = [k for k in self.config_cache.keys() if k.startswith(f"{gist_id}:")]
            for key in keys_to_remove:
                self.config_cache.pop(key, None)
        else:
            self.config_cache.clear()
        
        self._save_cache()
        log_info("已清理 Gist 缓存")
    
    def list_user_gists(self, token: Optional[str] = None) -> Tuple[bool, list, str]:
        """List gists for the authenticated user."""
        effective_token = self._get_token(token)
        if not effective_token:
            return False, [], "需要 GitHub Token 才能获取 Gist 列表"
        
        url = "https://api.github.com/gists"
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"token {effective_token}"
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            gists = response.json()
            return True, gists, ""
            
        except requests.exceptions.RequestException as e:
            return False, [], f"获取 Gist 列表失败: {e}"
        except Exception as e:
            return False, [], f"解析 Gist 列表失败: {e}"

    def find_config_gist(self, gists: list, filename: str = "REPO-GROUPS.md") -> Optional[Dict]:
        """Find a gist that contains the specific configuration file."""
        for gist in gists:
            files = gist.get("files", {})
            if filename in files:
                return {
                    "id": gist.get("id"),
                    "url": gist.get("html_url"),
                    "description": gist.get("description", ""),
                    "updated_at": gist.get("updated_at")
                }
        return None

    def validate_gist_url(self, gist_url: str) -> Tuple[bool, str]:
        """Extract and validate Gist ID from URL."""
        if not gist_url:
            return False, "Gist URL 不能为空"
        
        # 支持多种 URL 格式
        patterns = [
            r"github\.com/[^/]+/([a-f0-9]+)",
            r"gist\.github\.com/[^/]+/([a-f0-9]+)",
            r"^([a-f0-9]+)$"  # 直接的 Gist ID
        ]
        
        import re
        for pattern in patterns:
            match = re.search(pattern, gist_url)
            if match:
                gist_id = match.group(1)
                if len(gist_id) >= 32:  # Gist ID 通常至少32位
                    return True, gist_id
        
        return False, "无效的 Gist URL 格式"

    # ------------------------------------------------------------------
    # Active-gist tracking and end-to-end discover-or-create helper
    # ------------------------------------------------------------------

    def get_active_gist_id(self, filename: str = "REPO-GROUPS.md") -> Optional[str]:
        """Return the gist id currently bound to ``filename``, if cached."""
        meta = self.config_cache.get(self.META_KEY, {})
        if not isinstance(meta, dict):
            return None
        active_map = meta.get("active_gist_ids", {})
        if not isinstance(active_map, dict):
            return None
        value = active_map.get(filename)
        return value if isinstance(value, str) and value else None

    def set_active_gist_id(self, gist_id: str, filename: str = "REPO-GROUPS.md") -> None:
        """Persist ``gist_id`` as the active binding for ``filename``."""
        meta = self.config_cache.setdefault(self.META_KEY, {})
        if not isinstance(meta, dict):
            meta = {}
            self.config_cache[self.META_KEY] = meta
        active_map = meta.setdefault("active_gist_ids", {})
        if not isinstance(active_map, dict):
            active_map = {}
            meta["active_gist_ids"] = active_map
        active_map[filename] = gist_id
        self._save_cache()

    @staticmethod
    def default_initial_content(owner: str) -> str:
        """Bootstrap content used when auto-creating a brand new gist."""
        return (
            "# GitHub 仓库分组\n"
            "\n"
            f"仓库所有者: {owner}\n"
            "\n"
            "## 未分类\n"
        )

    def discover_or_create_repo_groups_gist(
        self,
        owner: str,
        token: Optional[str] = None,
        filename: str = "REPO-GROUPS.md",
        initial_content_factory: Optional[Callable[[], str]] = None,
    ) -> Tuple[bool, str, str, bool, str]:
        """Find or create a gist that holds ``filename``.

        Resolution order:

        1. Trust the cached active id if the file is still readable.
        2. Otherwise list the user's gists and find one with that filename.
        3. Otherwise create a new private gist with bootstrap content.

        Returns ``(ok, gist_id, gist_url, was_created, error)``. The
        ``error`` field is empty on success.
        """

        # Step 1: cached active id, if any
        cached_id = self.get_active_gist_id(filename)
        if cached_id:
            ok, _, _ = self._get_gist_content(cached_id, filename, token)
            if ok:
                gist_url = f"https://gist.github.com/{owner}/{cached_id}" if owner else f"https://gist.github.com/{cached_id}"
                return True, cached_id, gist_url, False, ""
            log_info(f"缓存的 Gist ID 已失效，重新发现: {cached_id}")

        # Step 2: search the user's gists
        ok, gists, err = self.list_user_gists(token)
        if not ok:
            return False, "", "", False, err

        found = self.find_config_gist(gists, filename)
        if found:
            gist_id = found.get("id") or ""
            gist_url = found.get("url") or (f"https://gist.github.com/{owner}/{gist_id}" if owner else f"https://gist.github.com/{gist_id}")
            if not gist_id:
                return False, "", "", False, "Gist 列表中找到匹配项但缺少 id"
            self.set_active_gist_id(gist_id, filename)
            log_info(f"已发现现有 Gist: {gist_url}")
            return True, gist_id, gist_url, False, ""

        # Step 3: create a brand new gist
        content = (initial_content_factory or (lambda: self.default_initial_content(owner)))()
        ok, gist_id, gist_url_or_err = self.create_gist(
            content,
            filename=filename,
            token=token,
            description="CloneX Configuration (Auto-created)",
            public=False,
        )
        if not ok:
            return False, "", "", False, gist_url_or_err
        self.set_active_gist_id(gist_id, filename)
        log_success(f"已创建新的 Gist: {gist_url_or_err}")
        return True, gist_id, gist_url_or_err, True, ""


# 全局实例
gist_manager = GistConfigManager()


__all__ = [
    "GistConfigManager",
    "gist_manager",
]
