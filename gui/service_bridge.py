#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Git2LogsService 与 GUI 之间的参数构建与结果处理（Mixin，逻辑不变）。"""
import json
import logging
import os
from datetime import datetime

from tkinter import messagebox

from config import ReportConfig
from models import ReportParams, AIParams, ExcelParams

logger = logging.getLogger(__name__)


class ServiceBridgeMixin:
    """将 Git2LogsService 接入 GUI 的辅助方法集合。"""

    def _service_log_callback(self, message, level="info"):
        """Git2LogsService 日志回调（线程安全）。"""
        self.log(message, level)

    def _attach_gui_log_handler(self):
        """将 root logger 重定向到 GUI 日志面板。"""
        class GUILogHandler(logging.Handler):
            def __init__(self, gui_log_func):
                super().__init__()
                self.gui_log_func = gui_log_func

            def emit(self, record):
                try:
                    msg = self.format(record)
                    log_type = (
                        "error" if record.levelno >= logging.ERROR
                        else "warning" if record.levelno >= logging.WARNING
                        else "info"
                    )
                    self.gui_log_func(msg, log_type)
                except Exception:
                    logger.debug("GUILogHandler发送日志到GUI失败")

        gui_handler = GUILogHandler(self.log)
        gui_handler.setLevel(logging.INFO)
        gui_handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
        root_logger = logging.getLogger()
        try:
            if hasattr(self, "_gui_log_handler") and self._gui_log_handler in root_logger.handlers:
                root_logger.removeHandler(self._gui_log_handler)
        except Exception:
            logger.debug("移除旧的GUI日志处理器失败")
        root_logger.addHandler(gui_handler)
        self._gui_log_handler = gui_handler
        root_logger.setLevel(logging.INFO)
        return gui_handler

    def _detach_gui_log_handler(self, gui_handler):
        """移除本次任务挂载的 GUI 日志 handler。"""
        try:
            root_logger = logging.getLogger()
            if gui_handler is not None and gui_handler in root_logger.handlers:
                root_logger.removeHandler(gui_handler)
        except Exception:
            logger.debug("清理GUI日志处理器失败")

    def _resolve_dates_from_cached(self, params: dict):
        """
        从预收集参数解析 since/until 日期。
        返回 (since_date, until_date)；校验失败时弹窗并返回 None。
        """
        since_date = None
        until_date = None
        use_today_value = params['use_today']
        self.log(f"调试: '今天'复选框状态: {use_today_value}", "info")

        if use_today_value:
            today_local = datetime.now()
            since_date = today_local.strftime('%Y-%m-%d')
            until_date = today_local.strftime('%Y-%m-%d')
            self.log(f"使用今天的日期: {since_date}", "info")
            from datetime import timezone
            today_utc = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            today_local_str = today_local.strftime('%Y-%m-%d')
            if today_local_str != today_utc:
                self.log(
                    f"提示: 本地日期为 {today_local_str}，UTC 日期为 {today_utc}，"
                    "GitLab API 将使用 UTC 时间查询",
                    "info",
                )
            return since_date, until_date

        since_date_str = params['since_date']
        until_date_str = params['until_date']
        self.log(
            f"调试: 从输入框获取的日期 - 起始: '{since_date_str}', 结束: '{until_date_str}'",
            "info",
        )

        if since_date_str and not until_date_str:
            until_date_str = since_date_str
            self.log(f"调试: 只填写了起始日期，自动设置结束日期为: {until_date_str}", "info")
        if until_date_str and not since_date_str:
            since_date_str = until_date_str
            self.log(f"调试: 只填写了结束日期，自动设置起始日期为: {since_date_str}", "info")

        if since_date_str:
            since_date = since_date_str
        if until_date_str:
            until_date = until_date_str

        if not since_date and not until_date:
            self.log("提示: 未指定日期范围，将查询所有提交记录", "info")
        elif since_date and until_date:
            try:
                datetime.strptime(since_date, '%Y-%m-%d')
                datetime.strptime(until_date, '%Y-%m-%d')
                self.log(f"调试: 日期格式验证通过 - 起始: {since_date}, 结束: {until_date}", "info")
                if since_date == until_date:
                    self.log(f"使用指定的日期: {since_date}", "info")
                else:
                    self.log(f"使用日期范围: {since_date} 至 {until_date}", "info")
            except ValueError as e:
                self.log(f"错误: 日期格式无效 - {str(e)}", "error")
                self.log(f"  起始日期: '{since_date}', 结束日期: '{until_date}'", "error")
                self.log("  日期格式应为 YYYY-MM-DD，例如: 2026-01-21", "error")
                self.root.after(
                    0,
                    lambda: messagebox.showerror(
                        "错误",
                        f"日期格式无效: {str(e)}\n\n日期格式应为 YYYY-MM-DD，例如: 2026-01-21",
                    ),
                )
                return None

        return since_date, until_date

    def _build_report_params(self, params: dict) -> ReportParams | None:
        """将预收集的 GUI 参数转为 ReportParams。"""
        gitlab_url = params['gitlab_url']
        placeholder_text = "https://gitlab.com 或 http://gitlab.yourcompany.com"
        if gitlab_url == placeholder_text:
            gitlab_url = ""

        token = params['token']
        author = params['author']
        repo = params['repo']
        branch = params['branch']

        self.log("配置参数:", "info")
        self.log(f"  GitLab URL: {gitlab_url}", "info")
        self.log(f"  提交者: {author}", "info")
        self.log(f"  仓库: {repo if repo else '(扫描所有项目)'}", "info")
        self.log(f"  分支: {branch if branch else '(所有分支)'}", "info")

        if not gitlab_url or not token or not author:
            self.log("错误: 请填写GitLab URL、访问令牌和提交者", "error")
            self.root.after(
                0,
                lambda: messagebox.showerror("错误", "请填写GitLab URL、访问令牌和提交者"),
            )
            return None

        dates = self._resolve_dates_from_cached(params)
        if dates is None:
            return None
        since_date, until_date = dates

        output_path = params['output_path']
        if not output_path:
            output_path = os.getcwd()
            self.log(f"未指定输出路径，使用当前目录: {output_path}", "info")

        scan_all = params['scan_all'] or not repo
        output_format = params['output_format']
        self.log(f"输出格式: {output_format}", "info")

        return ReportParams(
            gitlab_url=gitlab_url,
            token=token,
            author=author,
            since_date=since_date,
            until_date=until_date,
            branch=branch,
            output_format=output_format,
            output_path=output_path,
            scan_all=scan_all,
            repo_url=repo or None,
            daily_hours=ReportConfig.DEFAULT_DAILY_HOURS,
        )

    def _build_ai_params(self, cached: dict | None = None) -> AIParams:
        """构建 AI 分析参数（优先使用主线程预收集的 cached）。"""
        if cached:
            service = cached.get('ai_service') or 'openai'
            api_key = (cached.get('ai_api_key') or '').strip()
            model = cached.get('ai_model') or None
            base_url = (cached.get('ai_base_url') or '').strip() or None
        else:
            service = self.ai_service.get()
            api_key = self.ai_api_key.get().strip()
            model = self.ai_model.get() or None
            base_url = (
                self.ai_base_url.get().strip()
                if hasattr(self, 'ai_base_url')
                else None
            ) or None
        return AIParams(
            service=service,
            api_key=api_key,
            model=model,
            base_url=base_url,
        )

    def _build_excel_params(
        self,
        template: str,
        output: str,
        selected_projects: list | None,
    ) -> ExcelParams:
        return ExcelParams(
            template_path=template,
            output_path=output,
            work_hours_data=self._work_hours_data or {},
            selected_projects=selected_projects or [],
        )

    def _log_no_commits_troubleshooting(self, params: dict, since_date, until_date):
        """扫描全库无结果时的排查提示（与原 GUI 行为一致）。"""
        if not (params['scan_all'] or not params['repo']):
            return
        author = params['author']
        self.log("", "warning")
        self.log("未找到提交记录的可能原因：", "warning")
        self.log(
            "1. 日期范围问题：GitLab API 使用 UTC 时间，可能与本地时区不同",
            "warning",
        )
        self.log(
            "   当前查询日期: "
            + (f"{since_date} 至 {until_date}" if since_date and until_date else "未指定（查询所有）"),
            "warning",
        )
        self.log("2. 提交者名称不匹配：请确认提交者名称或邮箱与 GitLab 中的完全一致", "warning")
        self.log(f"   当前提交者: {author}", "warning")
        self.log("   提示: 请查看上面的'调试：查询到的提交示例'，确认实际作者格式", "warning")
        self.log("3. 分支问题：如果指定了分支，请确认该分支存在且有提交", "warning")
        self.log("4. 权限问题：请确认访问令牌有足够的权限", "warning")
        self.log("", "warning")
        self.log("排查建议：", "info")
        self.log("- 查看上面的调试信息，确认 GitLab 中实际提交的作者格式", "info")
        self.log("- 尝试只使用邮箱或只使用名称作为提交者", "info")
        self.log("- 如果指定了日期，尝试不指定日期范围（取消'今天'勾选，不填日期）", "info")
        self.log("- 尝试指定具体分支名称", "info")
        self.log("- 检查该日期范围内是否确实有提交（可以在 GitLab 网页上查看）", "info")

    def _apply_generate_report_result(self, result: dict, cached: dict, report_params: ReportParams):
        """根据 Git2LogsService.generate_report 返回值更新 GUI 状态。"""
        all_results = result.get('all_results') or {}
        if not all_results:
            self.log("未找到任何提交记录", "warning")
            self._log_no_commits_troubleshooting(
                cached,
                report_params.since_date,
                report_params.until_date,
            )
            self.root.after(0, lambda: messagebox.showwarning("提示", "未找到任何提交记录"))
            return

        work_hours_data = result.get('work_hours_data')
        if work_hours_data:
            self._work_hours_data = work_hours_data
            self.log("工时数据已缓存，可在「Excel导出」标签页导出", "info")
            self.root.after(0, self._refresh_excel_status)

        generated_files = result.get('generated_files') or {}
        output_format = report_params.output_format

        if output_format == "statistics":
            self.log("提示: 统计报告包含本地多维度评价，AI分析需要手动触发", "info")
            output_file = result.get('output_file')
            if cached.get('ai_enabled') and cached.get('ai_api_key'):
                self._pending_ai_data = {
                    'all_results': all_results,
                    'author': report_params.author,
                    'output_dir': os.path.dirname(output_file) if output_file else os.getcwd(),
                    'since_date': report_params.since_date,
                    'until_date': report_params.until_date,
                    'generated_files': generated_files,
                }
                self.log("数据已保存，可以点击'执行AI分析'按钮进行AI分析", "info")

        for file_type, file_path in generated_files.items():
            self.log(f"  - {file_type}: {file_path}", "info")

        output_file = result.get('output_file')
        if output_file and output_format not in ("all", "statistics"):
            self.log(f"报告已保存: {output_file}", "success")

        if output_format == "work_hours" and output_file and work_hours_data:
            json_file = output_file.replace(".md", "_data.json")
            with open(json_file, "w", encoding="utf-8") as jf:
                json.dump(work_hours_data, jf, ensure_ascii=False, indent=2)
            self.log(f"工时数据已保存: {json_file}", "info")
            self.log("提示: 可在「Excel导出」标签页加载此 JSON 文件", "info")

        self.log("=" * 60, "info")
