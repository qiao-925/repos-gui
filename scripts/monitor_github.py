#!/usr/bin/env python3
"""GitHub Actions 监控脚本"""

import subprocess
import json
import sys
from datetime import datetime

def run_smithery_command(cmd):
    """运行 smithery 命令并返回结果"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"命令执行失败: {result.stderr}")
            return None
        return json.loads(result.stdout)
    except Exception as e:
        print(f"解析 JSON 失败: {e}")
        return None

def get_workflow_runs():
    """获取最新的工作流运行状态"""
    cmd = '''smithery tool call github actions_list '{"method": "list_workflow_runs", "owner": "qiao-925", "repo": "repos-gui", "per_page": 5}' '''
    return run_smithery_command(cmd)

def format_run_info(run):
    """格式化运行信息"""
    status_emoji = {
        "queued": "⏳",
        "in_progress": "🔄", 
        "completed": "✅",
        "failure": "❌",
        "success": "✅"
    }
    
    conclusion_emoji = {
        "success": "✅",
        "failure": "❌", 
        "cancelled": "⏹️",
        "skipped": "⏭️"
    }
    
    status = run.get("status", "unknown")
    conclusion = run.get("conclusion")
    
    emoji = status_emoji.get(status, "❓")
    if conclusion:
        emoji = conclusion_emoji.get(conclusion, emoji)
    
    time_str = run.get("created_at", "")[:19].replace("T", " ")
    
    return f"{emoji} Run #{run['id']} - {status} ({conclusion or 'running'}) - {time_str}"

def main():
    print("🔍 CloneX GitHub Actions 监控")
    print("=" * 50)
    
    # 获取工作流运行状态
    data = get_workflow_runs()
    if not data:
        print("❌ 无法获取工作流状态")
        return
    
    workflow_runs = data.get("workflow_runs", [])
    if not workflow_runs:
        print("📭 没有找到工作流运行记录")
        return
    
    print(f"📊 最新 {len(workflow_runs)} 次运行记录:")
    print()
    
    for run in workflow_runs:
        print(format_run_info(run))
        
        # 如果是失败的运行，显示详细信息
        if run.get("conclusion") == "failure":
            print(f"   🔍 失败原因: {run.get('name', 'Unknown')}")
            print(f"   🔗 查看详情: {run.get('html_url', '')}")
            
    print()
    print("💡 提示: 使用 'smithery tool call github actions_get' 获取详细信息")

if __name__ == "__main__":
    main()
