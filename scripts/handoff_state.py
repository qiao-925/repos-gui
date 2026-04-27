from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
HANDOFF_DIR = ROOT_DIR / "handoff"
CURRENT_TASK_PATH = HANDOFF_DIR / "current-task.md"
CURSOR_PROMPT_PATH = HANDOFF_DIR / "cursor-prompt.md"
STATE_PATH = HANDOFF_DIR / "state.json"
REVIEW_FEEDBACK_PATH = HANDOFF_DIR / "review-feedback.md"
HISTORY_DIR = HANDOFF_DIR / "history"
SOURCE_PATHS = (CURRENT_TASK_PATH, CURSOR_PROMPT_PATH)
CODE_SPAN_PATTERN = re.compile(r"`([^`\n]+)`")
LINE_SUFFIX_PATTERN = re.compile(r":\d+(?:-\d+)?(?:,\d+(?:-\d+)?)*$")
TRACKABLE_SUFFIXES = {
    ".py",
    ".md",
    ".yml",
    ".yaml",
    ".toml",
    ".tsx",
    ".ts",
    ".js",
    ".json",
    ".html",
    ".sh",
}


class HandoffStateError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    mark_awaiting = subparsers.add_parser("mark-awaiting")
    mark_awaiting.add_argument("--relay-action", default="unknown")

    subparsers.add_parser("detect")
    subparsers.add_parser("show")
    subparsers.add_parser("mark-reviewed")
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_text(path: Path) -> str:
    if not path.exists():
        raise HandoffStateError(f"Missing file: {path}")
    return path.read_text(encoding="utf-8")


def read_state() -> dict:
    if not STATE_PATH.exists():
        raise HandoffStateError(f"Missing state file: {STATE_PATH}")
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def write_state(state: dict) -> None:
    HANDOFF_DIR.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_code_span(value: str) -> str | None:
    candidate = LINE_SUFFIX_PATTERN.sub("", value.strip())
    if not candidate or candidate.startswith("handoff/"):
        return None
    return candidate


def is_trackable_path(path: Path) -> bool:
    return path.is_file() and path.suffix in TRACKABLE_SUFFIXES


def discover_target_files() -> list[str]:
    discovered: list[str] = []
    seen: set[str] = set()

    for source_path in SOURCE_PATHS:
        content = read_text(source_path)
        for code_span in CODE_SPAN_PATTERN.findall(content):
            candidate = normalize_code_span(code_span)
            if not candidate:
                continue
            absolute_path = ROOT_DIR / candidate
            if not absolute_path.exists() or not is_trackable_path(absolute_path):
                continue
            relative_path = absolute_path.relative_to(ROOT_DIR).as_posix()
            if relative_path in seen:
                continue
            seen.add(relative_path)
            discovered.append(relative_path)

    if not discovered:
        raise HandoffStateError("No trackable target files were found from handoff artifacts")
    return discovered


def fingerprint_file(relative_path: str) -> str | None:
    absolute_path = ROOT_DIR / relative_path
    if not absolute_path.exists() or not absolute_path.is_file():
        return None
    digest = hashlib.sha256()
    digest.update(absolute_path.read_bytes())
    return digest.hexdigest()


def build_fingerprints(relative_paths: list[str]) -> dict[str, str | None]:
    return {relative_path: fingerprint_file(relative_path) for relative_path in relative_paths}


def _next_round() -> int:
    """Determine next round number from existing history dirs."""
    if not HISTORY_DIR.exists():
        return 1
    existing = [d.name for d in HISTORY_DIR.iterdir() if d.is_dir() and d.name.startswith("round-")]
    nums = []
    for name in existing:
        suffix = name[len("round-"):]
        if suffix.isdigit():
            nums.append(int(suffix))
    return max(nums, default=0) + 1


def _archive_round(round_num: int) -> None:
    """Archive current handoff files to history/round-N/ before overwriting."""
    round_dir = HISTORY_DIR / f"round-{round_num}"
    round_dir.mkdir(parents=True, exist_ok=True)

    for src in (CURRENT_TASK_PATH, CURSOR_PROMPT_PATH, REVIEW_FEEDBACK_PATH):
        if src.exists():
            shutil.copy2(src, round_dir / src.name)

    if STATE_PATH.exists():
        shutil.copy2(STATE_PATH, round_dir / STATE_PATH.name)

    print(f"archived: {round_dir}")


def mark_awaiting(relay_action: str) -> int:
    # Archive previous round if state.json exists (i.e. not the first round)
    if STATE_PATH.exists():
        prev_state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        prev_round = prev_state.get("round", 0)
        _archive_round(prev_round)

    round_num = _next_round()
    target_files = discover_target_files()
    timestamp = utc_now()
    state = {
        "status": "awaiting_cursor",
        "round": round_num,
        "created_at": timestamp,
        "updated_at": timestamp,
        "relay_action": relay_action,
        "target_files": target_files,
        "baseline_fingerprints": build_fingerprints(target_files),
        "changed_files": [],
    }
    write_state(state)
    print(f"status: {state['status']}")
    print(f"round: {round_num}")
    print(f"target_files: {len(target_files)}")
    print(f"state_file: {STATE_PATH}")
    return 0


def detect_review_ready() -> int:
    state = read_state()
    target_files = state.get("target_files", [])
    baseline_fingerprints = state.get("baseline_fingerprints", {})
    current_fingerprints = build_fingerprints(target_files)
    changed_files = [
        relative_path
        for relative_path in target_files
        if current_fingerprints.get(relative_path) != baseline_fingerprints.get(relative_path)
    ]

    state["changed_files"] = changed_files
    state["updated_at"] = utc_now()
    state["status"] = "review_ready" if changed_files else "awaiting_cursor"
    write_state(state)

    print(f"status: {state['status']}")
    print(f"changed_files: {len(changed_files)}")
    for relative_path in changed_files:
        print(relative_path)
    return 0


def show_state() -> int:
    state = read_state()
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0


def mark_reviewed() -> int:
    state = read_state()
    state["status"] = "reviewed"
    state["updated_at"] = utc_now()
    write_state(state)
    print(f"status: {state['status']}")
    print(f"state_file: {STATE_PATH}")
    return 0


def main() -> int:
    args = parse_args()

    try:
        if args.command == "mark-awaiting":
            return mark_awaiting(args.relay_action)
        if args.command == "detect":
            return detect_review_ready()
        if args.command == "show":
            return show_state()
        if args.command == "mark-reviewed":
            return mark_reviewed()
        raise HandoffStateError(f"Unsupported command: {args.command}")
    except HandoffStateError as exc:
        print(f"handoff state error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
