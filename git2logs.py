#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitLab 提交日志生成工具

本文件作为 CLI 入口和公共 API 门面；命令行实现见 cli.py。
"""
import logging
import sys

# 从拆分后的子模块 re-export，保持对外 API 兼容
from gitlab_client import (
    create_gitlab_client,
    parse_project_identifier,
    extract_gitlab_url,
    get_commits_by_author,
    group_commits_by_date,
    get_all_projects,
    scan_all_projects,
)
from commit_analysis import (
    analyze_commit_type,
    get_commit_details,
    get_commit_stats,
    calculate_code_statistics,
)
from work_hours import (
    calculate_work_hours,
    format_work_hours_table,
)
from report_generator import (
    generate_markdown_log,
    generate_multi_project_markdown,
    generate_work_hours_report,
    generate_statistics_report,
    generate_all_reports,
    generate_ai_analysis_report,
    generate_daily_report,
)

try:
    import gitlab  # pyright: ignore[reportMissingImports]
except ImportError:
    print("错误: 未安装 python-gitlab 库")
    print("请运行: pip install python-gitlab")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)


def analyze_with_ai(all_results, author_name, ai_config, since_date=None, until_date=None):
    """
    收集提交数据并使用 AI 进行分析（委托 Git2LogsService，保持对外 API 不变）。
    """
    from models import AIParams
    from service import Git2LogsService

    ai_params = AIParams(
        service=ai_config.get('service', 'openai'),
        api_key=ai_config.get('api_key', ''),
        model=ai_config.get('model'),
        base_url=ai_config.get('base_url'),
    )
    result = Git2LogsService().analyze_ai(
        all_results,
        author_name,
        ai_params,
        since_date=since_date,
        until_date=until_date,
        log_callback=lambda msg, _level="info": logger.info(msg),
    )
    return result['analysis_result']


def main(argv=None):
    """CLI 入口（委托 cli 模块）。"""
    from cli import main as cli_main
    cli_main(argv)


from cli import resolve_output_path as _resolve_output_path  # noqa: E402


if __name__ == '__main__':
    main()
