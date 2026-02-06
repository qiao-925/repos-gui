# GitHub OAuth 设备授权（Device Flow）与 Token 存储
#
# 目标：
#   - 无命令行参与：GUI 一键唤起浏览器授权
#   - Token 优先存入系统钥匙串，失败时回退到本地配置文件

import json
import os
import sys
import time
import webbrowser
from pathlib import Path
from typing import Dict, Optional, Tuple
from urllib import request, parse, error

APP_NAME = "gh-repos-gui"
SERVICE_NAME = "gh-repos-gui"
ACCOUNT_NAME = "token"
DEFAULT_CLIENT_ID = "Ov23libZp6UizRJ9QUwD"

DEVICE_CODE_URL = "https://github.com/login/device/code"
ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"
USER_API_URL = "https://api.github.com/user"


def _get_config_dir() -> Path:
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA") or str(Path.home())
    elif sys.platform == "darwin":
        base = str(Path.home() / "Library" / "Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    config_dir = Path(base) / APP_NAME
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def _get_config_path() -> Path:
    return _get_config_dir() / "auth.json"


def _load_config() -> Dict[str, str]:
    config_path = _get_config_path()
    if not config_path.exists():
        return {}
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_config(data: Dict[str, str]) -> None:
    config_path = _get_config_path()
    config_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_client_id() -> Optional[str]:
    return _load_config().get("client_id") or DEFAULT_CLIENT_ID


def save_client_id(client_id: str) -> None:
    data = _load_config()
    data["client_id"] = client_id.strip()
    _save_config(data)


def load_cached_login() -> Optional[str]:
    return _load_config().get("login")


def save_cached_login(login: str) -> None:
    data = _load_config()
    data["login"] = login.strip()
    _save_config(data)


def _keyring_available() -> bool:
    try:
        import keyring  # noqa: F401
        return True
    except Exception:
        return False


def _load_token_from_keyring() -> Optional[str]:
    import keyring
    return keyring.get_password(SERVICE_NAME, ACCOUNT_NAME)


def _save_token_to_keyring(token: str) -> None:
    import keyring
    keyring.set_password(SERVICE_NAME, ACCOUNT_NAME, token)


def _delete_token_from_keyring() -> None:
    import keyring
    try:
        keyring.delete_password(SERVICE_NAME, ACCOUNT_NAME)
    except Exception:
        pass


def _load_token_from_file() -> Optional[str]:
    return _load_config().get("token")


def _save_token_to_file(token: str) -> None:
    data = _load_config()
    data["token"] = token
    _save_config(data)


def _delete_token_from_file() -> None:
    data = _load_config()
    if "token" in data:
        del data["token"]
        _save_config(data)


def load_token() -> Tuple[Optional[str], str]:
    """加载 Token。优先 keyring，失败则回退到本地文件。"""
    if _keyring_available():
        try:
            token = _load_token_from_keyring()
            if token:
                return token, "keyring"
        except Exception:
            pass

    token = _load_token_from_file()
    if token and _keyring_available():
        # 尝试迁移到 keyring
        try:
            _save_token_to_keyring(token)
            _delete_token_from_file()
            return token, "keyring"
        except Exception:
            return token, "file"

    return token, "file" if token else "none"


def save_token(token: str) -> str:
    """保存 Token。优先 keyring，失败则回退文件。返回存储类型。"""
    if _keyring_available():
        try:
            _save_token_to_keyring(token)
            _delete_token_from_file()
            return "keyring"
        except Exception:
            pass
    _save_token_to_file(token)
    return "file"


def clear_token() -> None:
    if _keyring_available():
        try:
            _delete_token_from_keyring()
        except Exception:
            pass
    _delete_token_from_file()


def _post_form_json(url: str, data: Dict[str, str], timeout: int = 10) -> Dict:
    encoded = parse.urlencode(data).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    req = request.Request(url, data=encoded, headers=headers, method="POST")
    with request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def request_device_code(client_id: str, scope: str = "") -> Tuple[bool, Dict, str]:
    try:
        payload = {"client_id": client_id}
        if scope:
            payload["scope"] = scope
        data = _post_form_json(DEVICE_CODE_URL, payload, timeout=10)
    except error.HTTPError as e:
        return False, {}, f"授权请求失败: HTTP {e.code}"
    except Exception as e:
        return False, {}, f"授权请求失败: {e}"

    if "device_code" not in data or "user_code" not in data:
        return False, {}, f"授权响应异常: {data}"
    return True, data, ""


def poll_for_token(
    client_id: str,
    device_code: str,
    interval: int,
    expires_in: int
) -> Tuple[Optional[str], str]:
    start_time = time.time()
    interval = max(5, int(interval or 5))
    expires_in = int(expires_in or 900)

    while time.time() - start_time < expires_in:
        try:
            data = _post_form_json(
                ACCESS_TOKEN_URL,
                {
                    "client_id": client_id,
                    "device_code": device_code,
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code"
                },
                timeout=10
            )
        except error.HTTPError as e:
            return None, f"Token 获取失败: HTTP {e.code}"
        except Exception as e:
            return None, f"Token 获取失败: {e}"

        token = data.get("access_token")
        if token:
            return token, ""

        error_code = data.get("error")
        if error_code == "authorization_pending":
            time.sleep(interval)
            continue
        if error_code == "slow_down":
            interval += 5
            time.sleep(interval)
            continue
        if error_code == "access_denied":
            return None, "用户拒绝授权"
        if error_code == "expired_token":
            return None, "授权已过期，请重试"

        return None, f"授权失败: {error_code or data}"

    return None, "授权超时，请重试"


def open_verification_page(verification_url: str) -> None:
    try:
        webbrowser.open(verification_url)
    except Exception:
        pass


def fetch_user_profile(token: str) -> Tuple[Optional[str], int, str]:
    try:
        req = request.Request(
            USER_API_URL,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "User-Agent": "gh-repos-gui"
            }
        )
        with request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as e:
        return None, -1, f"获取用户信息失败: HTTP {e.code}"
    except Exception as e:
        return None, -1, f"获取用户信息失败: {e}"

    login = data.get("login")
    if not login:
        return None, -1, "未获取到登录账号"
    public_repos = data.get("public_repos", -1)
    return login, public_repos if isinstance(public_repos, int) else -1, ""


def fetch_login(token: str) -> Tuple[Optional[str], str]:
    """兼容旧接口：仅返回登录名。"""
    login, _, error = fetch_user_profile(token)
    if error:
        return None, error
    return login, ""
