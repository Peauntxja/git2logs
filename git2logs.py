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

from config import AIConfig

# 导入工具模块
from utils.date_utils import parse_iso_date

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
    收集提交数据并使用AI进行分析

    Args:
        all_results: 按项目分组的提交字典
        author_name: 提交者姓名
        ai_config: AI配置字典
            - service: 'openai', 'anthropic', 'gemini', 'doubao' 或 'deepseek'
            - api_key: API密钥
            - model: 模型名称（可选）
        since_date: 起始日期（可选）
        until_date: 结束日期（可选）

    Returns:
        dict: AI分析结果
    """
    from datetime import datetime

    try:
        from ai_analysis import analyze_with_ai as call_ai_service
    except ImportError:
        logger.error("无法导入 ai_analysis 模块")
        raise

    commits_data = {
        'total_commits': 0,
        'active_days': 0,
        'projects': [],
        'commit_messages': [],
        'time_distribution': {},
        'code_stats': {}
    }

    all_dates = set()
    all_commit_messages = []
    projects_set = set()

    try:
        code_stats = calculate_code_statistics(all_results, since_date, until_date)
        commits_data['code_stats'] = code_stats
    except Exception as e:
        logger.warning(f"计算代码统计失败: {str(e)}")
        commits_data['code_stats'] = {
            'total_additions': 0,
            'total_deletions': 0
        }

    for project_path, result in all_results.items():
        projects_set.add(project_path)
        commits = result['commits']
        commits_data['total_commits'] += len(commits)

        for commit in commits:
            if commit.message:
                all_commit_messages.append(commit.message[:200])

            commit_date = commit.committed_date
            if isinstance(commit_date, str):
                date_obj = parse_iso_date(commit_date)
            else:
                date_obj = commit_date
            date_str = date_obj.strftime('%Y-%m-%d')
            all_dates.add(date_str)

            month_key = date_obj.strftime('%Y-%m')
            commits_data['time_distribution'][month_key] = commits_data['time_distribution'].get(month_key, 0) + 1

    commits_data['active_days'] = len(all_dates)
    commits_data['projects'] = list(projects_set)
    commits_data['commit_messages'] = all_commit_messages[:50]

    timeout = AIConfig.TIMEOUT
    logger.info(f"正在调用AI服务进行分析（超时时间: {timeout}秒）...")
    try:
        analysis_result = call_ai_service(commits_data, ai_config, timeout=timeout)
        logger.info("AI分析完成")
        analysis_result['ai_service'] = ai_config.get('service', 'unknown')
        analysis_result['ai_model'] = ai_config.get('model', 'unknown')
        return analysis_result
    except TimeoutError as e:
        logger.error(f"AI分析超时: {str(e)}")
        raise
    except ValueError as e:
        logger.error(f"AI分析失败（可能是API密钥问题）: {str(e)}")
        raise
    except ConnectionError as e:
        logger.error(f"AI分析失败（网络连接问题）: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"AI分析失败: {str(e)}")
        raise


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
            gl = create_gitlab_client(gitlab_url, token)
            all_results = scan_all_projects(
                gl, args.author,
                since_date=args.since, until_date=args.until, branch=args.branch
            )

            if not all_results:
                logger.warning(f"未在任何项目中找到提交者 '{args.author}' 的提交记录")
                sys.exit(0)

            if args.statistics:
                markdown_content = generate_statistics_report(
                    all_results, args.author,
                    since_date=args.since, until_date=args.until
                )
                output_file = _resolve_output_path(args.output, 'statistics', args.branch)
            elif args.daily_report:
                markdown_content = generate_daily_report(
                    all_results, args.author,
                    since_date=args.since, until_date=args.until, branch=args.branch
                )
                output_file = _resolve_output_path(args.output, 'daily_report', args.branch)
            elif args.work_hours:
                markdown_content = generate_work_hours_report(
                    all_results, args.author,
                    since_date=args.since, until_date=args.until,
                    daily_hours=args.daily_hours, branch=args.branch
                )
                output_file = _resolve_output_path(args.output, 'work_hours', args.branch)
            else:
                markdown_content = generate_multi_project_markdown(
                    all_results, args.author,
                    since_date=args.since, until_date=args.until
                )
                output_file = _resolve_output_path(args.output, 'all_projects', args.branch)

        else:
            extracted_url = extract_gitlab_url(args.repo)
            if extracted_url:
                gitlab_url = extracted_url
                logger.info(f"从仓库 URL 提取 GitLab 实例: {gitlab_url}")

            gl = create_gitlab_client(gitlab_url, token)
            project_id = parse_project_identifier(args.repo)
            logger.info(f"项目标识符: {project_id}")

            try:
                project = gl.projects.get(project_id)
                logger.info(f"成功获取项目: {project.name}")
            except Exception as e:
                logger.error(f"获取项目失败: {str(e)}")
                logger.error("请检查项目路径是否正确，以及是否有访问权限")
                sys.exit(1)

            commits = get_commits_by_author(
                project, args.author,
                since_date=args.since, until_date=args.until, branch=args.branch
            )

            if not commits:
                logger.warning(f"未找到提交者 '{args.author}' 的提交记录")
                sys.exit(0)

            grouped_commits = group_commits_by_date(commits)
            markdown_content = generate_markdown_log(
                grouped_commits, args.author,
                repo_name=project.name, project=project
            )

            if args.daily_report:
                output_file = _resolve_output_path(args.output, 'daily_report', args.branch)
            else:
                output_file = _resolve_output_path(args.output, 'commits', args.branch)

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
