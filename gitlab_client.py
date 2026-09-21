#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitLab 客户端模块

负责 GitLab API 连接、项目发现、提交获取与分支管理。
从 git2logs.py 拆分而来，保持所有原始逻辑不变。
"""
import sys
import os
import logging
import threading
import time
from datetime import datetime
from collections import defaultdict
from urllib.parse import urlparse
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

from utils.date_utils import to_gitlab_datetime, to_local_date_str
from config import GitLabConfig
from models import OperationCancelled

try:
    import gitlab  # pyright: ignore[reportMissingImports]
except ImportError:
    print("错误: 未安装 python-gitlab 库")
    print("请运行: pip install python-gitlab")
    sys.exit(1)

logger = logging.getLogger(__name__)
_rate_limit_lock = threading.Lock()
_rate_limit_until = 0.0


def _is_retryable_error(exc):
    if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
        return True
    status_code = getattr(exc, "response_code", None) or getattr(exc, "status_code", None)
    if status_code in GitLabConfig.RETRYABLE_STATUS_CODES:
        return True
    message = str(exc).lower()
    return any(token in message for token in (
        "connection", "timeout", "temporarily unavailable", "too many requests",
        "bad gateway", "service unavailable", "gateway timeout",
    ))


def _is_rate_limited_error(exc):
    status_code = getattr(exc, "response_code", None) or getattr(exc, "status_code", None)
    return status_code == 429 or "too many requests" in str(exc).lower()


def _get_retry_delay(exc, attempt):
    if not _is_rate_limited_error(exc):
        return GitLabConfig.RETRY_BACKOFF_SECONDS * (2 ** attempt)

    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None) or getattr(exc, "headers", None) or {}
    try:
        return max(float(headers.get("Retry-After")), 0)
    except (AttributeError, TypeError, ValueError):
        return GitLabConfig.RATE_LIMIT_COOLDOWN_SECONDS


def _wait_for_rate_limit(known_until=0.0):
    with _rate_limit_lock:
        deadline = _rate_limit_until
    if deadline > known_until:
        delay = deadline - time.monotonic()
        if delay > 0:
            time.sleep(delay)
    return deadline


def _extend_rate_limit(delay):
    global _rate_limit_until
    with _rate_limit_lock:
        _rate_limit_until = max(_rate_limit_until, time.monotonic() + delay)
        return _rate_limit_until


def _raise_if_cancelled(cancel_event):
    if cancel_event and cancel_event.is_set():
        raise OperationCancelled("用户取消了扫描")


def retry_gitlab_call(operation, description):
    known_rate_limit_until = 0.0
    for attempt in range(GitLabConfig.REQUEST_RETRIES + 1):
        known_rate_limit_until = _wait_for_rate_limit(known_rate_limit_until)
        try:
            return operation()
        except Exception as exc:
            if not _is_retryable_error(exc) or attempt == GitLabConfig.REQUEST_RETRIES:
                raise
            delay = _get_retry_delay(exc, attempt)
            logger.warning(
                "%s 失败，%.1f 秒后重试（%d/%d）: %s",
                description,
                delay,
                attempt + 1,
                GitLabConfig.REQUEST_RETRIES,
                exc,
            )
            if _is_rate_limited_error(exc):
                known_rate_limit_until = _extend_rate_limit(delay)
            time.sleep(delay)


def create_gitlab_client(gitlab_url, token=None):
    """
    创建 GitLab 客户端连接
    
    Args:
        gitlab_url: GitLab 实例 URL（例如：https://gitlab.com）
        token: 访问令牌（可选，私有仓库需要）
    
    Returns:
        gitlab.Gitlab: GitLab 客户端实例
    """
    if not token:
        logger.warning("未提供访问令牌，可能无法访问私有仓库")
    
    try:
        gl = gitlab.Gitlab(
            gitlab_url,
            private_token=token,
            timeout=GitLabConfig.REQUEST_TIMEOUT,
        )
        retry_gitlab_call(gl.auth, "GitLab 认证")
        logger.info(f"成功连接到 GitLab 实例: {gitlab_url}")
        return gl
    except Exception as e:
        logger.error(f"连接 GitLab 失败: {str(e)}")
        raise


def parse_project_identifier(repo_url):
    """
    从仓库 URL 或路径解析项目标识符
    
    支持的格式：
    - https://gitlab.com/group/project
    - https://gitlab.com/group/project.git
    - http://gitlab.example.com/group/project.git
    - group/project
    - group%2Fproject
    
    Args:
        repo_url: 仓库 URL 或路径
    
    Returns:
        str: 项目标识符（group/project 格式）
    """
    # 如果是完整的 URL
    if repo_url.startswith('http://') or repo_url.startswith('https://'):
        parsed = urlparse(repo_url)
        path = parsed.path.strip('/')
        # 移除 .git 后缀
        if path.endswith('.git'):
            path = path[:-4]
        return path
    else:
        # 直接是路径格式
        return repo_url.strip('/')


def extract_gitlab_url(repo_url):
    """
    从仓库 URL 中提取 GitLab 实例 URL
    
    Args:
        repo_url: 仓库 URL
    
    Returns:
        str: GitLab 实例 URL，如果不是完整 URL 则返回 None
    """
    if repo_url.startswith('http://') or repo_url.startswith('https://'):
        parsed = urlparse(repo_url)
        return f"{parsed.scheme}://{parsed.netloc}"
    return None


def _should_skip_branch(branch_obj, since_date=None, until_date=None):
    """
    基于分支 tip 日期判断是否可跳过整支查询。

    仅当 tip 早于 since 时可跳过：tip 是最新提交，更早的祖先也必早于 since。
    tip 晚于 until 时绝不可跳过：范围内仍可能有历史提交（例如查昨天，今天 tip 又前进）。

    until_date 保留参数以兼容调用方，不参与跳过判断。
    """
    if not since_date:
        return False

    try:
        commit = getattr(branch_obj, 'commit', None)
        if not commit:
            return False

        commit_date_str = getattr(commit, 'committed_date', None)
        if not commit_date_str or not isinstance(commit_date_str, str):
            return False

        # 按上海日历日比较，避免早上提交 UTC 落在前一天被误跳过
        return to_local_date_str(commit_date_str) < since_date.strip()
    except Exception:
        return False


def _get_priority_branches(branches):
    """
    获取优先查询的分支列表（常用分支优先）
    
    Args:
        branches: 分支对象列表
    
    Returns:
        tuple: (优先分支列表, 其他分支列表)
    """
    priority_names = ['main', 'master', 'dev', 'develop', 'development']
    priority_branches = []
    other_branches = []
    
    for branch in branches:
        branch_name = branch.name.lower()
        if branch_name in priority_names:
            priority_branches.append(branch)
        else:
            other_branches.append(branch)
    
    # 按优先级排序
    priority_branches.sort(key=lambda b: priority_names.index(b.name.lower()) if b.name.lower() in priority_names else 999)
    
    return priority_branches, other_branches


def get_all_branches(project, cancel_event=None):
    branches = []
    params = {'per_page': GitLabConfig.PER_PAGE}
    page = 1

    while True:
        _raise_if_cancelled(cancel_event)
        params['page'] = page
        page_branches = retry_gitlab_call(
            lambda: project.branches.list(**params),
            "获取分支列表",
        )
        if not page_branches:
            break

        branches.extend(page_branches)
        if len(page_branches) < GitLabConfig.PER_PAGE:
            break
        page += 1

    return branches


def get_commits_by_author(
    project,
    author_name,
    since_date=None,
    until_date=None,
    branch=None,
    scan_metrics=None,
    cancel_event=None,
):
    """
    获取指定提交者的所有提交
    
    Args:
        project: GitLab 项目对象
        author_name: 提交者姓名或邮箱
        since_date: 起始日期（可选，格式：YYYY-MM-DD）
        until_date: 结束日期（可选，格式：YYYY-MM-DD）
        branch: 分支名称（可选，默认查询所有分支）
    
    Returns:
        list: 提交列表
    """
    metrics = scan_metrics if scan_metrics is not None else {}
    metrics.update({"branches_scanned": 0, "branches_skipped": 0})
    if branch:
        metrics["branches_scanned"] = 1
        logger.debug(f"开始获取提交者 '{author_name}' 在分支 '{branch}' 的提交记录...")
    else:
        logger.debug(f"开始获取提交者 '{author_name}' 的提交记录...")
    
    commits = []
    page = 1
    per_page = GitLabConfig.PER_PAGE
    
    if branch:
        params = {
            'author': author_name,
            'ref_name': branch,
            'per_page': per_page
        }
        
        # 添加日期范围（如果指定）
        if since_date:
            params['since'] = to_gitlab_datetime(since_date)
        if until_date:
            params['until'] = to_gitlab_datetime(until_date, end_of_day=True)
        
        logger.debug(f"查询参数: author={author_name}, since={params.get('since')}, until={params.get('until')}, branch={branch}")
        
        try:
            while True:
                _raise_if_cancelled(cancel_event)
                params['page'] = page
                page_commits = retry_gitlab_call(
                    lambda: project.commits.list(**params),
                    "获取提交记录",
                )
                
                if not page_commits:
                    # 如果第一页就没有结果，尝试不同的 author 格式
                    if page == 1:
                        import re
                        # 尝试提取邮箱（如果格式是 "Name <email>"）
                        email_match = re.search(r'<([^>]+)>', author_name)
                        if email_match:
                            email_only = email_match.group(1)
                            logger.debug(f"尝试使用邮箱格式查询: {email_only}")
                            params_alt = params.copy()
                            params_alt['author'] = email_only
                            try:
                                page_commits_alt = retry_gitlab_call(
                                    lambda: project.commits.list(**params_alt),
                                    "按邮箱获取提交记录",
                                )
                                if page_commits_alt:
                                    logger.debug(f"使用邮箱格式找到 {len(page_commits_alt)} 条提交")
                                    page_commits = page_commits_alt
                                    params = params_alt
                                    # 找到提交后，继续处理，不要 break
                                else:
                                    logger.debug("使用邮箱格式未找到提交")
                            except Exception as e:
                                logger.debug(f"使用邮箱格式查询失败: {e}")
                        
                        # 如果邮箱格式没找到，尝试只使用名称部分（如果格式是 "Name <email>"）
                        if not page_commits:
                            name_match = re.match(r'^([^<]+)', author_name)
                            if name_match:
                                name_only = name_match.group(1).strip()
                                if name_only and name_only != author_name:
                                    logger.debug(f"尝试使用名称格式查询: '{name_only}'")
                                    params_alt = params.copy()
                                    params_alt['author'] = name_only
                                    try:
                                        page_commits_alt = retry_gitlab_call(
                                            lambda: project.commits.list(**params_alt),
                                            "按名称获取提交记录",
                                        )
                                        if page_commits_alt:
                                            logger.debug(f"使用名称格式找到 {len(page_commits_alt)} 条提交")
                                            page_commits = page_commits_alt
                                            params = params_alt
                                            # 找到提交后，继续处理，不要 break
                                        else:
                                            logger.debug("使用名称格式未找到提交")
                                    except Exception as e:
                                        logger.debug(f"使用名称格式查询失败: {e}")
                        
                        # 如果所有格式都失败，给出提示并退出
                        if not page_commits:
                            logger.debug("所有作者格式都未找到提交")
                            break
                    else:
                        # 不是第一页，没有更多结果，退出
                        break
                
                # 处理找到的提交
                if page_commits:
                    commits.extend(page_commits)
                    logger.debug(f"已获取 {len(commits)} 条提交记录...")
                    
                    if len(page_commits) < per_page:
                        break
                    
                    page += 1
                else:
                    break
            
            logger.debug(f"共获取到 {len(commits)} 条提交记录")
            return commits
        except Exception as e:
            logger.error(f"获取提交记录失败: {str(e)}")
            raise
    else:
        # 不指定分支时，遍历所有分支查询
        # GitLab API 的 all=True 参数可能无法正确按作者过滤
        logger.debug("未指定分支，将遍历所有分支查询...")
        seen_ids = set()
        unique_commits = []
        branches = get_all_branches(project, cancel_event)
        logger.debug(f"找到 {len(branches)} 个分支，开始遍历查询...")
        
        # 分支预过滤：跳过不在日期范围内的分支
        filtered_branches = []
        skipped_count = 0
        for branch_obj in branches:
            if _should_skip_branch(branch_obj, since_date, until_date):
                skipped_count += 1
                logger.debug(f"跳过分支 '{branch_obj.name}'（最后提交时间不在日期范围内）")
            else:
                filtered_branches.append(branch_obj)
        
        if skipped_count > 0:
            logger.debug(f"预过滤：跳过了 {skipped_count} 个分支，剩余 {len(filtered_branches)} 个")
        
        # 智能分支优先级：优先查询常用分支
        priority_branches, other_branches = _get_priority_branches(filtered_branches)
        if priority_branches:
            logger.debug(f"优先查询 {len(priority_branches)} 个常用分支")
        
        # 合并分支列表：优先分支在前
        ordered_branches = priority_branches + other_branches
        metrics["branches_scanned"] = len(ordered_branches)
        metrics["branches_skipped"] = skipped_count
        
        # 用于跟踪是否在优先分支中找到了提交
        found_in_priority = False
        
        for idx, branch_obj in enumerate(ordered_branches, 1):
            try:
                _raise_if_cancelled(cancel_event)
                branch_params = {
                    'author': author_name,
                    'ref_name': branch_obj.name,
                    'per_page': per_page
                }
                
                if since_date:
                    branch_params['since'] = to_gitlab_datetime(since_date)
                if until_date:
                    branch_params['until'] = to_gitlab_datetime(until_date, end_of_day=True)
                
                branch_commits = []
                branch_page = 1
                while True:
                    _raise_if_cancelled(cancel_event)
                    branch_params['page'] = branch_page
                    page_commits = retry_gitlab_call(
                        lambda: project.commits.list(**branch_params),
                        f"获取分支 {branch_obj.name} 的提交记录",
                    )
                    
                    if not page_commits:
                        # 如果第一页第一个分支没有结果，尝试不同的 author 格式
                        if idx == 1 and branch_page == 1:
                            import re
                            email_match = re.search(r'<([^>]+)>', author_name)
                            if email_match:
                                email_only = email_match.group(1)
                                logger.debug(f"尝试使用邮箱格式查询分支 '{branch_obj.name}': {email_only}")
                                branch_params_alt = branch_params.copy()
                                branch_params_alt['author'] = email_only
                                page_commits_alt = retry_gitlab_call(
                                    lambda: project.commits.list(**branch_params_alt),
                                    f"按邮箱获取分支 {branch_obj.name} 的提交记录",
                                )
                                if page_commits_alt:
                                    logger.debug(f"使用邮箱格式找到 {len(page_commits_alt)} 条提交")
                                    page_commits = page_commits_alt
                                    branch_params = branch_params_alt
                            # 尝试只使用名称部分
                            name_match = re.match(r'^([^<]+)', author_name)
                            if name_match and not email_match:
                                name_only = name_match.group(1).strip()
                                logger.debug(f"尝试使用名称格式查询分支 '{branch_obj.name}': {name_only}")
                                branch_params_alt = branch_params.copy()
                                branch_params_alt['author'] = name_only
                                page_commits_alt = retry_gitlab_call(
                                    lambda: project.commits.list(**branch_params_alt),
                                    f"按名称获取分支 {branch_obj.name} 的提交记录",
                                )
                                if page_commits_alt:
                                    logger.debug(f"使用名称格式找到 {len(page_commits_alt)} 条提交")
                                    page_commits = page_commits_alt
                                    branch_params = branch_params_alt
                        break
                    
                    # 调试：显示第一条提交的作者信息（仅第一页第一个分支）
                    if idx == 1 and branch_page == 1 and page_commits:
                        first_commit = page_commits[0]
                        author_info = getattr(first_commit, 'author_name', 'N/A')
                        author_email = getattr(first_commit, 'author_email', 'N/A')
                        logger.debug(f"示例提交作者: {author_info} <{author_email}>")
                        # 如果作者不匹配，给出提示
                        if author_name.lower() not in str(author_info).lower() and author_name.lower() not in str(author_email).lower():
                            logger.debug(f"查询作者与返回作者不匹配: {author_info} <{author_email}>")
                    
                    branch_commits.extend(page_commits)
                    
                    if len(page_commits) < per_page:
                        break
                    
                    branch_page += 1
                
                if branch_commits:
                    logger.debug(f"[{idx}/{len(ordered_branches)}] 分支 '{branch_obj.name}': 找到 {len(branch_commits)} 条提交")
                    for commit in branch_commits:
                        if commit.id not in seen_ids:
                            seen_ids.add(commit.id)
                            unique_commits.append(commit)
                    # 如果在优先分支中找到提交，标记一下（但不跳过其他分支，确保不遗漏）
                    if branch_obj in priority_branches:
                        found_in_priority = True
                else:
                    # 调试：如果没找到提交，记录一下（仅在调试模式下）
                    logger.debug(f"[{idx}/{len(ordered_branches)}] 分支 '{branch_obj.name}': 未找到提交")
            except Exception as e:
                # 忽略权限不足等错误
                logger.debug(f"查询分支 '{branch_obj.name}' 时出错: {str(e)}")
                continue
        
        logger.debug(f"共获取到 {len(unique_commits)} 条提交记录")
        return unique_commits
    
    # 添加日期范围
    if since_date:
        params['since'] = to_gitlab_datetime(since_date)
    if until_date:
        params['until'] = to_gitlab_datetime(until_date, end_of_day=True)
    
    try:
        while True:
            _raise_if_cancelled(cancel_event)
            params['page'] = page
            page_commits = retry_gitlab_call(
                lambda: project.commits.list(**params),
                "获取提交记录",
            )
            
            if not page_commits:
                break
            
            commits.extend(page_commits)
            logger.debug(f"已获取 {len(commits)} 条提交记录...")
            
            # 如果返回的提交数少于每页数量，说明已经是最后一页
            if len(page_commits) < per_page:
                break
            
            page += 1
        
        logger.debug(f"共获取到 {len(commits)} 条提交记录")
        return commits
    
    except Exception as e:
        logger.error(f"获取提交记录失败: {str(e)}")
        raise


def group_commits_by_date(commits):
    """
    按日期分组提交
    
    Args:
        commits: 提交列表
    
    Returns:
        dict: 按日期分组的提交字典，格式：{date: [commits]}
    """
    grouped = defaultdict(list)
    
    for commit in commits:
        date_str = to_local_date_str(commit.committed_date)
        grouped[date_str].append(commit)
    
    # 按日期排序
    sorted_dates = sorted(grouped.keys(), reverse=True)
    return {date: grouped[date] for date in sorted_dates}


def get_all_projects(gl, owned=False, membership=False):
    """
    获取用户有权限访问的所有项目
    
    Args:
        gl: GitLab 客户端实例
        owned: 是否只获取用户拥有的项目（默认：False）
        membership: 是否只获取用户是成员的项目（默认：False）
    
    Returns:
        list: 项目列表
    """
    logger.info("开始获取所有项目列表...")
    projects = []
    
    try:
        # 获取项目列表
        params = {'per_page': 100}
        if owned:
            params['owned'] = True
        if membership:
            params['membership'] = True
        
        page = 1
        while True:
            params['page'] = page
            page_projects = retry_gitlab_call(
                lambda: gl.projects.list(**params),
                "获取项目列表",
            )
            
            if not page_projects:
                break
            
            projects.extend(page_projects)
            logger.info(f"已获取 {len(projects)} 个项目...")
            
            if len(page_projects) < 100:
                break
            
            page += 1
        
        logger.info(f"共获取到 {len(projects)} 个项目")
        return projects
    
    except Exception as e:
        logger.error(f"获取项目列表失败: {str(e)}")
        raise


def scan_all_projects(
    gl,
    author_name,
    since_date=None,
    until_date=None,
    branch=None,
    max_workers=GitLabConfig.SCAN_MAX_WORKERS,
    progress_callback=None,
    cancel_event=None,
    scan_summary=None,
):
    """
    扫描所有项目，查找指定提交者的提交
    
    Args:
        gl: GitLab 客户端实例
        author_name: 提交者姓名或邮箱
        since_date: 起始日期（可选）
        until_date: 结束日期（可选）
        branch: 分支名称（可选）
        max_workers: 最大并发线程数（默认：10）
    
    Returns:
        dict: 按项目分组的提交字典，格式：{project_path: {'project': project, 'commits': commits}}
    """
    logger.info(f"开始扫描所有项目，查找提交者 '{author_name}' 的提交...")
    
    # 获取所有项目
    scan_started = time.monotonic()
    projects = get_all_projects(gl)
    
    results = {}
    total_commits = 0
    summary = scan_summary if scan_summary is not None else {}
    summary.update({
        "total": len(projects),
        "success": 0,
        "empty": 0,
        "skipped": 0,
        "failed": 0,
        "cancelled": False,
        "branches_scanned": 0,
        "branches_skipped": 0,
    })

    def report_progress(completed, project_path=""):
        if progress_callback:
            progress_callback(completed, len(projects), project_path)
    
    # 使用线程池并行处理项目
    def process_project(project):
        """处理单个项目的函数"""
        project_path = project.path_with_namespace
        try:
            project_metrics = {}
            # 获取该项目的提交
            commits = get_commits_by_author(
                project,
                author_name,
                since_date=since_date,
                until_date=until_date,
                branch=branch,
                scan_metrics=project_metrics,
                cancel_event=cancel_event,
            )
            
            if commits:
                return {
                    'status': 'success',
                    'project_path': project_path,
                    'project': project,
                    'commits': commits,
                    'count': len(commits),
                    'metrics': project_metrics,
                }
            return {
                'status': 'empty',
                'project_path': project_path,
                'metrics': project_metrics,
            }
        except OperationCancelled:
            return {'status': 'cancelled', 'project_path': project_path}
        except Exception as e:
            # 只记录重要错误，忽略权限不足等常见错误
            error_msg = str(e)
            if '403' in error_msg or '401' in error_msg or 'Not Found' in error_msg:
                logger.debug(f"  跳过项目 {project_path}（无权限或不存在）")
                status = "skipped"
            else:
                logger.warning(f"  扫描项目 {project_path} 时出错: {error_msg}")
                status = "failed"
            return {'status': status, 'project_path': project_path}
    
    # 并行处理项目
    completed = 0
    project_iterator = iter(projects)
    future_to_project = {}
    executor = ThreadPoolExecutor(max_workers=max_workers)

    def submit_next_project():
        if cancel_event and cancel_event.is_set():
            return False
        try:
            project = next(project_iterator)
        except StopIteration:
            return False
        future_to_project[executor.submit(process_project, project)] = project
        return True

    try:
        report_progress(0)
        for _ in range(min(max_workers, len(projects))):
            submit_next_project()

        while future_to_project:
            done, _ = wait(future_to_project, return_when=FIRST_COMPLETED)
            for future in done:
                project = future_to_project.pop(future)
                if cancel_event and cancel_event.is_set():
                    summary["cancelled"] = True
                    break

                completed += 1
                project_path = project.path_with_namespace
                try:
                    result = future.result()
                    metrics = result.get("metrics") or {}
                    summary["branches_scanned"] += metrics.get("branches_scanned", 0)
                    summary["branches_skipped"] += metrics.get("branches_skipped", 0)
                    if result["status"] == "success":
                        results[result['project_path']] = {
                            'project': result['project'],
                            'commits': result['commits']
                        }
                        total_commits += result['count']
                        summary["success"] += 1
                        logger.info(f"[{completed}/{len(projects)}] ✓ {project_path}: 找到 {result['count']} 条提交")
                    elif result["status"] != "cancelled":
                        summary[result["status"]] += 1
                        logger.debug(f"[{completed}/{len(projects)}] {project_path}: 未找到提交")
                except Exception as e:
                    summary["failed"] += 1
                    logger.warning(f"[{completed}/{len(projects)}] {project_path}: 处理失败: {str(e)}")

                report_progress(completed, project_path)
                if completed % GitLabConfig.SCAN_PROGRESS_LOG_INTERVAL == 0:
                    logger.info(
                        "扫描进度 %d/%d：命中 %d，提交 %d",
                        completed,
                        len(projects),
                        summary["success"],
                        total_commits,
                    )
                submit_next_project()

            if summary["cancelled"]:
                break
    finally:
        for pending in future_to_project:
            pending.cancel()
        executor.shutdown(wait=not summary["cancelled"], cancel_futures=summary["cancelled"])

    summary["completed"] = completed
    summary["duration_seconds"] = round(time.monotonic() - scan_started, 2)
    summary["commits"] = total_commits
    logger.info(
        f"扫描完成：命中 {summary['success']}，无提交 {summary['empty']}，"
        f"跳过/失败 {summary['skipped']}/{summary['failed']}，"
        f"分支扫描/预过滤 {summary['branches_scanned']}/{summary['branches_skipped']}，"
        f"耗时 {summary['duration_seconds']:.2f} 秒"
    )
    return results
