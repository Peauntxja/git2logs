#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitLab 提交日志生成工具
从 GitLab 仓库获取指定提交者每天的代码提交，生成简洁的 Markdown 格式日志

本文件作为 CLI 入口和公共 API 门面，实际逻辑分布在以下模块：
- gitlab_client.py: GitLab API 交互
- commit_analysis.py: 提交分析与统计
- work_hours.py: 工时计算与格式化
- report_generator.py: 报告生成
- ai_analysis.py: AI 分析
"""
import argparse
import sys
import os
from datetime import datetime
import logging

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
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def analyze_with_ai(all_results, author_name, ai_config, since_date=None, until_date=None):
    """
    收集提交数据并使用 AI 进行分析（委托 Git2LogsService，保持对外 API 不变）。

    Args:
        all_results: 按项目分组的提交字典
        author_name: 提交者姓名
        ai_config: AI 配置字典（service / api_key / model / base_url 可选）
        since_date: 起始日期（可选）
        until_date: 结束日期（可选）

    Returns:
        dict: AI 分析结果
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


def _resolve_output_path(output, report_type, branch=None):
    """解析输出文件路径，处理目录、无扩展名等情况"""
    today = datetime.now().strftime('%Y-%m-%d')
    branch_suffix = f"_{branch}" if branch else ""

    if output:
        if os.path.isdir(output):
            filename = f"{today}_{report_type}{branch_suffix}.md"
            resolved = os.path.join(output, filename)
            logger.info(f"输出路径是目录，自动生成文件名: {resolved}")
            return resolved
        if not os.path.splitext(output)[1]:
            resolved = output + '.md'
            logger.info(f"输出文件无扩展名，自动添加 .md: {resolved}")
            return resolved
        return output

    return f"{today}_{report_type}{branch_suffix}.md"


def _cli_output_format(args) -> str:
    """将 CLI 标志映射为 Git2LogsService 的 output_format。"""
    if args.statistics:
        return 'statistics'
    if args.daily_report:
        return 'daily_report'
    if args.work_hours:
        return 'work_hours'
    return 'commits'


def _cli_report_type_name(args) -> str:
    """用于 _resolve_output_path 的文件名类型段。"""
    if args.statistics:
        return 'statistics'
    if args.daily_report:
        return 'daily_report'
    if args.work_hours:
        return 'work_hours'
    return 'all_projects'


def _run_single_repo_legacy(args, token: str) -> None:
    """
    单仓库模式：经 fetch_commits 拉取数据，报告内容仍为 commits Markdown。

    --daily-report 仅影响输出文件名（历史 CLI 行为，不切换日报正文格式）。
    """
    from models import ReportParams, GitLabConnectionError
    from service import Git2LogsService

    gitlab_url = args.gitlab_url
    extracted_url = extract_gitlab_url(args.repo)
    if extracted_url:
        gitlab_url = extracted_url
        logger.info(f"从仓库 URL 提取 GitLab 实例: {gitlab_url}")

    params = ReportParams(
        gitlab_url=gitlab_url,
        token=token,
        author=args.author,
        since_date=args.since,
        until_date=args.until,
        branch=args.branch,
        output_format='commits',
        scan_all=False,
        repo_url=args.repo,
    )

    try:
        all_results = Git2LogsService().fetch_commits(
            params,
            log_callback=logger.info,
            strict_single_project=True,
        )
    except GitLabConnectionError as exc:
        logger.error(str(exc))
        logger.error("请检查项目路径是否正确，以及是否有访问权限")
        sys.exit(1)

    if not all_results:
        logger.warning(f"未找到提交者 '{args.author}' 的提交记录")
        sys.exit(0)

    project_data = next(iter(all_results.values()))
    project = project_data['project']
    grouped_commits = group_commits_by_date(project_data['commits'])
    markdown_content = generate_markdown_log(
        grouped_commits,
        args.author,
        repo_name=project.name,
        project=project,
    )

    report_type = 'daily_report' if args.daily_report else 'commits'
    output_file = _resolve_output_path(args.output, report_type, args.branch)
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(markdown_content)
    logger.info(f"日志已保存到: {output_file}")


def _run_scan_all_via_service(args, token: str) -> None:
    """scan-all 模式：经 Git2LogsService 生成报告（输出路径与旧 CLI 一致）。"""
    from models import ReportParams
    from service import Git2LogsService

    report_type = _cli_report_type_name(args)
    output_file = _resolve_output_path(args.output, report_type, args.branch)

    params = ReportParams(
        gitlab_url=args.gitlab_url,
        token=token,
        author=args.author,
        since_date=args.since,
        until_date=args.until,
        branch=args.branch,
        output_format=_cli_output_format(args),
        output_path=output_file,
        scan_all=True,
        repo_url=None,
        daily_hours=args.daily_hours,
    )

    result = Git2LogsService().generate_report(params, log_callback=logger.info)
    all_results = result.get('all_results') or {}
    if not all_results:
        logger.warning(f"未在任何项目中找到提交者 '{args.author}' 的提交记录")
        sys.exit(0)

    saved = result.get('output_file')
    if saved:
        logger.info(f"日志已保存到: {saved}")
    for _ftype, path in (result.get('generated_files') or {}).items():
        if path and path != saved:
            logger.info(f"已生成: {path}")


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

    parser.add_argument('--repo', help='GitLab 仓库地址或路径')
    parser.add_argument('--author', required=True, help='提交者姓名或邮箱')
    parser.add_argument('--scan-all', action='store_true', help='自动扫描所有有权限访问的项目')
    parser.add_argument('--token', help='GitLab 访问令牌')
    parser.add_argument('--gitlab-url', default='https://gitlab.com', help='GitLab 实例 URL')
    parser.add_argument('--since', help='起始日期（格式：YYYY-MM-DD）')
    parser.add_argument('--until', help='结束日期（格式：YYYY-MM-DD）')
    parser.add_argument('--branch', help='指定分支名称')
    parser.add_argument('--today', action='store_true', help='仅获取今天的提交')
    parser.add_argument('--output', '-o', help='输出文件路径')
    parser.add_argument('--daily-report', action='store_true', help='生成开发日报格式')
    parser.add_argument('--statistics', action='store_true', help='生成统计报告格式')
    parser.add_argument('--work-hours', action='store_true', help='生成工时分配报告')
    parser.add_argument('--daily-hours', type=float, default=8.0, help='每日标准工时（默认：8.0小时）')

    args = parser.parse_args()

    if args.scan_all and args.repo:
        logger.error("--scan-all 和 --repo 不能同时使用")
        sys.exit(1)

    if not args.scan_all and not args.repo:
        logger.error("必须提供 --repo 或使用 --scan-all")
        sys.exit(1)

    if args.today:
        today = datetime.now().strftime('%Y-%m-%d')
        args.since = today
        args.until = today
        logger.info(f"已设置日期范围为今天: {today}")

    try:
        token = args.token or os.environ.get('GITLAB_TOKEN')
        if not token:
            logger.error("必须提供访问令牌（--token 或环境变量 GITLAB_TOKEN）")
            sys.exit(1)

        gitlab_url = args.gitlab_url

        if args.scan_all:
            if not gitlab_url or gitlab_url == 'https://gitlab.com':
                logger.error("使用 --scan-all 时必须指定 --gitlab-url")
                sys.exit(1)

            logger.info(f"使用自动扫描模式，GitLab 实例: {gitlab_url}")
            _run_scan_all_via_service(args, token)
            return

        else:
            _run_single_repo_legacy(args, token)

    except KeyboardInterrupt:
        logger.info("用户中断操作")
        sys.exit(1)
    except Exception as e:
        logger.error(f"程序执行失败: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()
