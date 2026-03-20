#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
业务编排层

作为 GUI 与核心逻辑模块之间的中间层，封装完整的业务工作流，
使 GUI 只需关心参数收集和结果展示，不再直接拼装底层调用。
"""

import os
import json
import logging
import traceback
from datetime import datetime
from pathlib import Path

from gitlab_client import (
    create_gitlab_client,
    scan_all_projects,
    get_commits_by_author,
    group_commits_by_date,
    extract_gitlab_url,
    parse_project_identifier,
)
from report_generator import (
    generate_markdown_log,
    generate_multi_project_markdown,
    generate_daily_report,
    generate_statistics_report,
    generate_all_reports,
    generate_work_hours_report,
    generate_ai_analysis_report,
)
from work_hours import calculate_work_hours
from commit_analysis import clear_commit_cache
from models import (
    ReportParams,
    AIParams,
    ExcelParams,
    Git2LogsError,
    GitLabConnectionError,
    ReportGenerationError,
    AIAnalysisError,
)
from config import ReportConfig, AIConfig

logger = logging.getLogger(__name__)


class Git2LogsService:
    """业务编排服务，封装报告生成、Excel 导出、AI 分析等完整工作流。"""

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    @staticmethod
    def _log(callback, message, level="info"):
        """安全调用日志回调"""
        if callback:
            try:
                callback(message, level)
            except Exception:
                logger.debug("日志回调执行失败")

    @staticmethod
    def _resolve_output_file(output_path, report_type, since_date=None, until_date=None):
        """根据输出路径和报告类型，确定最终文件路径。"""
        if since_date and until_date and since_date == until_date:
            date_prefix = since_date
        else:
            date_prefix = datetime.now().strftime('%Y-%m-%d')

        if not output_path:
            output_path = os.getcwd()

        if os.path.isdir(output_path):
            return os.path.join(output_path, f"{date_prefix}_{report_type}.md")

        return output_path

    # ------------------------------------------------------------------
    # 核心工作流：报告生成
    # ------------------------------------------------------------------

    def generate_report(self, params: ReportParams, log_callback=None) -> dict:
        """
        主报告生成工作流。

        Returns:
            dict: {
                'content': markdown 字符串（部分格式可能为 None）,
                'output_file': 主输出文件路径（或 None）,
                'generated_files': {type: path} 字典（all 格式时多文件）,
                'work_hours_data': 工时数据字典（work_hours 格式时）,
                'all_results': 原始查询结果（供后续 AI 分析使用）,
            }

        Raises:
            GitLabConnectionError: GitLab 连接失败
            ReportGenerationError: 报告生成失败
        """
        self._log(log_callback, "开始生成日志...", "info")

        clear_commit_cache()

        # 1. 连接 GitLab
        self._log(log_callback, f"正在连接到 GitLab: {params.gitlab_url}", "info")
        try:
            gl = create_gitlab_client(params.gitlab_url, params.token)
        except Exception as exc:
            raise GitLabConnectionError(f"连接 GitLab 失败: {exc}") from exc

        # 2. 获取提交记录
        all_results = self._fetch_commits(
            gl, params, log_callback,
        )

        if not all_results:
            self._log(log_callback, "未找到任何提交记录", "warning")
            return {
                'content': None,
                'output_file': None,
                'generated_files': {},
                'work_hours_data': None,
                'all_results': {},
            }

        # 3. 根据输出格式生成报告
        try:
            result = self._build_report(all_results, params, log_callback)
        except Exception as exc:
            raise ReportGenerationError(f"报告生成失败: {exc}") from exc

        result['all_results'] = all_results
        self._log(log_callback, "生成完成！", "success")
        return result

    # ------------------------------------------------------------------
    # 提交获取（scan_all / 单项目）
    # ------------------------------------------------------------------

    def _fetch_commits(self, gl, params: ReportParams, log_callback=None):
        """根据 params 中的模式获取提交记录，返回 all_results 字典。"""
        all_results = {}

        if params.scan_all or not params.repo_url:
            self._log(log_callback, "正在扫描所有项目...", "info")
            all_results = scan_all_projects(
                gl, params.author,
                since_date=params.since_date,
                until_date=params.until_date,
                branch=params.branch,
            )
            self._log(
                log_callback,
                f"扫描完成，共在 {len(all_results)} 个项目中找到提交记录",
                "success" if all_results else "warning",
            )
        else:
            all_results = self._fetch_single_project(
                gl, params, log_callback,
            )

        return all_results

    def _fetch_single_project(self, gl, params: ReportParams, log_callback=None):
        """单项目模式：解析 URL → 获取项目 → 获取提交。"""
        all_results = {}
        repo_url = params.repo_url

        extracted_url = extract_gitlab_url(repo_url)
        if extracted_url:
            self._log(log_callback, f"从仓库 URL 提取 GitLab 实例: {extracted_url}", "info")
            gl = create_gitlab_client(extracted_url, params.token)

        project_identifier = parse_project_identifier(repo_url)
        self._log(log_callback, f"正在获取项目: {project_identifier}", "info")

        try:
            project = gl.projects.get(project_identifier)
            commits = get_commits_by_author(
                project, params.author,
                since_date=params.since_date,
                until_date=params.until_date,
                branch=params.branch,
            )
            if commits:
                all_results[project_identifier] = {
                    'project': project,
                    'commits': commits,
                }
                self._log(log_callback, f"找到 {len(commits)} 条提交记录", "success")
        except Exception as exc:
            self._log(log_callback, f"获取项目失败: {exc}", "error")

        return all_results

    # ------------------------------------------------------------------
    # 报告构建（按 output_format 分发）
    # ------------------------------------------------------------------

    def _build_report(self, all_results, params: ReportParams, log_callback=None):
        """按 output_format 生成对应报告，返回结果字典。"""
        fmt = params.output_format
        output_path = params.output_path or os.getcwd()
        since = params.since_date
        until = params.until_date
        author = params.author
        branch = params.branch

        result = {
            'content': None,
            'output_file': None,
            'generated_files': {},
            'work_hours_data': None,
        }

        if fmt == "all":
            return self._build_all_reports(all_results, params, log_callback)

        if fmt == "statistics":
            return self._build_statistics(all_results, params, log_callback)

        report_content = self._generate_single_format(
            fmt, all_results, author, since, until, branch, params.daily_hours, log_callback,
        )

        if report_content is None:
            self._log(log_callback, f"暂不支持 {fmt} 格式的直接生成", "error")
            return result

        output_file = self._resolve_output_file(output_path, fmt, since, until)
        self._write_file(output_file, report_content)

        result['content'] = report_content
        result['output_file'] = output_file
        result['generated_files'] = {fmt: output_file}
        self._log(log_callback, f"报告已保存: {output_file}", "success")

        if fmt == "work_hours":
            work_hours_data = calculate_work_hours(
                all_results,
                since_date=since, until_date=until,
                daily_hours=params.daily_hours, branch=branch,
            )
            result['work_hours_data'] = work_hours_data

            json_file = output_file.replace(".md", "_data.json")
            with open(json_file, "w", encoding="utf-8") as jf:
                json.dump(work_hours_data, jf, ensure_ascii=False, indent=2)
            self._log(log_callback, f"工时数据已保存: {json_file}", "info")

        return result

    def _generate_single_format(self, fmt, all_results, author, since, until, branch, daily_hours, log_callback=None):
        """生成单一格式的 Markdown 内容，返回字符串或 None。"""
        self._log(log_callback, f"正在生成 {fmt} 格式...", "info")

        if fmt == "commits":
            if len(all_results) == 1:
                project_data = list(all_results.values())[0]
                grouped = group_commits_by_date(project_data['commits'])
                return generate_markdown_log(grouped, author)
            return generate_multi_project_markdown(all_results, author, since_date=since, until_date=until)

        if fmt == "daily_report":
            return generate_daily_report(
                all_results, author,
                since_date=since, until_date=until, branch=branch,
            )

        if fmt == "work_hours":
            return generate_work_hours_report(
                all_results, author,
                since_date=since, until_date=until,
                daily_hours=daily_hours, branch=branch,
            )

        return None

    def _build_statistics(self, all_results, params: ReportParams, log_callback=None):
        """生成统计报告并返回结果字典。"""
        self._log(log_callback, "正在生成统计报告...", "info")
        report_content = generate_statistics_report(
            all_results, params.author,
            since_date=params.since_date, until_date=params.until_date,
        )

        output_file = self._resolve_output_file(
            params.output_path, "statistics", params.since_date, params.until_date,
        )
        self._write_file(output_file, report_content)
        self._log(log_callback, f"统计报告已保存: {output_file}", "success")

        return {
            'content': report_content,
            'output_file': output_file,
            'generated_files': {'statistics': output_file},
            'work_hours_data': None,
        }

    def _build_all_reports(self, all_results, params: ReportParams, log_callback=None):
        """批量生成所有格式。"""
        output_path = params.output_path or os.getcwd()
        self._log(log_callback, "正在批量生成所有格式...", "info")

        generated_files = generate_all_reports(
            all_results, params.author, output_path,
            since_date=params.since_date, until_date=params.until_date,
        )
        self._log(log_callback, f"批量生成完成，共生成 {len(generated_files)} 个文件", "success")

        for file_type, file_path in generated_files.items():
            self._log(log_callback, f"  - {file_type}: {file_path}", "info")

        return {
            'content': None,
            'output_file': None,
            'generated_files': generated_files,
            'work_hours_data': None,
        }

    # ------------------------------------------------------------------
    # Excel 导出
    # ------------------------------------------------------------------

    def export_excel(self, params: ExcelParams, log_callback=None) -> str:
        """
        Excel 导出工作流。

        Returns:
            str: 输出文件路径

        Raises:
            Git2LogsError: 导出失败
        """
        from excel_exporter import fill_excel_template

        self._log(log_callback, "开始导出 Excel 工时表…", "info")

        if params.selected_projects:
            self._log(log_callback, f"导出项目: {', '.join(params.selected_projects)}", "info")
        else:
            self._log(log_callback, "导出所有项目", "info")

        try:
            count = fill_excel_template(
                template_path=params.template_path,
                work_hours_data=params.work_hours_data,
                output_path=params.output_path,
                project_filters=params.selected_projects or None,
            )
            self._log(log_callback, f"导出成功：共写入 {count} 行任务数据", "success")
            self._log(log_callback, f"文件已保存至: {params.output_path}", "success")
            return params.output_path
        except (ImportError, ValueError, FileNotFoundError) as exc:
            raise Git2LogsError(f"Excel 导出失败: {exc}") from exc
        except Exception as exc:
            raise Git2LogsError(f"Excel 导出异常: {exc}") from exc

    # ------------------------------------------------------------------
    # AI 分析
    # ------------------------------------------------------------------

    def analyze_ai(self, all_results, author, ai_params: AIParams,
                   since_date=None, until_date=None, log_callback=None) -> dict:
        """
        AI 分析工作流（基于提交数据）。

        Returns:
            dict: {
                'analysis_result': AI 原始分析结果,
                'report_content': AI 分析报告 Markdown,
                'output_file': 保存的文件路径（如提供 output_dir 则写入）,
            }

        Raises:
            AIAnalysisError: AI 分析失败
        """
        from ai_analysis import analyze_with_ai as call_ai_service
        from commit_analysis import calculate_code_statistics
        from utils.date_utils import parse_iso_date

        self._log(log_callback, "开始 AI 分析...", "info")
        self._log(log_callback, f"AI 服务: {ai_params.service}, 模型: {ai_params.model}", "info")

        ai_config = {
            'service': ai_params.service,
            'api_key': ai_params.api_key,
            'model': ai_params.model,
        }
        if ai_params.base_url:
            ai_config['base_url'] = ai_params.base_url

        try:
            commits_data = self._collect_commits_data(all_results, since_date, until_date)

            self._log(log_callback, f"正在调用 AI 服务进行分析（超时时间: {AIConfig.TIMEOUT}秒）...", "info")
            analysis_result = call_ai_service(commits_data, ai_config, timeout=AIConfig.TIMEOUT)
            analysis_result['ai_service'] = ai_params.service
            analysis_result['ai_model'] = ai_params.model or 'default'

            self._log(log_callback, "AI 分析完成，正在生成报告...", "success")

            report_content = generate_ai_analysis_report(
                analysis_result, author,
                since_date=since_date, until_date=until_date,
            )

            return {
                'analysis_result': analysis_result,
                'report_content': report_content,
                'output_file': None,
            }

        except TimeoutError as exc:
            raise AIAnalysisError(f"AI 分析超时: {exc}") from exc
        except ValueError as exc:
            raise AIAnalysisError(f"AI 分析失败（API 密钥或配置问题）: {exc}") from exc
        except ConnectionError as exc:
            raise AIAnalysisError(f"AI 分析失败（网络连接问题）: {exc}") from exc
        except Exception as exc:
            raise AIAnalysisError(f"AI 分析失败: {exc}") from exc

    def analyze_ai_from_file(self, report_content, ai_params: AIParams,
                             log_callback=None) -> dict:
        """
        基于报告文件内容进行 AI 分析（不需要 GitLab 数据）。

        Returns:
            dict: {
                'analysis_result': AI 原始分析结果,
                'report_content': AI 分析报告 Markdown,
            }

        Raises:
            AIAnalysisError: AI 分析失败
        """
        import re
        from ai_analysis import analyze_report_file

        self._log(log_callback, "开始 AI 分析（基于报告文件内容）...", "info")
        self._log(log_callback, f"AI 服务: {ai_params.service}, 模型: {ai_params.model}", "info")

        ai_config = {
            'service': ai_params.service,
            'api_key': ai_params.api_key,
            'model': ai_params.model,
        }

        try:
            analysis_result = analyze_report_file(report_content, ai_config, timeout=AIConfig.TIMEOUT)

            author_match = re.search(r'\*\*提交者\*\*: (.+)', report_content)
            author = author_match.group(1).strip() if author_match else "未知作者"

            date_range_match = re.search(r'\*\*统计时间范围\*\*: (.+?) 至 (.+?)(?:\n|$)', report_content)
            if date_range_match:
                since_date = date_range_match.group(1).strip()
                until_date = date_range_match.group(2).strip()
            else:
                since_match = re.search(r'\*\*起始日期\*\*: (.+?)(?:\n|$)', report_content)
                until_match = re.search(r'\*\*结束日期\*\*: (.+?)(?:\n|$)', report_content)
                since_date = since_match.group(1).strip() if since_match else None
                until_date = until_match.group(1).strip() if until_match else None

            self._log(log_callback, "AI 分析完成，正在生成报告...", "success")

            ai_report = generate_ai_analysis_report(
                analysis_result, author,
                since_date=since_date, until_date=until_date,
            )

            return {
                'analysis_result': analysis_result,
                'report_content': ai_report,
            }

        except TimeoutError as exc:
            raise AIAnalysisError(f"AI 分析超时: {exc}") from exc
        except ValueError as exc:
            raise AIAnalysisError(f"AI 分析失败（API 密钥或配置问题）: {exc}") from exc
        except ConnectionError as exc:
            raise AIAnalysisError(f"AI 分析失败（网络连接问题）: {exc}") from exc
        except Exception as exc:
            raise AIAnalysisError(f"AI 分析失败: {exc}") from exc

    def test_ai_connection(self, ai_params: AIParams) -> bool:
        """
        测试 AI 服务连接。

        Returns:
            True 连接成功

        Raises:
            AIAnalysisError: 连接失败
        """
        from ai_analysis import get_ai_service

        try:
            service_class = get_ai_service(ai_params.service)
            service_class(
                api_key=ai_params.api_key,
                model=ai_params.model,
                timeout=AIConfig.CONNECTION_TEST_TIMEOUT,
            )

            if ai_params.service == "gemini":
                import google.generativeai as genai
                genai.configure(api_key=ai_params.api_key)
                model_name = ai_params.model or "gemini-pro"
                genai.get_model(f"models/{model_name}" if "/" not in model_name else model_name)

            return True
        except Exception as exc:
            raise AIAnalysisError(f"AI 连接测试失败: {exc}") from exc

    # ------------------------------------------------------------------
    # 内部数据收集
    # ------------------------------------------------------------------

    @staticmethod
    def _collect_commits_data(all_results, since_date=None, until_date=None):
        """将 all_results 转换为 AI 分析所需的 commits_data 字典。"""
        from commit_analysis import calculate_code_statistics
        from utils.date_utils import parse_iso_date

        commits_data = {
            'total_commits': 0,
            'active_days': 0,
            'projects': [],
            'commit_messages': [],
            'time_distribution': {},
            'code_stats': {},
        }

        all_dates = set()
        all_messages = []
        projects_set = set()

        try:
            commits_data['code_stats'] = calculate_code_statistics(
                all_results, since_date, until_date,
            )
        except Exception:
            commits_data['code_stats'] = {'total_additions': 0, 'total_deletions': 0}

        for project_path, result in all_results.items():
            projects_set.add(project_path)
            commits = result['commits']
            commits_data['total_commits'] += len(commits)

            for commit in commits:
                if commit.message:
                    all_messages.append(commit.message[:200])

                commit_date = commit.committed_date
                if isinstance(commit_date, str):
                    date_obj = parse_iso_date(commit_date)
                else:
                    date_obj = commit_date
                date_str = date_obj.strftime('%Y-%m-%d')
                all_dates.add(date_str)

                month_key = date_obj.strftime('%Y-%m')
                commits_data['time_distribution'][month_key] = (
                    commits_data['time_distribution'].get(month_key, 0) + 1
                )

        commits_data['active_days'] = len(all_dates)
        commits_data['projects'] = list(projects_set)
        commits_data['commit_messages'] = all_messages[:50]

        return commits_data

    # ------------------------------------------------------------------
    # 文件写入
    # ------------------------------------------------------------------

    @staticmethod
    def _write_file(path, content):
        """确保父目录存在后写入文件。"""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
