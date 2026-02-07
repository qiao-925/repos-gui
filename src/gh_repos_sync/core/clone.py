# 仓库克隆模块：实现单个仓库的克隆操作
#
# 主要功能：
#   - clone_repo()：克隆单个仓库，使用 Git 并行传输参数和优化配置
#
# 特性：
#   - 自动选择最优协议（SSH 优先，回退到 HTTPS）
#   - Git 配置优化（网络、压缩、多线程）
#   - 增量更新：先检查仓库是否存在且完整，存在且完整则跳过克隆
#   - 失败时输出错误信息

import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from .check import check_repo
from .process_control import (
    background_subprocess_kwargs,
    is_shutdown_requested,
    start_tracked_process,
    terminate_process,
    untrack_process,
)
from ..infra.logger import log_error, log_info, log_success


def get_repo_url(repo_full: str) -> str:
    """检测并选择最优协议（SSH 优先，回退到 HTTPS）
    
    Args:
        repo_full: 仓库全名（格式：owner/repo）
    
    Returns:
        仓库 URL（SSH 或 HTTPS）
    """
    # 检测 SSH 是否可用（静默检测，避免输出干扰）
    try:
        result = subprocess.run(
            ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=2', '-T', 'git@github.com'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=3,
            **background_subprocess_kwargs(),
        )
        # 检查输出中是否包含 "successfully authenticated"
        output = result.stdout.decode() + result.stderr.decode()
        if 'successfully authenticated' in output:
            return f"git@github.com:{repo_full}.git"
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
        pass
    
    # 回退到 HTTPS
    return f"https://github.com/{repo_full}.git"


def get_cpu_cores() -> int:
    """获取 CPU 核心数（跨平台）
    
    Returns:
        CPU 核心数（至少为 1，默认 8）
    """
    cores = None
    
    # Linux: 使用 nproc 或 /proc/cpuinfo
    if platform.system() == 'Linux':
        try:
            result = subprocess.run(
                ['nproc'],
                capture_output=True,
                text=True,
                timeout=1,
                **background_subprocess_kwargs(),
            )
            if result.returncode == 0:
                cores = int(result.stdout.strip())
        except (FileNotFoundError, ValueError, subprocess.TimeoutExpired):
            pass
        
        if cores is None:
            try:
                cpuinfo_path = Path('/proc/cpuinfo')
                if cpuinfo_path.exists():
                    count = len([line for line in cpuinfo_path.read_text().splitlines() 
                                if line.startswith('processor')])
                    if count > 0:
                        cores = count
            except Exception:
                pass
    
    # macOS: 使用 sysctl
    elif platform.system() == 'Darwin':
        try:
            result = subprocess.run(
                ['sysctl', '-n', 'hw.ncpu'],
                capture_output=True,
                text=True,
                timeout=1,
                **background_subprocess_kwargs(),
            )
            if result.returncode == 0:
                cores = int(result.stdout.strip())
        except (FileNotFoundError, ValueError, subprocess.TimeoutExpired):
            pass
    
    # Windows 或其他系统：使用 os.cpu_count()
    if cores is None:
        cores = os.cpu_count() or 8
    
    # 确保至少为 1，如果小于 1 则使用默认值 8
    if cores < 1:
        cores = 8
    
    return cores


def clone_repo(
    repo_full: str,
    repo_name: str,
    group_folder: str,
    parallel_connections: int = 8
) -> bool:
    """克隆单个仓库
    
    Args:
        repo_full: 仓库全名（格式：owner/repo）
        repo_name: 仓库名
        group_folder: 目标文件夹路径
        parallel_connections: 并行连接数（默认 8）
    
    Returns:
        True 如果克隆成功，False 如果失败
    """
    if not repo_full or not repo_name or not group_folder:
        log_error("clone_repo: 参数不完整")
        return False

    if is_shutdown_requested():
        log_error(f"克隆已取消（程序正在退出）: {repo_full}")
        return False
    
    # 构建目标路径
    target_path = Path(group_folder) / repo_name
    
    # 增量更新：先检查仓库是否存在且完整
    if target_path.exists() and target_path.is_dir():
        # 检查是否是 Git 仓库
        if (target_path / ".git").exists():
            # 检查仓库完整性
            is_valid, error_msg = check_repo(target_path, repo_full, timeout=30)
            if is_valid:
                # 仓库存在且完整，跳过克隆
                log_success(f"仓库已存在且完整，跳过克隆: {repo_full}")
                return True
            else:
                # 仓库存在但不完整，需要重新克隆
                log_info(f"仓库存在但不完整 ({error_msg})，将重新克隆: {repo_full}")
        else:
            # 目录存在但不是 Git 仓库，需要删除后重新克隆
            log_info(f"目录存在但不是 Git 仓库，将删除后重新克隆: {repo_full}")
        
        # 删除已存在的目录（不完整或不是 Git 仓库）
        log_info(f"删除已存在的目录: {target_path}")
        try:
            shutil.rmtree(target_path)
        except (OSError, PermissionError) as e:
            # Windows 兼容：如果删除失败，尝试使用 Windows 命令
            if platform.system() == 'Windows':
                try:
                    # 使用 Windows 的 rmdir 命令强制删除
                    subprocess.run(
                        ['cmd.exe', '/c', 'rmdir', '/s', '/q', str(target_path)],
                        check=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=10,
                        **background_subprocess_kwargs(),
                    )
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
                    log_error(f"删除目录失败: {target_path} - {e}")
                    log_error("提示: 目录可能被其他程序占用，请手动删除后重试")
                    return False
            else:
                log_error(f"删除目录失败: {target_path} - {e}")
                return False
        except Exception as e:
            log_error(f"删除目录失败: {target_path} - {e}")
            return False
    
    # 确保目标文件夹的父目录存在
    try:
        Path(group_folder).mkdir(parents=True, exist_ok=True)
    except Exception as e:
        log_error(f"创建目录失败: {group_folder} - {e}")
        return False
    
    # 获取最优仓库 URL（SSH 优先，回退到 HTTPS）
    repo_url = get_repo_url(repo_full)
    cpu_cores = get_cpu_cores()
    
    # 执行克隆，使用优化的 Git 配置和并行传输参数
    log_info(f"开始克隆: {repo_full} -> {target_path}")
    
    # 构建 Git 命令
    # 使用优化的 Git 配置执行克隆
    # -c 参数临时设置配置，不影响全局 Git 配置
    git_cmd = [
        'git',
        '-c', 'http.postBuffer=524288000',
        '-c', 'http.lowSpeedLimit=0',
        '-c', 'http.lowSpeedTime=0',
        '-c', 'http.version=HTTP/2',
        '-c', f'pack.windowMemory=1073741824',
        '-c', f'pack.threads={cpu_cores}',
        '-c', 'core.compression=1',
        'clone',
        '--progress',
        '--jobs', str(parallel_connections),
        repo_url,
        str(target_path)
    ]
    
    try:
        process = start_tracked_process(
            git_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            result_code = process.wait()
        finally:
            untrack_process(process)

        if is_shutdown_requested():
            terminate_process(process)
            log_error(f"克隆已取消（程序正在退出）: {repo_full}")
            _cleanup_failed_directory(target_path)
            return False

        if result_code != 0:
            raise subprocess.CalledProcessError(result_code, git_cmd)
        
        log_success(f"克隆成功: {repo_full}")
        return True
        
    except subprocess.CalledProcessError as e:
        log_error(f"克隆失败: {repo_full}")
        
        # 如果克隆失败，清理不完整的目录
        _cleanup_failed_directory(target_path)
        
        return False
    
    except Exception as e:
        log_error(f"克隆异常: {repo_full} - {e}")
        
        # 如果克隆失败，清理不完整的目录
        _cleanup_failed_directory(target_path)
        
        return False


def _cleanup_failed_directory(target_path: Path) -> None:
    """清理失败的目录（Windows 兼容）
    
    Args:
        target_path: 要清理的目录路径
    """
    if not target_path.exists():
        return
    
    try:
        shutil.rmtree(target_path)
    except (OSError, PermissionError):
        # Windows 兼容：如果删除失败，尝试使用 Windows 命令
        if platform.system() == 'Windows':
            try:
                subprocess.run(
                    ['cmd.exe', '/c', 'rmdir', '/s', '/q', str(target_path)],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=5,
                    **background_subprocess_kwargs(),
                )
            except Exception:
                pass  # 忽略清理失败
        else:
            pass  # 忽略清理失败
    except Exception:
        pass  # 忽略清理失败

