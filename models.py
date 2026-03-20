#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
核心数据模型定义

为项目中隐式传递的字典结构提供类型化的数据类，
提升代码可读性和可维护性。
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ProjectResult:
    """单个项目的查询结果"""
    project: Any
    commits: List[Any] = field(default_factory=list)


@dataclass
class ReportParams:
    """报告生成参数"""
    gitlab_url: str
    token: str
    author: str
    since_date: Optional[str] = None
    until_date: Optional[str] = None
    branch: Optional[str] = None
    output_format: str = 'commits'
    output_path: Optional[str] = None
    scan_all: bool = False
    repo_url: Optional[str] = None
    daily_hours: float = 8.0


@dataclass
class AIParams:
    """AI 分析参数"""
    service: str
    api_key: str
    model: Optional[str] = None
    base_url: Optional[str] = None


@dataclass
class ExcelParams:
    """Excel 导出参数"""
    template_path: str
    output_path: str
    work_hours_data: Dict[str, Any] = field(default_factory=dict)
    selected_projects: List[str] = field(default_factory=list)


@dataclass
class WorkHoursEntry:
    """单条工时记录"""
    task: str
    hours: float
    percentage: float
    commit_count: int = 0


@dataclass
class CommitDisplayInfo:
    """提交展示信息（从 get_commit_details 提取的通用结构）"""
    short_message: str
    full_message: str
    stats: Optional[Dict[str, int]] = None
    changed_files: List[Dict[str, str]] = field(default_factory=list)
    commit_id: str = ''
    web_url: str = ''


class Git2LogsError(Exception):
    """项目基础异常"""
    pass


class GitLabConnectionError(Git2LogsError):
    """GitLab 连接失败"""
    pass


class ReportGenerationError(Git2LogsError):
    """报告生成失败"""
    pass


class ExportError(Git2LogsError):
    """导出操作失败"""
    pass


class AIAnalysisError(Git2LogsError):
    """AI 分析失败"""
    pass
