# DeepSeek API：分类仓库

import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple
from urllib import request, error

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"

APP_NAME = "gh-repos-gui"
SERVICE_NAME = "gh-repos-gui"
ACCOUNT_NAME = "deepseek_api_key"
CLASSIFY_PROMPT_FILE = "ai_classify_system_prompt.txt"
GROUPS_PLACEHOLDER = "{{ALLOWED_GROUPS}}"
MAX_GROUPS_PLACEHOLDER = "{{MAX_GROUPS}}"
MAX_CLASSIFY_GROUPS = 10
PREFIX_MIN_LENGTH = 3

DEFAULT_CLASSIFY_PROMPT_TEMPLATE = """你是一个严谨的 GitHub 仓库分类助手。

任务目标：
- 根据仓库 name / description / language / topics，为每个仓库分配一个 `group`。

分类规则：
1. 优先复用已有分组，避免同义重复（如 Tools / Tooling 不要并存）。
2. 分组名称要简洁、稳定、可复用，尽量体现“用途/领域”而非临时特征。
3. 先看仓库用途，再参考语言；语言仅作为次级线索。
4. 教程、练习、示例项目可归入已有 Practice/Tutorial 类分组；若无对应分组再新建。
5. 仓库名前缀一致时（如 `abc-api` / `abc-web` / `abc-docs`），应优先归为同一分组。
6. 最终分组总数不能超过 {{MAX_GROUPS}} 个（包含“未分类”），超过时合并到语义最接近的大类。
7. 无法判断时必须使用“未分类”。

输出约束（必须严格遵守）：
- 只输出 JSON 数组，不要 markdown，不要解释文字。
- 数组长度必须与输入 repos 数量一致。
- 每个元素必须包含：{"name":"原仓库名","group":"分组名"}
- `name` 必须与输入完全一致，不得改写、不得遗漏、不得新增。
- `group` 不能为空；不确定时填“未分类”。

可优先复用的分组：
{{ALLOWED_GROUPS}}

现在开始分类，并仅输出 JSON 数组。"""

HARD_CONSTRAINTS_TEMPLATE = """
硬性约束（系统追加）：
- 分组总数不得超过 {{MAX_GROUPS}} 个（包含“未分类”）。
- 仓库名前缀一致时（如 `abc-api` / `abc-web`）优先归同一分组。
- 若会超过上限，优先合并小类到语义最接近的已有分组。
"""


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


def _get_classify_prompt_path() -> Path:
    return _get_config_dir() / CLASSIFY_PROMPT_FILE


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


def get_classify_prompt_path() -> Path:
    """Return editable system prompt file path for AI classification."""
    return _get_classify_prompt_path()


def _read_prompt_template() -> str:
    prompt_path = _get_classify_prompt_path()
    if prompt_path.exists():
        try:
            content = prompt_path.read_text(encoding="utf-8").strip()
            if content:
                return content
        except Exception:
            pass

    try:
        prompt_path.write_text(DEFAULT_CLASSIFY_PROMPT_TEMPLATE, encoding="utf-8")
    except Exception:
        pass
    return DEFAULT_CLASSIFY_PROMPT_TEMPLATE


def _normalize_groups(groups: Sequence[str]) -> List[str]:
    normalized: List[str] = []
    seen = set()
    for group in groups:
        group_name = str(group).strip()
        if not group_name or group_name in seen:
            continue
        seen.add(group_name)
        normalized.append(group_name)

    if "未分类" not in seen:
        normalized.append("未分类")

    return normalized


def _build_groups_hint(groups: Sequence[str]) -> str:
    normalized_groups = _normalize_groups(groups)
    if not normalized_groups:
        return "- 未分类"
    return "\n".join(f"- {group}" for group in normalized_groups)


def _normalize_text_key(value: str) -> str:
    return "".join(ch for ch in value.lower().strip() if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")


def _extract_repo_prefix(repo_name: str) -> str:
    name = repo_name.lower().strip()
    if not name:
        return ""

    parts = [part for part in re.split(r"[-_.]+", name) if part]
    if parts:
        return parts[0]
    return name


def _pick_dominant_group(group_counts: Counter) -> str:
    if not group_counts:
        return "未分类"

    ordered = sorted(group_counts.items(), key=lambda item: (-item[1], item[0]))
    non_unclassified = [name for name, _ in ordered if name != "未分类"]
    if non_unclassified:
        return non_unclassified[0]
    return ordered[0][0]


def _apply_repo_prefix_grouping(mapping: Dict[str, str], repo_names: Sequence[str]) -> Dict[str, str]:
    by_prefix: Dict[str, List[str]] = {}
    for name in repo_names:
        repo_name = str(name).strip()
        if not repo_name:
            continue
        prefix = _extract_repo_prefix(repo_name)
        if not prefix:
            continue
        by_prefix.setdefault(prefix, []).append(repo_name)

    updated = dict(mapping)
    for prefix, names in by_prefix.items():
        if len(names) < 2:
            continue
        if len(prefix) < PREFIX_MIN_LENGTH and len(names) < 3:
            continue

        group_counts = Counter((updated.get(name, "") or "未分类").strip() or "未分类" for name in names)
        dominant_group = _pick_dominant_group(group_counts)

        for name in names:
            updated[name] = dominant_group

    return updated


def _best_merge_target(source_group: str, target_groups: Sequence[str]) -> Optional[str]:
    source_key = _normalize_text_key(source_group)
    if not source_key:
        return None

    best_target: Optional[str] = None
    best_score = 0

    for target in target_groups:
        target_key = _normalize_text_key(target)
        if not target_key:
            continue

        score = 0
        common_max = min(len(source_key), len(target_key))
        while score < common_max and source_key[score] == target_key[score]:
            score += 1

        if source_key.startswith(target_key) or target_key.startswith(source_key):
            score += 2

        if score > best_score:
            best_score = score
            best_target = target

    if best_score < 3:
        return None
    return best_target


def _enforce_group_limit(mapping: Dict[str, str], max_groups: int) -> Dict[str, str]:
    if max_groups < 1:
        max_groups = 1

    updated = {name: (group or "未分类").strip() or "未分类" for name, group in mapping.items()}
    group_counts = Counter(updated.values())
    if len(group_counts) <= max_groups:
        return updated

    keep_groups: List[str] = []
    if "未分类" in group_counts:
        keep_groups.append("未分类")

    remaining_slots = max_groups - len(keep_groups)
    if remaining_slots > 0:
        popular_groups = [
            group for group, _ in sorted(group_counts.items(), key=lambda item: (-item[1], item[0])) if group != "未分类"
        ]
        keep_groups.extend(popular_groups[:remaining_slots])

    if not keep_groups:
        keep_groups = [group for group, _ in group_counts.most_common(max_groups)]

    keep_set = set(keep_groups)
    fallback_group = "未分类" if "未分类" in keep_set else keep_groups[0]
    merge_targets = [group for group in keep_groups if group != "未分类"]

    group_remap: Dict[str, str] = {}
    for group in list(group_counts.keys()):
        if group in keep_set:
            group_remap[group] = group
            continue

        best_target = _best_merge_target(group, merge_targets)
        group_remap[group] = best_target or fallback_group

    return {name: group_remap.get(group, fallback_group) for name, group in updated.items()}


def _post_process_mapping(
    mapping: Dict[str, str],
    repo_names: Sequence[str],
    max_groups: int,
) -> Dict[str, str]:
    if not mapping:
        return mapping

    normalized = {name: (group or "未分类").strip() or "未分类" for name, group in mapping.items()}
    prefixed = _apply_repo_prefix_grouping(normalized, repo_names)
    return _enforce_group_limit(prefixed, max_groups)


def build_classify_system_prompt(groups: Sequence[str], max_groups: int = MAX_CLASSIFY_GROUPS) -> str:
    template = _read_prompt_template()
    groups_hint = _build_groups_hint(groups)

    template_with_max = template.replace(MAX_GROUPS_PLACEHOLDER, str(max_groups))

    if GROUPS_PLACEHOLDER in template_with_max:
        prompt_body = template_with_max.replace(GROUPS_PLACEHOLDER, groups_hint)
    else:
        prompt_body = f"{template_with_max.rstrip()}\n\n可优先复用的分组：\n{groups_hint}"

    hard_constraints = HARD_CONSTRAINTS_TEMPLATE.replace(MAX_GROUPS_PLACEHOLDER, str(max_groups)).strip()
    return f"{prompt_body.rstrip()}\n\n{hard_constraints}"


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
    max_groups: int = MAX_CLASSIFY_GROUPS,
    progress_cb: Optional[Callable[[int, int], None]] = None
) -> Tuple[Dict[str, str], str]:
    if not repos:
        return {}, ""

    if max_groups < 1:
        max_groups = 1

    mapping: Dict[str, str] = {}
    total = len(repos)
    chunks = [repos[i:i + chunk_size] for i in range(0, total, chunk_size)]
    active_groups = _normalize_groups(groups)

    for idx, chunk in enumerate(chunks, 1):
        system_prompt = build_classify_system_prompt(active_groups, max_groups=max_groups)
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

        expected_names = {str(repo.get("name", "")).strip() for repo in chunk if str(repo.get("name", "")).strip()}

        for item in result:
            name = str(item.get("name", "")).strip()
            group = str(item.get("group", "")).strip()
            if name and name in expected_names:
                final_group = group or "未分类"
                mapping[name] = final_group
                if final_group not in active_groups:
                    active_groups.append(final_group)

        for expected_name in expected_names:
            if expected_name not in mapping:
                mapping[expected_name] = "未分类"

        if progress_cb:
            progress_cb(idx, len(chunks))

    repo_names = [str(repo.get("name", "")).strip() for repo in repos]
    mapping = _post_process_mapping(mapping, repo_names, max_groups=max_groups)
    return mapping, ""
