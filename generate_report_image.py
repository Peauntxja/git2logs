#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成日报图片
优先使用 HTML 转图片方法，保证与 HTML 显示完全一致
"""
import re
import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path

def parse_daily_report(file_path):
    """解析日报文件（支持日报格式和多项目日志格式）"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 判断是日报格式、所有项目汇总格式还是单项目日志格式
    is_daily_report = '**日期**:' in content or '✨ 功能开发:' in content
    is_all_projects = '所有项目提交汇总日志' in content or '**涉及项目数**:' in content
    
    if is_daily_report:
        # 解析日报格式
        date_match = re.search(r'\*\*日期\*\*: (.*?) \(', content)
        date = date_match.group(1) if date_match else '2025年12月12日'
        
        projects_match = re.search(r'\*\*涉及项目\*\*: (\d+) 个', content)
        projects_count = int(projects_match.group(1)) if projects_match else 0
        
        commits_match = re.search(r'\*\*总提交数\*\*: (\d+) 次', content)
        commits_count = int(commits_match.group(1)) if commits_match else 0
        
        time_match = re.search(r'\*\*工作时间\*\*: (.*)', content)
        work_time = time_match.group(1).strip() if time_match else ''
        
        # 提取工作类型
        feat_matches = re.findall(r'✨ 功能开发: (\d+) 次', content)
        bug_matches = re.findall(r'🐛 Bug修复: (\d+) 次', content)
        feat_count = int(feat_matches[0]) if feat_matches else 0
        bug_count = int(bug_matches[0]) if bug_matches else 0
        
        # 提取项目详情
        project_sections = re.findall(r'### (.*?) \(([^)]+)\)\n\*\*项目链接\*\*.*?\n\*\*提交数\*\*: (\d+) 次', content, re.DOTALL)
        projects_data = []
        for match in project_sections:
            projects_data.append({
                'name': match[0],
                'path': match[1],
                'commits': int(match[2])
            })
        
        # 提取时间线
        timeline_matches = re.findall(r'- \*\*(\d{2}:\d{2})\*\* (.) \[([^\]]+)\]', content)
        timeline_data = []
        for match in timeline_matches:
            timeline_data.append({
                'time': match[0],
                'type': match[1],
                'project': match[2]
            })
    elif is_all_projects:
        # 解析所有项目汇总日志格式
        # 提取生成时间
        time_match = re.search(r'\*\*生成时间\*\*: (.*)', content)
        gen_time = time_match.group(1).strip() if time_match else ''
        
        # 提取涉及项目数
        projects_match = re.search(r'\*\*涉及项目数\*\*: (\d+)', content)
        projects_count = int(projects_match.group(1)) if projects_match else 0
        
        # 提取总提交数
        commits_match = re.search(r'\*\*总提交数\*\*: (\d+)', content)
        commits_count = int(commits_match.group(1)) if commits_match else 0
        
        # 提取日期范围
        date_range_match = re.search(r'\*\*日期范围\*\*: (.*)', content)
        if date_range_match:
            date = date_range_match.group(1).strip()
        else:
            # 从各个日期标题提取
            date_matches = re.findall(r'## (\d{4}年\d{1,2}月\d{1,2}日) \((\d{4}-\d{2}-\d{2})\)', content)
            if date_matches:
                first_date = date_matches[0][0]
                last_date = date_matches[-1][0]
                date = f"{first_date} 至 {last_date}"
            else:
                date = gen_time.split()[0] if gen_time else '未知日期'
        
        # 提取所有项目信息
        # 格式: ### 📦 example-group/example-project
        #       **项目**: [example-project](...)
        #       **提交数**: 15
        projects_dict = {}  # 使用字典去重，key为项目路径
        
        # 方法1: 完整匹配（包含提交数）
        project_sections = re.findall(r'### 📦 (.+?)\n\*\*项目\*\*: \[([^\]]+)\]\([^\)]+\)\n\*\*提交数\*\*: (\d+)', content, re.DOTALL)
        for match in project_sections:
            project_path, project_name, commits = match
            project_path = project_path.strip()
            project_name = project_name.strip()
            
            # 如果项目已存在，累加提交数；否则新建
            if project_path in projects_dict:
                projects_dict[project_path]['commits'] += int(commits)
            else:
                projects_dict[project_path] = {
                    'name': project_name,
                    'path': project_path,
                    'commits': int(commits)
                }
        
        # 方法2: 如果方法1没找到，尝试只匹配项目名和路径，然后统计提交数
        if not projects_dict:
            project_sections = re.findall(r'### 📦 (.+?)\n\*\*项目\*\*: \[([^\]]+)\]', content, re.DOTALL)
            for match in project_sections:
                project_path, project_name = match
                project_path = project_path.strip()
                project_name = project_name.strip()
                
                # 统计该项目的提交数（查找该项目下的所有 #### 开头的提交）
                # 找到该项目的开始位置
                project_start = content.find(f'### 📦 {project_path}')
                if project_start != -1:
                    # 找到下一个项目或结束位置
                    next_project = content.find('### 📦 ', project_start + 1)
                    if next_project == -1:
                        project_section = content[project_start:]
                    else:
                        project_section = content[project_start:next_project]
                    
                    # 统计提交数
                    commits = len(re.findall(r'#### \d+\.', project_section))
                else:
                    commits = 0
                
                # 如果项目已存在，累加提交数；否则新建
                if project_path in projects_dict:
                    projects_dict[project_path]['commits'] += commits
                else:
                    projects_dict[project_path] = {
                        'name': project_name,
                        'path': project_path,
                        'commits': commits
                    }
        
        # 转换为列表
        projects_data = list(projects_dict.values())
        
        # 提取所有提交记录，分析工作类型并关联项目
        # 格式: #### 1. [hash](...) message
        #       **时间**: 15:09:09
        # 需要找到每个提交所属的项目（向上查找最近的 ### 📦）
        lines = content.split('\n')
        current_project = '未知项目'
        feat_count = 0
        bug_count = 0
        timeline_data = []
        
        for i, line in enumerate(lines):
            # 检测项目标题
            project_match = re.match(r'### 📦 (.+?)$', line)
            if project_match:
                project_path = project_match.group(1)
                # 找到项目名称
                for j in range(i, min(i+5, len(lines))):
                    name_match = re.search(r'\*\*项目\*\*: \[([^\]]+)\]', lines[j])
                    if name_match:
                        current_project = name_match.group(1)
                        break
                else:
                    current_project = project_path.split('/')[-1] if '/' in project_path else project_path
            
            # 检测提交记录
            commit_match = re.match(r'#### \d+\. \[([a-f0-9]+)\]\([^\)]+\) (.+?)$', line)
            if commit_match:
                commit_hash, message = commit_match.groups()
                message = message.strip()
                
                # 查找时间（在接下来的几行中）
                time = None
                for j in range(i+1, min(i+5, len(lines))):
                    time_match = re.search(r'\*\*时间\*\*: (\d{2}:\d{2})', lines[j])
                    if time_match:
                        time = time_match.group(1)
                        break
                
                if time:
                    # 判断提交类型
                    if message.lower().startswith('feat') or '功能' in message or '优化' in message or '增加' in message or '新增' in message:
                        feat_count += 1
                        commit_type = '✨'
                    elif message.lower().startswith('fix') or '修复' in message or 'bug' in message.lower():
                        bug_count += 1
                        commit_type = '🐛'
                    else:
                        commit_type = '📝'
                    
                    timeline_data.append({
                        'time': time,
                        'type': commit_type,
                        'project': current_project
                    })
        
        # 计算工作时间（从最早到最晚）
        if timeline_data:
            times = [item['time'] for item in timeline_data]
            times.sort()
            if len(times) > 1:
                work_time = f"{times[0]} - {times[-1]}"
            else:
                work_time = times[0] if times else ''
        else:
            work_time = ''
    
    else:
        # 解析单项目日志格式
        # 提取标题中的项目名和日期
        title_match = re.search(r'^# (.+?) - .+ 提交日志', content, re.MULTILINE)
        project_name = title_match.group(1) if title_match else '未知项目'
        
        # 提取生成时间
        time_match = re.search(r'\*\*生成时间\*\*: (.*)', content)
        gen_time = time_match.group(1).strip() if time_match else ''
        
        # 提取总提交数
        commits_match = re.search(r'\*\*总提交数\*\*: (\d+)', content)
        commits_count = int(commits_match.group(1)) if commits_match else 0
        
        # 提取日期范围（从各个日期标题）
        date_matches = re.findall(r'## (\d{4}年\d{1,2}月\d{1,2}日) \((\d{4}-\d{2}-\d{2})\)', content)
        if date_matches:
            # 使用第一个和最后一个日期
            first_date = date_matches[0][0]
            last_date = date_matches[-1][0]
            date = f"{first_date} 至 {last_date}"
        else:
            date = gen_time.split()[0] if gen_time else '未知日期'
        
        # 统计项目（只有一个项目）
        projects_data = [{
            'name': project_name,
            'path': project_name,
            'commits': commits_count
        }]
        projects_count = 1
        
        # 提取所有提交记录，分析工作类型
        commit_matches = re.findall(r'#### \d+\. \[([a-f0-9]+)\]\([^\)]+\) (.+?)\n\*\*时间\*\*: (\d{2}:\d{2})', content, re.DOTALL)
        feat_count = 0
        bug_count = 0
        timeline_data = []
        
        for commit_match in commit_matches:
            commit_hash, message, time = commit_match
            message = message.strip()
            
            # 判断提交类型
            if message.lower().startswith('feat') or '功能' in message or '优化' in message or '增加' in message:
                feat_count += 1
                commit_type = '✨'
            elif message.lower().startswith('fix') or '修复' in message or 'bug' in message.lower():
                bug_count += 1
                commit_type = '🐛'
            else:
                commit_type = '📝'
            
            timeline_data.append({
                'time': time,
                'type': commit_type,
                'project': project_name
            })
        
        # 计算工作时间（从最早到最晚）
        if timeline_data:
            times = [item['time'] for item in timeline_data]
            times.sort()
            if len(times) > 1:
                work_time = f"{times[0]} - {times[-1]}"
            else:
                work_time = times[0] if times else ''
        else:
            work_time = ''
    
    return {
        'date': date,
        'projects_count': projects_count,
        'commits_count': commits_count,
        'work_time': work_time,
        'feat_count': feat_count,
        'bug_count': bug_count,
        'projects': projects_data,
        'timeline': timeline_data
    }

def generate_html_report(data, output_file):
    """生成HTML格式的日报表格"""
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{data['date']} - MIZUKI 开发日报</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Microsoft YaHei', 'SimHei', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            min-height: 100vh;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            padding: 30px;
        }}
        h1 {{
            text-align: center;
            color: #333;
            margin-bottom: 30px;
            font-size: 32px;
            border-bottom: 3px solid #667eea;
            padding-bottom: 15px;
        }}
        .grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 30px;
        }}
        .card {{
            background: #f8f9fa;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .card h2 {{
            color: #667eea;
            margin-bottom: 15px;
            font-size: 20px;
            border-left: 4px solid #667eea;
            padding-left: 10px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }}
        th {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: bold;
        }}
        td {{
            padding: 10px 12px;
            border-bottom: 1px solid #ddd;
        }}
        tr:nth-child(even) {{
            background-color: #f8f9fa;
        }}
        tr:hover {{
            background-color: #e9ecef;
        }}
        .stat-box {{
            display: flex;
            justify-content: space-around;
            margin-top: 15px;
        }}
        .stat-item {{
            text-align: center;
            padding: 15px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            flex: 1;
            margin: 0 5px;
        }}
        .stat-number {{
            font-size: 32px;
            font-weight: bold;
            color: #667eea;
        }}
        .stat-label {{
            font-size: 14px;
            color: #666;
            margin-top: 5px;
        }}
        .chart-container {{
            margin-top: 20px;
            text-align: center;
        }}
        .bar-chart {{
            display: flex;
            align-items: flex-end;
            justify-content: space-around;
            height: 200px;
            margin-top: 20px;
        }}
        .bar {{
            width: 80px;
            background: linear-gradient(to top, #667eea, #764ba2);
            border-radius: 5px 5px 0 0;
            position: relative;
            margin: 0 10px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
        }}
        .bar-label {{
            position: absolute;
            top: -25px;
            left: 50%;
            transform: translateX(-50%);
            font-weight: bold;
            color: #333;
        }}
        .bar-value {{
            position: absolute;
            bottom: -25px;
            left: 50%;
            transform: translateX(-50%);
            font-weight: bold;
            color: #667eea;
        }}
        .full-width {{
            grid-column: 1 / -1;
        }}
        .pie-chart {{
            display: flex;
            justify-content: center;
            align-items: center;
            margin-top: 20px;
        }}
        .pie-segment {{
            width: 150px;
            height: 150px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
            font-size: 18px;
            margin: 0 10px;
            box-shadow: 0 4px 10px rgba(0,0,0,0.2);
        }}
        .feat {{
            background: linear-gradient(135deg, #4CAF50, #45a049);
        }}
        .bug {{
            background: linear-gradient(135deg, #F44336, #d32f2f);
        }}
        .timeline {{
            /* 移除高度限制，让所有内容都显示，方便截图 */
            /* max-height: 400px; */
            /* overflow-y: auto; */
        }}
        .timeline-item {{
            padding: 10px;
            border-left: 3px solid #667eea;
            margin-bottom: 10px;
            background: #f8f9fa;
            border-radius: 5px;
        }}
        .time {{
            font-weight: bold;
            color: #667eea;
        }}
        .type {{
            display: inline-block;
            width: 25px;
            text-align: center;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{data['date']} - MIZUKI 开发日报</h1>
        
        <div class="grid">
            <div class="card">
                <h2>📊 工作概览</h2>
                <table>
                    <tr>
                        <th>项目</th>
                        <th>数值</th>
                    </tr>
                    <tr>
                        <td>涉及项目</td>
                        <td><strong>{data['projects_count']} 个</strong></td>
                    </tr>
                    <tr>
                        <td>总提交数</td>
                        <td><strong>{data['commits_count']} 次</strong></td>
                    </tr>
                    <tr>
                        <td>工作时间</td>
                        <td><strong>{data['work_time']}</strong></td>
                    </tr>
                    <tr>
                        <td>功能开发</td>
                        <td><strong>{data['feat_count']} 次</strong></td>
                    </tr>
                    <tr>
                        <td>Bug修复</td>
                        <td><strong>{data['bug_count']} 次</strong></td>
                    </tr>
                </table>
            </div>
            
            <div class="card">
                <h2>📦 项目统计</h2>
                <table>
                    <tr>
                        <th>项目名称</th>
                        <th>项目路径</th>
                        <th>提交数</th>
                    </tr>
"""
    
    for project in data['projects']:
        html += f"""
                    <tr>
                        <td>{project['name']}</td>
                        <td>{project['path']}</td>
                        <td><strong>{project['commits']} 次</strong></td>
                    </tr>
"""
    
    html += """
                </table>
            </div>
            
            <div class="card">
                <h2>📋 工作类型分布</h2>
                <div class="pie-chart">
                    <div class="pie-segment feat">
                        <div>
                            <div>功能开发</div>
                            <div style="font-size: 24px;">{}</div>
                        </div>
                    </div>
                    <div class="pie-segment bug">
                        <div>
                            <div>Bug修复</div>
                            <div style="font-size: 24px;">{}</div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <h2>📈 项目提交数量对比</h2>
                <div class="bar-chart">
""".format(data['feat_count'], data['bug_count'])
    
    max_commits = max([p['commits'] for p in data['projects']]) if data['projects'] else 1
    for project in data['projects']:
        height = (project['commits'] / max_commits) * 150
        html += f"""
                    <div class="bar" style="height: {height}px;">
                        <div class="bar-label">{project['name']}</div>
                        <div class="bar-value">{project['commits']}</div>
                    </div>
"""
    
    html += """
                </div>
            </div>
            
            <div class="card full-width">
                <h2>⏰ 工作时间线</h2>
                <div class="timeline">
"""
    
    for item in data['timeline']:  # 显示所有时间线条目
        type_emoji = '✨' if item['type'] == '✨' else '🐛'
        html += f"""
                    <div class="timeline-item">
                        <span class="time">{item['time']}</span>
                        <span class="type">{type_emoji}</span>
                        <span>{item['project']}</span>
                    </div>
"""
    
    html += """
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f'HTML日报已生成: {output_file}')

def html_to_image_chrome(html_file, output_file):
    """使用 Chrome headless 将 HTML 转换为图片"""
    import os
    import subprocess
    from pathlib import Path
    
    html_path = Path(html_file).absolute()
    output_path = Path(output_file).absolute()
    
    # 检查 Chrome 是否在常见位置
    chrome_paths = [
        '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '/Applications/Chromium.app/Contents/MacOS/Chromium',
    ]
    
    chrome_path = None
    for path in chrome_paths:
        if os.path.exists(path):
            chrome_path = path
            break
    
    if not chrome_path:
        return False
    
    try:
        # 使用 Chrome 的 headless 模式截图
        # 增加窗口高度以容纳更多内容（特别是时间线）
        # 使用 --virtual-time-budget 等待页面完全加载和渲染
        cmd = [
            chrome_path,
            '--headless',
            '--disable-gpu',
            '--window-size=1600,6000',  # 增加高度以容纳完整的时间线
            '--virtual-time-budget=3000',  # 等待页面完全加载（3秒）
            '--run-all-compositor-stages-before-draw',  # 等待所有渲染完成
            '--screenshot=' + str(output_path),
            f'file://{html_path}'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0 and output_path.exists():
            return True
        return False
            
    except Exception:
        return False

def find_markdown_files(path):
    """查找路径中的 Markdown 文件（过滤掉文档文件）"""
    path_obj = Path(path)
    
    # 排除的文档文件名
    exclude_files = {'README.md', 'CHANGELOG.md', 'TEST_RESULTS.md', 'LICENSE.md'}
    
    if path_obj.is_file():
        # 如果是文件，直接返回（如果不是排除的文件）
        if path_obj.suffix.lower() == '.md' and path_obj.name not in exclude_files:
            return [path_obj]
        else:
            return []
    elif path_obj.is_dir():
        # 如果是目录，查找所有 .md 文件
        all_md_files = list(path_obj.glob('*.md'))
        # 过滤掉文档文件
        md_files = [f for f in all_md_files if f.name not in exclude_files]
        # 去重并排序
        return sorted(set(md_files))
    else:
        return []

if __name__ == '__main__':
    import sys
    from pathlib import Path
    
    # 确定输入和输出文件
    input_path = None
    md_files = []
    
    if len(sys.argv) > 1:
        input_path = sys.argv[1]
        md_files = find_markdown_files(input_path)
    else:
        # 默认查找当前目录的日报文件
        today = datetime.now().strftime('%Y-%m-%d')
        default_files = [
            Path(f'{today}_daily_report.md'),
            Path(f'{today}_commits.md'),
            Path(f'{today}_all_projects.md')
        ]
        md_files = [f for f in default_files if f.exists()]
    
    if not md_files:
        if input_path:
            if Path(input_path).is_dir():
                print(f"错误: 在目录 '{input_path}' 中未找到 Markdown 文件")
                print("请确保目录中包含 .md 格式的日报文件")
            else:
                print(f"错误: 文件 '{input_path}' 不存在或不是 Markdown 文件")
        else:
            print("错误: 未找到 Markdown 文件")
            print("使用方法:")
            print("  python3 generate_report_image.py <markdown文件或目录>")
            print("  python3 generate_report_image.py 2025-12-12_daily_report.md")
            print("  python3 generate_report_image.py /path/to/directory")
        sys.exit(1)
    
    # 处理所有找到的 Markdown 文件
    for md_file in md_files:
        print(f"\n处理文件: {md_file}")
        print("=" * 60)
        
        try:
            # 解析 Markdown 并生成 HTML
            data = parse_daily_report(str(md_file))
            base_name = md_file.stem
            html_file = md_file.parent / f"{base_name}.html"
            png_file = md_file.parent / f"{base_name}.png"
            
            generate_html_report(data, str(html_file))
            
            # 尝试将 HTML 转换为图片
            print(f'\n正在将 HTML 转换为图片...')
            if html_to_image_chrome(str(html_file), str(png_file)):
                print(f'✓ 图片已生成: {png_file} (与 HTML 显示完全一致)')
            else:
                print(f'⚠ HTML 转图片失败，但 HTML 文件已生成: {html_file}')
                print('   您可以手动在浏览器中打开 HTML 文件并截图')
        
        except Exception as e:
            print(f'✗ 处理文件 {md_file} 时出错: {str(e)}')
            import traceback
            traceback.print_exc()
            continue
    
    print("\n" + "=" * 60)
    print(f"处理完成，共处理 {len(md_files)} 个文件")

