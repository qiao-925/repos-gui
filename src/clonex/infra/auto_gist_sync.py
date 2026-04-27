"""Automatic Gist synchronization for configuration files."""

import json
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

from .auth import load_token
from .gist_config import gist_manager
from .logger import log_error, log_info, log_success, log_warning


class AutoGistSync:
    """Automatic Gist synchronization manager."""
    
    def __init__(self, config_file: str, token: Optional[str] = None):
        self.config_file = config_file
        self.token = token
        self.settings_file = Path(config_file).parent / ".auto_gist_settings.json"
        self.settings = self._load_settings()
    
    def _load_settings(self) -> Dict:
        """Load auto-sync settings."""
        if not self.settings_file.exists():
            return {
                "enabled": False,
                "gist_id": "",
                "auto_upload": False,
                "auto_download": False,
                "last_sync": 0,
                "sync_interval": 3600,  # 1 hour
                "conflict_resolution": "local"  # local, remote, manual
            }
        
        try:
            with open(self.settings_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            log_error(f"加载自动同步设置失败: {e}")
            return {}
    
    def _save_settings(self) -> None:
        """Save auto-sync settings."""
        try:
            self.settings_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log_error(f"保存自动同步设置失败: {e}")
    
    def is_enabled(self) -> bool:
        """Check if auto-sync is enabled."""
        return self.settings.get("enabled", False)
    
    def _get_token(self, provided_token: Optional[str] = None) -> Optional[str]:
        """Get token from provided or auth module."""
        if provided_token:
            return provided_token
        token, _ = load_token()
        return token

    def enable_auto_sync(self, gist_id: str, auto_upload: bool = True, auto_download: bool = True) -> Tuple[bool, str]:
        """Enable automatic synchronization."""
        if not gist_id:
            return False, "Gist ID 不能为空"
        
        effective_token = self._get_token(self.token)
        if not effective_token:
            return False, "需要 GitHub Token 才能启用自动同步"
        
        # 验证 Gist 是否存在且可访问
        success, content, error = gist_manager.download_config(gist_id, "REPO-GROUPS.md", effective_token)
        if not success:
            return False, f"无法访问 Gist: {error}"
        
        self.settings.update({
            "enabled": True,
            "gist_id": gist_id,
            "auto_upload": auto_upload,
            "auto_download": auto_download,
            "last_sync": int(time.time())
        })
        self._save_settings()
        
        log_success(f"已启用自动同步，Gist ID: {gist_id}")
        return True, "自动同步已启用"
    
    def disable_auto_sync(self) -> None:
        """Disable automatic synchronization."""
        self.settings["enabled"] = False
        self._save_settings()
        log_info("已禁用自动同步")
    
    def should_sync(self) -> bool:
        """Check if synchronization should be performed."""
        if not self.is_enabled():
            return False
        
        last_sync = self.settings.get("last_sync", 0)
        sync_interval = self.settings.get("sync_interval", 3600)
        
        return time.time() - last_sync >= sync_interval
    
    def auto_init_sync(self, token: Optional[str] = None) -> Tuple[bool, str]:
        """Automatically initialize sync by finding or creating a Gist."""
        effective_token = self._get_token(token)
        if not effective_token:
            return False, "未登录 GitHub"

        if self.is_enabled() and self.settings.get("gist_id"):
            return True, "已启用同步"

        # 1. 尝试搜索现有的配置 Gist
        success, gists, error = gist_manager.list_user_gists(effective_token)
        if success:
            gist_info = gist_manager.find_config_gist(gists)
            if gist_info:
                gist_id = gist_info["id"]
                self.settings.update({
                    "enabled": True,
                    "gist_id": gist_id,
                    "auto_upload": True,
                    "auto_download": True,
                    "last_sync": int(time.time())
                })
                self._save_settings()
                log_success(f"自动发现并关联 Gist: {gist_id}")
                return True, "已自动发现并关联配置 Gist"

        # 2. 如果没找到，启用自动上传，首次配置变更时自动创建 Gist
        self.settings.update({
            "enabled": True,
            "auto_upload": True,
            "auto_download": True,
        })
        self._save_settings()
        log_info("未发现现有配置 Gist，将在首次配置变更时自动创建")
        return True, "准备就绪，将在首次同步时创建 Gist"

    def auto_upload_config(self) -> Tuple[bool, str]:
        """Automatically upload configuration to Gist, creating one if needed."""
        if not self.settings.get("auto_upload", True): # 默认开启
            return False, "自动上传未启用"
        
        effective_token = self._get_token(self.token)
        if not effective_token:
            return False, "未获取到有效 Token"

        gist_id = self.settings.get("gist_id", "")
        
        try:
            from ..core.repo_config import save_config_to_gist, create_gist_from_config
            
            if not gist_id:
                # 自动创建私有 Gist
                log_info("正在为用户创建私有配置 Gist...")
                success, new_gist_id, gist_url = create_gist_from_config(
                    self.config_file, 
                    token=effective_token, 
                    public=False,
                    description="CloneX Configuration (Auto-created)"
                )
                if success:
                    gist_id = new_gist_id
                    self.settings.update({
                        "enabled": True,
                        "gist_id": gist_id,
                        "auto_upload": True,
                        "auto_download": True
                    })
                    # 不需要立即保存 settings，下面上传成功后会统一更新 last_sync 并保存
                else:
                    return False, f"自动创建 Gist 失败: {new_gist_id}"

            success, error = save_config_to_gist(self.config_file, gist_id, token=effective_token)
            
            if success:
                self.settings["last_sync"] = int(time.time())
                self._save_settings()
                log_success(f"自动同步成功: {gist_id}")
                return True, "自动同步成功"
            else:
                log_error(f"自动上传配置失败: {error}")
                return False, f"上传失败: {error}"
        
        except Exception as e:
            error_msg = f"自动上传异常: {e}"
            log_error(error_msg)
            return False, error_msg
    
    def auto_download_config(self) -> Tuple[bool, str]:
        """Automatically download configuration from Gist."""
        # 即使没有显式启用，如果存在 gist_id，也尝试静默同步
        gist_id = self.settings.get("gist_id", "")
        if not gist_id:
            return False, "未配置 Gist ID"
        
        effective_token = self._get_token(self.token)
        if not effective_token:
            return False, "未获取到有效 Token"

        try:
            from ..core.repo_config import sync_config_from_gist
            # 静默下载，不弹窗
            success, error = sync_config_from_gist(self.config_file, gist_id, token=effective_token)
            
            if success:
                self.settings["last_sync"] = int(time.time())
                self._save_settings()
                log_success(f"静默同步（下载）成功: {gist_id}")
                return True, "静默同步成功"
            else:
                return False, f"下载失败: {error}"
        
        except Exception as e:
            return False, str(e)

    def sync_on_config_change(self) -> Tuple[bool, str]:
        """Sync configuration when local file changes."""
        # 始终尝试同步，只要有 Token
        effective_token = self._get_token(self.token)
        if not effective_token:
            return False, "未登录，跳过自动同步"
        
        config_path = Path(self.config_file)
        if not config_path.exists():
            return False, "配置文件不存在"
        
        try:
            local_mtime = config_path.stat().st_mtime
            last_sync = self.settings.get("last_sync", 0)
            
            # 如果本地更新，执行自动上传（含自动创建逻辑）
            if local_mtime > last_sync:
                return self.auto_upload_config()
            
            # 否则如果是定期同步点，尝试下载
            elif self.should_sync():
                return self.auto_download_config()
            
            return False, "无需同步"
        
        except Exception as e:
            return False, str(e)
    
    def get_status(self) -> Dict:
        """Get current auto-sync status."""
        return {
            "enabled": self.is_enabled(),
            "gist_id": self.settings.get("gist_id", ""),
            "auto_upload": self.settings.get("auto_upload", False),
            "auto_download": self.settings.get("auto_download", False),
            "last_sync": self.settings.get("last_sync", 0),
            "sync_interval": self.settings.get("sync_interval", 3600),
            "conflict_resolution": self.settings.get("conflict_resolution", "local")
        }


# 全局实例
_auto_gist_sync_instance = None


def get_auto_gist_sync(config_file: str, token: Optional[str] = None) -> AutoGistSync:
    """Get or create AutoGistSync instance."""
    global _auto_gist_sync_instance
    if _auto_gist_sync_instance is None or _auto_gist_sync_instance.config_file != config_file:
        _auto_gist_sync_instance = AutoGistSync(config_file, token)
    return _auto_gist_sync_instance


__all__ = [
    "AutoGistSync",
    "get_auto_gist_sync",
]
