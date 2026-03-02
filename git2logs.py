#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitLab 提交日志生成工具
从 GitLab 仓库获取指定提交者每天的代码提交，生成简洁的 Markdown 格式日志
"""
import argparse
import sys
import os
from datetime import datetime
from collections import defaultdict
from urllib.parse import urlparse
import logging
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed

# 导入工具模块
from utils.date_utils import (
    parse_iso_date,
    parse_simple_date,
    safe_parse_commit_date,
    format_date_chinese,
    format_date_range,
    get_date_range_days
)
from utils.api_utils import GitLabAPIParams, extract_email_from_author, extract_name_from_author
from utils.patterns import FIX_KEYWORDS, FEAT_KEYWORDS, check_commit_type, classify_commit

try:
    import gitlab  # pyright: ignore[reportMissingImports]
except ImportError:
    print("错误: 未安装 python-gitlab 库")
    print("请运行: pip install python-gitlab")
    sys.exit(1)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 性能优化：是否使用并行API调用（可通过环境变量控制）
USE_PARALLEL_API = os.getenv('GIT2LOGS_PARALLEL', 'true').lower() == 'true'
MAX_PARALLEL_WORKERS = int(os.getenv('GIT2LOGS_MAX_WORKERS', '5'))


def _query_branch_commits(project, branch_obj, author_name, since_date, until_date, per_page=100):
    """
    查询单个分支的提交记录（用于并行调用）

    Args:
        project: GitLab项目对象
        branch_obj: 分支对象
        author_name: 提交者名称
        since_date: 开始日期
        until_date: 结束日期
        per_page: 每页数量

    Returns:
        tuple: (分支名称, 提交列表)
    """
    try:
        from utils.api_utils import GitLabAPIParams

        # 构建查询参数
        params = GitLabAPIParams.build_commits_params(
            author=author_name,
            branch=branch_obj.name,
            since_date=since_date,
            until_date=until_date,
            per_page=per_page
        )

        branch_commits = []
        page = 1

        while True:
            params['page'] = page
            page_commits = project.commits.list(**params)

            if not page_commits:
                break

            branch_commits.extend(page_commits)

            if len(page_commits) < per_page:
                break

            page += 1

        if branch_commits:
            logger.debug(f"✓ 分支 '{branch_obj.name}': {len(branch_commits)} 条提交")

        return (branch_obj.name, branch_commits)

    except Exception as e:
        logger.debug(f"✗ 分支 '{branch_obj.name}' 查询失败: {str(e)}")
        return (branch_obj.name, [])


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
    per_page = 100
    
    # 如果指定了分支，直接查询该分支
    if branch:
        params = {
            'author': author_name,
            'ref_name': branch,
            'per_page': per_page
        }
        
        # 添加日期范围（如果指定）
        if since_date:
            params['since'] = f"{since_date}T00:00:00Z"
        if until_date:
            params['until'] = f"{until_date}T23:59:59Z"
        
        logger.debug(f"查询参数: author={author_name}, since={params.get('since')}, until={params.get('until')}, branch={branch}")
        
        try:
            # 首先尝试不指定作者，获取一些提交看看实际的作者格式
            try:
                debug_params = {'ref_name': branch, 'per_page': 5}
                if since_date:
                    debug_params['since'] = f"{since_date}T00:00:00Z"
                if until_date:
                    debug_params['until'] = f"{until_date}T23:59:59Z"
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
        branches = project.branches.list(per_page=100)
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
                    branch_params['since'] = f"{since_date}T00:00:00Z"
                if until_date:
                    branch_params['until'] = f"{until_date}T23:59:59Z"
                
                # 首先尝试不指定作者，获取一些提交看看实际的作者格式（仅第一个分支）
                if idx == 1:
                    try:
                        debug_params = {'ref_name': branch_obj.name, 'per_page': 20}
                        if since_date:
                            debug_params['since'] = f"{since_date}T00:00:00Z"
                        if until_date:
                            debug_params['until'] = f"{until_date}T23:59:59Z"
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
                                    except:
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
        params['since'] = f"{since_date}T00:00:00Z"
    if until_date:
        params['until'] = f"{until_date}T23:59:59Z"
    
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


def generate_markdown_log(grouped_commits, author_name, repo_name=None, project=None):
    """
    生成 Markdown 格式的日志
    
    Args:
        grouped_commits: 按日期分组的提交字典
        author_name: 提交者姓名
        repo_name: 仓库名称（可选）
        project: GitLab 项目对象（可选，用于获取详细commit信息）
    
    Returns:
        str: Markdown 格式的日志内容
    """
    lines = []
    
    # 标题
    if repo_name:
        lines.append(f"# {repo_name} - {author_name} 提交日志\n")
    else:
        lines.append(f"# {author_name} 提交日志\n")
    
    lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    lines.append(f"**提交者**: {author_name}\n")
    lines.append(f"**总提交数**: {sum(len(commits) for commits in grouped_commits.values())}\n")
    lines.append(f"**提交天数**: {len(grouped_commits)}\n")
    lines.append("\n---\n\n")
    
    # 按日期输出提交
    for date, commits in grouped_commits.items():
        # 日期标题
        date_obj = parse_simple_date(date)
        date_formatted = date_obj.strftime('%Y年%m月%d日')
        lines.append(f"## {date_formatted} ({date})\n")
        
        # 当日统计
        lines.append(f"**提交数**: {len(commits)}\n\n")
        
        # 提交列表
        for idx, commit in enumerate(commits, 1):
            # 获取详细commit信息
            if project:
                try:
                    details = get_commit_details(project, commit)
                    short_message = details['short_message']
                    full_message = details['full_message']
                    stats = details['stats']
                    changed_files = details['changed_files']
                except Exception as e:
                    logger.debug(f"获取commit详情失败: {str(e)}")
                    short_message = commit.message.split('\n')[0] if commit.message else ''
                    full_message = commit.message or ''
                    stats = None
                    changed_files = []
            else:
                short_message = commit.message.split('\n')[0] if commit.message else ''
                full_message = commit.message or ''
                stats = None
                changed_files = []
            
            commit_id = commit.id[:8]  # 短提交 ID
            commit_url = getattr(commit, 'web_url', '')
            
            lines.append(f"### {idx}. [{commit_id}]({commit_url}) {short_message}\n")
            
            # 提交时间
            commit_time = commit.committed_date
            if isinstance(commit_time, str):
                time_obj = parse_iso_date(commit_time)
            else:
                time_obj = commit_time
            time_str = time_obj.strftime('%H:%M:%S')
            lines.append(f"**时间**: {time_str}\n")
            
            # 显示完整的commit message（如果有多行）
            if full_message and '\n' in full_message:
                filtered_msg = '\n'.join(
                    l for l in full_message.split('\n')
                    if not l.strip().lower().startswith('made-with:')
                ).strip()
                if filtered_msg and '\n' in filtered_msg:
                    lines.append(f"**完整提交信息**:\n```\n{filtered_msg}\n```\n")

            # 显示代码行数统计
            if stats:
                lines.append(f"**代码变更**: +{stats.get('additions', 0)} -{stats.get('deletions', 0)} (总计: {stats.get('total', 0)} 行)\n")
            elif hasattr(commit, 'stats') and commit.stats:
                try:
                    commit_stats = commit.stats
                    if isinstance(commit_stats, dict):
                        lines.append(f"**代码变更**: +{commit_stats.get('additions', 0)} -{commit_stats.get('deletions', 0)}\n")
                except:
                    pass
            
            # 显示文件变更列表
            if changed_files:
                lines.append(f"**变更文件** ({len(changed_files)} 个):\n")
                for file_info in changed_files[:10]:  # 最多显示10个文件
                    file_path = file_info.get('new_path') or file_info.get('old_path') or file_info.get('path', '')
                    if file_path:
                        lines.append(f"- `{file_path}`\n")
                if len(changed_files) > 10:
                    lines.append(f"- ... 还有 {len(changed_files) - 10} 个文件\n")
            
            lines.append("\n")
        
        lines.append("---\n\n")
    
    return ''.join(lines)


def generate_multi_project_markdown(all_results, author_name, since_date=None, until_date=None):
    """
    生成多项目汇总的 Markdown 格式日志
    
    Args:
        all_results: 按项目分组的提交字典
        author_name: 提交者姓名
        since_date: 起始日期（可选）
        until_date: 结束日期（可选）
    
    Returns:
        str: Markdown 格式的日志内容
    """
    lines = []
    
    # 标题
    lines.append(f"# {author_name} - 所有项目提交汇总日志\n")
    lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    lines.append(f"**提交者**: {author_name}\n")
    
    # 日期范围
    if since_date and until_date:
        lines.append(f"**日期范围**: {since_date} 至 {until_date}\n")
    elif since_date:
        lines.append(f"**起始日期**: {since_date}\n")
    elif until_date:
        lines.append(f"**结束日期**: {until_date}\n")
    
    # 统计信息
    total_projects = len(all_results)
    total_commits = sum(len(result['commits']) for result in all_results.values())
    
    # 按日期汇总所有提交
    all_commits_by_date = defaultdict(list)
    for project_path, result in all_results.items():
        commits = result['commits']
        for commit in commits:
            commit_date = commit.committed_date
            if isinstance(commit_date, str):
                date_obj = parse_iso_date(commit_date)
            else:
                date_obj = commit_date
            date_str = date_obj.strftime('%Y-%m-%d')
            all_commits_by_date[date_str].append({
                'project': project_path,
                'commit': commit
            })
    
    lines.append(f"**涉及项目数**: {total_projects}\n")
    lines.append(f"**总提交数**: {total_commits}\n")
    lines.append(f"**提交天数**: {len(all_commits_by_date)}\n")
    lines.append("\n---\n\n")
    
    # 按日期输出提交
    sorted_dates = sorted(all_commits_by_date.keys(), reverse=True)
    for date in sorted_dates:
        date_obj = parse_simple_date(date)
        date_formatted = date_obj.strftime('%Y年%m月%d日')
        lines.append(f"## {date_formatted} ({date})\n")
        
        commits_on_date = all_commits_by_date[date]
        lines.append(f"**提交数**: {len(commits_on_date)}\n\n")
        
        # 按项目分组
        commits_by_project = defaultdict(list)
        for item in commits_on_date:
            commits_by_project[item['project']].append(item['commit'])
        
        # 输出每个项目的提交
        for project_path in sorted(commits_by_project.keys()):
            project_commits = commits_by_project[project_path]
            project_info = all_results[project_path]['project']
            
            lines.append(f"### 📦 {project_path}\n")
            lines.append(f"**项目**: [{project_info.name}]({project_info.web_url})\n")
            lines.append(f"**提交数**: {len(project_commits)}\n\n")
            
            # 按时间排序
            project_commits.sort(key=lambda c: c.committed_date, reverse=True)
            
            # 获取项目对象用于获取详细commit信息
            project = all_results[project_path]['project']
            
            for idx, commit in enumerate(project_commits, 1):
                # 获取详细commit信息
                try:
                    details = get_commit_details(project, commit)
                    short_message = details['short_message']
                    full_message = details['full_message']
                    stats = details['stats']
                    changed_files = details['changed_files']
                except Exception as e:
                    logger.debug(f"获取commit详情失败: {str(e)}")
                    short_message = commit.message.split('\n')[0] if commit.message else ''
                    full_message = commit.message or ''
                    stats = None
                    changed_files = []
                
                commit_id = commit.id[:8]
                commit_url = getattr(commit, 'web_url', '')
                
                lines.append(f"#### {idx}. [{commit_id}]({commit_url}) {short_message}\n")
                
                commit_time = commit.committed_date
                if isinstance(commit_time, str):
                    time_obj = parse_iso_date(commit_time)
                else:
                    time_obj = commit_time
                time_str = time_obj.strftime('%H:%M:%S')
                lines.append(f"**时间**: {time_str}\n")
                
                # 显示完整的commit message（如果有多行）
                if full_message and '\n' in full_message:
                    lines.append(f"**完整提交信息**:\n```\n{full_message}\n```\n")
                
                # 显示代码行数统计
                if stats:
                    lines.append(f"**代码变更**: +{stats.get('additions', 0)} -{stats.get('deletions', 0)} (总计: {stats.get('total', 0)} 行)\n")
                elif hasattr(commit, 'stats') and commit.stats:
                    try:
                        commit_stats = commit.stats
                        if isinstance(commit_stats, dict):
                            lines.append(f"**代码变更**: +{commit_stats.get('additions', 0)} -{commit_stats.get('deletions', 0)}\n")
                    except:
                        pass
                
                # 显示文件变更列表（最多显示5个）
                if changed_files:
                    lines.append(f"**变更文件** ({len(changed_files)} 个):\n")
                    for file_info in changed_files[:5]:
                        file_path = file_info.get('new_path') or file_info.get('old_path') or file_info.get('path', '')
                        if file_path:
                            lines.append(f"- `{file_path}`\n")
                    if len(changed_files) > 5:
                        lines.append(f"- ... 还有 {len(changed_files) - 5} 个文件\n")
                
                lines.append("\n")
            
            lines.append("---\n\n")
    
    return ''.join(lines)


def analyze_commit_type(commit_message):
    """
    分析提交类型
    
    Args:
        commit_message: 提交信息
    
    Returns:
        tuple: (类型, emoji)
    """
    message_lower = commit_message.lower()
    
    # 优先检查前缀（更准确）
    if message_lower.startswith('fix') or message_lower.startswith('修复'):
        return ('Bug修复', '🐛')
    elif message_lower.startswith('feat') or message_lower.startswith('新增') or message_lower.startswith('添加'):
        return ('功能开发', '✨')
    elif message_lower.startswith('refactor') or message_lower.startswith('重构'):
        return ('代码重构', '♻️')
    elif message_lower.startswith('chore') or message_lower.startswith('删除') or message_lower.startswith('清理'):
        return ('代码维护', '🔧')
    elif message_lower.startswith('docs') or message_lower.startswith('文档'):
        return ('文档更新', '📝')
    elif message_lower.startswith('style') or message_lower.startswith('样式'):
        return ('样式调整', '💄')
    elif message_lower.startswith('test') or message_lower.startswith('测试'):
        return ('测试相关', '✅')
    # 然后检查关键词
    elif '修复' in commit_message or '解决' in commit_message or 'bug' in message_lower:
        return ('Bug修复', '🐛')
    elif '新增' in commit_message or '添加' in commit_message:
        return ('功能开发', '✨')
    elif '重构' in commit_message or ('优化' in commit_message and '修复' not in commit_message):
        return ('代码重构', '♻️')
    else:
        return ('其他', '📌')


def get_commit_details(project, commit, timeout=10, max_files=50, max_message_length=5000):
    """
    获取单个提交的详细信息（带超时和异常处理）
    
    Args:
        project: GitLab 项目对象
        commit: GitLab commit 对象
        timeout: 超时时间（秒），默认10秒
        max_files: 最大文件数量，默认50个
        max_message_length: 最大消息长度，默认5000字符
    
    Returns:
        dict: 包含完整信息的字典
            - full_message: 完整的commit message（多行，已截断）
            - short_message: 第一行commit message
            - changed_files: 文件变更列表（已限制数量）
            - stats: 代码行数统计
            - author: 作者信息
            - committed_date: 提交时间
    """
    import signal
    
    # 限制commit message长度
    full_message = commit.message or ''
    if len(full_message) > max_message_length:
        full_message = full_message[:max_message_length] + '\n... (消息过长，已截断)'
        logger.debug(f"Commit {commit.id[:8]} 消息过长，已截断至 {max_message_length} 字符")
    
    details = {
        'full_message': full_message,
        'short_message': full_message.split('\n')[0] if full_message else '',
        'changed_files': [],
        'stats': None,
        'author': getattr(commit, 'author_name', ''),
        'committed_date': commit.committed_date,
        'web_url': getattr(commit, 'web_url', '')
    }
    
    # 超时处理函数
    def timeout_handler(signum, frame):
        raise TimeoutError(f"获取commit详情超时（{timeout}秒）")
    
    try:
        # 设置超时（仅Unix系统）
        if hasattr(signal, 'SIGALRM'):
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(timeout)
        
        try:
            # 尝试获取详细的commit信息
            detailed_commit = project.commits.get(commit.id)
            
            # 获取文件变更列表（限制数量和大小）
            try:
                if hasattr(detailed_commit, 'diff'):
                    diffs = detailed_commit.diff()
                    file_count = 0
                    for diff in diffs:
                        if file_count >= max_files:
                            logger.debug(f"Commit {commit.id[:8]} 文件数量超过限制，仅显示前 {max_files} 个")
                            break
                        
                        try:
                            diff_text = getattr(diff, 'diff', '')
                            # 限制单个diff的大小
                            if diff_text and len(diff_text) > 10000:
                                diff_text = diff_text[:10000] + '\n... (diff过长，已截断)'
                            
                            file_info = {
                                'path': getattr(diff, 'new_path', getattr(diff, 'old_path', '')),
                                'old_path': getattr(diff, 'old_path', ''),
                                'new_path': getattr(diff, 'new_path', ''),
                                'diff': diff_text[:500] if diff_text else ''  # 限制显示长度
                            }
                            details['changed_files'].append(file_info)
                            file_count += 1
                        except Exception as e:
                            logger.debug(f"处理单个文件diff失败: {str(e)}")
                            continue
                    
                    if len(diffs) > max_files:
                        details['changed_files'].append({
                            'path': f'... 还有 {len(diffs) - max_files} 个文件未显示',
                            'old_path': '',
                            'new_path': '',
                            'diff': ''
                        })
            except TimeoutError:
                logger.warning(f"获取commit {commit.id[:8]} 文件变更列表超时")
            except Exception as e:
                logger.debug(f"获取文件变更列表失败: {str(e)}")
            
            # 获取统计信息
            try:
                if hasattr(detailed_commit, 'stats') and detailed_commit.stats:
                    stats = detailed_commit.stats
                    if isinstance(stats, dict):
                        details['stats'] = {
                            'additions': stats.get('additions', 0),
                            'deletions': stats.get('deletions', 0),
                            'total': stats.get('total', 0)
                        }
            except Exception as e:
                logger.debug(f"获取统计信息失败: {str(e)}")
        
        finally:
            # 取消超时
            if hasattr(signal, 'SIGALRM'):
                signal.alarm(0)
    
    except TimeoutError as e:
        logger.warning(f"获取commit {commit.id[:8]} 详情超时: {str(e)}")
    except Exception as e:
        logger.debug(f"获取详细commit信息失败: {str(e)}")
        # 降级：使用基本信息
        try:
            if hasattr(commit, 'stats') and commit.stats:
                stats = commit.stats
                if isinstance(stats, dict):
                    details['stats'] = {
                        'additions': stats.get('additions', 0),
                        'deletions': stats.get('deletions', 0),
                        'total': stats.get('total', 0)
                    }
        except:
            pass
    
    return details


def get_commit_stats(project, commit):
    """
    获取单个提交的代码行数统计
    
    Args:
        project: GitLab 项目对象
        commit: GitLab commit 对象
    
    Returns:
        dict: 包含 additions, deletions, total 的字典，如果无法获取则返回 None
    """
    try:
        # 方法1: 尝试直接访问 stats 属性
        if hasattr(commit, 'stats') and commit.stats:
            stats = commit.stats
            if isinstance(stats, dict):
                return {
                    'additions': stats.get('additions', 0),
                    'deletions': stats.get('deletions', 0),
                    'total': stats.get('total', 0)
                }
        
        # 方法2: 尝试通过 API 获取详细 commit 信息
        try:
            detailed_commit = project.commits.get(commit.id)
            if hasattr(detailed_commit, 'stats') and detailed_commit.stats:
                stats = detailed_commit.stats
                if isinstance(stats, dict):
                    return {
                        'additions': stats.get('additions', 0),
                        'deletions': stats.get('deletions', 0),
                        'total': stats.get('total', 0)
                    }
        except Exception:
            pass
        
        # 方法3: 尝试通过 diff 计算（性能较低，作为最后手段）
        try:
            diffs = commit.diff()
            additions = 0
            deletions = 0
            for diff in diffs:
                if hasattr(diff, 'diff'):
                    diff_text = diff.diff
                    if diff_text:
                        # 计算新增和删除的行数
                        for line in diff_text.split('\n'):
                            if line.startswith('+') and not line.startswith('+++'):
                                additions += 1
                            elif line.startswith('-') and not line.startswith('---'):
                                deletions += 1
            return {
                'additions': additions,
                'deletions': deletions,
                'total': additions + deletions
            }
        except Exception:
            pass
        
        return None
    except Exception as e:
        logger.debug(f"获取提交 {commit.id[:8]} 的统计信息失败: {str(e)}")
        return None


def calculate_code_statistics(all_results, since_date=None, until_date=None):
    """
    计算总体代码行数统计
    
    Args:
        all_results: 按项目分组的提交字典
        since_date: 起始日期（可选）
        until_date: 结束日期（可选）
    
    Returns:
        dict: 包含总新增行数、总删除行数、净增行数、平均每次提交代码行数等统计信息
    """
    total_additions = 0
    total_deletions = 0
    total_commits_with_stats = 0
    total_commits = 0
    
    # 用于缓存已获取的统计信息，避免重复API调用
    stats_cache = {}
    
    for project_path, result in all_results.items():
        project = result['project']
        commits = result['commits']
        
        for commit in commits:
            total_commits += 1
            
            # 尝试从缓存获取
            commit_id = commit.id
            if commit_id in stats_cache:
                stats = stats_cache[commit_id]
            else:
                stats = get_commit_stats(project, commit)
                stats_cache[commit_id] = stats
            
            if stats:
                total_additions += stats.get('additions', 0)
                total_deletions += stats.get('deletions', 0)
                total_commits_with_stats += 1
    
    net_lines = total_additions - total_deletions
    avg_lines_per_commit = (total_additions + total_deletions) / total_commits_with_stats if total_commits_with_stats > 0 else 0
    
    return {
        'total_additions': total_additions,
        'total_deletions': total_deletions,
        'net_lines': net_lines,
        'total_commits': total_commits,
        'commits_with_stats': total_commits_with_stats,
        'avg_lines_per_commit': round(avg_lines_per_commit, 2),
        'stats_availability': total_commits_with_stats / total_commits if total_commits > 0 else 0
    }


def calculate_work_hours(all_results, since_date=None, until_date=None, daily_hours=8.0, branch=None):
    """
    计算工时分配

    基于代码变更量、提交频率、文件变更数的权重算法计算每个项目的工时分配

    Args:
        all_results: 按项目分组的提交字典
        since_date: 起始日期（可选，格式：YYYY-MM-DD）
        until_date: 结束日期（可选，格式：YYYY-MM-DD）
        daily_hours: 每日标准工时（默认8小时）
        branch: 分支名称（可选，用于显示）

    Returns:
        dict: 按日期分组的工时数据
              格式: {
                  '2026-01-28': {
                      'date': '2026-01-28',
                      'projects': {
                          'project1': {
                              'project_name': 'project1',
                              'tasks': [
                                  {
                                      'task_name': '任务名称',
                                      'task_type': '功能开发',
                                      'hours': 4.5,
                                      'commits': 1,
                                      'code_changes': 120
                                  }
                              ]
                          }
                      }
                  }
              }
    """
    from collections import defaultdict
    from datetime import datetime

    # 按日期分组工时数据
    work_hours_by_date = {}

    # 收集所有提交并按日期分组
    commits_by_date = defaultdict(list)

    for project_path, result in all_results.items():
        commits = result['commits']
        project_obj = result.get('project')  # 获取项目对象

        for commit in commits:
            # 解析日期
            commit_date = commit.committed_date
            if isinstance(commit_date, str):
                date_obj = parse_iso_date(commit_date)
            else:
                date_obj = commit_date
            date_str = date_obj.strftime('%Y-%m-%d')

            commits_by_date[date_str].append({
                'project': project_path,
                'commit': commit,
                'result': result,
                'project_obj': project_obj  # 保存项目对象以获取URL等信息
            })

    # 为每个日期计算工时分配
    for date_str, day_commits in commits_by_date.items():
        # 计算该日每个项目的权重
        project_weights = {}
        total_weight = 0

        for commit_info in day_commits:
            project = commit_info['project']
            commit = commit_info['commit']
            project_obj = commit_info.get('project_obj')

            # 获取代码变更量 - 改进版：尝试多种方式获取
            code_changes = 0
            additions = 0
            deletions = 0

            # 方式1: 尝试从commit.stats获取
            if hasattr(commit, 'stats') and commit.stats:
                if hasattr(commit.stats, 'total') and commit.stats.total:
                    # 有些API返回total字典
                    if isinstance(commit.stats.total, dict):
                        additions = commit.stats.total.get('additions', 0)
                        deletions = commit.stats.total.get('deletions', 0)
                        code_changes = commit.stats.total.get('lines', 0) or (additions + deletions)
                    else:
                        # 有些返回对象
                        additions = getattr(commit.stats.total, 'additions', 0) or 0
                        deletions = getattr(commit.stats.total, 'deletions', 0) or 0
                        code_changes = additions + deletions
                elif hasattr(commit.stats, 'additions') and hasattr(commit.stats, 'deletions'):
                    # 直接在stats对象上
                    additions = commit.stats.additions or 0
                    deletions = commit.stats.deletions or 0
                    code_changes = additions + deletions

            # 方式2: 如果还是0，尝试从result中的commit详情获取
            if code_changes == 0 and 'commits' in commit_info.get('result', {}):
                for c in commit_info['result']['commits']:
                    if hasattr(c, 'id') and hasattr(commit, 'id') and c.id == commit.id:
                        if hasattr(c, 'stats') and c.stats:
                            if hasattr(c.stats, 'additions'):
                                additions = c.stats.additions or 0
                                deletions = c.stats.deletions or 0
                                code_changes = additions + deletions
                        break

            # 获取文件变更数
            files_changed = 0
            if hasattr(commit, 'stats') and commit.stats:
                if hasattr(commit.stats, 'total') and commit.stats.total:
                    if isinstance(commit.stats.total, dict):
                        files_changed = commit.stats.total.get('files', 0)
                    else:
                        files_changed = getattr(commit.stats.total, 'files', 0) or 0

            # 备选方案：从diff获取文件数
            if files_changed == 0:
                try:
                    if hasattr(commit, 'diff'):
                        diff_attr = getattr(commit, 'diff')
                        # 检查diff是方法还是属性
                        if callable(diff_attr):
                            # 如果是方法，调用它
                            diff_result = diff_attr()
                            if diff_result:
                                files_changed = len(diff_result) if hasattr(diff_result, '__len__') else 0
                        elif diff_attr:
                            # 如果是属性，直接使用
                            files_changed = len(diff_attr) if hasattr(diff_attr, '__len__') else 0
                except Exception:
                    # 如果获取diff失败，忽略错误
                    pass

            if project not in project_weights:
                project_weights[project] = {
                    'code_changes': 0,
                    'commit_count': 0,
                    'files_changed': 0,
                    'commits': [],
                    'project_obj': project_obj  # 保存项目对象
                }

            project_weights[project]['code_changes'] += code_changes
            project_weights[project]['commit_count'] += 1
            project_weights[project]['files_changed'] += files_changed
            project_weights[project]['commits'].append(commit)

        # 计算总权重
        for project, stats in project_weights.items():
            # 权重算法：代码变更量60% + 提交频率20% + 文件变更数20%
            code_weight = stats['code_changes'] / 100.0 * 0.6
            commit_weight = stats['commit_count'] * 0.5 * 0.2
            file_weight = stats['files_changed'] * 0.3 * 0.2
            weight = code_weight + commit_weight + file_weight
            stats['weight'] = weight
            total_weight += weight

        # 分配工时
        date_data = {
            'date': date_str,
            'total_hours': daily_hours,
            'projects': {}
        }

        for project, stats in project_weights.items():
            if total_weight > 0:
                project_hours = (stats['weight'] / total_weight) * daily_hours
            else:
                project_hours = daily_hours / len(project_weights)

            # 提取项目名称（去除路径）
            project_name = project.split('/')[-1] if '/' in project else project

            # 获取GitLab URL和分支信息
            project_obj = stats.get('project_obj')
            gitlab_url = ''
            if project_obj:
                gitlab_url = getattr(project_obj, 'web_url', '') or getattr(project_obj, 'http_url_to_repo', '')

            # 按提交生成任务列表
            tasks = []
            for commit in stats['commits']:
                # 获取代码变更量 - 改进版
                code_changes = 0
                additions = 0
                deletions = 0

                if hasattr(commit, 'stats') and commit.stats:
                    if hasattr(commit.stats, 'total') and commit.stats.total:
                        if isinstance(commit.stats.total, dict):
                            additions = commit.stats.total.get('additions', 0)
                            deletions = commit.stats.total.get('deletions', 0)
                            code_changes = commit.stats.total.get('lines', 0) or (additions + deletions)
                        else:
                            additions = getattr(commit.stats.total, 'additions', 0) or 0
                            deletions = getattr(commit.stats.total, 'deletions', 0) or 0
                            code_changes = additions + deletions
                    elif hasattr(commit.stats, 'additions') and hasattr(commit.stats, 'deletions'):
                        additions = commit.stats.additions or 0
                        deletions = commit.stats.deletions or 0
                        code_changes = additions + deletions

                # 获取commit信息
                commit_id = commit.id[:8] if hasattr(commit, 'id') else ''
                commit_url = getattr(commit, 'web_url', '')

                # 获取分支信息（优先级：commit.refs > 参数指定的branch > '多分支'）
                commit_branch = ''
                if hasattr(commit, 'refs') and commit.refs:
                    # 从refs中提取分支信息
                    refs = commit.refs if isinstance(commit.refs, list) else [commit.refs]
                    for ref in refs:
                        if isinstance(ref, str):
                            if not ref.startswith('tag:'):
                                commit_branch = ref
                                break
                        elif hasattr(ref, 'name'):
                            if ref.type == 'branch':
                                commit_branch = ref.name
                                break

                # 如果从commit.refs获取不到，使用参数传入的branch
                if not commit_branch and branch:
                    commit_branch = branch

                # 如果还是没有，显示为"多分支"
                if not commit_branch:
                    commit_branch = '多分支'

                # 识别提交类型和任务名称
                commit_message = commit.message.strip()
                first_line = commit_message.split('\n')[0]

                task_type, _ = analyze_commit_type(commit_message)
                task_name = first_line

                # 计算该任务的工时（按提交权重分配）
                commit_code_weight = code_changes / 100.0 * 0.6
                commit_weight_value = 0.5 * 0.2
                commit_total_weight = commit_code_weight + commit_weight_value

                if stats['weight'] > 0:
                    task_hours = (commit_total_weight / stats['weight']) * project_hours
                else:
                    task_hours = project_hours / len(stats['commits'])

                tasks.append({
                    'task_name': task_name,
                    'task_type': task_type,
                    'hours': round(task_hours, 2),
                    'commits': 1,
                    'additions': additions,
                    'deletions': deletions,
                    'commit_id': commit_id,
                    'commit_url': commit_url,
                    'branch': commit_branch,
                    'gitlab_url': gitlab_url
                })

            date_data['projects'][project] = {
                'project_name': project_name,
                'total_hours': round(project_hours, 2),
                'tasks': tasks,
                'commit_count': stats['commit_count'],
                'code_changes': stats['code_changes']
            }

        work_hours_by_date[date_str] = date_data

    return work_hours_by_date


def format_work_hours_table(date_data):
    """
    格式化工时数据为Markdown表格

    Args:
        date_data: 单日工时数据

    Returns:
        str: Markdown格式的工时表格
    """
    lines = []

    lines.append("## ⏱️ 工时分配表\n\n")
    lines.append(f"**统计日期**: {date_data['date']}\n")
    lines.append(f"**标准工时**: {date_data['total_hours']} 小时\n")

    # 计算实际分配工时
    actual_hours = sum(p['total_hours'] for p in date_data['projects'].values())
    lines.append(f"**实际分配**: {actual_hours:.1f} 小时\n\n")

    # 生成表格
    lines.append("| 项目名称 | 任务名称 | 任务类型 | 工时(h) | Commit ID | 分支 | GitLab地址 |\n")
    lines.append("|---------|---------|---------|--------|-----------|------|----------|\n")

    for project_path, project_data in date_data['projects'].items():
        project_name = project_data['project_name']
        project_hours = project_data['total_hours']

        # 第一行显示项目汇总
        first_task = True
        for task in project_data['tasks']:
            # 截断过长的commit信息
            commit_id = task.get('commit_id', '')[:8]
            branch_name = task.get('branch', 'N/A')
            if len(branch_name) > 20:
                branch_name = branch_name[:17] + '...'

            # GitLab地址 - 直接显示URL
            commit_url = task.get('commit_url', '')
            gitlab_url = task.get('gitlab_url', '')
            if commit_url:
                display_url = commit_url
            elif gitlab_url:
                display_url = gitlab_url
            else:
                display_url = 'N/A'

            if first_task:
                lines.append(f"| **{project_name}** ({project_hours:.1f}h) | {task['task_name']} | {task['task_type']} | {task['hours']:.2f} | {commit_id} | {branch_name} | {display_url} |\n")
                first_task = False
            else:
                lines.append(f"| | {task['task_name']} | {task['task_type']} | {task['hours']:.2f} | {commit_id} | {branch_name} | {display_url} |\n")

    lines.append("\n")
    return ''.join(lines)


def generate_work_hours_report(all_results, author_name, since_date=None, until_date=None, daily_hours=8.0, branch=None):
    """
    生成工时分配报告

    Args:
        all_results: 按项目分组的提交字典
        author_name: 提交者姓名
        since_date: 起始日期（可选）
        until_date: 结束日期（可选）
        daily_hours: 每日标准工时（默认8小时）
        branch: 分支名称（可选，用于显示）

    Returns:
        str: Markdown格式的工时报告
    """
    lines = []

    # 标题
    lines.append(f"# {author_name} - 工时分配报告\n")
    lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    lines.append(f"**提交者**: {author_name}\n")

    # 日期范围
    if since_date and until_date:
        if since_date == until_date:
            date_display = f"{format_date_chinese(since_date)} ({since_date})"
        else:
            date_display = format_date_range(since_date, until_date)
            date_display += f" ({since_date} 至 {until_date})"
        lines.append(f"**统计时间**: {date_display}\n")
    lines.append(f"**标准工时**: {daily_hours} 小时/天\n")
    lines.append("\n---\n\n")

    # 计算工时
    try:
        work_hours_data = calculate_work_hours(all_results, since_date, until_date, daily_hours, branch)

        if not work_hours_data:
            lines.append("**提示**: 在指定时间范围内没有找到提交记录。\n")
            return ''.join(lines)

        # 统计总体数据
        total_work_days = len(work_hours_data)
        total_hours = sum(data['total_hours'] for data in work_hours_data.values())
        all_tasks = []
        project_hours_summary = {}

        for date_str, date_data in sorted(work_hours_data.items()):
            for project_path, project_data in date_data['projects'].items():
                project_name = project_data['project_name']
                if project_name not in project_hours_summary:
                    project_hours_summary[project_name] = 0
                project_hours_summary[project_name] += project_data['total_hours']

                for task in project_data['tasks']:
                    all_tasks.append({
                        **task,
                        'date': date_str,
                        'project': project_name
                    })

        # 概览
        lines.append("## 📊 工时概览\n\n")
        lines.append(f"- **工作天数**: {total_work_days} 天\n")
        lines.append(f"- **总工时**: {total_hours:.1f} 小时\n")
        if total_work_days > 0:
            lines.append(f"- **日均工时**: {total_hours / total_work_days:.1f} 小时\n")
        lines.append(f"- **总任务数**: {len(all_tasks)} 个\n")
        lines.append("\n---\n\n")

        # 按项目统计
        if project_hours_summary:
            lines.append("## 📦 项目工时分布\n\n")
            lines.append("| 项目名称 | 总工时(小时) | 占比 | 任务数 |\n")
            lines.append("|---------|------------|------|-------|\n")

            # 统计每个项目的任务数
            project_task_count = {}
            for task in all_tasks:
                project = task['project']
                project_task_count[project] = project_task_count.get(project, 0) + 1

            for project_name, hours in sorted(project_hours_summary.items(), key=lambda x: x[1], reverse=True):
                percentage = (hours / total_hours * 100) if total_hours > 0 else 0
                task_count = project_task_count.get(project_name, 0)
                lines.append(f"| {project_name} | {hours:.1f} | {percentage:.1f}% | {task_count} |\n")

            lines.append("\n---\n\n")

        # 如果是单日，显示详细表格
        if len(work_hours_data) == 1:
            date_str = list(work_hours_data.keys())[0]
            lines.append(format_work_hours_table(work_hours_data[date_str]))

        # 如果是多日，按日期显示
        else:
            lines.append("## 📅 每日工时明细\n\n")
            for date_str in sorted(work_hours_data.keys()):
                date_data = work_hours_data[date_str]
                lines.append(f"### {format_date_chinese(date_str)} ({date_str})\n\n")
                lines.append(format_work_hours_table(date_data))
                lines.append("\n")

    except Exception as e:
        logger.error(f"生成工时报告时出错: {str(e)}")
        lines.append(f"\n**错误**: 生成工时报告时出现错误: {str(e)}\n")
        import traceback
        lines.append(f"\n```\n{traceback.format_exc()}\n```\n")

    return ''.join(lines)


def generate_statistics_report(all_results, author_name, since_date=None, until_date=None):
    """
    生成包含统计和评分的报告
    
    Args:
        all_results: 按项目分组的提交字典
        author_name: 提交者姓名
        since_date: 起始日期（可选）
        until_date: 结束日期（可选）
    
    Returns:
        str: Markdown 格式的统计报告内容
    """
    lines = []
    
    # 标题
    lines.append(f"# {author_name} - 代码统计与评分报告\n")
    lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    lines.append(f"**提交者**: {author_name}\n")
    
    # 日期范围
    if since_date and until_date:
        lines.append(f"**统计时间范围**: {since_date} 至 {until_date}\n")
    elif since_date:
        lines.append(f"**起始日期**: {since_date}\n")
    elif until_date:
        lines.append(f"**结束日期**: {until_date}\n")
    
    lines.append("\n---\n\n")
    
    # 计算代码统计（可能较慢，添加异常处理）
    code_stats = None
    try:
        logger.info("正在计算代码行数统计（可能需要一些时间）...")
        code_stats = calculate_code_statistics(all_results, since_date, until_date)
        logger.info("代码行数统计计算完成")
    except Exception as e:
        logger.warning(f"计算代码行数统计时出错: {str(e)}")
        logger.warning("将跳过代码行数统计，继续生成评分报告")
        # 创建一个默认的统计结果
        total_commits = sum(len(result['commits']) for result in all_results.values())
        code_stats = {
            'total_additions': 0,
            'total_deletions': 0,
            'net_lines': 0,
            'total_commits': total_commits,
            'commits_with_stats': 0,
            'avg_lines_per_commit': 0,
            'stats_availability': 0
        }
    
    # 代码行数统计
    lines.append("## 📊 代码行数统计\n\n")
    if code_stats['commits_with_stats'] > 0:
        lines.append(f"- **总新增行数**: {code_stats['total_additions']:,}\n")
        lines.append(f"- **总删除行数**: {code_stats['total_deletions']:,}\n")
        lines.append(f"- **净增行数**: {code_stats['net_lines']:,}\n")
        lines.append(f"- **总提交数**: {code_stats['total_commits']}\n")
        lines.append(f"- **有统计信息的提交数**: {code_stats['commits_with_stats']}\n")
        lines.append(f"- **平均每次提交代码行数**: {code_stats['avg_lines_per_commit']}\n")
        lines.append(f"- **统计信息可用率**: {code_stats['stats_availability']:.1%}\n")
    else:
        lines.append(f"- **总提交数**: {code_stats['total_commits']}\n")
        lines.append("- **代码行数统计**: 暂不可用（需要API权限或API调用失败）\n")
        lines.append("- **提示**: 代码行数统计需要额外的API调用，可能因为权限不足或网络问题而无法获取\n")
    lines.append("\n---\n\n")

    # 注意：本地评分系统已移除，如需评分功能请使用AI分析报告
    lines.append("**提示**: 本报告不包含评分信息。如需详细的工作分析和评分，请使用 `--ai-analysis` 生成AI分析报告。\n\n")

    return ''.join(lines)


def generate_all_reports(all_results, author_name, output_dir, since_date=None, until_date=None, 
                         generate_statistics=True, generate_daily=True, generate_html=True, 
                         generate_png=True, logger_func=None):
    """
    批量生成所有格式的报告
    
    Args:
        all_results: 按项目分组的提交字典
        author_name: 提交者姓名
        output_dir: 输出目录
        since_date: 起始日期（可选）
        until_date: 结束日期（可选）
        generate_statistics: 是否生成统计报告
        generate_daily: 是否生成开发日报
        generate_html: 是否生成HTML格式
        generate_png: 是否生成PNG图片
        logger_func: 日志输出函数（可选）
    
    Returns:
        dict: 生成的文件路径字典
    """
    import os
    from pathlib import Path
    from datetime import datetime
    
    if logger_func:
        log = logger_func
    else:
        log = logger.info
    
    # 确保输出目录存在
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 确定文件前缀
    if since_date and until_date and since_date == until_date:
        date_prefix = since_date
    else:
        date_prefix = datetime.now().strftime('%Y-%m-%d')
    
    generated_files = {}
    
    # 1. 生成统计报告
    if generate_statistics:
        try:
            log("正在生成统计报告...")
            stats_content = generate_statistics_report(
                all_results, author_name, since_date, until_date
            )
            stats_file = output_path / f"{date_prefix}_statistics.md"
            with open(stats_file, 'w', encoding='utf-8') as f:
                f.write(stats_content)
            generated_files['statistics'] = str(stats_file)
            log(f"✓ 统计报告已保存: {stats_file}")
        except Exception as e:
            log(f"✗ 生成统计报告失败: {str(e)}")
            generated_files['statistics'] = None
    
    # 2. 生成开发日报
    daily_file = None
    if generate_daily:
        try:
            log("正在生成开发日报...")
            daily_content = generate_daily_report(
                all_results, author_name, since_date, until_date
            )
            daily_file = output_path / f"{date_prefix}_daily_report.md"
            with open(daily_file, 'w', encoding='utf-8') as f:
                f.write(daily_content)
            generated_files['daily_report'] = str(daily_file)
            log(f"✓ 开发日报已保存: {daily_file}")
        except Exception as e:
            log(f"✗ 生成开发日报失败: {str(e)}")
            generated_files['daily_report'] = None
    
    # 3. 生成HTML格式（需要基于日报）
    html_file = None
    if generate_html and daily_file and daily_file.exists():
        try:
            log("正在生成HTML格式...")
            # 尝试导入 generate_report_image 模块
            try:
                from generate_report_image import parse_daily_report, generate_html_report
                data = parse_daily_report(str(daily_file))
                html_file = output_path / f"{date_prefix}_daily_report.html"
                generate_html_report(data, str(html_file))
                generated_files['html'] = str(html_file)
                log(f"✓ HTML文件已保存: {html_file}")
            except ImportError:
                log("⚠ 无法导入 generate_report_image 模块，跳过HTML生成")
                generated_files['html'] = None
            except Exception as e:
                log(f"✗ 生成HTML失败: {str(e)}")
                generated_files['html'] = None
        except Exception as e:
            log(f"✗ 生成HTML失败: {str(e)}")
            generated_files['html'] = None
    
    # 4. 生成PNG图片（需要基于HTML）
    if generate_png and html_file and html_file.exists():
        try:
            log("正在生成PNG图片...")
            try:
                from generate_report_image import html_to_image_chrome
                png_file = output_path / f"{date_prefix}_daily_report.png"
                if html_to_image_chrome(str(html_file), str(png_file)):
                    generated_files['png'] = str(png_file)
                    log(f"✓ PNG图片已保存: {png_file}")
                else:
                    log("⚠ PNG图片生成失败（可能需要Chrome浏览器）")
                    generated_files['png'] = None
            except ImportError:
                log("⚠ 无法导入 generate_report_image 模块，跳过PNG生成")
                generated_files['png'] = None
            except Exception as e:
                log(f"✗ 生成PNG失败: {str(e)}")
                generated_files['png'] = None
        except Exception as e:
            log(f"✗ 生成PNG失败: {str(e)}")
            generated_files['png'] = None
    
    log(f"批量生成完成！共生成 {len([f for f in generated_files.values() if f])} 个文件")
    return generated_files


def analyze_with_ai(all_results, author_name, ai_config, since_date=None, until_date=None):
    """
    收集提交数据并使用AI进行分析
    
    Args:
        all_results: 按项目分组的提交字典
        author_name: 提交者姓名
        ai_config: AI配置字典
            - service: 'openai', 'anthropic', 'gemini', 'doubao' 或 'deepseek'
            - api_key: API密钥
            - model: 模型名称（可选）
        since_date: 起始日期（可选）
        until_date: 结束日期（可选）
    
    Returns:
        dict: AI分析结果
    """
    # 确保 datetime 已导入（避免作用域问题）
    from datetime import datetime
    
    try:
        from ai_analysis import analyze_with_ai as call_ai_service
    except ImportError:
        logger.error("无法导入 ai_analysis 模块")
        raise
    
    # 收集提交数据
    commits_data = {
        'total_commits': 0,
        'active_days': 0,
        'projects': [],
        'commit_messages': [],
        'time_distribution': {},
        'code_stats': {}
    }
    
    all_dates = set()
    all_commit_messages = []
    projects_set = set()
    
    # 计算代码统计
    try:
        code_stats = calculate_code_statistics(all_results, since_date, until_date)
        commits_data['code_stats'] = code_stats
    except Exception as e:
        logger.warning(f"计算代码统计失败: {str(e)}")
        commits_data['code_stats'] = {
            'total_additions': 0,
            'total_deletions': 0
        }
    
    # 收集提交信息
    for project_path, result in all_results.items():
        projects_set.add(project_path)
        commits = result['commits']
        commits_data['total_commits'] += len(commits)
        
        for commit in commits:
            # 收集commit message
            if commit.message:
                all_commit_messages.append(commit.message[:200])  # 限制长度
            
            # 收集日期
            commit_date = commit.committed_date
            if isinstance(commit_date, str):
                date_obj = parse_iso_date(commit_date)
            else:
                date_obj = commit_date
            date_str = date_obj.strftime('%Y-%m-%d')
            all_dates.add(date_str)
            
            # 收集时间分布（按月）
            month_key = date_obj.strftime('%Y-%m')
            commits_data['time_distribution'][month_key] = commits_data['time_distribution'].get(month_key, 0) + 1
    
    commits_data['active_days'] = len(all_dates)
    commits_data['projects'] = list(projects_set)
    commits_data['commit_messages'] = all_commit_messages[:50]  # 最多50条
    
    # 调用AI分析（带超时）
    timeout = 120  # 默认120秒超时
    logger.info(f"正在调用AI服务进行分析（超时时间: {timeout}秒）...")
    try:
        analysis_result = call_ai_service(commits_data, ai_config, timeout=timeout)
        logger.info("AI分析完成")
        # 在结果中添加AI服务信息
        analysis_result['ai_service'] = ai_config.get('service', 'unknown')
        analysis_result['ai_model'] = ai_config.get('model', 'unknown')
        return analysis_result
    except TimeoutError as e:
        logger.error(f"AI分析超时: {str(e)}")
        raise
    except ValueError as e:
        # API密钥错误等
        logger.error(f"AI分析失败（可能是API密钥问题）: {str(e)}")
        raise
    except ConnectionError as e:
        # 网络错误
        logger.error(f"AI分析失败（网络连接问题）: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"AI分析失败: {str(e)}")
        raise


def generate_local_analysis_report(all_results, author_name, since_date=None, until_date=None):
    """
    【已弃用】使用本地评价逻辑生成分析报告（当没有AI密钥时使用）

    注意：本函数已弃用，因为本地评分系统已移除。
    建议使用 AI 分析报告功能（--ai-analysis）获取详细的工作分析。

    Args:
        all_results: 按项目分组的提交字典
        author_name: 提交者姓名
        since_date: 起始日期（可选）
        until_date: 结束日期（可选）

    Returns:
        str: Markdown格式的提示信息
    """
    import warnings
    warnings.warn(
        "generate_local_analysis_report 已弃用，本地评分系统已移除。"
        "请使用 AI 分析报告功能（--ai-analysis）。",
        DeprecationWarning,
        stacklevel=2
    )

    lines = []

    # 标题
    lines.append(f"# {author_name} - 分析报告\n")
    lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    lines.append(f"**提交者**: {author_name}\n\n")

    lines.append("## ⚠️ 功能已弃用\n\n")
    lines.append("本地评分系统已移除。如需详细的工作分析和评分，请使用以下方式：\n\n")
    lines.append("1. **AI分析报告**（推荐）: 使用 `--ai-analysis` 参数生成基于AI的深度分析\n")
    lines.append("2. **统计报告**: 使用 `--statistics-report` 查看基础统计数据\n")
    lines.append("3. **日报**: 使用 `--daily-report` 查看每日工作总结和工时分配\n\n")

    if since_date and until_date:
        lines.append(f"**查询时间范围**: {since_date} 至 {until_date}\n")
    elif since_date:
        lines.append(f"**起始日期**: {since_date}\n")
    elif until_date:
        lines.append(f"**结束日期**: {until_date}\n")

    lines.append("\n")

    return ''.join(lines)


def generate_ai_analysis_report(analysis_result, author_name, since_date=None, until_date=None):
    """
    生成AI分析报告
    
    Args:
        analysis_result: AI分析结果字典
        author_name: 提交者姓名
        since_date: 起始日期（可选）
        until_date: 结束日期（可选）
    
    Returns:
        str: Markdown格式的AI分析报告
    """
    lines = []
    
    # 标题
    lines.append(f"# {author_name} - AI智能分析报告\n")
    lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    lines.append(f"**提交者**: {author_name}\n")
    lines.append(f"**分析方式**: 🤖 AI智能分析（使用AI模型进行深度分析）\n")
    
    # 从analysis_result中提取AI服务信息（如果存在）
    if 'ai_service' in analysis_result:
        lines.append(f"**AI服务**: {analysis_result.get('ai_service', '未知')}\n")
    if 'ai_model' in analysis_result:
        lines.append(f"**AI模型**: {analysis_result.get('ai_model', '未知')}\n")
    
    if since_date and until_date:
        lines.append(f"**分析时间范围**: {since_date} 至 {until_date}\n")
    elif since_date:
        lines.append(f"**起始日期**: {since_date}\n")
    elif until_date:
        lines.append(f"**结束日期**: {until_date}\n")
    
    lines.append("\n---\n\n")
    
    # 检查是否有错误
    if 'error' in analysis_result:
        lines.append("## ⚠️ 分析错误\n\n")
        lines.append(f"AI分析过程中出现错误: {analysis_result['error']}\n\n")
        if 'raw_response' in analysis_result:
            lines.append("### 原始响应\n\n")
            lines.append(f"```\n{analysis_result['raw_response']}\n```\n")
        return ''.join(lines)
    
    # 检查是否有原始响应但无法解析（这种情况也应该显示原始响应）
    if 'raw_response' in analysis_result and not any(
        dim in analysis_result and isinstance(analysis_result[dim], dict) 
        for dim in ['code_quality', 'work_pattern', 'tech_stack', 'problem_solving', 'innovation', 'collaboration']
    ):
        lines.append("## ⚠️ 解析警告\n\n")
        lines.append("AI返回的响应无法解析为结构化JSON格式，以下是原始响应：\n\n")
        lines.append("### 原始响应\n\n")
        lines.append(f"```\n{analysis_result['raw_response']}\n```\n\n")
        lines.append("**提示**: 这可能是由于AI返回的格式不符合预期，或者响应中包含无法解析的内容。\n")
        return ''.join(lines)
    
    # 执行摘要
    lines.append("## 📋 执行摘要\n\n")
    
    # 计算总体评分
    dimensions = ['code_quality', 'work_pattern', 'tech_stack', 'problem_solving', 'innovation', 'collaboration']
    scores = []
    for dim in dimensions:
        if dim in analysis_result and isinstance(analysis_result[dim], dict):
            score = analysis_result[dim].get('score', 0)
            scores.append(score)
    
    if scores:
        overall_score = sum(scores) / len(scores)
        lines.append(f"**总体评分**: {overall_score:.1f} / 100\n\n")
        lines.append("**各维度评分**:\n")
        for dim in dimensions:
            if dim in analysis_result and isinstance(analysis_result[dim], dict):
                score = analysis_result[dim].get('score', 0)
                dim_name = {
                    'code_quality': '代码质量',
                    'work_pattern': '工作模式',
                    'tech_stack': '技术栈',
                    'problem_solving': '问题解决能力',
                    'innovation': '创新性',
                    'collaboration': '团队协作'
                }.get(dim, dim)
                lines.append(f"- {dim_name}: {score:.1f} / 100\n")
        lines.append("\n")
    
    lines.append("---\n\n")
    
    # 详细分析
    lines.append("## 🔍 详细分析\n\n")
    
    dimension_names = {
        'code_quality': '代码质量评估',
        'work_pattern': '工作模式分析',
        'tech_stack': '技术栈评估',
        'problem_solving': '问题解决能力',
        'innovation': '创新性分析',
        'collaboration': '团队协作'
    }
    
    for dim in dimensions:
        if dim in analysis_result and isinstance(analysis_result[dim], dict):
            dim_data = analysis_result[dim]
            dim_name = dimension_names.get(dim, dim)
            score = dim_data.get('score', 0)
            
            lines.append(f"### {dim_name}: {score:.1f} / 100\n\n")
            
            # 详细分析
            if 'analysis' in dim_data:
                lines.append(f"**分析**:\n{dim_data['analysis']}\n\n")
            
            # 优势
            if 'strengths' in dim_data and dim_data['strengths']:
                lines.append("**优势**:\n")
                if isinstance(dim_data['strengths'], list):
                    for strength in dim_data['strengths']:
                        lines.append(f"- {strength}\n")
                else:
                    lines.append(f"- {dim_data['strengths']}\n")
                lines.append("\n")
            
            # 改进建议
            if 'improvements' in dim_data and dim_data['improvements']:
                lines.append("**改进建议**:\n")
                if isinstance(dim_data['improvements'], list):
                    for improvement in dim_data['improvements']:
                        lines.append(f"- {improvement}\n")
                else:
                    lines.append(f"- {dim_data['improvements']}\n")
                lines.append("\n")
            
            lines.append("---\n\n")
    
    # 如果有原始响应但无法解析
    if 'raw_response' in analysis_result and not any(dim in analysis_result for dim in dimensions):
        lines.append("## 📄 原始分析结果\n\n")
        lines.append(f"```\n{analysis_result['raw_response']}\n```\n")
    
    lines.append("\n---\n\n")
    lines.append("**注**: 本报告由AI自动生成，仅供参考。\n")
    
    return ''.join(lines)


def generate_daily_report(all_results, author_name, since_date=None, until_date=None, branch=None):
    """
    生成开发日报格式的 Markdown 文档

    Args:
        all_results: 按项目分组的提交字典
        author_name: 提交者姓名
        since_date: 起始日期（可选）
        until_date: 结束日期（可选）
        branch: 分支名称（可选，用于显示）

    Returns:
        str: Markdown 格式的日报内容
    """
    lines = []

    # 确定日期显示
    if since_date and until_date:
        if since_date == until_date:
            # 单日报告
            date_display = f"{format_date_chinese(since_date)} ({since_date})"
        else:
            # 区间报告
            date_display = format_date_range(since_date, until_date)
            date_display += f" ({since_date} 至 {until_date})"
    else:
        # 使用当前日期
        report_date = datetime.now().strftime('%Y-%m-%d')
        date_display = f"{format_date_chinese(report_date)} ({report_date})"

    # 标题
    lines.append(f"# {author_name} - 工作报告\n")
    lines.append(f"**日期**: {date_display}\n")
    lines.append(f"**提交者**: {author_name}\n")
    lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    lines.append("\n---\n\n")
    
    # 工作概览
    total_projects = len(all_results)
    total_commits = sum(len(result['commits']) for result in all_results.values())
    
    # 按类型统计
    commit_types = defaultdict(int)
    commits_by_type = defaultdict(list)
    
    # 按项目和时间组织提交
    project_commits = {}
    time_range = {'start': None, 'end': None}
    
    for project_path, result in all_results.items():
        project = result['project']
        commits = result['commits']
        
        project_commits[project_path] = {
            'project': project,
            'commits': [],
            'types': defaultdict(int)
        }
        
        for commit in commits:
            commit_type, emoji = analyze_commit_type(commit.message)
            commit_types[commit_type] += 1
            commits_by_type[commit_type].append({
                'project': project_path,
                'commit': commit
            })
            
            # 解析时间
            commit_time = commit.committed_date
            if isinstance(commit_time, str):
                time_obj = parse_iso_date(commit_time)
            else:
                time_obj = commit_time
            
            if time_range['start'] is None or time_obj < time_range['start']:
                time_range['start'] = time_obj
            if time_range['end'] is None or time_obj > time_range['end']:
                time_range['end'] = time_obj
            
            project_commits[project_path]['commits'].append({
                'commit': commit,
                'type': commit_type,
                'emoji': emoji,
                'time': time_obj
            })
            project_commits[project_path]['types'][commit_type] += 1
        
        # 按时间排序
        project_commits[project_path]['commits'].sort(key=lambda x: x['time'], reverse=True)
    
    # 工作概览
    lines.append("## 📊 工作概览\n\n")
    lines.append(f"- **涉及项目**: {total_projects} 个\n")
    lines.append(f"- **总提交数**: {total_commits} 次\n")
    
    if time_range['start'] and time_range['end']:
        start_str = time_range['start'].strftime('%H:%M')
        end_str = time_range['end'].strftime('%H:%M')
        lines.append(f"- **工作时间**: {start_str} - {end_str}\n")
    
    lines.append(f"- **工作类型分布**:\n")
    for commit_type, count in sorted(commit_types.items(), key=lambda x: x[1], reverse=True):
        emoji = analyze_commit_type('')[1] if commit_type == '其他' else commits_by_type[commit_type][0]['commit'].message
        type_emoji = analyze_commit_type(commits_by_type[commit_type][0]['commit'].message)[1] if commits_by_type[commit_type] else '📌'
        lines.append(f"  - {type_emoji} {commit_type}: {count} 次\n")
    
    lines.append("\n---\n\n")
    
    # 按项目详细工作内容
    lines.append("## 📦 工作详情\n\n")
    
    for project_path in sorted(project_commits.keys()):
        project_info = project_commits[project_path]
        project = project_info['project']
        commits = project_info['commits']
        
        lines.append(f"### {project.name} ({project_path})\n")
        lines.append(f"**项目链接**: [{project.web_url}]({project.web_url})\n")
        lines.append(f"**提交数**: {len(commits)} 次\n")
        
        # 工作类型统计
        if project_info['types']:
            type_summary_parts = []
            for t, c in sorted(project_info['types'].items(), key=lambda x: x[1], reverse=True):
                # 获取该类型的 emoji
                type_emoji = analyze_commit_type('')[1]  # 默认
                for item in commits:
                    if item['type'] == t:
                        type_emoji = item['emoji']
                        break
                type_summary_parts.append(f"{type_emoji} {t}: {c}次")
            lines.append(f"**工作类型**: {', '.join(type_summary_parts)}\n")
        
        lines.append("\n**提交记录**:\n\n")
        
        for idx, item in enumerate(commits, 1):
            commit = item['commit']
            commit_type = item['type']
            emoji = item['emoji']
            # 显示完整日期+时间，便于跨多天的日报查看
            time_str = item['time'].strftime('%Y-%m-%d %H:%M')
            
            # 获取详细commit信息
            try:
                details = get_commit_details(project, commit)
                short_message = details['short_message']
                full_message = details['full_message']
                stats = details['stats']
                changed_files = details['changed_files']
            except Exception as e:
                logger.debug(f"获取commit详情失败: {str(e)}")
                short_message = commit.message.split('\n')[0] if commit.message else ''
                full_message = commit.message or ''
                stats = None
                changed_files = []
            
            commit_id = commit.id[:8]
            commit_url = getattr(commit, 'web_url', '')
            
            lines.append(f"{idx}. **{emoji} [{commit_type}]** [{commit_id}]({commit_url}) {short_message}\n")
            lines.append(f"   - 时间: {time_str}\n")
            
            # 显示完整的commit message（如果有多行）
            if full_message and '\n' in full_message:
                # 过滤 IDE 自动追加的元数据行（如 Made-with: Cursor）
                filtered_lines = [
                    l for l in full_message.split('\n')
                    if not l.strip().lower().startswith('made-with:')
                ]
                filtered_message = '\n'.join(filtered_lines).strip()
                if filtered_message and '\n' in filtered_message:
                    indented_message = '\n   '.join(filtered_message.split('\n'))
                    lines.append(f"   - 完整提交信息:\n   ```\n   {indented_message}\n   ```\n")
            
            # 显示代码行数统计
            if stats:
                lines.append(f"   - 代码变更: +{stats.get('additions', 0)} -{stats.get('deletions', 0)} (总计: {stats.get('total', 0)} 行)\n")
            elif hasattr(commit, 'stats') and commit.stats:
                try:
                    commit_stats = commit.stats
                    if isinstance(commit_stats, dict):
                        lines.append(f"   - 代码变更: +{commit_stats.get('additions', 0)} -{commit_stats.get('deletions', 0)}\n")
                except:
                    pass
            
            # 显示文件变更列表（最多显示3个）
            if changed_files:
                lines.append(f"   - 变更文件 ({len(changed_files)} 个): ")
                file_paths = []
                for file_info in changed_files[:3]:
                    file_path = file_info.get('new_path') or file_info.get('old_path') or file_info.get('path', '')
                    if file_path:
                        file_paths.append(f"`{file_path}`")
                lines.append(', '.join(file_paths))
                if len(changed_files) > 3:
                    lines.append(f" 等 {len(changed_files)} 个文件")
                lines.append("\n")
        
        lines.append("\n---\n\n")
    
    # 工时分配表
    try:
        work_hours_data = calculate_work_hours(all_results, since_date, until_date, branch=branch)

        # 单日报告: 显示该日的详细工时分配表
        if since_date and until_date and since_date == until_date:
            if since_date in work_hours_data:
                lines.append(format_work_hours_table(work_hours_data[since_date]))
                lines.append("---\n\n")
        # 区间报告: 显示工时汇总
        else:
            if work_hours_data:
                lines.append("## ⏱️ 工时分配汇总\n\n")

                # 计算工作天数和总工时
                work_days = len(work_hours_data)
                total_hours = sum(data['total_hours'] for data in work_hours_data.values())

                lines.append(f"- **工作天数**: {work_days} 天\n")
                lines.append(f"- **总工时**: {total_hours:.1f} 小时\n")
                if work_days > 0:
                    lines.append(f"- **日均工时**: {total_hours / work_days:.1f} 小时\n")

                # 按项目汇总工时
                project_hours = {}
                for date_data in work_hours_data.values():
                    for project_path, project_data in date_data['projects'].items():
                        project_name = project_data['project_name']
                        if project_name not in project_hours:
                            project_hours[project_name] = 0
                        project_hours[project_name] += project_data['total_hours']

                if project_hours:
                    lines.append(f"\n**按项目分布**:\n\n")
                    lines.append("| 项目名称 | 总工时(小时) | 占比 |\n")
                    lines.append("|---------|------------|-----|\n")

                    for project_name, hours in sorted(project_hours.items(), key=lambda x: x[1], reverse=True):
                        percentage = (hours / total_hours * 100) if total_hours > 0 else 0
                        lines.append(f"| {project_name} | {hours:.1f} | {percentage:.1f}% |\n")

                lines.append("\n---\n\n")

    except Exception as e:
        logger.warning(f"生成工时分配表时出错: {str(e)}")

    # 总结
    lines.append("## 📝 工作总结\n\n")

    # 根据日期范围选择合适的文字
    if since_date and until_date and since_date == until_date:
        summary_text = "本日"
    else:
        summary_text = "本期"

    lines.append(f"{summary_text}共完成 {total_commits} 次提交，涉及 {total_projects} 个项目。")
    
    if commit_types:
        main_work = max(commit_types.items(), key=lambda x: x[1])
        lines.append(f"主要工作类型为 **{main_work[0]}**（{main_work[1]} 次）。")
    
    lines.append("\n")
    lines.append("\n---\n\n")
    
    # 添加代码统计信息
    try:
        code_stats = calculate_code_statistics(all_results, since_date, until_date)

        lines.append("## 📊 代码统计\n\n")
        if code_stats['commits_with_stats'] > 0:
            lines.append(f"- **总新增行数**: {code_stats['total_additions']:,}\n")
            lines.append(f"- **总删除行数**: {code_stats['total_deletions']:,}\n")
            lines.append(f"- **净增行数**: {code_stats['net_lines']:,}\n")
            lines.append(f"- **平均每次提交代码行数**: {code_stats['avg_lines_per_commit']}\n")
        else:
            lines.append("- **代码行数统计**: 暂不可用（需要API权限）\n")
        lines.append("\n")
    except Exception as e:
        logger.warning(f"生成代码统计信息时出错: {str(e)}")
        lines.append("## 📊 代码统计\n\n")
        lines.append("- **代码统计**: 生成时出现错误，请检查数据\n\n")
    
    return ''.join(lines)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='从 GitLab 仓库获取提交者每天的代码提交，生成 Markdown 格式日志',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 基本用法：指定仓库、分支、提交者（输出文件名自动使用当天日期）
  python git2logs.py --repo http://gitlab.example.com/group/project.git --branch main --author "MIZUKI" --token YOUR_TOKEN
  
  # 获取今天的提交（自动使用今天日期作为文件名前缀）
  python git2logs.py --repo http://gitlab.example.com/group/project.git --branch develop --author "MIZUKI" --today --token YOUR_TOKEN
  
  # 自动扫描所有项目，查找指定提交者今天的提交
  python git2logs.py --scan-all --gitlab-url http://gitlab.example.com --author "MIZUKI" --today --token YOUR_TOKEN
  
  # 自动扫描所有项目，指定分支和日期范围
  python git2logs.py --scan-all --gitlab-url http://gitlab.example.com --branch master --author "MIZUKI" --since 2024-01-01 --until 2024-12-31 --token YOUR_TOKEN
  
  # 手动指定输出文件
  python git2logs.py --repo group/project --branch main --author "John Doe" --output commits.md
        """
    )
    
    parser.add_argument(
        '--repo',
        help='GitLab 仓库地址或路径（例如：https://gitlab.com/group/project 或 group/project）。如果使用 --scan-all，则不需要此参数'
    )
    
    parser.add_argument(
        '--author',
        required=True,
        help='提交者姓名或邮箱'
    )
    
    parser.add_argument(
        '--scan-all',
        action='store_true',
        help='自动扫描所有有权限访问的项目，查找指定提交者的提交（需要提供 GitLab URL 和访问令牌）'
    )
    
    parser.add_argument(
        '--token',
        help='GitLab 访问令牌（私有仓库需要，也可通过环境变量 GITLAB_TOKEN 设置）'
    )
    
    parser.add_argument(
        '--gitlab-url',
        default='https://gitlab.com',
        help='GitLab 实例 URL（默认：https://gitlab.com）'
    )
    
    parser.add_argument(
        '--since',
        help='起始日期（格式：YYYY-MM-DD）'
    )
    
    parser.add_argument(
        '--until',
        help='结束日期（格式：YYYY-MM-DD）'
    )
    
    parser.add_argument(
        '--branch',
        help='指定分支名称（默认查询所有分支）'
    )
    
    parser.add_argument(
        '--today',
        action='store_true',
        help='仅获取今天的提交（自动设置日期范围为今天）'
    )
    
    parser.add_argument(
        '--output',
        '-o',
        help='输出文件路径（默认：使用当天日期作为文件名前缀，格式：YYYY-MM-DD_commits.md）'
    )
    
    parser.add_argument(
        '--daily-report',
        action='store_true',
        help='生成开发日报格式（更详细的工作分析和分类）'
    )

    parser.add_argument(
        '--statistics',
        action='store_true',
        help='生成统计报告格式（包含代码行数统计）'
    )

    parser.add_argument(
        '--work-hours',
        action='store_true',
        help='生成工时分配报告（详细的工时统计和任务分配）'
    )

    parser.add_argument(
        '--daily-hours',
        type=float,
        default=8.0,
        help='每日标准工时（默认：8.0小时）'
    )
    
    args = parser.parse_args()
    
    # 验证参数
    if args.scan_all and args.repo:
        logger.error("--scan-all 和 --repo 不能同时使用")
        sys.exit(1)
    
    if not args.scan_all and not args.repo:
        logger.error("必须提供 --repo 或使用 --scan-all")
        sys.exit(1)
    
    # 如果指定了 --today，自动设置日期范围为今天
    if args.today:
        today = datetime.now().strftime('%Y-%m-%d')
        args.since = today
        args.until = today
        logger.info(f"已设置日期范围为今天: {today}")
    
    try:
        # 获取访问令牌（优先使用命令行参数，其次使用环境变量）
        token = args.token or None
        if not token:
            token = os.environ.get('GITLAB_TOKEN')
        
        if not token:
            logger.error("必须提供访问令牌（--token 或环境变量 GITLAB_TOKEN）")
            sys.exit(1)
        
        # 确定 GitLab URL
        gitlab_url = args.gitlab_url
        
        if args.scan_all:
            # 扫描所有项目模式
            if not gitlab_url or gitlab_url == 'https://gitlab.com':
                logger.error("使用 --scan-all 时必须指定 --gitlab-url")
                sys.exit(1)
            
            logger.info(f"使用自动扫描模式，GitLab 实例: {gitlab_url}")
            
            # 创建 GitLab 客户端
            gl = create_gitlab_client(gitlab_url, token)
            
            # 扫描所有项目
            all_results = scan_all_projects(
                gl,
                args.author,
                since_date=args.since,
                until_date=args.until,
                branch=args.branch
            )
            
            if not all_results:
                logger.warning(f"未在任何项目中找到提交者 '{args.author}' 的提交记录")
                sys.exit(0)
            
            # 生成 Markdown 日志
            if args.statistics:
                markdown_content = generate_statistics_report(
                    all_results,
                    args.author,
                    since_date=args.since,
                    until_date=args.until
                )
                # 确定输出文件名
                if args.output:
                    output_file = args.output
                    # 检查是否是目录，如果是目录则自动生成文件名
                    if os.path.isdir(output_file):
                        today = datetime.now().strftime('%Y-%m-%d')
                        branch_suffix = f"_{args.branch}" if args.branch else ""
                        filename = f"{today}_statistics{branch_suffix}.md"
                        output_file = os.path.join(output_file, filename)
                        logger.info(f"输出路径是目录，自动生成文件名: {output_file}")
                    # 如果输出文件没有扩展名，自动添加 .md
                    elif not os.path.splitext(output_file)[1]:
                        output_file = output_file + '.md'
                        logger.info(f"输出文件无扩展名，自动添加 .md: {output_file}")
                else:
                    today = datetime.now().strftime('%Y-%m-%d')
                    branch_suffix = f"_{args.branch}" if args.branch else ""
                    output_file = f"{today}_statistics{branch_suffix}.md"
            elif args.daily_report:
                markdown_content = generate_daily_report(
                    all_results,
                    args.author,
                    since_date=args.since,
                    until_date=args.until,
                    branch=args.branch
                )
                # 确定输出文件名
                if args.output:
                    output_file = args.output
                    # 检查是否是目录，如果是目录则自动生成文件名
                    if os.path.isdir(output_file):
                        today = datetime.now().strftime('%Y-%m-%d')
                        branch_suffix = f"_{args.branch}" if args.branch else ""
                        filename = f"{today}_daily_report{branch_suffix}.md"
                        output_file = os.path.join(output_file, filename)
                        logger.info(f"输出路径是目录，自动生成文件名: {output_file}")
                    # 如果输出文件没有扩展名，自动添加 .md
                    elif not os.path.splitext(output_file)[1]:
                        output_file = output_file + '.md'
                        logger.info(f"输出文件无扩展名，自动添加 .md: {output_file}")
                else:
                    today = datetime.now().strftime('%Y-%m-%d')
                    branch_suffix = f"_{args.branch}" if args.branch else ""
                    output_file = f"{today}_daily_report{branch_suffix}.md"
            elif args.work_hours:
                markdown_content = generate_work_hours_report(
                    all_results,
                    args.author,
                    since_date=args.since,
                    until_date=args.until,
                    daily_hours=args.daily_hours,
                    branch=args.branch
                )
                # 确定输出文件名
                if args.output:
                    output_file = args.output
                    # 检查是否是目录，如果是目录则自动生成文件名
                    if os.path.isdir(output_file):
                        today = datetime.now().strftime('%Y-%m-%d')
                        branch_suffix = f"_{args.branch}" if args.branch else ""
                        filename = f"{today}_work_hours{branch_suffix}.md"
                        output_file = os.path.join(output_file, filename)
                        logger.info(f"输出路径是目录，自动生成文件名: {output_file}")
                    # 如果输出文件没有扩展名，自动添加 .md
                    elif not os.path.splitext(output_file)[1]:
                        output_file = output_file + '.md'
                        logger.info(f"输出文件无扩展名，自动添加 .md: {output_file}")
                else:
                    today = datetime.now().strftime('%Y-%m-%d')
                    branch_suffix = f"_{args.branch}" if args.branch else ""
                    output_file = f"{today}_work_hours{branch_suffix}.md"
            else:
                markdown_content = generate_multi_project_markdown(
                    all_results,
                    args.author,
                    since_date=args.since,
                    until_date=args.until
                )
                # 确定输出文件名
                if args.output:
                    output_file = args.output
                    # 检查是否是目录，如果是目录则自动生成文件名
                    if os.path.isdir(output_file):
                        today = datetime.now().strftime('%Y-%m-%d')
                        branch_suffix = f"_{args.branch}" if args.branch else ""
                        filename = f"{today}_all_projects{branch_suffix}.md"
                        output_file = os.path.join(output_file, filename)
                        logger.info(f"输出路径是目录，自动生成文件名: {output_file}")
                    # 如果输出文件没有扩展名，自动添加 .md
                    elif not os.path.splitext(output_file)[1]:
                        output_file = output_file + '.md'
                        logger.info(f"输出文件无扩展名，自动添加 .md: {output_file}")
                else:
                    today = datetime.now().strftime('%Y-%m-%d')
                    branch_suffix = f"_{args.branch}" if args.branch else ""
                    output_file = f"{today}_all_projects{branch_suffix}.md"
        
        else:
            # 单项目模式
            # 如果仓库 URL 是完整 URL，尝试从中提取 GitLab URL
            extracted_url = extract_gitlab_url(args.repo)
            if extracted_url:
                gitlab_url = extracted_url
                logger.info(f"从仓库 URL 提取 GitLab 实例: {gitlab_url}")
            
            # 创建 GitLab 客户端
            gl = create_gitlab_client(gitlab_url, token)
            
            # 解析项目标识符
            project_id = parse_project_identifier(args.repo)
            logger.info(f"项目标识符: {project_id}")
            
            # 获取项目
            try:
                project = gl.projects.get(project_id)
                logger.info(f"成功获取项目: {project.name}")
            except Exception as e:
                logger.error(f"获取项目失败: {str(e)}")
                logger.error("请检查项目路径是否正确，以及是否有访问权限")
                sys.exit(1)
            
            # 获取提交记录
            commits = get_commits_by_author(
                project,
                args.author,
                since_date=args.since,
                until_date=args.until,
                branch=args.branch
            )
            
            if not commits:
                logger.warning(f"未找到提交者 '{args.author}' 的提交记录")
                sys.exit(0)
            
            # 按日期分组
            grouped_commits = group_commits_by_date(commits)
            
            # 生成 Markdown 日志
            markdown_content = generate_markdown_log(
                grouped_commits,
                args.author,
                repo_name=project.name,
                project=project
            )
            
            # 确定输出文件名
            if args.output:
                output_file = args.output
                # 检查是否是目录，如果是目录则自动生成文件名
                if os.path.isdir(output_file):
                    today = datetime.now().strftime('%Y-%m-%d')
                    branch_suffix = f"_{args.branch}" if args.branch else ""
                    if args.daily_report:
                        filename = f"{today}_daily_report{branch_suffix}.md"
                    else:
                        filename = f"{today}_all_projects{branch_suffix}.md"
                    output_file = os.path.join(output_file, filename)
                    logger.info(f"输出路径是目录，自动生成文件名: {output_file}")
                # 如果输出文件没有扩展名，自动添加 .md
                elif not os.path.splitext(output_file)[1]:
                    output_file = output_file + '.md'
                    logger.info(f"输出文件无扩展名，自动添加 .md: {output_file}")
            else:
                # 如果未指定输出文件，使用当天日期作为文件名前缀
                today = datetime.now().strftime('%Y-%m-%d')
                branch_suffix = f"_{args.branch}" if args.branch else ""
                output_file = f"{today}_commits{branch_suffix}.md"
        
        # 输出结果
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        logger.info(f"日志已保存到: {output_file}")
    
    except KeyboardInterrupt:
        logger.info("用户中断操作")
        sys.exit(1)
    except Exception as e:
        logger.error(f"程序执行失败: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()
