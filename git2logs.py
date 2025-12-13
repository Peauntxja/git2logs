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
                
                if len(page_commits) < per_page:
                    break
                
                page += 1
            
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
                
                branch_commits = []
                branch_page = 1
                while True:
                    branch_params['page'] = branch_page
                    page_commits = project.commits.list(**branch_params)
                    
                    if not page_commits:
                        break
                    
                    branch_commits.extend(page_commits)
                    
                    if len(page_commits) < per_page:
                        break
                    
                    branch_page += 1
                
                if branch_commits:
                    logger.info(f"[{idx}/{len(branches)}] 分支 '{branch_obj.name}': 找到 {len(branch_commits)} 条提交")
                    all_commits.extend(branch_commits)
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


def generate_markdown_log(grouped_commits, author_name, repo_name=None):
    """
    生成 Markdown 格式的日志
    
    Args:
        grouped_commits: 按日期分组的提交字典
        author_name: 提交者姓名
        repo_name: 仓库名称（可选）
    
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
            # 提交信息
            commit_id = commit.id[:8]  # 短提交 ID
            commit_message = commit.message.split('\n')[0]  # 第一行提交信息
            
            lines.append(f"### {idx}. [{commit_id}]({commit.web_url}) {commit_message}\n")
            
            # 提交时间
            commit_time = commit.committed_date
            if isinstance(commit_time, str):
                time_obj = datetime.fromisoformat(commit_time.replace('Z', '+00:00'))
            else:
                time_obj = commit_time
            time_str = time_obj.strftime('%H:%M:%S')
            lines.append(f"**时间**: {time_str}\n")
            
            # 如果有文件变更统计
            try:
                commit_detail = commit
                if hasattr(commit_detail, 'stats'):
                    stats = commit_detail.stats
                    if stats:
                        lines.append(f"**变更**: +{stats.get('additions', 0)} -{stats.get('deletions', 0)}\n")
            except:
                pass
            
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
            
            for idx, commit in enumerate(project_commits, 1):
                commit_id = commit.id[:8]
                commit_message = commit.message.split('\n')[0]
                
                lines.append(f"#### {idx}. [{commit_id}]({commit.web_url}) {commit_message}\n")
                
                commit_time = commit.committed_date
                if isinstance(commit_time, str):
                    time_obj = datetime.fromisoformat(commit_time.replace('Z', '+00:00'))
                else:
                    time_obj = commit_time
                time_str = time_obj.strftime('%H:%M:%S')
                lines.append(f"**时间**: {time_str}\n\n")
            
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
            
            commit_id = commit.id[:8]
            commit_message = commit.message.split('\n')[0]
            
            lines.append(f"{idx}. **{emoji} [{commit_type}]** [{commit_id}]({commit.web_url}) {commit_message}\n")
            lines.append(f"   - 时间: {time_str}\n")
        
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
            if args.daily_report:
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
                repo_name=project.name
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
