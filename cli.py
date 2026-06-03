#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Git2Logs 命令行：参数解析与 Git2LogsService 编排。"""
import argparse
import logging
import os
import sys
from datetime import datetime

from gitlab_client import extract_gitlab_url, group_commits_by_date
from report_generator import generate_markdown_log

logger = logging.getLogger(__name__)


def resolve_output_path(output, report_type, branch=None):
    """解析输出文件路径，处理目录、无扩展名等情况。"""
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


def cli_output_format(args) -> str:
    if args.statistics:
        return 'statistics'
    if args.daily_report:
        return 'daily_report'
    if args.work_hours:
        return 'work_hours'
    return 'commits'


def cli_report_type_name(args) -> str:
    if args.statistics:
        return 'statistics'
    if args.daily_report:
        return 'daily_report'
    if args.work_hours:
        return 'work_hours'
    return 'all_projects'


def run_single_repo_legacy(args, token: str) -> None:
    """
    单仓库模式：经 fetch_commits 拉取数据，报告内容仍为 commits Markdown。

    --daily-report 仅影响输出文件名（历史 CLI 行为，不切换日报正文格式）。
    """
    from models import GitLabConnectionError, ReportParams
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
    output_file = resolve_output_path(args.output, report_type, args.branch)
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(markdown_content)
    logger.info(f"日志已保存到: {output_file}")


def run_scan_all_via_service(args, token: str) -> None:
    """scan-all 模式：经 Git2LogsService 生成报告（输出路径与旧 CLI 一致）。"""
    from models import ReportParams
    from service import Git2LogsService

    report_type = cli_report_type_name(args)
    output_file = resolve_output_path(args.output, report_type, args.branch)

    params = ReportParams(
        gitlab_url=args.gitlab_url,
        token=token,
        author=args.author,
        since_date=args.since,
        until_date=args.until,
        branch=args.branch,
        output_format=cli_output_format(args),
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


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='从 GitLab 仓库获取提交者每天的代码提交，生成 Markdown 格式日志',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python git2logs.py --repo http://gitlab.example.com/group/project.git --branch main --author "MIZUKI" --token YOUR_TOKEN
  python git2logs.py --scan-all --gitlab-url http://gitlab.example.com --author "MIZUKI" --today --token YOUR_TOKEN
        """,
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
    return parser


def run_cli(args: argparse.Namespace) -> None:
    """执行已解析的 CLI 参数（供测试或 git2logs.main 调用）。"""
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
        run_scan_all_via_service(args, token)
        return

    run_single_repo_legacy(args, token)


def main(argv=None) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
    )
    parser = build_argument_parser()
    args = parser.parse_args(argv)
    try:
        run_cli(args)
    except KeyboardInterrupt:
        logger.info("用户中断操作")
        sys.exit(1)
    except Exception as e:
        logger.error(f"程序执行失败: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()
