# DeepSeek API：分类仓库

import json
import os
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple
from urllib import request, error

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"

APP_NAME = "gh-repos-gui"
SERVICE_NAME = "gh-repos-gui"
ACCOUNT_NAME = "deepseek_api_key"


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


def load_ai_config() -> Tuple[str, str]:
    data = _load_config()
    base_url = data.get("ai_base_url", DEFAULT_BASE_URL)
    model = data.get("ai_model", DEFAULT_MODEL)
    return base_url, model


def save_ai_config(base_url: str, model: str) -> None:
    data = _load_config()
    data["ai_base_url"] = base_url.strip()
    data["ai_model"] = model.strip()
    _save_config(data)


def _keyring_available() -> bool:
    try:
        import keyring  # noqa: F401
        return True
    except Exception:
        return False


def _load_key_from_keyring() -> Optional[str]:
    import keyring
    return keyring.get_password(SERVICE_NAME, ACCOUNT_NAME)


def _save_key_to_keyring(key: str) -> None:
    import keyring
    keyring.set_password(SERVICE_NAME, ACCOUNT_NAME, key)


def _delete_key_from_keyring() -> None:
    import keyring
    try:
        keyring.delete_password(SERVICE_NAME, ACCOUNT_NAME)
    except Exception:
        pass


def _load_key_from_file() -> Optional[str]:
    return _load_config().get("ai_api_key")


def _save_key_to_file(key: str) -> None:
    data = _load_config()
    data["ai_api_key"] = key
    _save_config(data)


def _delete_key_from_file() -> None:
    data = _load_config()
    if "ai_api_key" in data:
        del data["ai_api_key"]
        _save_config(data)


def load_api_key() -> Tuple[Optional[str], str]:
    if _keyring_available():
        try:
            key = _load_key_from_keyring()
            if key:
                return key, "keyring"
        except Exception:
            pass

    key = _load_key_from_file()
    if key and _keyring_available():
        try:
            _save_key_to_keyring(key)
            _delete_key_from_file()
            return key, "keyring"
        except Exception:
            return key, "file"

    return key, "file" if key else "none"


def save_api_key(key: str) -> str:
    if _keyring_available():
        try:
            _save_key_to_keyring(key)
            _delete_key_from_file()
            return "keyring"
        except Exception:
            pass
    _save_key_to_file(key)
    return "file"


def clear_api_key() -> None:
    if _keyring_available():
        try:
            _delete_key_from_keyring()
        except Exception:
            pass
    _delete_key_from_file()


def _post_json(url: str, payload: Dict, api_key: str, timeout: int = 30) -> Dict:
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
    )
    with request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _extract_json_array(text: str) -> Optional[List[Dict[str, str]]]:
    try:
        return json.loads(text)
    except Exception:
        pass
    start = text.find("[")
    end = text.rfind("]")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except Exception:
            return None
    return None


def classify_repos(
    repos: List[Dict[str, object]],
    groups: List[str],
    api_key: str,
    base_url: str = DEFAULT_BASE_URL,
    model: str = DEFAULT_MODEL,
    chunk_size: int = 40,
    progress_cb: Optional[Callable[[int, int], None]] = None
) -> Tuple[Dict[str, str], str]:
    if not repos:
        return {}, ""

    mapping: Dict[str, str] = {}
    total = len(repos)
    chunks = [repos[i:i + chunk_size] for i in range(0, total, chunk_size)]

    for idx, chunk in enumerate(chunks, 1):
        system_prompt = (
            "你是一个通用的 GitHub 仓库分类助手。"
            "请根据仓库名称、描述、语言、topics 判断分组。"
            "分组名称由你决定，尽量语义清晰、可复用。"
            "若无法判断，请使用“未分类”。"
            "只输出 JSON 数组，不要输出任何解释或其他文字。"
            "JSON 结构示例: [{\"name\": \"repo\", \"group\": \"分组名\"}]"
        )
        user_payload = {
            "repos": [
                {
                    "name": repo.get("name", ""),
                    "description": repo.get("description", ""),
                    "language": repo.get("language", ""),
                    "topics": repo.get("topics", []),
                }
                for repo in chunk
            ]
        }
        payload = {
            "model": model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)}
            ]
        }

        try:
            url = f"{base_url.rstrip('/')}/chat/completions"
            data = _post_json(url, payload, api_key)
        except error.HTTPError as e:
            return {}, f"AI 请求失败: HTTP {e.code}"
        except Exception as e:
            return {}, f"AI 请求失败: {e}"

        content = ""
        try:
            content = data["choices"][0]["message"]["content"]
        except Exception:
            return {}, f"AI 响应解析失败: {data}"

        result = _extract_json_array(content)
        if result is None:
            return {}, f"AI 输出不是有效 JSON: {content[:200]}"

        for item in result:
            name = str(item.get("name", "")).strip()
            group = str(item.get("group", "")).strip()
            if name:
                mapping[name] = group

        if progress_cb:
            progress_cb(idx, len(chunks))

    return mapping, ""
