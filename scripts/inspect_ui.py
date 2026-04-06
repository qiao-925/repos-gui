#!/usr/bin/env python3
"""
CloneX Desktop UI Self-Check via Linux AT-SPI.

Usage:
  # 1. Start CloneX in dev mode (accessibility enabled):
  #    QT_ACCESSIBILITY=1 QT_LINUX_ACCESSIBILITY_ALWAYS_ON=1 uv run python gui.py &
  #
  # 2. Run this script:
  #    uv run python scripts/inspect_ui.py [--tree] [--check] [--click BUTTON_NAME]

Prerequisites:
  - gsettings set org.gnome.desktop.interface toolkit-accessibility true
  - pip packages: pygobject (provides gi.repository.Atspi)
"""

import argparse
import sys
import time

import gi
gi.require_version("Atspi", "2.0")
from gi.repository import Atspi


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

APP_NAMES = ("gui.py", "CloneX")


def get_desktop():
    return Atspi.get_desktop(0)


def find_app():
    """Find the CloneX application on the AT-SPI bus."""
    desktop = get_desktop()
    for name in APP_NAMES:
        for i in range(desktop.get_child_count()):
            child = desktop.get_child_at_index(i)
            if child and child.get_name() == name:
                return child
    return None


def walk(node, depth=0, max_depth=8):
    """Yield (node, depth) for every accessible in the subtree."""
    if depth > max_depth or not node:
        return
    yield node, depth
    for i in range(node.get_child_count()):
        yield from walk(node.get_child_at_index(i), depth + 1, max_depth)


def find_by_role_and_name(root_node, role, name=None, partial=False):
    """Find accessible nodes by role (and optionally name)."""
    results = []
    for node, _ in walk(root_node):
        if node.get_role_name() != role:
            continue
        node_name = node.get_name() or ""
        if name is None:
            results.append(node)
        elif partial and name in node_name:
            results.append(node)
        elif node_name == name:
            results.append(node)
    return results


def do_action(node, action_name="click"):
    """Execute a named action on an accessible node."""
    ai = node.get_action_iface()
    if ai is None:
        return False
    for i in range(ai.get_n_actions()):
        if ai.get_action_name(i) == action_name:
            ai.do_action(i)
            return True
    return False


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_tree(app):
    """Print the full accessible tree."""
    print(f"=== CloneX UI Tree ===\n")
    for node, depth in walk(app):
        indent = "  " * depth
        name = node.get_name() or ""
        role = node.get_role_name() or ""
        count = node.get_child_count()
        line = f'{indent}[{role}] "{name}"'
        if count:
            line += f"  ({count})"
        print(line)


def cmd_check(app):
    """Run automated health-checks on the CloneX UI."""
    passed = 0
    failed = 0

    def ok(msg):
        nonlocal passed
        passed += 1
        print(f"  ✅ {msg}")

    def fail(msg):
        nonlocal failed
        failed += 1
        print(f"  ❌ {msg}")

    print("=== CloneX UI Health Check ===\n")

    # 1. Main window exists
    frames = find_by_role_and_name(app, "frame")
    if frames:
        ok(f"主窗口存在: \"{frames[0].get_name()}\"")
    else:
        fail("主窗口未找到")

    # 2. Key buttons
    expected_buttons = [
        "AI 自动分类（全量重建）",
        "增量更新到未分类（推荐）",
        "手动编辑",
        "编辑 AI Prompt",
        "Gist 自动同步",
        "开始克隆",
        "批量更新已克隆仓库",
        "一键重试失败仓库",
        "恢复默认参数",
    ]
    all_buttons = find_by_role_and_name(app, "push button")
    button_names = {b.get_name() for b in all_buttons}

    for name in expected_buttons:
        if name in button_names:
            ok(f"按钮存在: \"{name}\"")
        else:
            fail(f"按钮缺失: \"{name}\"")

    # 3. Login status
    labels = find_by_role_and_name(app, "label")
    login_labels = [l for l in labels if "登录状态" in (l.get_name() or "")]
    if login_labels:
        status_text = login_labels[0].get_name()
        if "已登录" in status_text:
            ok(f"已登录: {status_text}")
        else:
            ok(f"登录状态可见: {status_text}")
    else:
        fail("登录状态标签未找到")

    # 4. Progress bar
    progress = find_by_role_and_name(app, "progress bar")
    if progress:
        ok("进度条存在")
    else:
        fail("进度条缺失")

    # 5. Spin buttons (parallel params)
    spins = find_by_role_and_name(app, "spin button")
    if len(spins) >= 2:
        ok(f"并行参数控件存在 ({len(spins)} 个)")
    else:
        fail(f"并行参数控件不足 (期望>=2, 实际={len(spins)})")

    # 6. Log panel
    texts = find_by_role_and_name(app, "text")
    if texts:
        ok("日志面板存在")
    else:
        fail("日志面板缺失")

    print(f"\n--- 结果: {passed} 通过, {failed} 失败 ---")
    return failed == 0


def cmd_click(app, button_name):
    """Click a button by name."""
    buttons = find_by_role_and_name(app, "push button", button_name)
    if not buttons:
        buttons = find_by_role_and_name(app, "push button", button_name, partial=True)
    if not buttons:
        print(f"❌ 未找到按钮: \"{button_name}\"")
        return False

    btn = buttons[0]
    print(f"🖱️  点击按钮: \"{btn.get_name()}\"")
    if do_action(btn):
        print("  ✅ 点击成功")
        return True
    else:
        print("  ⚠️  按钮没有可用的 click action，尝试 Press...")
        if do_action(btn, "Press"):
            print("  ✅ Press 成功")
            return True
        print("  ❌ 无法执行点击操作")
        return False


def cmd_list_buttons(app):
    """List all buttons and their available actions."""
    buttons = find_by_role_and_name(app, "push button")
    print(f"=== 所有按钮 ({len(buttons)}) ===\n")
    for btn in buttons:
        name = btn.get_name() or "(unnamed)"
        ai = btn.get_action_iface()
        actions = []
        if ai:
            for i in range(ai.get_n_actions()):
                actions.append(ai.get_action_name(i))
        print(f"  [{name}]  actions={actions}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="CloneX UI Self-Check (AT-SPI)")
    parser.add_argument("--tree", action="store_true", help="Print full UI tree")
    parser.add_argument("--check", action="store_true", help="Run health checks")
    parser.add_argument("--click", type=str, help="Click a button by name")
    parser.add_argument("--buttons", action="store_true", help="List all buttons")
    args = parser.parse_args()

    if not any([args.tree, args.check, args.click, args.buttons]):
        args.tree = True
        args.check = True

    app = find_app()
    if not app:
        print("❌ CloneX 未在 AT-SPI 总线上找到。")
        print("   请确保以 dev 模式启动:")
        print("   QT_ACCESSIBILITY=1 QT_LINUX_ACCESSIBILITY_ALWAYS_ON=1 uv run python gui.py")
        sys.exit(1)

    print(f"✅ 找到应用: \"{app.get_name()}\"\n")

    if args.tree:
        cmd_tree(app)
        print()

    if args.buttons:
        cmd_list_buttons(app)
        print()

    if args.check:
        success = cmd_check(app)
        if not success:
            sys.exit(1)

    if args.click:
        if not cmd_click(app, args.click):
            sys.exit(1)


if __name__ == "__main__":
    main()
