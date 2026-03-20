#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工时计算与格式化模块

基于代码变更量、提交频率、文件变更数的权重算法，
计算每个项目的工时分配并输出 Markdown 表格。
"""

import logging
from datetime import datetime
from collections import defaultdict

from utils.date_utils import parse_iso_date
from config import ReportConfig
from commit_analysis import analyze_commit_type

logger = logging.getLogger(__name__)


def calculate_work_hours(all_results, since_date=None, until_date=None,
                         daily_hours=ReportConfig.DEFAULT_DAILY_HOURS, branch=None):
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

    work_hours_by_date = {}

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
                    logger.debug("获取commit diff失败，跳过文件变更统计")

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
