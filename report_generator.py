"""
报告生成模块

负责生成各种格式的报告，包括：
- Markdown 提交日志
- 多项目汇总日志
- 工时分配报告
- 统计与评分报告
- AI 分析报告
- 开发日报
"""

import os
import logging
from datetime import datetime
from collections import defaultdict
from pathlib import Path

from utils.date_utils import (
    parse_iso_date,
    parse_simple_date,
    safe_parse_commit_date,
    format_date_chinese,
    format_date_range,
    get_date_range_days,
)
from config import ReportConfig
from commit_analysis import (
    analyze_commit_type, get_commit_details,
    calculate_code_statistics, get_commit_display_info,
)
from work_hours import calculate_work_hours, format_work_hours_table

logger = logging.getLogger(__name__)


def _append_report_header(lines, author_name, since_date=None, until_date=None):
    """向报告追加通用的头部信息（生成时间、提交者、日期范围）"""
    lines.append(f"**生成时间**: {datetime.now().strftime(ReportConfig.DATETIME_FORMAT)}\n")
    lines.append(f"**提交者**: {author_name}\n")
    if since_date and until_date:
        lines.append(f"**时间范围**: {since_date} 至 {until_date}\n")
    elif since_date:
        lines.append(f"**起始日期**: {since_date}\n")
    elif until_date:
        lines.append(f"**结束日期**: {until_date}\n")


def generate_markdown_log(grouped_commits, author_name, repo_name=None, project=None):
    """
    生成 Markdown 格式的日志
    
    Args:
        grouped_commits: 按日期分组的提交字典
        author_name: 提交者姓名
        repo_name: 仓库名称（可选）
        project: GitLab 项目对象（可选，用于获取详细commit信息）
    
    Returns:
        str: Markdown 格式的日志内容
    """
    lines = []
    
    # 标题
    if repo_name:
        lines.append(f"# {repo_name} - {author_name} 提交日志\n")
    else:
        lines.append(f"# {author_name} 提交日志\n")
    
    lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    lines.append(f"**提交者**: {author_name}\n")
    lines.append(f"**总提交数**: {sum(len(commits) for commits in grouped_commits.values())}\n")
    lines.append(f"**提交天数**: {len(grouped_commits)}\n")
    lines.append("\n---\n\n")
    
    # 按日期输出提交
    for date, commits in grouped_commits.items():
        # 日期标题
        date_obj = parse_simple_date(date)
        date_formatted = date_obj.strftime('%Y年%m月%d日')
        lines.append(f"## {date_formatted} ({date})\n")
        
        # 当日统计
        lines.append(f"**提交数**: {len(commits)}\n\n")
        
        # 提交列表
        for idx, commit in enumerate(commits, 1):
            # 获取详细commit信息
            if project:
                try:
                    details = get_commit_details(project, commit)
                    short_message = details['short_message']
                    full_message = details['full_message']
                    stats = details['stats']
                    changed_files = details['changed_files']
                except Exception as e:
                    logger.debug(f"获取commit详情失败: {str(e)}")
                    short_message = commit.message.split('\n')[0] if commit.message else ''
                    full_message = commit.message or ''
                    stats = None
                    changed_files = []
            else:
                short_message = commit.message.split('\n')[0] if commit.message else ''
                full_message = commit.message or ''
                stats = None
                changed_files = []
            
            commit_id = commit.id[:8]  # 短提交 ID
            commit_url = getattr(commit, 'web_url', '')
            
            lines.append(f"### {idx}. [{commit_id}]({commit_url}) {short_message}\n")
            
            # 提交时间
            commit_time = commit.committed_date
            if isinstance(commit_time, str):
                time_obj = parse_iso_date(commit_time)
            else:
                time_obj = commit_time
            time_str = time_obj.strftime('%H:%M:%S')
            lines.append(f"**时间**: {time_str}\n")
            
            # 显示完整的commit message（如果有多行）
            if full_message and '\n' in full_message:
                filtered_msg = '\n'.join(
                    l for l in full_message.split('\n')
                    if not l.strip().lower().startswith('made-with:')
                ).strip()
                if filtered_msg and '\n' in filtered_msg:
                    lines.append(f"**完整提交信息**:\n```\n{filtered_msg}\n```\n")

            # 显示代码行数统计
            if stats:
                lines.append(f"**代码变更**: +{stats.get('additions', 0)} -{stats.get('deletions', 0)} (总计: {stats.get('total', 0)} 行)\n")
            elif hasattr(commit, 'stats') and commit.stats:
                try:
                    commit_stats = commit.stats
                    if isinstance(commit_stats, dict):
                        lines.append(f"**代码变更**: +{commit_stats.get('additions', 0)} -{commit_stats.get('deletions', 0)}\n")
                except Exception:
                    logger.debug("读取commit stats属性失败")
            
            # 显示文件变更列表
            if changed_files:
                lines.append(f"**变更文件** ({len(changed_files)} 个):\n")
                for file_info in changed_files[:10]:  # 最多显示10个文件
                    file_path = file_info.get('new_path') or file_info.get('old_path') or file_info.get('path', '')
                    if file_path:
                        lines.append(f"- `{file_path}`\n")
                if len(changed_files) > 10:
                    lines.append(f"- ... 还有 {len(changed_files) - 10} 个文件\n")
            
            lines.append("\n")
        
        lines.append("---\n\n")
    
    return ''.join(lines)


def generate_multi_project_markdown(all_results, author_name, since_date=None, until_date=None):
    """
    生成多项目汇总的 Markdown 格式日志
    
    Args:
        all_results: 按项目分组的提交字典
        author_name: 提交者姓名
        since_date: 起始日期（可选）
        until_date: 结束日期（可选）
    
    Returns:
        str: Markdown 格式的日志内容
    """
    lines = []
    
    # 标题
    lines.append(f"# {author_name} - 所有项目提交汇总日志\n")
    lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    lines.append(f"**提交者**: {author_name}\n")
    
    # 日期范围
    if since_date and until_date:
        lines.append(f"**日期范围**: {since_date} 至 {until_date}\n")
    elif since_date:
        lines.append(f"**起始日期**: {since_date}\n")
    elif until_date:
        lines.append(f"**结束日期**: {until_date}\n")
    
    # 统计信息
    total_projects = len(all_results)
    total_commits = sum(len(result['commits']) for result in all_results.values())
    
    # 按日期汇总所有提交
    all_commits_by_date = defaultdict(list)
    for project_path, result in all_results.items():
        commits = result['commits']
        for commit in commits:
            commit_date = commit.committed_date
            if isinstance(commit_date, str):
                date_obj = parse_iso_date(commit_date)
            else:
                date_obj = commit_date
            date_str = date_obj.strftime('%Y-%m-%d')
            all_commits_by_date[date_str].append({
                'project': project_path,
                'commit': commit
            })
    
    lines.append(f"**涉及项目数**: {total_projects}\n")
    lines.append(f"**总提交数**: {total_commits}\n")
    lines.append(f"**提交天数**: {len(all_commits_by_date)}\n")
    lines.append("\n---\n\n")
    
    # 按日期输出提交
    sorted_dates = sorted(all_commits_by_date.keys(), reverse=True)
    for date in sorted_dates:
        date_obj = parse_simple_date(date)
        date_formatted = date_obj.strftime('%Y年%m月%d日')
        lines.append(f"## {date_formatted} ({date})\n")
        
        commits_on_date = all_commits_by_date[date]
        lines.append(f"**提交数**: {len(commits_on_date)}\n\n")
        
        # 按项目分组
        commits_by_project = defaultdict(list)
        for item in commits_on_date:
            commits_by_project[item['project']].append(item['commit'])
        
        # 输出每个项目的提交
        for project_path in sorted(commits_by_project.keys()):
            project_commits = commits_by_project[project_path]
            project_info = all_results[project_path]['project']
            
            lines.append(f"### 📦 {project_path}\n")
            lines.append(f"**项目**: [{project_info.name}]({project_info.web_url})\n")
            lines.append(f"**提交数**: {len(project_commits)}\n\n")
            
            # 按时间排序
            project_commits.sort(key=lambda c: c.committed_date, reverse=True)
            
            # 获取项目对象用于获取详细commit信息
            project = all_results[project_path]['project']
            
            for idx, commit in enumerate(project_commits, 1):
                # 获取详细commit信息
                try:
                    details = get_commit_details(project, commit)
                    short_message = details['short_message']
                    full_message = details['full_message']
                    stats = details['stats']
                    changed_files = details['changed_files']
                except Exception as e:
                    logger.debug(f"获取commit详情失败: {str(e)}")
                    short_message = commit.message.split('\n')[0] if commit.message else ''
                    full_message = commit.message or ''
                    stats = None
                    changed_files = []
                
                commit_id = commit.id[:8]
                commit_url = getattr(commit, 'web_url', '')
                
                lines.append(f"#### {idx}. [{commit_id}]({commit_url}) {short_message}\n")
                
                commit_time = commit.committed_date
                if isinstance(commit_time, str):
                    time_obj = parse_iso_date(commit_time)
                else:
                    time_obj = commit_time
                time_str = time_obj.strftime('%H:%M:%S')
                lines.append(f"**时间**: {time_str}\n")
                
                # 显示完整的commit message（如果有多行）
                if full_message and '\n' in full_message:
                    lines.append(f"**完整提交信息**:\n```\n{full_message}\n```\n")
                
                # 显示代码行数统计
                if stats:
                    lines.append(f"**代码变更**: +{stats.get('additions', 0)} -{stats.get('deletions', 0)} (总计: {stats.get('total', 0)} 行)\n")
                elif hasattr(commit, 'stats') and commit.stats:
                    try:
                        commit_stats = commit.stats
                        if isinstance(commit_stats, dict):
                            lines.append(f"**代码变更**: +{commit_stats.get('additions', 0)} -{commit_stats.get('deletions', 0)}\n")
                    except Exception:
                        logger.debug("读取commit stats属性失败")
                
                # 显示文件变更列表（最多显示5个）
                if changed_files:
                    lines.append(f"**变更文件** ({len(changed_files)} 个):\n")
                    for file_info in changed_files[:5]:
                        file_path = file_info.get('new_path') or file_info.get('old_path') or file_info.get('path', '')
                        if file_path:
                            lines.append(f"- `{file_path}`\n")
                    if len(changed_files) > 5:
                        lines.append(f"- ... 还有 {len(changed_files) - 5} 个文件\n")
                
                lines.append("\n")
            
            lines.append("---\n\n")
    
    return ''.join(lines)


def generate_work_hours_report(all_results, author_name, since_date=None, until_date=None,
                               daily_hours=ReportConfig.DEFAULT_DAILY_HOURS, branch=None):
    """
    生成工时分配报告

    Args:
        all_results: 按项目分组的提交字典
        author_name: 提交者姓名
        since_date: 起始日期（可选）
        until_date: 结束日期（可选）
        daily_hours: 每日标准工时（默认8小时）
        branch: 分支名称（可选，用于显示）

    Returns:
        str: Markdown格式的工时报告
    """
    lines = []

    # 标题
    lines.append(f"# {author_name} - 工时分配报告\n")
    lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    lines.append(f"**提交者**: {author_name}\n")

    # 日期范围
    if since_date and until_date:
        if since_date == until_date:
            date_display = f"{format_date_chinese(since_date)} ({since_date})"
        else:
            date_display = format_date_range(since_date, until_date)
            date_display += f" ({since_date} 至 {until_date})"
        lines.append(f"**统计时间**: {date_display}\n")
    lines.append(f"**标准工时**: {daily_hours} 小时/天\n")
    lines.append("\n---\n\n")

    # 计算工时
    try:
        work_hours_data = calculate_work_hours(all_results, since_date, until_date, daily_hours, branch)

        if not work_hours_data:
            lines.append("**提示**: 在指定时间范围内没有找到提交记录。\n")
            return ''.join(lines)

        # 统计总体数据
        total_work_days = len(work_hours_data)
        total_hours = sum(data['total_hours'] for data in work_hours_data.values())
        all_tasks = []
        project_hours_summary = {}

        for date_str, date_data in sorted(work_hours_data.items()):
            for project_path, project_data in date_data['projects'].items():
                project_name = project_data['project_name']
                if project_name not in project_hours_summary:
                    project_hours_summary[project_name] = 0
                project_hours_summary[project_name] += project_data['total_hours']

                for task in project_data['tasks']:
                    all_tasks.append({
                        **task,
                        'date': date_str,
                        'project': project_name
                    })

        # 概览
        lines.append("## 📊 工时概览\n\n")
        lines.append(f"- **工作天数**: {total_work_days} 天\n")
        lines.append(f"- **总工时**: {total_hours:.1f} 小时\n")
        if total_work_days > 0:
            lines.append(f"- **日均工时**: {total_hours / total_work_days:.1f} 小时\n")
        lines.append(f"- **总任务数**: {len(all_tasks)} 个\n")
        lines.append("\n---\n\n")

        # 按项目统计
        if project_hours_summary:
            lines.append("## 📦 项目工时分布\n\n")
            lines.append("| 项目名称 | 总工时(小时) | 占比 | 任务数 |\n")
            lines.append("|---------|------------|------|-------|\n")

            # 统计每个项目的任务数
            project_task_count = {}
            for task in all_tasks:
                project = task['project']
                project_task_count[project] = project_task_count.get(project, 0) + 1

            for project_name, hours in sorted(project_hours_summary.items(), key=lambda x: x[1], reverse=True):
                percentage = (hours / total_hours * 100) if total_hours > 0 else 0
                task_count = project_task_count.get(project_name, 0)
                lines.append(f"| {project_name} | {hours:.1f} | {percentage:.1f}% | {task_count} |\n")

            lines.append("\n---\n\n")

        # 如果是单日，显示详细表格
        if len(work_hours_data) == 1:
            date_str = list(work_hours_data.keys())[0]
            lines.append(format_work_hours_table(work_hours_data[date_str]))

        # 如果是多日，按日期显示
        else:
            lines.append("## 📅 每日工时明细\n\n")
            for date_str in sorted(work_hours_data.keys()):
                date_data = work_hours_data[date_str]
                lines.append(f"### {format_date_chinese(date_str)} ({date_str})\n\n")
                lines.append(format_work_hours_table(date_data))
                lines.append("\n")

    except Exception as e:
        logger.error(f"生成工时报告时出错: {str(e)}")
        lines.append(f"\n**错误**: 生成工时报告时出现错误: {str(e)}\n")
        import traceback
        lines.append(f"\n```\n{traceback.format_exc()}\n```\n")

    return ''.join(lines)


def generate_statistics_report(all_results, author_name, since_date=None, until_date=None):
    """
    生成包含统计和评分的报告
    
    Args:
        all_results: 按项目分组的提交字典
        author_name: 提交者姓名
        since_date: 起始日期（可选）
        until_date: 结束日期（可选）
    
    Returns:
        str: Markdown 格式的统计报告内容
    """
    lines = []
    
    # 标题
    lines.append(f"# {author_name} - 代码统计与评分报告\n")
    lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    lines.append(f"**提交者**: {author_name}\n")
    
    # 日期范围
    if since_date and until_date:
        lines.append(f"**统计时间范围**: {since_date} 至 {until_date}\n")
    elif since_date:
        lines.append(f"**起始日期**: {since_date}\n")
    elif until_date:
        lines.append(f"**结束日期**: {until_date}\n")
    
    lines.append("\n---\n\n")
    
    # 计算代码统计（可能较慢，添加异常处理）
    code_stats = None
    try:
        logger.info("正在计算代码行数统计（可能需要一些时间）...")
        code_stats = calculate_code_statistics(all_results, since_date, until_date)
        logger.info("代码行数统计计算完成")
    except Exception as e:
        logger.warning(f"计算代码行数统计时出错: {str(e)}")
        logger.warning("将跳过代码行数统计，继续生成评分报告")
        # 创建一个默认的统计结果
        total_commits = sum(len(result['commits']) for result in all_results.values())
        code_stats = {
            'total_additions': 0,
            'total_deletions': 0,
            'net_lines': 0,
            'total_commits': total_commits,
            'commits_with_stats': 0,
            'avg_lines_per_commit': 0,
            'stats_availability': 0
        }
    
    # 代码行数统计
    lines.append("## 📊 代码行数统计\n\n")
    if code_stats['commits_with_stats'] > 0:
        lines.append(f"- **总新增行数**: {code_stats['total_additions']:,}\n")
        lines.append(f"- **总删除行数**: {code_stats['total_deletions']:,}\n")
        lines.append(f"- **净增行数**: {code_stats['net_lines']:,}\n")
        lines.append(f"- **总提交数**: {code_stats['total_commits']}\n")
        lines.append(f"- **有统计信息的提交数**: {code_stats['commits_with_stats']}\n")
        lines.append(f"- **平均每次提交代码行数**: {code_stats['avg_lines_per_commit']}\n")
        lines.append(f"- **统计信息可用率**: {code_stats['stats_availability']:.1%}\n")
    else:
        lines.append(f"- **总提交数**: {code_stats['total_commits']}\n")
        lines.append("- **代码行数统计**: 暂不可用（需要API权限或API调用失败）\n")
        lines.append("- **提示**: 代码行数统计需要额外的API调用，可能因为权限不足或网络问题而无法获取\n")
    lines.append("\n---\n\n")

    # 注意：本地评分系统已移除，如需评分功能请使用AI分析报告
    lines.append("**提示**: 本报告不包含评分信息。如需详细的工作分析和评分，请使用 `--ai-analysis` 生成AI分析报告。\n\n")

    return ''.join(lines)


def generate_all_reports(all_results, author_name, output_dir, since_date=None, until_date=None, 
                         generate_statistics=True, generate_daily=True, generate_html=True, 
                         generate_png=True, logger_func=None):
    """
    批量生成所有格式的报告
    
    Args:
        all_results: 按项目分组的提交字典
        author_name: 提交者姓名
        output_dir: 输出目录
        since_date: 起始日期（可选）
        until_date: 结束日期（可选）
        generate_statistics: 是否生成统计报告
        generate_daily: 是否生成开发日报
        generate_html: 是否生成HTML格式
        generate_png: 是否生成PNG图片
        logger_func: 日志输出函数（可选）
    
    Returns:
        dict: 生成的文件路径字典
    """
    import os
    from pathlib import Path
    from datetime import datetime
    
    if logger_func:
        log = logger_func
    else:
        log = logger.info
    
    # 确保输出目录存在
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 确定文件前缀
    if since_date and until_date and since_date == until_date:
        date_prefix = since_date
    else:
        date_prefix = datetime.now().strftime('%Y-%m-%d')
    
    generated_files = {}
    
    # 1. 生成统计报告
    if generate_statistics:
        try:
            log("正在生成统计报告...")
            stats_content = generate_statistics_report(
                all_results, author_name, since_date, until_date
            )
            stats_file = output_path / f"{date_prefix}_statistics.md"
            with open(stats_file, 'w', encoding='utf-8') as f:
                f.write(stats_content)
            generated_files['statistics'] = str(stats_file)
            log(f"✓ 统计报告已保存: {stats_file}")
        except Exception as e:
            log(f"✗ 生成统计报告失败: {str(e)}")
            generated_files['statistics'] = None
    
    # 2. 生成开发日报
    daily_file = None
    if generate_daily:
        try:
            log("正在生成开发日报...")
            daily_content = generate_daily_report(
                all_results, author_name, since_date, until_date
            )
            daily_file = output_path / f"{date_prefix}_daily_report.md"
            with open(daily_file, 'w', encoding='utf-8') as f:
                f.write(daily_content)
            generated_files['daily_report'] = str(daily_file)
            log(f"✓ 开发日报已保存: {daily_file}")
        except Exception as e:
            log(f"✗ 生成开发日报失败: {str(e)}")
            generated_files['daily_report'] = None
    
    # 3. 生成HTML格式（需要基于日报）
    html_file = None
    if generate_html and daily_file and daily_file.exists():
        try:
            log("正在生成HTML格式...")
            # 尝试导入 generate_report_image 模块
            try:
                from generate_report_image import parse_daily_report, generate_html_report
                data = parse_daily_report(str(daily_file))
                html_file = output_path / f"{date_prefix}_daily_report.html"
                generate_html_report(data, str(html_file))
                generated_files['html'] = str(html_file)
                log(f"✓ HTML文件已保存: {html_file}")
            except ImportError:
                log("⚠ 无法导入 generate_report_image 模块，跳过HTML生成")
                generated_files['html'] = None
            except Exception as e:
                log(f"✗ 生成HTML失败: {str(e)}")
                generated_files['html'] = None
        except Exception as e:
            log(f"✗ 生成HTML失败: {str(e)}")
            generated_files['html'] = None
    
    # 4. 生成PNG图片（需要基于HTML）
    if generate_png and html_file and html_file.exists():
        try:
            log("正在生成PNG图片...")
            try:
                from generate_report_image import html_to_image_chrome
                png_file = output_path / f"{date_prefix}_daily_report.png"
                if html_to_image_chrome(str(html_file), str(png_file)):
                    generated_files['png'] = str(png_file)
                    log(f"✓ PNG图片已保存: {png_file}")
                else:
                    log("⚠ PNG图片生成失败（可能需要Chrome浏览器）")
                    generated_files['png'] = None
            except ImportError:
                log("⚠ 无法导入 generate_report_image 模块，跳过PNG生成")
                generated_files['png'] = None
            except Exception as e:
                log(f"✗ 生成PNG失败: {str(e)}")
                generated_files['png'] = None
        except Exception as e:
            log(f"✗ 生成PNG失败: {str(e)}")
            generated_files['png'] = None
    
    log(f"批量生成完成！共生成 {len([f for f in generated_files.values() if f])} 个文件")
    return generated_files


def generate_ai_analysis_report(analysis_result, author_name, since_date=None, until_date=None):
    """
    生成AI分析报告
    
    Args:
        analysis_result: AI分析结果字典
        author_name: 提交者姓名
        since_date: 起始日期（可选）
        until_date: 结束日期（可选）
    
    Returns:
        str: Markdown格式的AI分析报告
    """
    lines = []
    
    # 标题
    lines.append(f"# {author_name} - AI智能分析报告\n")
    lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    lines.append(f"**提交者**: {author_name}\n")
    lines.append(f"**分析方式**: 🤖 AI智能分析（使用AI模型进行深度分析）\n")
    
    # 从analysis_result中提取AI服务信息（如果存在）
    if 'ai_service' in analysis_result:
        lines.append(f"**AI服务**: {analysis_result.get('ai_service', '未知')}\n")
    if 'ai_model' in analysis_result:
        lines.append(f"**AI模型**: {analysis_result.get('ai_model', '未知')}\n")
    
    if since_date and until_date:
        lines.append(f"**分析时间范围**: {since_date} 至 {until_date}\n")
    elif since_date:
        lines.append(f"**起始日期**: {since_date}\n")
    elif until_date:
        lines.append(f"**结束日期**: {until_date}\n")
    
    lines.append("\n---\n\n")
    
    # 检查是否有错误
    if 'error' in analysis_result:
        lines.append("## ⚠️ 分析错误\n\n")
        lines.append(f"AI分析过程中出现错误: {analysis_result['error']}\n\n")
        if 'raw_response' in analysis_result:
            lines.append("### 原始响应\n\n")
            lines.append(f"```\n{analysis_result['raw_response']}\n```\n")
        return ''.join(lines)
    
    # 检查是否有原始响应但无法解析（这种情况也应该显示原始响应）
    if 'raw_response' in analysis_result and not any(
        dim in analysis_result and isinstance(analysis_result[dim], dict) 
        for dim in ['code_quality', 'work_pattern', 'tech_stack', 'problem_solving', 'innovation', 'collaboration']
    ):
        lines.append("## ⚠️ 解析警告\n\n")
        lines.append("AI返回的响应无法解析为结构化JSON格式，以下是原始响应：\n\n")
        lines.append("### 原始响应\n\n")
        lines.append(f"```\n{analysis_result['raw_response']}\n```\n\n")
        lines.append("**提示**: 这可能是由于AI返回的格式不符合预期，或者响应中包含无法解析的内容。\n")
        return ''.join(lines)
    
    # 执行摘要
    lines.append("## 📋 执行摘要\n\n")
    
    # 计算总体评分
    dimensions = ['code_quality', 'work_pattern', 'tech_stack', 'problem_solving', 'innovation', 'collaboration']
    scores = []
    for dim in dimensions:
        if dim in analysis_result and isinstance(analysis_result[dim], dict):
            score = analysis_result[dim].get('score', 0)
            scores.append(score)
    
    if scores:
        overall_score = sum(scores) / len(scores)
        lines.append(f"**总体评分**: {overall_score:.1f} / 100\n\n")
        lines.append("**各维度评分**:\n")
        for dim in dimensions:
            if dim in analysis_result and isinstance(analysis_result[dim], dict):
                score = analysis_result[dim].get('score', 0)
                dim_name = {
                    'code_quality': '代码质量',
                    'work_pattern': '工作模式',
                    'tech_stack': '技术栈',
                    'problem_solving': '问题解决能力',
                    'innovation': '创新性',
                    'collaboration': '团队协作'
                }.get(dim, dim)
                lines.append(f"- {dim_name}: {score:.1f} / 100\n")
        lines.append("\n")
    
    lines.append("---\n\n")
    
    # 详细分析
    lines.append("## 🔍 详细分析\n\n")
    
    dimension_names = {
        'code_quality': '代码质量评估',
        'work_pattern': '工作模式分析',
        'tech_stack': '技术栈评估',
        'problem_solving': '问题解决能力',
        'innovation': '创新性分析',
        'collaboration': '团队协作'
    }
    
    for dim in dimensions:
        if dim in analysis_result and isinstance(analysis_result[dim], dict):
            dim_data = analysis_result[dim]
            dim_name = dimension_names.get(dim, dim)
            score = dim_data.get('score', 0)
            
            lines.append(f"### {dim_name}: {score:.1f} / 100\n\n")
            
            # 详细分析
            if 'analysis' in dim_data:
                lines.append(f"**分析**:\n{dim_data['analysis']}\n\n")
            
            # 优势
            if 'strengths' in dim_data and dim_data['strengths']:
                lines.append("**优势**:\n")
                if isinstance(dim_data['strengths'], list):
                    for strength in dim_data['strengths']:
                        lines.append(f"- {strength}\n")
                else:
                    lines.append(f"- {dim_data['strengths']}\n")
                lines.append("\n")
            
            # 改进建议
            if 'improvements' in dim_data and dim_data['improvements']:
                lines.append("**改进建议**:\n")
                if isinstance(dim_data['improvements'], list):
                    for improvement in dim_data['improvements']:
                        lines.append(f"- {improvement}\n")
                else:
                    lines.append(f"- {dim_data['improvements']}\n")
                lines.append("\n")
            
            lines.append("---\n\n")
    
    # 如果有原始响应但无法解析
    if 'raw_response' in analysis_result and not any(dim in analysis_result for dim in dimensions):
        lines.append("## 📄 原始分析结果\n\n")
        lines.append(f"```\n{analysis_result['raw_response']}\n```\n")
    
    lines.append("\n---\n\n")
    lines.append("**注**: 本报告由AI自动生成，仅供参考。\n")
    
    return ''.join(lines)


def generate_daily_report(all_results, author_name, since_date=None, until_date=None, branch=None):
    """
    生成开发日报格式的 Markdown 文档

    Args:
        all_results: 按项目分组的提交字典
        author_name: 提交者姓名
        since_date: 起始日期（可选）
        until_date: 结束日期（可选）
        branch: 分支名称（可选，用于显示）

    Returns:
        str: Markdown 格式的日报内容
    """
    lines = []

    # 确定日期显示
    if since_date and until_date:
        if since_date == until_date:
            # 单日报告
            date_display = f"{format_date_chinese(since_date)} ({since_date})"
        else:
            # 区间报告
            date_display = format_date_range(since_date, until_date)
            date_display += f" ({since_date} 至 {until_date})"
    else:
        # 使用当前日期
        report_date = datetime.now().strftime('%Y-%m-%d')
        date_display = f"{format_date_chinese(report_date)} ({report_date})"

    # 标题
    lines.append(f"# {author_name} - 工作报告\n")
    lines.append(f"**日期**: {date_display}\n")
    lines.append(f"**提交者**: {author_name}\n")
    lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    lines.append("\n---\n\n")
    
    # 工作概览
    total_projects = len(all_results)
    total_commits = sum(len(result['commits']) for result in all_results.values())
    
    # 按类型统计
    commit_types = defaultdict(int)
    commits_by_type = defaultdict(list)
    
    # 按项目和时间组织提交
    project_commits = {}
    time_range = {'start': None, 'end': None}
    
    for project_path, result in all_results.items():
        project = result['project']
        commits = result['commits']
        
        project_commits[project_path] = {
            'project': project,
            'commits': [],
            'types': defaultdict(int)
        }
        
        for commit in commits:
            commit_type, emoji = analyze_commit_type(commit.message)
            commit_types[commit_type] += 1
            commits_by_type[commit_type].append({
                'project': project_path,
                'commit': commit
            })
            
            # 解析时间
            commit_time = commit.committed_date
            if isinstance(commit_time, str):
                time_obj = parse_iso_date(commit_time)
            else:
                time_obj = commit_time
            
            if time_range['start'] is None or time_obj < time_range['start']:
                time_range['start'] = time_obj
            if time_range['end'] is None or time_obj > time_range['end']:
                time_range['end'] = time_obj
            
            project_commits[project_path]['commits'].append({
                'commit': commit,
                'type': commit_type,
                'emoji': emoji,
                'time': time_obj
            })
            project_commits[project_path]['types'][commit_type] += 1
        
        # 按时间排序
        project_commits[project_path]['commits'].sort(key=lambda x: x['time'], reverse=True)
    
    # 工作概览
    lines.append("## 📊 工作概览\n\n")
    lines.append(f"- **涉及项目**: {total_projects} 个\n")
    lines.append(f"- **总提交数**: {total_commits} 次\n")
    
    if time_range['start'] and time_range['end']:
        start_str = time_range['start'].strftime('%H:%M')
        end_str = time_range['end'].strftime('%H:%M')
        lines.append(f"- **工作时间**: {start_str} - {end_str}\n")
    
    lines.append(f"- **工作类型分布**:\n")
    for commit_type, count in sorted(commit_types.items(), key=lambda x: x[1], reverse=True):
        emoji = analyze_commit_type('')[1] if commit_type == '其他' else commits_by_type[commit_type][0]['commit'].message
        type_emoji = analyze_commit_type(commits_by_type[commit_type][0]['commit'].message)[1] if commits_by_type[commit_type] else '📌'
        lines.append(f"  - {type_emoji} {commit_type}: {count} 次\n")
    
    lines.append("\n---\n\n")
    
    # 按项目详细工作内容
    lines.append("## 📦 工作详情\n\n")
    
    for project_path in sorted(project_commits.keys()):
        project_info = project_commits[project_path]
        project = project_info['project']
        commits = project_info['commits']
        
        lines.append(f"### {project.name} ({project_path})\n")
        lines.append(f"**项目链接**: [{project.web_url}]({project.web_url})\n")
        lines.append(f"**提交数**: {len(commits)} 次\n")
        
        # 工作类型统计
        if project_info['types']:
            type_summary_parts = []
            for t, c in sorted(project_info['types'].items(), key=lambda x: x[1], reverse=True):
                # 获取该类型的 emoji
                type_emoji = analyze_commit_type('')[1]  # 默认
                for item in commits:
                    if item['type'] == t:
                        type_emoji = item['emoji']
                        break
                type_summary_parts.append(f"{type_emoji} {t}: {c}次")
            lines.append(f"**工作类型**: {', '.join(type_summary_parts)}\n")
        
        lines.append("\n**提交记录**:\n\n")
        
        for idx, item in enumerate(commits, 1):
            commit = item['commit']
            commit_type = item['type']
            emoji = item['emoji']
            # 显示完整日期+时间，便于跨多天的日报查看
            time_str = item['time'].strftime('%Y-%m-%d %H:%M')
            
            # 获取详细commit信息
            try:
                details = get_commit_details(project, commit)
                short_message = details['short_message']
                full_message = details['full_message']
                stats = details['stats']
                changed_files = details['changed_files']
            except Exception as e:
                logger.debug(f"获取commit详情失败: {str(e)}")
                short_message = commit.message.split('\n')[0] if commit.message else ''
                full_message = commit.message or ''
                stats = None
                changed_files = []
            
            commit_id = commit.id[:8]
            commit_url = getattr(commit, 'web_url', '')
            
            lines.append(f"{idx}. **{emoji} [{commit_type}]** [{commit_id}]({commit_url}) {short_message}\n")
            lines.append(f"   - 时间: {time_str}\n")
            
            # 显示完整的commit message（如果有多行）
            if full_message and '\n' in full_message:
                # 过滤 IDE 自动追加的元数据行（如 Made-with: Cursor）
                filtered_lines = [
                    l for l in full_message.split('\n')
                    if not l.strip().lower().startswith('made-with:')
                ]
                filtered_message = '\n'.join(filtered_lines).strip()
                if filtered_message and '\n' in filtered_message:
                    indented_message = '\n   '.join(filtered_message.split('\n'))
                    lines.append(f"   - 完整提交信息:\n   ```\n   {indented_message}\n   ```\n")
            
            # 显示代码行数统计
            if stats:
                lines.append(f"   - 代码变更: +{stats.get('additions', 0)} -{stats.get('deletions', 0)} (总计: {stats.get('total', 0)} 行)\n")
            elif hasattr(commit, 'stats') and commit.stats:
                try:
                    commit_stats = commit.stats
                    if isinstance(commit_stats, dict):
                        lines.append(f"   - 代码变更: +{commit_stats.get('additions', 0)} -{commit_stats.get('deletions', 0)}\n")
                except Exception:
                    logger.debug("读取commit stats属性失败")
            
            # 显示文件变更列表（最多显示3个）
            if changed_files:
                lines.append(f"   - 变更文件 ({len(changed_files)} 个): ")
                file_paths = []
                for file_info in changed_files[:3]:
                    file_path = file_info.get('new_path') or file_info.get('old_path') or file_info.get('path', '')
                    if file_path:
                        file_paths.append(f"`{file_path}`")
                lines.append(', '.join(file_paths))
                if len(changed_files) > 3:
                    lines.append(f" 等 {len(changed_files)} 个文件")
                lines.append("\n")
        
        lines.append("\n---\n\n")
    
    # 工时分配表
    try:
        work_hours_data = calculate_work_hours(all_results, since_date, until_date, branch=branch)

        # 单日报告: 显示该日的详细工时分配表
        if since_date and until_date and since_date == until_date:
            if since_date in work_hours_data:
                lines.append(format_work_hours_table(work_hours_data[since_date]))
                lines.append("---\n\n")
        # 区间报告: 显示工时汇总
        else:
            if work_hours_data:
                lines.append("## ⏱️ 工时分配汇总\n\n")

                # 计算工作天数和总工时
                work_days = len(work_hours_data)
                total_hours = sum(data['total_hours'] for data in work_hours_data.values())

                lines.append(f"- **工作天数**: {work_days} 天\n")
                lines.append(f"- **总工时**: {total_hours:.1f} 小时\n")
                if work_days > 0:
                    lines.append(f"- **日均工时**: {total_hours / work_days:.1f} 小时\n")

                # 按项目汇总工时
                project_hours = {}
                for date_data in work_hours_data.values():
                    for project_path, project_data in date_data['projects'].items():
                        project_name = project_data['project_name']
                        if project_name not in project_hours:
                            project_hours[project_name] = 0
                        project_hours[project_name] += project_data['total_hours']

                if project_hours:
                    lines.append(f"\n**按项目分布**:\n\n")
                    lines.append("| 项目名称 | 总工时(小时) | 占比 |\n")
                    lines.append("|---------|------------|-----|\n")

                    for project_name, hours in sorted(project_hours.items(), key=lambda x: x[1], reverse=True):
                        percentage = (hours / total_hours * 100) if total_hours > 0 else 0
                        lines.append(f"| {project_name} | {hours:.1f} | {percentage:.1f}% |\n")

                lines.append("\n---\n\n")

    except Exception as e:
        logger.warning(f"生成工时分配表时出错: {str(e)}")

    # 总结
    lines.append("## 📝 工作总结\n\n")

    # 根据日期范围选择合适的文字
    if since_date and until_date and since_date == until_date:
        summary_text = "本日"
    else:
        summary_text = "本期"

    lines.append(f"{summary_text}共完成 {total_commits} 次提交，涉及 {total_projects} 个项目。")
    
    if commit_types:
        main_work = max(commit_types.items(), key=lambda x: x[1])
        lines.append(f"主要工作类型为 **{main_work[0]}**（{main_work[1]} 次）。")
    
    lines.append("\n")
    lines.append("\n---\n\n")
    
    # 添加代码统计信息
    try:
        code_stats = calculate_code_statistics(all_results, since_date, until_date)

        lines.append("## 📊 代码统计\n\n")
        if code_stats['commits_with_stats'] > 0:
            lines.append(f"- **总新增行数**: {code_stats['total_additions']:,}\n")
            lines.append(f"- **总删除行数**: {code_stats['total_deletions']:,}\n")
            lines.append(f"- **净增行数**: {code_stats['net_lines']:,}\n")
            lines.append(f"- **平均每次提交代码行数**: {code_stats['avg_lines_per_commit']}\n")
        else:
            lines.append("- **代码行数统计**: 暂不可用（需要API权限）\n")
        lines.append("\n")
    except Exception as e:
        logger.warning(f"生成代码统计信息时出错: {str(e)}")
        lines.append("## 📊 代码统计\n\n")
        lines.append("- **代码统计**: 生成时出现错误，请检查数据\n\n")
    
    return ''.join(lines)
