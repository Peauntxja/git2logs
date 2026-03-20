#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
提交分析模块

提供 commit 类型分析、详情获取、代码行数统计等功能，
从 git2logs.py 拆分而来。
"""

import signal
import logging
import functools

from config import GitLabConfig

logger = logging.getLogger(__name__)

_commit_details_cache = {}
_commit_stats_cache = {}


def clear_commit_cache():
    """清空提交详情和统计缓存，在新一轮查询前调用"""
    _commit_details_cache.clear()
    _commit_stats_cache.clear()


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


def get_commit_details(project, commit, timeout=GitLabConfig.COMMIT_DETAIL_TIMEOUT,
                       max_files=GitLabConfig.MAX_DISPLAY_FILES,
                       max_message_length=GitLabConfig.MAX_MESSAGE_LENGTH):
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
    cache_key = (getattr(project, 'id', id(project)), commit.id)
    if cache_key in _commit_details_cache:
        return _commit_details_cache[cache_key]

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
        except Exception:
            logger.debug("降级读取commit stats属性失败")
    
    _commit_details_cache[cache_key] = details
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
    cache_key = (getattr(project, 'id', id(project)), commit.id)
    if cache_key in _commit_stats_cache:
        return _commit_stats_cache[cache_key]

    result = _get_commit_stats_uncached(project, commit)
    _commit_stats_cache[cache_key] = result
    return result


def _get_commit_stats_uncached(project, commit):
    """get_commit_stats 的无缓存实现"""
    try:
        if hasattr(commit, 'stats') and commit.stats:
            stats = commit.stats
            if isinstance(stats, dict):
                return {
                    'additions': stats.get('additions', 0),
                    'deletions': stats.get('deletions', 0),
                    'total': stats.get('total', 0)
                }

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
            logger.debug("通过API获取详细commit信息失败")

        try:
            diffs = commit.diff()
            additions = 0
            deletions = 0
            for diff in diffs:
                if hasattr(diff, 'diff'):
                    diff_text = diff.diff
                    if diff_text:
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
            logger.debug("通过diff计算代码统计失败")

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


def get_commit_display_info(project, commit):
    """
    获取提交的展示信息，失败时自动降级。

    统一了 generate_markdown_log / generate_multi_project_markdown / generate_daily_report
    三处重复的 get_commit_details + fallback 模式。

    Returns:
        dict: 包含 short_message, full_message, stats, changed_files 的字典
    """
    try:
        return get_commit_details(project, commit)
    except Exception as e:
        logger.debug(f"获取commit详情失败: {str(e)}")
        message = commit.message or ''
        return {
            'short_message': message.split('\n')[0],
            'full_message': message,
            'stats': None,
            'changed_files': [],
        }
