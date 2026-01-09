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
        
        for idx, branch_obj in enumerate(branches, 1):
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
                                        dc_date_obj = datetime.fromisoformat(dc_date.replace('Z', '+00:00'))
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
                            logger.warning(f"调试：分支 '{branch_obj.name}' 在指定日期范围内（{since_date or '全部'} 至 {until_date or '全部'}）没有任何提交（不指定作者）")
                            # 如果指定了日期范围但没有找到提交，再查询一次不限制日期的，看看最近有哪些提交
                            if since_date or until_date:
                                logger.info(f"调试：查询分支 '{branch_obj.name}' 最近的提交（不限制日期范围）：")
                                try:
                                    debug_params_no_date = {'ref_name': branch_obj.name, 'per_page': 10}
                                    debug_commits_no_date = project.commits.list(**debug_params_no_date)
                                    if debug_commits_no_date:
                                        logger.info(f"  找到 {len(debug_commits_no_date)} 条最近的提交：")
                                        for dc_idx, dc in enumerate(debug_commits_no_date[:5], 1):
                                            dc_author = getattr(dc, 'author_name', 'N/A')
                                            dc_email = getattr(dc, 'author_email', 'N/A')
                                            dc_date = getattr(dc, 'committed_date', 'N/A')
                                            # 格式化日期
                                            if isinstance(dc_date, str):
                                                try:
                                                    from datetime import datetime
                                                    dc_date_obj = datetime.fromisoformat(dc_date.replace('Z', '+00:00'))
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
                                            logger.info(f"    提交 {dc_idx}: 作者='{dc_author}' 邮箱='{dc_email}' 日期={dc_date_str} (UTC日期={dc_date_local}){marker}")
                                        logger.info(f"  提示：如果看到匹配的提交，请检查其 UTC 日期是否在查询范围内")
                                    else:
                                        logger.warning(f"  该分支没有任何提交记录")
                                except Exception as e:
                                    logger.debug(f"查询最近提交失败: {e}")
                            else:
                                logger.warning(f"提示：如果确定有提交，可能是时区问题。GitLab 使用 UTC 时间，请检查提交的实际 UTC 日期")
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
                    logger.info(f"[{idx}/{len(branches)}] 分支 '{branch_obj.name}': 找到 {len(branch_commits)} 条提交")
                    all_commits.extend(branch_commits)
                else:
                    # 调试：如果没找到提交，记录一下（仅在调试模式下）
                    logger.debug(f"[{idx}/{len(branches)}] 分支 '{branch_obj.name}': 未找到提交")
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
        
        logger.info(f"共获取到 {len(unique_commits)} 条提交记录（遍历了 {len(branches)} 个分支）")
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
            date_obj = datetime.fromisoformat(commit_date.replace('Z', '+00:00'))
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


def scan_all_projects(gl, author_name, since_date=None, until_date=None, branch=None):
    """
    扫描所有项目，查找指定提交者的提交
    
    Args:
        gl: GitLab 客户端实例
        author_name: 提交者姓名或邮箱
        since_date: 起始日期（可选）
        until_date: 结束日期（可选）
        branch: 分支名称（可选）
    
    Returns:
        dict: 按项目分组的提交字典，格式：{project_path: {'project': project, 'commits': commits}}
    """
    logger.info(f"开始扫描所有项目，查找提交者 '{author_name}' 的提交...")
    
    # 获取所有项目
    projects = get_all_projects(gl)
    
    results = {}
    total_commits = 0
    
    for idx, project in enumerate(projects, 1):
        project_path = project.path_with_namespace
        logger.info(f"[{idx}/{len(projects)}] 正在扫描项目: {project_path}")
        
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
                results[project_path] = {
                    'project': project,
                    'commits': commits
                }
                total_commits += len(commits)
                logger.info(f"  ✓ 找到 {len(commits)} 条提交")
            # 不输出未找到提交的信息，减少日志噪音
        
        except Exception as e:
            # 只记录重要错误，忽略权限不足等常见错误
            error_msg = str(e)
            if '403' in error_msg or '401' in error_msg or 'Not Found' in error_msg:
                logger.debug(f"  跳过项目 {project_path}（无权限或不存在）")
            else:
                logger.warning(f"  扫描项目 {project_path} 时出错: {error_msg}")
            continue
    
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
        date_obj = datetime.strptime(date, '%Y-%m-%d')
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
                time_obj = datetime.fromisoformat(commit_time.replace('Z', '+00:00'))
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
                date_obj = datetime.fromisoformat(commit_date.replace('Z', '+00:00'))
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
        date_obj = datetime.strptime(date, '%Y-%m-%d')
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
                    time_obj = datetime.fromisoformat(commit_time.replace('Z', '+00:00'))
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


def calculate_scores(all_results, since_date=None, until_date=None):
    """
    计算5个维度的评分（满分100分）
    
    Args:
        all_results: 按项目分组的提交字典
        since_date: 起始日期（可选，格式：YYYY-MM-DD）
        until_date: 结束日期（可选，格式：YYYY-MM-DD）
    
    Returns:
        dict: 包含5个维度评分的字典
    """
    from collections import defaultdict
    import statistics
    from datetime import datetime, timedelta
    
    # 收集所有提交
    all_commits = []
    all_dates = set()
    projects_set = set()
    
    # 修复类关键词
    fix_keywords = ['fix', 'bug', '修复', '报错', '解决', 'error', 'issue', 'bugfix', 'hotfix']
    # 功能类关键词
    feat_keywords = ['feat', 'add', '开发', '新增', 'feature', 'implement', '实现', '开发', '添加']
    
    fix_commits = 0
    feat_commits = 0
    
    for project_path, result in all_results.items():
        projects_set.add(project_path)
        commits = result['commits']
        
        for commit in commits:
            all_commits.append(commit)
            
            # 解析日期
            commit_date = commit.committed_date
            if isinstance(commit_date, str):
                date_obj = datetime.fromisoformat(commit_date.replace('Z', '+00:00'))
            else:
                date_obj = commit_date
            date_str = date_obj.strftime('%Y-%m-%d')
            all_dates.add(date_str)
            
            # 检查提交类型
            commit_message = commit.message.lower()
            is_fix = any(keyword in commit_message for keyword in fix_keywords)
            is_feat = any(keyword in commit_message for keyword in feat_keywords)
            
            if is_fix:
                fix_commits += 1
            if is_feat:
                feat_commits += 1
    
    total_commits = len(all_commits)
    active_days = len(all_dates)
    
    # 确定日期范围
    if since_date and until_date:
        try:
            start_date = datetime.strptime(since_date, '%Y-%m-%d')
            end_date = datetime.strptime(until_date, '%Y-%m-%d')
        except ValueError:
            # 如果日期格式错误，使用实际提交的日期范围
            if all_dates:
                sorted_dates = sorted(all_dates)
                start_date = datetime.strptime(sorted_dates[0], '%Y-%m-%d')
                end_date = datetime.strptime(sorted_dates[-1], '%Y-%m-%d')
            else:
                start_date = datetime.now()
                end_date = datetime.now()
    elif all_dates:
        sorted_dates = sorted(all_dates)
        start_date = datetime.strptime(sorted_dates[0], '%Y-%m-%d')
        end_date = datetime.strptime(sorted_dates[-1], '%Y-%m-%d')
    else:
        start_date = datetime.now()
        end_date = datetime.now()
    
    total_days = (end_date - start_date).days + 1 if (end_date - start_date).days >= 0 else 1
    
    # 1. 勤奋度 (Diligence) - 满分100
    # 活跃天数占比：活跃天数 / 总天数 * 50分
    active_days_score = min(50, (active_days / total_days) * 50) if total_days > 0 else 0
    
    # 提交频率：(总提交数 / 总天数) / 基准频率 * 50分（基准频率：1次/天）
    base_frequency = 1.0
    actual_frequency = total_commits / total_days if total_days > 0 else 0
    frequency_score = min(50, (actual_frequency / base_frequency) * 50)
    
    diligence_score = min(100, active_days_score + frequency_score)
    
    # 2. 稳定性 (Stability) - 满分100
    # 计算每月提交数
    monthly_commits = defaultdict(int)
    for commit in all_commits:
        commit_date = commit.committed_date
        if isinstance(commit_date, str):
            date_obj = datetime.fromisoformat(commit_date.replace('Z', '+00:00'))
        else:
            date_obj = commit_date
        month_key = date_obj.strftime('%Y-%m')
        monthly_commits[month_key] += 1
    
    cv = 0
    mean_commits = 0
    
    if len(monthly_commits) > 0:
        commit_counts = list(monthly_commits.values())
        if len(commit_counts) > 1:
            mean_commits = statistics.mean(commit_counts)
            if mean_commits > 0:
                std_commits = statistics.stdev(commit_counts)
                cv = std_commits / mean_commits  # 离散系数
                base_cv = 1.0
                stability_score = 100 * (1 - min(1, cv / base_cv))
            else:
                stability_score = 0
        else:
            stability_score = 100  # 只有一个月，认为非常稳定
    else:
        stability_score = 0
    
    # 如果每月都有提交，给予额外加分（最多10分）
    if since_date and until_date:
        try:
            start = datetime.strptime(since_date, '%Y-%m-%d')
            end = datetime.strptime(until_date, '%Y-%m-%d')
            expected_months = set()
            current = start.replace(day=1)
            while current <= end:
                expected_months.add(current.strftime('%Y-%m'))
                if current.month == 12:
                    current = current.replace(year=current.year + 1, month=1)
                else:
                    current = current.replace(month=current.month + 1)
            
            actual_months = set(monthly_commits.keys())
            if actual_months == expected_months:
                stability_score = min(100, stability_score + 10)
        except ValueError:
            pass
    
    stability_score = max(0, min(100, stability_score))
    
    # 3. 解决问题能力 (Problem Solving) - 满分100
    problem_solving_score = (fix_commits / total_commits * 100) if total_commits > 0 else 0
    problem_solving_score = max(0, min(100, problem_solving_score))
    
    # 4. 功能创新力 (Feature/Innovation) - 满分100
    feature_score = (feat_commits / total_commits * 100) if total_commits > 0 else 0
    feature_score = max(0, min(100, feature_score))
    
    # 5. 多线作战能力 (Versatility) - 满分100
    project_count = len(projects_set)
    project_score = min(50, project_count * 10)  # 最多50分
    
    time_span_days = (end_date - start_date).days + 1
    time_span_score = min(50, (time_span_days / 365) * 50)  # 最多50分
    
    versatility_score = project_score + time_span_score
    versatility_score = max(0, min(100, versatility_score))
    
    # 计算总体评分（平均值）
    overall_score = (diligence_score + stability_score + problem_solving_score + 
                     feature_score + versatility_score) / 5
    
    # 生成详细分析文本
    def generate_analysis_text():
        analysis = {}
        
        # 代码质量评估（基于提交频率、稳定性、代码行数等）
        code_quality_score = (diligence_score * 0.3 + stability_score * 0.3 + 
                             min(100, actual_frequency * 20) * 0.2 + 
                             min(100, project_count * 10) * 0.2)
        code_quality_analysis = f"基于提交频率({actual_frequency:.2f}次/天)、活跃天数({active_days}天)和项目参与度({project_count}个项目)的综合评估。"
        if actual_frequency > 2:
            code_quality_analysis += "提交频率较高，显示出良好的开发习惯。"
        if active_days / total_days > 0.5:
            code_quality_analysis += "活跃天数占比高，工作持续性良好。"
        
        analysis['code_quality'] = {
            'score': round(code_quality_score, 2),
            'analysis': code_quality_analysis,
            'strengths': [
                f"活跃天数: {active_days} 天" if active_days > 0 else "需要提高活跃度",
                f"提交频率: {actual_frequency:.2f} 次/天" if actual_frequency > 0 else "提交频率较低",
                f"涉及项目: {project_count} 个" if project_count > 0 else "项目参与度较低"
            ],
            'improvements': [
                "建议保持稳定的提交频率" if actual_frequency < 1 else "提交频率良好",
                "建议提高代码提交的持续性" if active_days / total_days < 0.3 else "工作持续性良好"
            ]
        }
        
        # 工作模式分析
        work_pattern_analysis = f"工作模式分析：活跃天数占比 {active_days/total_days*100:.1f}%，"
        if len(monthly_commits) > 0:
            work_pattern_analysis += f"涉及 {len(monthly_commits)} 个月，平均每月 {mean_commits:.1f} 次提交。"
        if cv < 0.5:
            work_pattern_analysis += "提交分布非常均匀，工作节奏稳定。"
        elif cv < 1.0:
            work_pattern_analysis += "提交分布较为均匀，工作节奏较稳定。"
        else:
            work_pattern_analysis += "提交分布波动较大，建议保持更稳定的工作节奏。"
        
        analysis['work_pattern'] = {
            'score': round(stability_score, 2),
            'analysis': work_pattern_analysis,
            'strengths': [
                f"稳定性系数: {cv:.3f}" if cv > 0 else "提交非常稳定",
                f"月度分布: {len(monthly_commits)} 个月有提交" if len(monthly_commits) > 0 else "需要提高月度分布"
            ],
            'improvements': [
                "建议保持每月都有提交记录" if len(monthly_commits) < 3 else "月度分布良好",
                "建议减少提交数量的波动" if cv > 1.0 else "提交分布稳定"
            ]
        }
        
        # 技术栈评估（基于项目数量和提交类型）
        tech_stack_analysis = f"技术栈评估：参与 {project_count} 个项目，"
        if project_count > 5:
            tech_stack_analysis += "项目参与度高，显示出良好的多项目协作能力。"
        elif project_count > 2:
            tech_stack_analysis += "项目参与度中等，建议扩展项目范围。"
        else:
            tech_stack_analysis += "项目参与度较低，建议增加项目参与。"
        
        analysis['tech_stack'] = {
            'score': round(min(100, project_count * 15 + min(50, time_span_days / 365 * 50)), 2),
            'analysis': tech_stack_analysis,
            'strengths': [
                f"项目数量: {project_count} 个",
                f"时间跨度: {time_span_days} 天"
            ],
            'improvements': [
                "建议参与更多不同类型的项目" if project_count < 3 else "项目参与度良好",
                "建议保持长期的项目参与" if time_span_days < 90 else "项目参与时间充足"
            ]
        }
        
        # 问题解决能力
        problem_solving_analysis = f"问题解决能力：修复类提交占比 {fix_commits/total_commits*100:.1f}% ({fix_commits}/{total_commits})。"
        if fix_commits / total_commits > 0.3:
            problem_solving_analysis += "修复类提交占比较高，显示出良好的问题解决能力。"
        elif fix_commits / total_commits > 0.1:
            problem_solving_analysis += "修复类提交占比中等，问题解决能力良好。"
        else:
            problem_solving_analysis += "修复类提交占比较低，建议提高问题解决能力。"
        
        analysis['problem_solving'] = {
            'score': round(problem_solving_score, 2),
            'analysis': problem_solving_analysis,
            'strengths': [
                f"修复类提交: {fix_commits} 次",
                f"修复占比: {fix_commits/total_commits*100:.1f}%" if total_commits > 0 else "无修复记录"
            ],
            'improvements': [
                "建议提高bug修复的及时性" if fix_commits / total_commits < 0.1 else "问题解决能力良好",
                "建议记录更详细的修复信息" if fix_commits > 0 else "建议增加问题修复的提交"
            ]
        }
        
        # 创新性分析
        innovation_analysis = f"创新性分析：功能开发类提交占比 {feat_commits/total_commits*100:.1f}% ({feat_commits}/{total_commits})。"
        if feat_commits / total_commits > 0.4:
            innovation_analysis += "功能开发类提交占比较高，显示出良好的创新能力和功能开发能力。"
        elif feat_commits / total_commits > 0.2:
            innovation_analysis += "功能开发类提交占比中等，创新能力良好。"
        else:
            innovation_analysis += "功能开发类提交占比较低，建议增加新功能开发。"
        
        analysis['innovation'] = {
            'score': round(feature_score, 2),
            'analysis': innovation_analysis,
            'strengths': [
                f"功能开发提交: {feat_commits} 次",
                f"功能占比: {feat_commits/total_commits*100:.1f}%" if total_commits > 0 else "无功能开发记录"
            ],
            'improvements': [
                "建议增加新功能的开发" if feat_commits / total_commits < 0.2 else "功能开发能力良好",
                "建议记录更详细的功能开发信息" if feat_commits > 0 else "建议增加功能开发的提交"
            ]
        }
        
        # 团队协作
        collaboration_analysis = f"团队协作：同时维护 {project_count} 个项目，时间跨度 {time_span_days} 天。"
        if project_count > 3 and time_span_days > 180:
            collaboration_analysis += "多项目协作能力强，能够同时维护多个项目并保持长期参与。"
        elif project_count > 1:
            collaboration_analysis += "具备多项目协作能力，建议保持长期参与。"
        else:
            collaboration_analysis += "建议增加项目参与，提高团队协作能力。"
        
        analysis['collaboration'] = {
            'score': round(versatility_score, 2),
            'analysis': collaboration_analysis,
            'strengths': [
                f"项目数量: {project_count} 个",
                f"时间跨度: {time_span_days} 天",
                f"活跃天数: {active_days} 天"
            ],
            'improvements': [
                "建议参与更多项目" if project_count < 2 else "项目参与度良好",
                "建议保持长期的项目参与" if time_span_days < 90 else "项目参与时间充足"
            ]
        }
        
        return analysis
    
    detailed_analysis = generate_analysis_text()
    
    return {
        'diligence': {
            'score': round(diligence_score, 2),
            'active_days': active_days,
            'total_days': total_days,
            'total_commits': total_commits,
            'frequency': round(actual_frequency, 2)
        },
        'stability': {
            'score': round(stability_score, 2),
            'monthly_commits': dict(monthly_commits),
            'cv': round(cv, 3) if len(monthly_commits) > 1 and mean_commits > 0 else 0
        },
        'problem_solving': {
            'score': round(problem_solving_score, 2),
            'fix_commits': fix_commits,
            'total_commits': total_commits,
            'ratio': round(fix_commits / total_commits, 3) if total_commits > 0 else 0
        },
        'feature_innovation': {
            'score': round(feature_score, 2),
            'feat_commits': feat_commits,
            'total_commits': total_commits,
            'ratio': round(feat_commits / total_commits, 3) if total_commits > 0 else 0
        },
        'versatility': {
            'score': round(versatility_score, 2),
            'project_count': project_count,
            'time_span_days': time_span_days
        },
        'overall': round(overall_score, 2),
        'detailed_analysis': detailed_analysis  # 新增详细分析
    }


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
    
    # 计算评分
    try:
        logger.info("正在计算多维度评分...")
        scores = calculate_scores(all_results, since_date, until_date)
        logger.info("多维度评分计算完成")
    except Exception as e:
        logger.error(f"计算评分时出错: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise  # 评分是核心功能，如果失败应该抛出异常
    
    # 评分详情
    lines.append("## 🎯 多维度评分\n\n")
    lines.append(f"**总体评分**: {scores['overall']:.2f} / 100\n\n")
    
    # 勤奋度
    lines.append(f"### 1. 勤奋度 (Diligence): {scores['diligence']['score']:.2f} / 100\n\n")
    lines.append(f"- 活跃天数: {scores['diligence']['active_days']} 天 / {scores['diligence']['total_days']} 天\n")
    lines.append(f"- 总提交数: {scores['diligence']['total_commits']} 次\n")
    lines.append(f"- 平均提交频率: {scores['diligence']['frequency']:.2f} 次/天\n")
    lines.append(f"- 评分说明: 基于活跃天数和提交频率综合评估\n\n")
    
    # 稳定性
    lines.append(f"### 2. 稳定性 (Stability): {scores['stability']['score']:.2f} / 100\n\n")
    lines.append(f"- 月度提交分布: {len(scores['stability']['monthly_commits'])} 个月有提交\n")
    if scores['stability']['cv'] > 0:
        lines.append(f"- 离散系数: {scores['stability']['cv']:.3f}\n")
    lines.append(f"- 评分说明: 基于每月提交分布的离散程度评估，离散系数越小越稳定\n\n")
    
    # 解决问题能力
    lines.append(f"### 3. 解决问题能力 (Problem Solving): {scores['problem_solving']['score']:.2f} / 100\n\n")
    lines.append(f"- 修复类提交: {scores['problem_solving']['fix_commits']} 次\n")
    lines.append(f"- 修复类提交占比: {scores['problem_solving']['ratio']:.1%}\n")
    lines.append(f"- 评分说明: 基于修复类提交（fix/bug/修复等关键词）的占比\n\n")
    
    # 功能创新力
    lines.append(f"### 4. 功能创新力 (Feature/Innovation): {scores['feature_innovation']['score']:.2f} / 100\n\n")
    lines.append(f"- 功能类提交: {scores['feature_innovation']['feat_commits']} 次\n")
    lines.append(f"- 功能类提交占比: {scores['feature_innovation']['ratio']:.1%}\n")
    lines.append(f"- 评分说明: 基于新功能开发提交（feat/add/新增等关键词）的占比\n\n")
    
    # 多线作战能力
    lines.append(f"### 5. 多线作战能力 (Versatility): {scores['versatility']['score']:.2f} / 100\n\n")
    lines.append(f"- 涉及项目数: {scores['versatility']['project_count']} 个\n")
    lines.append(f"- 时间跨度: {scores['versatility']['time_span_days']} 天\n")
    lines.append(f"- 评分说明: 基于同时维护的项目数量和时间跨度\n\n")
    
    lines.append("---\n\n")
    
    # 评分可视化（使用进度条）
    lines.append("## 📈 评分可视化\n\n")
    
    def progress_bar(score, max_score=100, length=20):
        """生成进度条"""
        filled = int(score / max_score * length)
        bar = '█' * filled + '░' * (length - filled)
        return f"`{bar}` {score:.1f}%"
    
    lines.append(f"- **勤奋度**: {progress_bar(scores['diligence']['score'])}\n")
    lines.append(f"- **稳定性**: {progress_bar(scores['stability']['score'])}\n")
    lines.append(f"- **解决问题能力**: {progress_bar(scores['problem_solving']['score'])}\n")
    lines.append(f"- **功能创新力**: {progress_bar(scores['feature_innovation']['score'])}\n")
    lines.append(f"- **多线作战能力**: {progress_bar(scores['versatility']['score'])}\n")
    lines.append(f"- **总体评分**: {progress_bar(scores['overall'])}\n")
    
    lines.append("\n---\n\n")
    
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
            - service: 'openai', 'anthropic' 或 'gemini'
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
                date_obj = datetime.fromisoformat(commit_date.replace('Z', '+00:00'))
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
    使用本地评价逻辑生成分析报告（当没有AI密钥时使用）
    
    Args:
        all_results: 按项目分组的提交字典
        author_name: 提交者姓名
        since_date: 起始日期（可选）
        until_date: 结束日期（可选）
    
    Returns:
        str: Markdown格式的本地分析报告
    """
    lines = []
    
    # 标题
    lines.append(f"# {author_name} - 本地智能分析报告\n")
    lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    lines.append(f"**提交者**: {author_name}\n")
    lines.append(f"**分析方式**: 📊 本地评价逻辑（基于统计数据和规则算法，无需AI服务）\n")
    
    if since_date and until_date:
        lines.append(f"**分析时间范围**: {since_date} 至 {until_date}\n")
    elif since_date:
        lines.append(f"**起始日期**: {since_date}\n")
    elif until_date:
        lines.append(f"**结束日期**: {until_date}\n")
    
    lines.append("\n---\n\n")
    
    # 计算评分和详细分析
    try:
        scores = calculate_scores(all_results, since_date, until_date)
        detailed_analysis = scores.get('detailed_analysis', {})
        
        # 执行摘要
        lines.append("## 📋 执行摘要\n\n")
        overall_score = scores.get('overall', 0)
        lines.append(f"**总体评分**: {overall_score:.1f} / 100\n\n")
        lines.append("**各维度评分**:\n")
        
        dimension_map = {
            'code_quality': '代码质量',
            'work_pattern': '工作模式',
            'tech_stack': '技术栈',
            'problem_solving': '问题解决能力',
            'innovation': '创新性',
            'collaboration': '团队协作'
        }
        
        for dim_key, dim_name in dimension_map.items():
            if dim_key in detailed_analysis:
                score = detailed_analysis[dim_key].get('score', 0)
                lines.append(f"- {dim_name}: {score:.1f} / 100\n")
        
        lines.append("\n---\n\n")
        
        # 详细分析
        lines.append("## 🔍 详细分析\n\n")
        
        for dim_key, dim_name in dimension_map.items():
            if dim_key in detailed_analysis:
                dim_data = detailed_analysis[dim_key]
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
        
        # 原始评分数据
        lines.append("## 📊 原始评分数据\n\n")
        lines.append(f"- **勤奋度**: {scores.get('diligence', {}).get('score', 0):.1f} / 100\n")
        lines.append(f"- **稳定性**: {scores.get('stability', {}).get('score', 0):.1f} / 100\n")
        lines.append(f"- **问题解决能力**: {scores.get('problem_solving', {}).get('score', 0):.1f} / 100\n")
        lines.append(f"- **功能创新力**: {scores.get('feature_innovation', {}).get('score', 0):.1f} / 100\n")
        lines.append(f"- **多线作战能力**: {scores.get('versatility', {}).get('score', 0):.1f} / 100\n")
        
    except Exception as e:
        logger.error(f"生成本地分析报告失败: {str(e)}")
        lines.append(f"**错误**: 生成分析报告时出错: {str(e)}\n")
    
    lines.append("\n---\n\n")
    lines.append("**注**: 本报告使用本地评价逻辑生成，基于统计数据和规则分析。如需更深入的AI分析，请配置AI服务。\n")
    
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


def generate_daily_report(all_results, author_name, since_date=None, until_date=None):
    """
    生成开发日报格式的 Markdown 文档
    
    Args:
        all_results: 按项目分组的提交字典
        author_name: 提交者姓名
        since_date: 起始日期（可选）
        until_date: 结束日期（可选）
    
    Returns:
        str: Markdown 格式的日报内容
    """
    lines = []
    
    # 确定日期
    if since_date and until_date and since_date == until_date:
        report_date = since_date
    else:
        report_date = datetime.now().strftime('%Y-%m-%d')
    
    date_obj = datetime.strptime(report_date, '%Y-%m-%d')
    date_formatted = date_obj.strftime('%Y年%m月%d日')
    
    # 标题
    lines.append(f"# {author_name} - 开发日报\n")
    lines.append(f"**日期**: {date_formatted} ({report_date})\n")
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
                time_obj = datetime.fromisoformat(commit_time.replace('Z', '+00:00'))
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
            time_str = item['time'].strftime('%H:%M')
            
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
                # 缩进显示完整信息
                indented_message = '\n   '.join(full_message.split('\n'))
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
    
    # 工作分类汇总
    lines.append("## 📋 工作分类汇总\n\n")
    
    for commit_type in sorted(commit_types.keys(), key=lambda x: commit_types[x], reverse=True):
        type_emoji = analyze_commit_type(commits_by_type[commit_type][0]['commit'].message)[1] if commits_by_type[commit_type] else '📌'
        lines.append(f"### {type_emoji} {commit_type} ({commit_types[commit_type]} 次)\n\n")
        
        # 按项目分组
        by_project = defaultdict(list)
        for item in commits_by_type[commit_type]:
            by_project[item['project']].append(item['commit'])
        
        for project_path in sorted(by_project.keys()):
            project = all_results[project_path]['project']
            commits = by_project[project_path]
            
            lines.append(f"**{project.name}** ({len(commits)} 次):\n")
            for commit in commits:
                commit_id = commit.id[:8]
                commit_message = commit.message.split('\n')[0]
                lines.append(f"- [{commit_id}]({commit.web_url}) {commit_message}\n")
            lines.append("\n")
        
        lines.append("---\n\n")
    
    # 时间线
    lines.append("## ⏰ 工作时间线\n\n")
    
    all_commits_timeline = []
    for project_path, result in all_results.items():
        for commit in result['commits']:
            commit_time = commit.committed_date
            if isinstance(commit_time, str):
                time_obj = datetime.fromisoformat(commit_time.replace('Z', '+00:00'))
            else:
                time_obj = commit_time
            
            commit_type, emoji = analyze_commit_type(commit.message)
            all_commits_timeline.append({
                'time': time_obj,
                'project': project_path,
                'commit': commit,
                'type': commit_type,
                'emoji': emoji
            })
    
    all_commits_timeline.sort(key=lambda x: x['time'], reverse=True)
    
    for item in all_commits_timeline:
        time_str = item['time'].strftime('%H:%M')
        commit = item['commit']
        commit_id = commit.id[:8]
        commit_message = commit.message.split('\n')[0]
        
        lines.append(f"- **{time_str}** {item['emoji']} [{item['project']}]({all_results[item['project']]['project'].web_url}) - [{commit_id}]({commit.web_url}) {commit_message}\n")
    
    lines.append("\n---\n\n")
    
    # 总结
    lines.append("## 📝 工作总结\n\n")
    lines.append(f"今日共完成 {total_commits} 次提交，涉及 {total_projects} 个项目。")
    
    if commit_types:
        main_work = max(commit_types.items(), key=lambda x: x[1])
        lines.append(f"主要工作类型为 **{main_work[0]}**（{main_work[1]} 次）。")
    
    lines.append("\n")
    lines.append("\n---\n\n")
    
    # 添加代码统计和评分信息
    try:
        code_stats = calculate_code_statistics(all_results, since_date, until_date)
        scores = calculate_scores(all_results, since_date, until_date)
        
        lines.append("## 📊 代码统计\n\n")
        if code_stats['commits_with_stats'] > 0:
            lines.append(f"- **总新增行数**: {code_stats['total_additions']:,}\n")
            lines.append(f"- **总删除行数**: {code_stats['total_deletions']:,}\n")
            lines.append(f"- **净增行数**: {code_stats['net_lines']:,}\n")
            lines.append(f"- **平均每次提交代码行数**: {code_stats['avg_lines_per_commit']}\n")
        else:
            lines.append("- **代码行数统计**: 暂不可用（需要API权限）\n")
        lines.append("\n---\n\n")
        
        lines.append("## 🎯 多维度评分\n\n")
        lines.append(f"**总体评分**: {scores['overall']:.2f} / 100\n\n")
        
        def progress_bar(score, max_score=100, length=15):
            """生成进度条"""
            filled = int(score / max_score * length)
            bar = '█' * filled + '░' * (length - filled)
            return f"`{bar}` {score:.1f}%"
        
        lines.append(f"- **勤奋度**: {progress_bar(scores['diligence']['score'])} (活跃 {scores['diligence']['active_days']} 天，平均 {scores['diligence']['frequency']:.2f} 次/天)\n")
        lines.append(f"- **稳定性**: {progress_bar(scores['stability']['score'])} ({len(scores['stability']['monthly_commits'])} 个月有提交)\n")
        lines.append(f"- **解决问题能力**: {progress_bar(scores['problem_solving']['score'])} (修复类提交占比 {scores['problem_solving']['ratio']:.1%})\n")
        lines.append(f"- **功能创新力**: {progress_bar(scores['feature_innovation']['score'])} (功能类提交占比 {scores['feature_innovation']['ratio']:.1%})\n")
        lines.append(f"- **多线作战能力**: {progress_bar(scores['versatility']['score'])} ({scores['versatility']['project_count']} 个项目，跨度 {scores['versatility']['time_span_days']} 天)\n")
        
        lines.append("\n")
    except Exception as e:
        logger.warning(f"生成统计和评分信息时出错: {str(e)}")
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
        help='生成统计报告格式（包含代码行数统计和多维度评分）'
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
                    until_date=args.until
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
