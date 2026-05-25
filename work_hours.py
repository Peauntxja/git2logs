#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工时计算与格式化模块

基于代码变更量、提交频率、文件变更数的权重算法，
计算每个项目的工时分配并输出 Markdown 表格。
"""

import logging
import math
from datetime import datetime
from collections import defaultdict

from config import ReportConfig
from commit_analysis import analyze_commit_type


def _parse_iso_date(date_string: str) -> datetime:
    """解析 ISO 格式日期字符串（处理 Z 时区后缀）"""
    return datetime.fromisoformat(date_string.replace('Z', '+00:00'))

logger = logging.getLogger(__name__)


def _get_task_difficulty_multiplier(task_type: str, task_name: str) -> float:
    """
    基于任务类型 + 关键词的难易度倍率（纯规则，避免依赖外部 AI）。
    返回值范围：0.5 ~ 2.0
    """
    base_map: dict[str, float] = {
        "Bug修复": 1.6,
        "功能开发": 1.3,
        "代码重构": 1.7,
        "代码维护": 1.0,
        "样式调整": 0.7,
        "测试相关": 1.1,
        "文档更新": 0.6,
        "其他": 1.0,
    }
    base = base_map.get(task_type, 1.0)

    name = (task_name or "").lower()
    # 规则上倾向：包含“联调/性能/优化/迁移/适配/权限/流程/富文本/图片”等更复杂内容时，提高倍率
    positive_keywords = [
        "联调",
        "性能",
        "优化",
        "重构",
        "迁移",
        "适配",
        "兼容",
        "回滚",
        "revert",
        "权限",
        "安全",
        "并发",
        "事务",
        "流程",
        "审批",
        "校验",
        "富文本",
        "富text",
        "图片",
        "日志",
        "监控",
        "埋点",
        "多端",
        "端适配",
    ]
    # 规则上倾向：纯同步/忽略类提交难度较低
    negative_keywords = [
        "merge branch",
        "同步",
        "忽略",
        "chore",
        "cursor",
        "insights",
    ]

    bonus_hits = 0
    for kw in positive_keywords:
        if kw.lower() in name:
            bonus_hits += 1

    negative_hits = 0
    for kw in negative_keywords:
        if kw.lower() in name:
            negative_hits += 1

    # 将“多关键词命中”转为倍率；同时对负面关键词做衰减。
    bonus = bonus_hits * 0.12
    penalty = negative_hits * 0.10
    multiplier = base * (1.0 + bonus - penalty)
    return max(0.5, min(2.0, multiplier))


def _round_to_2dp_with_total(values: list[float], target_total: float) -> list[float]:
    """
    将浮点数按两位小数取整（0.01精度），并保证和严格等于 target_total（同样以0.01计）。
    采用：floor + 最大余数（largest remainder）分配，修正小数误差。
    """
    if not values:
        return []

    target_cents = int(round(target_total * 100))
    raw_cents = [v * 100.0 for v in values]
    floors = [int(math.floor(c + 1e-9)) for c in raw_cents]
    fracs = [c - f for c, f in zip(raw_cents, floors)]
    current = sum(floors)
    diff = target_cents - current

    # diff > 0：向余数最大的项逐个加 1cent
    # diff < 0：向余数最小的项逐个减 1cent
    cents = floors[:]
    if diff > 0:
        order = sorted(range(len(values)), key=lambda i: fracs[i], reverse=True)
        for k in range(diff):
            cents[order[k % len(values)]] += 1
    elif diff < 0:
        order = sorted(range(len(values)), key=lambda i: fracs[i])
        for k in range(-diff):
            idx = order[k % len(values)]
            # 保底：不允许出现负工时
            if cents[idx] > 0:
                cents[idx] -= 1

    return [c / 100.0 for c in cents]


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
                date_obj = _parse_iso_date(commit_date)
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
        # 计算该日每个项目（已引入难易度加权）的权重
        project_stats: dict[str, dict] = {}

        for commit_info in day_commits:
            project = commit_info['project']
            commit = commit_info['commit']
            project_obj = commit_info.get('project_obj')

            # 获取代码变更量 - 尝试多种方式获取
            code_changes = 0
            additions = 0
            deletions = 0

            # 方式1: 尝试从commit.stats获取
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
                        if callable(diff_attr):
                            diff_result = diff_attr()
                            if diff_result:
                                files_changed = len(diff_result) if hasattr(diff_result, '__len__') else 0
                        elif diff_attr:
                            files_changed = len(diff_attr) if hasattr(diff_attr, '__len__') else 0
                except Exception:
                    logger.debug("获取commit diff失败，跳过文件变更统计")

            # 获取commit信息/分支
            commit_id = commit.id[:8] if hasattr(commit, 'id') else ''
            commit_url = getattr(commit, 'web_url', '')

            commit_branch = ''
            if hasattr(commit, 'refs') and commit.refs:
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

            if not commit_branch and branch:
                commit_branch = branch
            if not commit_branch:
                commit_branch = '多分支'

            # 识别提交类型和任务名称（用于难易度规则）
            commit_message = (commit.message or "").strip()
            first_line = commit_message.split('\n')[0] if commit_message else ""
            task_type, _ = analyze_commit_type(commit_message)
            task_name = first_line
            multiplier = _get_task_difficulty_multiplier(task_type, task_name)

            # 基于旧权重算法计算“每个 commit 的基础权重”，再乘难易度倍率
            commit_code_weight = code_changes / 100.0 * 0.6
            commit_weight_value = 0.5 * 0.2  # 每次提交基础权重
            commit_file_weight = files_changed * 0.3 * 0.2
            commit_base_weight = commit_code_weight + commit_weight_value + commit_file_weight
            commit_total_weight = commit_base_weight * multiplier

            if project not in project_stats:
                project_stats[project] = {
                    'project_obj': project_obj,
                    'commits': [],
                    'total_weight': 0.0,
                    'commit_count': 0,
                    'code_changes': 0,
                }

            project_stats[project]['total_weight'] += commit_total_weight
            project_stats[project]['commit_count'] += 1
            project_stats[project]['code_changes'] += code_changes
            project_stats[project]['commits'].append({
                'task_name': task_name,
                'task_type': task_type,
                'additions': additions,
                'deletions': deletions,
                'commit_id': commit_id,
                'commit_url': commit_url,
                'branch': commit_branch,
                'gitlab_url': '',
                'code_changes': code_changes,
                'commit_total_weight': commit_total_weight,
            })

        # 分配工时
        date_data = {
            'date': date_str,
            'total_hours': daily_hours,
            'projects': {}
        }

        total_weight = sum(p['total_weight'] for p in project_stats.values())

        # 修正 project_hours 的四舍五入误差：保证该日项目总和 = daily_hours（0.01 精度）
        projects_in_order = list(project_stats.keys())
        project_hours_unrounded = []
        for project in projects_in_order:
            stats = project_stats[project]
            if total_weight > 0:
                project_hours_unrounded.append((stats['total_weight'] / total_weight) * daily_hours)
            else:
                project_hours_unrounded.append(daily_hours / max(len(project_stats), 1))

        project_hours_rounded_list = _round_to_2dp_with_total(
            project_hours_unrounded,
            target_total=round(daily_hours, 2),
        )

        for idx, project in enumerate(projects_in_order):
            stats = project_stats[project]
            project_hours = project_hours_rounded_list[idx]

            # 提取项目名称（去除路径）
            project_name = project.split('/')[-1] if '/' in project else project

            # 获取GitLab URL和分支信息
            project_obj = stats.get('project_obj')
            gitlab_url = ''
            if project_obj:
                gitlab_url = getattr(project_obj, 'web_url', '') or getattr(project_obj, 'http_url_to_repo', '')

            # 按提交生成任务列表（小时分配：基于难易加权后的权重）
            commits = stats['commits']
            project_total_weight = stats.get('total_weight', 0.0) or 0.0
            tasks_unrounded = []
            for entry in commits:
                if project_total_weight > 0:
                    tasks_unrounded.append((entry['commit_total_weight'] / project_total_weight) * project_hours)
                else:
                    tasks_unrounded.append(project_hours / max(len(commits), 1))

            tasks_rounded = _round_to_2dp_with_total(
                tasks_unrounded,
                target_total=project_hours,
            )

            tasks = []
            for i, entry in enumerate(commits):
                tasks.append({
                    'task_name': entry['task_name'],
                    'task_type': entry['task_type'],
                    'hours': tasks_rounded[i],
                    'commits': 1,
                    'additions': entry['additions'],
                    'deletions': entry['deletions'],
                    'commit_id': entry['commit_id'],
                    'commit_url': entry['commit_url'],
                    'branch': entry['branch'],
                    'gitlab_url': gitlab_url,
                })

            date_data['projects'][project] = {
                'project_name': project_name,
                'total_hours': project_hours,
                'tasks': tasks,
                'commit_count': stats['commit_count'],
                'code_changes': stats['code_changes'],
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
