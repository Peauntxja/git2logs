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
from datetime import datetime
from collections import defaultdict
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

from utils.date_utils import parse_iso_date, parse_simple_date, to_gitlab_datetime
from config import GitLabConfig

try:
    import gitlab  # pyright: ignore[reportMissingImports]
except ImportError:
    print("错误: 未安装 python-gitlab 库")
    print("请运行: pip install python-gitlab")
    sys.exit(1)

logger = logging.getLogger(__name__)


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
        gl = gitlab.Gitlab(gitlab_url, private_token=token)
        gl.auth()  # 验证连接
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
    检查分支是否应该被跳过（基于最后提交时间）
    
    Args:
        branch_obj: GitLab 分支对象
        since_date: 起始日期（可选，格式：YYYY-MM-DD）
        until_date: 结束日期（可选，格式：YYYY-MM-DD）
    
    Returns:
        bool: True 表示应该跳过，False 表示应该查询
    """
    if not since_date and not until_date:
        # 没有日期限制，不跳过
        return False
    
    try:
        # 获取分支的最后提交时间
        commit = branch_obj.commit
        if not commit:
            return False
        
        commit_date_str = getattr(commit, 'committed_date', None)
        if not commit_date_str:
            return False
        
        # 解析提交日期
        if isinstance(commit_date_str, str):
            commit_date = parse_iso_date(commit_date_str)
        else:
            return False
        
        commit_date_only = commit_date.date()
        
        # 检查是否在日期范围内
        if since_date:
            since = parse_simple_date(since_date).date()
            if commit_date_only < since:
                return True  # 最后提交时间早于起始日期，跳过
        
        if until_date:
            until = parse_simple_date(until_date).date()
            if commit_date_only > until:
                return True  # 最后提交时间晚于结束日期，跳过
        
        return False  # 在日期范围内，不跳过
    except Exception:
        # 如果检查失败，不跳过（保守策略）
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


def get_commits_by_author(project, author_name, since_date=None, until_date=None, branch=None):
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
    if branch:
        logger.info(f"开始获取提交者 '{author_name}' 在分支 '{branch}' 的提交记录...")
    else:
        logger.info(f"开始获取提交者 '{author_name}' 的提交记录...")
    
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
            # 首先尝试不指定作者，获取一些提交看看实际的作者格式
            try:
                debug_params = {'ref_name': branch, 'per_page': 5}
                if since_date:
                    debug_params['since'] = to_gitlab_datetime(since_date)
                if until_date:
                    debug_params['until'] = to_gitlab_datetime(until_date, end_of_day=True)
                debug_commits = project.commits.list(**debug_params)
                if debug_commits:
                    logger.info("调试：查询到的提交示例（不指定作者）：")
                    for idx, dc in enumerate(debug_commits[:3], 1):
                        dc_author = getattr(dc, 'author_name', 'N/A')
                        dc_email = getattr(dc, 'author_email', 'N/A')
                        logger.info(f"  提交 {idx}: 作者='{dc_author}' 邮箱='{dc_email}'")
            except Exception as e:
                logger.debug(f"调试查询失败: {e}")
            
            while True:
                params['page'] = page
                page_commits = project.commits.list(**params)
                
                if not page_commits:
                    # 如果第一页就没有结果，尝试不同的 author 格式
                    if page == 1:
                        import re
                        # 尝试提取邮箱（如果格式是 "Name <email>"）
                        email_match = re.search(r'<([^>]+)>', author_name)
                        if email_match:
                            email_only = email_match.group(1)
                            logger.info(f"尝试使用邮箱格式查询: {email_only}")
                            params_alt = params.copy()
                            params_alt['author'] = email_only
                            try:
                                page_commits_alt = project.commits.list(**params_alt)
                                if page_commits_alt:
                                    logger.info(f"✓ 使用邮箱格式找到 {len(page_commits_alt)} 条提交")
                                    page_commits = page_commits_alt
                                    params = params_alt
                                    # 找到提交后，继续处理，不要 break
                                else:
                                    logger.info(f"✗ 使用邮箱格式未找到提交")
                            except Exception as e:
                                logger.debug(f"使用邮箱格式查询失败: {e}")
                        
                        # 如果邮箱格式没找到，尝试只使用名称部分（如果格式是 "Name <email>"）
                        if not page_commits:
                            name_match = re.match(r'^([^<]+)', author_name)
                            if name_match:
                                name_only = name_match.group(1).strip()
                                if name_only and name_only != author_name:
                                    logger.info(f"尝试使用名称格式查询: '{name_only}'")
                                    params_alt = params.copy()
                                    params_alt['author'] = name_only
                                    try:
                                        page_commits_alt = project.commits.list(**params_alt)
                                        if page_commits_alt:
                                            logger.info(f"✓ 使用名称格式找到 {len(page_commits_alt)} 条提交")
                                            page_commits = page_commits_alt
                                            params = params_alt
                                            # 找到提交后，继续处理，不要 break
                                        else:
                                            logger.info(f"✗ 使用名称格式未找到提交")
                                    except Exception as e:
                                        logger.debug(f"使用名称格式查询失败: {e}")
                        
                        # 如果所有格式都失败，给出提示并退出
                        if not page_commits:
                            logger.warning("所有作者格式都未找到提交，可能的原因：")
                            logger.warning("1. 该分支在指定日期范围内确实没有提交")
                            logger.warning("2. 作者名称格式不匹配（请检查上面的示例提交作者格式）")
                            logger.warning("3. 日期范围问题（GitLab 使用 UTC 时间）")
                            break
                    else:
                        # 不是第一页，没有更多结果，退出
                        break
                
                # 处理找到的提交
                if page_commits:
                    commits.extend(page_commits)
                    logger.info(f"已获取 {len(commits)} 条提交记录...")
                    
                    if len(page_commits) < per_page:
                        break
                    
                    page += 1
                else:
                    break
            
            logger.info(f"共获取到 {len(commits)} 条提交记录")
            return commits
        except Exception as e:
            logger.error(f"获取提交记录失败: {str(e)}")
            raise
    else:
        # 不指定分支时，遍历所有分支查询
        # GitLab API 的 all=True 参数可能无法正确按作者过滤
        logger.info("未指定分支，将遍历所有分支查询...")
        all_commits = []
        branches = project.branches.list(per_page=GitLabConfig.PER_PAGE)
        logger.info(f"找到 {len(branches)} 个分支，开始遍历查询...")
        
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
            logger.info(f"预过滤：跳过了 {skipped_count} 个不在日期范围内的分支，剩余 {len(filtered_branches)} 个分支需要查询")
        
        # 智能分支优先级：优先查询常用分支
        priority_branches, other_branches = _get_priority_branches(filtered_branches)
        if priority_branches:
            logger.info(f"优先查询 {len(priority_branches)} 个常用分支: {[b.name for b in priority_branches]}")
        
        # 合并分支列表：优先分支在前
        ordered_branches = priority_branches + other_branches
        
        # 用于跟踪是否在优先分支中找到了提交
        found_in_priority = False
        
        for idx, branch_obj in enumerate(ordered_branches, 1):
            try:
                branch_params = {
                    'author': author_name,
                    'ref_name': branch_obj.name,
                    'per_page': per_page
                }
                
                if since_date:
                    branch_params['since'] = to_gitlab_datetime(since_date)
                if until_date:
                    branch_params['until'] = to_gitlab_datetime(until_date, end_of_day=True)
                
                # 首先尝试不指定作者，获取一些提交看看实际的作者格式（仅第一个分支）
                if idx == 1:
                    try:
                        debug_params = {'ref_name': branch_obj.name, 'per_page': 20}
                        if since_date:
                            debug_params['since'] = to_gitlab_datetime(since_date)
                        if until_date:
                            debug_params['until'] = to_gitlab_datetime(until_date, end_of_day=True)
                        debug_commits = project.commits.list(**debug_params)
                        if debug_commits:
                            logger.info(f"调试：分支 '{branch_obj.name}' 的提交示例（不指定作者，日期范围 {since_date or '全部'} 至 {until_date or '全部'}，共 {len(debug_commits)} 条）：")
                            for dc_idx, dc in enumerate(debug_commits[:10], 1):
                                dc_author = getattr(dc, 'author_name', 'N/A')
                                dc_email = getattr(dc, 'author_email', 'N/A')
                                dc_date = getattr(dc, 'committed_date', 'N/A')
                                # 格式化日期
                                if isinstance(dc_date, str):
                                    try:
                                        from datetime import datetime
                                        dc_date_obj = parse_iso_date(dc_date)
                                        dc_date_str = dc_date_obj.strftime('%Y-%m-%d %H:%M:%S')
                                        dc_date_local = dc_date_obj.strftime('%Y-%m-%d')
                                    except Exception:
                                        dc_date_str = str(dc_date)
                                        dc_date_local = 'N/A'
                                else:
                                    dc_date_str = str(dc_date)
                                    dc_date_local = 'N/A'
                                # 检查是否是目标作者
                                is_target = False
                                if author_name.lower() in str(dc_author).lower() or author_name.lower() in str(dc_email).lower():
                                    is_target = True
                                marker = " ← 匹配" if is_target else ""
                                logger.info(f"  提交 {dc_idx}: 作者='{dc_author}' 邮箱='{dc_email}' 日期={dc_date_str} (UTC日期={dc_date_local}){marker}")
                        else:
                            logger.debug(f"调试：分支 '{branch_obj.name}' 在指定日期范围内（{since_date or '全部'} 至 {until_date or '全部'}）没有任何提交（不指定作者）")
                    except Exception as e:
                        logger.warning(f"调试查询失败: {e}")
                
                branch_commits = []
                branch_page = 1
                while True:
                    branch_params['page'] = branch_page
                    page_commits = project.commits.list(**branch_params)
                    
                    if not page_commits:
                        # 如果第一页第一个分支没有结果，尝试不同的 author 格式
                        if idx == 1 and branch_page == 1:
                            import re
                            email_match = re.search(r'<([^>]+)>', author_name)
                            if email_match:
                                email_only = email_match.group(1)
                                logger.info(f"尝试使用邮箱格式查询分支 '{branch_obj.name}': {email_only}")
                                branch_params_alt = branch_params.copy()
                                branch_params_alt['author'] = email_only
                                page_commits_alt = project.commits.list(**branch_params_alt)
                                if page_commits_alt:
                                    logger.info(f"使用邮箱格式找到 {len(page_commits_alt)} 条提交")
                                    page_commits = page_commits_alt
                                    branch_params = branch_params_alt
                            # 尝试只使用名称部分
                            name_match = re.match(r'^([^<]+)', author_name)
                            if name_match and not email_match:
                                name_only = name_match.group(1).strip()
                                logger.info(f"尝试使用名称格式查询分支 '{branch_obj.name}': {name_only}")
                                branch_params_alt = branch_params.copy()
                                branch_params_alt['author'] = name_only
                                page_commits_alt = project.commits.list(**branch_params_alt)
                                if page_commits_alt:
                                    logger.info(f"使用名称格式找到 {len(page_commits_alt)} 条提交")
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
                            logger.warning(f"注意: 查询的作者 '{author_name}' 与返回的提交作者 '{author_info} <{author_email}>' 不匹配")
                            logger.warning(f"建议: 尝试使用 '{author_info}' 或 '{author_email}' 作为提交者名称")
                    
                    branch_commits.extend(page_commits)
                    
                    if len(page_commits) < per_page:
                        break
                    
                    branch_page += 1
                
                if branch_commits:
                    logger.info(f"[{idx}/{len(ordered_branches)}] 分支 '{branch_obj.name}': 找到 {len(branch_commits)} 条提交")
                    all_commits.extend(branch_commits)
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
        
        # 去重（同一个提交可能在多个分支上）
        seen_ids = set()
        unique_commits = []
        for commit in all_commits:
            if commit.id not in seen_ids:
                seen_ids.add(commit.id)
                unique_commits.append(commit)
        
        logger.info(f"共获取到 {len(unique_commits)} 条提交记录（遍历了 {len(ordered_branches)} 个分支，跳过了 {skipped_count} 个不在日期范围内的分支）")
        return unique_commits
    
    # 添加日期范围
    if since_date:
        params['since'] = to_gitlab_datetime(since_date)
    if until_date:
        params['until'] = to_gitlab_datetime(until_date, end_of_day=True)
    
    try:
        while True:
            params['page'] = page
            page_commits = project.commits.list(**params)
            
            if not page_commits:
                break
            
            commits.extend(page_commits)
            logger.info(f"已获取 {len(commits)} 条提交记录...")
            
            # 如果返回的提交数少于每页数量，说明已经是最后一页
            if len(page_commits) < per_page:
                break
            
            page += 1
        
        logger.info(f"共获取到 {len(commits)} 条提交记录")
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
        # 解析提交日期
        commit_date = commit.committed_date
        if isinstance(commit_date, str):
            # 解析 ISO 8601 格式日期
            date_obj = parse_iso_date(commit_date)
        else:
            date_obj = commit_date
        
        # 提取日期部分（YYYY-MM-DD）
        date_str = date_obj.strftime('%Y-%m-%d')
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
            page_projects = gl.projects.list(**params)
            
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


def scan_all_projects(gl, author_name, since_date=None, until_date=None, branch=None, max_workers=10):
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
    projects = get_all_projects(gl)
    
    results = {}
    total_commits = 0
    
    # 使用线程池并行处理项目
    def process_project(project):
        """处理单个项目的函数"""
        project_path = project.path_with_namespace
        try:
            # 获取该项目的提交
            commits = get_commits_by_author(
                project,
                author_name,
                since_date=since_date,
                until_date=until_date,
                branch=branch
            )
            
            if commits:
                return {
                    'project_path': project_path,
                    'project': project,
                    'commits': commits,
                    'count': len(commits)
                }
            return None
        except Exception as e:
            # 只记录重要错误，忽略权限不足等常见错误
            error_msg = str(e)
            if '403' in error_msg or '401' in error_msg or 'Not Found' in error_msg:
                logger.debug(f"  跳过项目 {project_path}（无权限或不存在）")
            else:
                logger.warning(f"  扫描项目 {project_path} 时出错: {error_msg}")
            return None
    
    # 并行处理项目
    completed = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        future_to_project = {executor.submit(process_project, project): project for project in projects}
        
        # 处理完成的任务
        for future in as_completed(future_to_project):
            completed += 1
            project = future_to_project[future]
            project_path = project.path_with_namespace
            
            try:
                result = future.result()
                if result:
                    results[result['project_path']] = {
                        'project': result['project'],
                        'commits': result['commits']
                    }
                    total_commits += result['count']
                    logger.info(f"[{completed}/{len(projects)}] ✓ {project_path}: 找到 {result['count']} 条提交")
                else:
                    logger.debug(f"[{completed}/{len(projects)}] {project_path}: 未找到提交")
            except Exception as e:
                logger.warning(f"[{completed}/{len(projects)}] {project_path}: 处理失败: {str(e)}")
    
    logger.info(f"扫描完成，共在 {len(results)} 个项目中找到 {total_commits} 条提交")
    return results
