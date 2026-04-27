#!/usr/bin/env python3
"""
Sync platform-agnostic agent rules from docs/agent-rules/ to tool-specific directories.

This script maintains a single source of truth in docs/agent-rules/*.md
and generates tool-specific configurations in .cursor/ and .windsurf/ directories.
"""

import os
import sys
from pathlib import Path
from typing import Dict

# Project root
PROJECT_ROOT = Path(__file__).parent.parent
DOCS_RULES_DIR = PROJECT_ROOT / "docs" / "agent-rules"
CURSOR_RULES_DIR = PROJECT_ROOT / ".cursor" / "rules"
WINDSURF_RULES_DIR = PROJECT_ROOT / ".windsurf" / "rules"
WINDSURF_WORKFLOWS_DIR = PROJECT_ROOT / ".windsurf" / "workflows"


def read_source_file(filepath: Path) -> str:
    """Read source markdown file."""
    if not filepath.exists():
        raise FileNotFoundError(f"Source file not found: {filepath}")
    return filepath.read_text(encoding="utf-8")


def write_cursor_rule(source_path: Path, target_path: Path, description: str, globs: str = "**/*"):
    """Write Cursor-specific .mdc file with frontmatter."""
    content = read_source_file(source_path)
    
    frontmatter = f"""---
description: "{description}"
globs: "{globs}"
alwaysApply: true
---

"""
    
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(frontmatter + content, encoding="utf-8")
    print(f"✓ Generated {target_path}")


def write_windsurf_rule(source_path: Path, target_path: Path, description: str, globs: str = "**/*"):
    """Write Windsurf-specific .mdc file with frontmatter."""
    content = read_source_file(source_path)
    
    frontmatter = f"""---
description: "{description}"
globs: "{globs}"
alwaysApply: true
---

"""
    
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(frontmatter + content, encoding="utf-8")
    print(f"✓ Generated {target_path}")


def write_windsurf_workflow(source_path: Path, target_path: Path, description: str, auto_execution_mode: str = "0"):
    """Write Windsurf workflow .md file with frontmatter."""
    content = read_source_file(source_path)
    
    frontmatter = f"""---
auto_execution_mode: {auto_execution_mode}
description: {description}
---
"""
    
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(frontmatter + content, encoding="utf-8")
    print(f"✓ Generated {target_path}")


def sync_rules():
    """Sync all rules from docs/agent-rules/ to tool-specific directories."""
    
    if not DOCS_RULES_DIR.exists():
        print(f"Error: Source directory not found: {DOCS_RULES_DIR}")
        sys.exit(1)
    
    print(f"Syncing rules from {DOCS_RULES_DIR}...")
    print()
    
    # Define rule mappings
    rule_mappings = [
        # Cursor rules
        {
            "source": "agent-workflow.md",
            "cursor_target": "agent-workflow.mdc",
            "cursor_desc": "Agent execution rule for risk-based confirmation, batch questions, and default-first planning",
            "cursor_globs": "**/*",
        },
        # Windsurf rules
        {
            "source": "release-gate.md",
            "windsurf_target": "clonex-release-gate.mdc",
            "windsurf_desc": "CloneX release gate rule with PEP 440, SemVer, and PyPI publishing constraints",
            "windsurf_globs": "**/*",
        },
        # Windsurf workflows
        {
            "source": "handoff.md",
            "windsurf_workflow_target": "handoff.md",
            "windsurf_workflow_desc": "调研当前任务并生成 Cursor-executable prompt",
            "windsurf_auto_mode": "0",
        },
        {
            "source": "review.md",
            "windsurf_workflow_target": "review.md",
            "windsurf_workflow_desc": "Review Cursor-delivered changes against current handoff constraints",
            "windsurf_auto_mode": "0",
        },
    ]
    
    for mapping in rule_mappings:
        source_file = DOCS_RULES_DIR / mapping["source"]
        
        # Cursor rule
        if "cursor_target" in mapping:
            cursor_target = CURSOR_RULES_DIR / mapping["cursor_target"]
            write_cursor_rule(
                source_file,
                cursor_target,
                mapping["cursor_desc"],
                mapping.get("cursor_globs", "**/*")
            )
        
        # Windsurf rule
        if "windsurf_target" in mapping:
            windsurf_target = WINDSURF_RULES_DIR / mapping["windsurf_target"]
            write_windsurf_rule(
                source_file,
                windsurf_target,
                mapping["windsurf_desc"],
                mapping.get("windsurf_globs", "**/*")
            )
        
        # Windsurf workflow
        if "windsurf_workflow_target" in mapping:
            windsurf_workflow_target = WINDSURF_WORKFLOWS_DIR / mapping["windsurf_workflow_target"]
            write_windsurf_workflow(
                source_file,
                windsurf_workflow_target,
                mapping["windsurf_workflow_desc"],
                mapping.get("windsurf_auto_mode", "0")
            )
    
    print()
    print("✓ All rules synced successfully!")
    print()
    print("Source of truth: docs/agent-rules/")
    print("Generated configurations:")
    print(f"  - {CURSOR_RULES_DIR}/")
    print(f"  - {WINDSURF_RULES_DIR}/")
    print(f"  - {WINDSURF_WORKFLOWS_DIR}/")


def check_rules() -> bool:
    """Check if generated files are up-to-date without modifying them.
    
    Returns True if all files are up-to-date, False otherwise.
    """
    import tempfile
    import shutil
    
    if not DOCS_RULES_DIR.exists():
        print(f"Error: Source directory not found: {DOCS_RULES_DIR}")
        return False
    
    print("Checking if generated files are up-to-date...")
    print()
    
    # Create temporary directory for comparison
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_cursor_dir = Path(temp_dir) / ".cursor" / "rules"
        temp_windsurf_rules_dir = Path(temp_dir) / ".windsurf" / "rules"
        temp_windsurf_workflows_dir = Path(temp_dir) / ".windsurf" / "workflows"
        
        all_up_to_date = True
        
        # Define rule mappings
        rule_mappings = [
            {
                "source": "agent-workflow.md",
                "cursor_target": "agent-workflow.mdc",
                "cursor_desc": "Agent execution rule for risk-based confirmation, batch questions, and default-first planning",
                "cursor_globs": "**/*",
            },
            {
                "source": "release-gate.md",
                "windsurf_target": "clonex-release-gate.mdc",
                "windsurf_desc": "CloneX release gate rule with PEP 440, SemVer, and PyPI publishing constraints",
                "windsurf_globs": "**/*",
            },
            {
                "source": "handoff.md",
                "windsurf_workflow_target": "handoff.md",
                "windsurf_workflow_desc": "调研当前任务并生成 Cursor-executable prompt",
                "windsurf_auto_mode": "0",
            },
            {
                "source": "review.md",
                "windsurf_workflow_target": "review.md",
                "windsurf_workflow_desc": "Review Cursor-delivered changes against current handoff constraints",
                "windsurf_auto_mode": "0",
            },
        ]
        
        for mapping in rule_mappings:
            source_file = DOCS_RULES_DIR / mapping["source"]
            
            # Generate to temp directory
            if "cursor_target" in mapping:
                temp_cursor_target = temp_cursor_dir / mapping["cursor_target"]
                write_cursor_rule(
                    source_file,
                    temp_cursor_target,
                    mapping["cursor_desc"],
                    mapping.get("cursor_globs", "**/*")
                )
                
                # Compare with actual file
                actual_target = CURSOR_RULES_DIR / mapping["cursor_target"]
                if actual_target.exists():
                    if temp_cursor_target.read_text(encoding="utf-8") != actual_target.read_text(encoding="utf-8"):
                        print(f"✗ {actual_target} is out of date")
                        all_up_to_date = False
                    else:
                        print(f"✓ {actual_target} is up to date")
                else:
                    print(f"✗ {actual_target} does not exist")
                    all_up_to_date = False
            
            if "windsurf_target" in mapping:
                temp_windsurf_target = temp_windsurf_rules_dir / mapping["windsurf_target"]
                write_windsurf_rule(
                    source_file,
                    temp_windsurf_target,
                    mapping["windsurf_desc"],
                    mapping.get("windsurf_globs", "**/*")
                )
                
                actual_target = WINDSURF_RULES_DIR / mapping["windsurf_target"]
                if actual_target.exists():
                    if temp_windsurf_target.read_text(encoding="utf-8") != actual_target.read_text(encoding="utf-8"):
                        print(f"✗ {actual_target} is out of date")
                        all_up_to_date = False
                    else:
                        print(f"✓ {actual_target} is up to date")
                else:
                    print(f"✗ {actual_target} does not exist")
                    all_up_to_date = False
            
            if "windsurf_workflow_target" in mapping:
                temp_windsurf_workflow_target = temp_windsurf_workflows_dir / mapping["windsurf_workflow_target"]
                write_windsurf_workflow(
                    source_file,
                    temp_windsurf_workflow_target,
                    mapping["windsurf_workflow_desc"],
                    mapping.get("windsurf_auto_mode", "0")
                )
                
                actual_target = WINDSURF_WORKFLOWS_DIR / mapping["windsurf_workflow_target"]
                if actual_target.exists():
                    if temp_windsurf_workflow_target.read_text(encoding="utf-8") != actual_target.read_text(encoding="utf-8"):
                        print(f"✗ {actual_target} is out of date")
                        all_up_to_date = False
                    else:
                        print(f"✓ {actual_target} is up to date")
                else:
                    print(f"✗ {actual_target} does not exist")
                    all_up_to_date = False
    
    print()
    if all_up_to_date:
        print("✓ All generated files are up to date")
        return True
    else:
        print("✗ Some generated files are out of date")
        print("Run 'python scripts/sync-agent-rules.py' to sync")
        return False


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Sync agent rules from docs/agent-rules/ to tool-specific directories"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if generated files are up-to-date without modifying them"
    )
    
    args = parser.parse_args()
    
    if args.check:
        success = check_rules()
        sys.exit(0 if success else 1)
    else:
        sync_rules()


if __name__ == "__main__":
    main()
