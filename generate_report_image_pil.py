#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用PIL生成日报图片
"""
import re
from PIL import Image, ImageDraw, ImageFont
import os

def parse_daily_report(file_path):
    """解析日报文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 提取数据
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
    
    # 提取时间线数据
    timeline_matches = re.findall(r'- \*\*(\d{2}:\d{2})\*\* (.) \[([^\]]+)\]', content)
    timeline_data = []
    for match in timeline_matches:
        timeline_data.append({
            'time': match[0],
            'type': match[1],
            'project': match[2]
        })
    
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

def get_font(size, bold=False):
    """获取字体 - 优先使用支持中文的字体"""
    font_paths = [
        # macOS 中文字体
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
        # 备用字体
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Arial.ttf",
    ]
    
    for font_path in font_paths:
        try:
            import os
            if os.path.exists(font_path):
                # 对于 TTC 字体文件，可能需要指定字体索引
                if font_path.endswith('.ttc'):
                    # PingFang.ttc 索引：0=Regular, 1=Bold
                    font_index = 1 if bold else 0
                    return ImageFont.truetype(font_path, size, index=font_index)
                else:
                    return ImageFont.truetype(font_path, size)
        except Exception as e:
            continue
    
    # 如果所有字体都失败，使用默认字体
    return ImageFont.load_default()

def draw_table(draw, x, y, headers, rows, font, header_font, width=400):
    """绘制表格"""
    row_height = 35
    col_width = width // len(headers)
    
    # 绘制表头
    for i, header in enumerate(headers):
        draw.rectangle([x + i * col_width, y, x + (i + 1) * col_width, y + row_height], 
                      fill='#4A90E2', outline='#333')
        bbox = draw.textbbox((0, 0), header, font=header_font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        draw.text((x + i * col_width + col_width//2 - text_width//2, 
                  y + row_height//2 - text_height//2), 
                 header, fill='white', font=header_font)
    
    # 绘制数据行
    for row_idx, row in enumerate(rows):
        y_pos = y + row_height * (row_idx + 1)
        for col_idx, cell in enumerate(row):
            fill_color = '#F5F5F5' if row_idx % 2 == 0 else 'white'
            draw.rectangle([x + col_idx * col_width, y_pos, 
                          x + (col_idx + 1) * col_width, y_pos + row_height], 
                          fill=fill_color, outline='#ddd')
            bbox = draw.textbbox((0, 0), str(cell), font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            draw.text((x + col_idx * col_width + 10, 
                      y_pos + row_height//2 - text_height//2), 
                     str(cell), fill='#333', font=font)
    
    return y + row_height * (len(rows) + 1)

def draw_timeline(draw, x, y, timeline_data, font, small_font, width=1500):
    """绘制时间线"""
    row_height = 35
    max_items = min(len(timeline_data), 16)  # 最多显示16条
    
    # 绘制表头
    headers = ['时间', '类型', '项目']
    col_widths = [120, 80, width - 200]
    
    for i, header in enumerate(headers):
        draw.rectangle([x + sum(col_widths[:i]), y, 
                       x + sum(col_widths[:i+1]), y + row_height], 
                      fill='#4A90E2', outline='#333')
        bbox = draw.textbbox((0, 0), header, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        draw.text((x + sum(col_widths[:i]) + col_widths[i]//2 - text_width//2, 
                  y + row_height//2 - text_height//2), 
                 header, fill='white', font=font)
    
    # 绘制数据行
    for row_idx in range(max_items):
        item = timeline_data[row_idx]
        y_pos = y + row_height * (row_idx + 1)
        
        # 时间
        fill_color = '#F5F5F5' if row_idx % 2 == 0 else 'white'
        draw.rectangle([x, y_pos, x + col_widths[0], y_pos + row_height], 
                      fill=fill_color, outline='#ddd')
        bbox = draw.textbbox((0, 0), item['time'], font=font)
        text_height = bbox[3] - bbox[1]
        draw.text((x + col_widths[0]//2 - (bbox[2] - bbox[0])//2, 
                  y_pos + row_height//2 - text_height//2), 
                 item['time'], fill='#667eea', font=font)
        
        # 类型
        draw.rectangle([x + col_widths[0], y_pos, 
                       x + col_widths[0] + col_widths[1], y_pos + row_height], 
                      fill=fill_color, outline='#ddd')
        type_text = '功能' if item['type'] == '✨' else 'Bug'
        bbox = draw.textbbox((0, 0), type_text, font=font)
        text_height = bbox[3] - bbox[1]
        draw.text((x + col_widths[0] + col_widths[1]//2 - (bbox[2] - bbox[0])//2, 
                  y_pos + row_height//2 - text_height//2), 
                 type_text, fill='#333', font=font)
        
        # 项目
        draw.rectangle([x + col_widths[0] + col_widths[1], y_pos, 
                       x + width, y_pos + row_height], 
                      fill=fill_color, outline='#ddd')
        # 处理长项目名
        project_text = item['project']
        bbox = draw.textbbox((0, 0), project_text, font=small_font)
        if bbox[2] - bbox[0] > col_widths[2] - 20:
            # 截断过长的文本
            while bbox[2] - bbox[0] > col_widths[2] - 20 and len(project_text) > 0:
                project_text = project_text[:-1]
                bbox = draw.textbbox((0, 0), project_text + '...', font=small_font)
            project_text += '...'
        bbox = draw.textbbox((0, 0), project_text, font=small_font)
        text_height = bbox[3] - bbox[1]
        draw.text((x + col_widths[0] + col_widths[1] + 10, 
                  y_pos + row_height//2 - text_height//2), 
                 project_text, fill='#333', font=small_font)
    
    return y + row_height * (max_items + 1)

def generate_image(data, output_file):
    """生成图片"""
    # 计算所需高度（包含时间线）
    timeline_items = len(data.get('timeline', []))
    timeline_rows = min(timeline_items, 16) if timeline_items > 0 else 0
    timeline_height = timeline_rows * 35 + 100 if timeline_rows > 0 else 0
    # 创建图片 - 增加高度以容纳时间线
    width, height = 1600, int(3000 + timeline_height)
    img = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(img)
    
    # 字体
    title_font = get_font(36, bold=True)
    header_font = get_font(18, bold=True)
    normal_font = get_font(14)
    small_font = get_font(12)
    
    y = 50
    
    # 标题
    title = f"{data['date']} - MIZUKI 开发日报"
    bbox = draw.textbbox((0, 0), title, font=title_font)
    title_width = bbox[2] - bbox[0]
    draw.text(((width - title_width) // 2, y), title, fill='#333', font=title_font)
    y += 80
    
    # 工作概览表格
    draw.text((50, y), "工作概览", fill='#667eea', font=header_font)
    y += 40
    
    overview_headers = ['项目', '数值']
    overview_rows = [
        ['涉及项目', f"{data['projects_count']} 个"],
        ['总提交数', f"{data['commits_count']} 次"],
        ['工作时间', data['work_time']],
        ['功能开发', f"{data['feat_count']} 次"],
        ['Bug修复', f"{data['bug_count']} 次"]
    ]
    y = draw_table(draw, 50, y, overview_headers, overview_rows, normal_font, header_font, 500)
    y += 40
    
    # 项目统计表格
    draw.text((50, y), "项目统计", fill='#667eea', font=header_font)
    y += 40
    
    project_headers = ['项目名称', '项目路径', '提交数']
    project_rows = [[p['name'], p['path'], f"{p['commits']} 次"] for p in data['projects']]
    y = draw_table(draw, 50, y, project_headers, project_rows, small_font, header_font, 1500)
    y += 40
    
    # 工作类型分布
    draw.text((50, y), "工作类型分布", fill='#667eea', font=header_font)
    y += 50
    
    # 绘制简单的饼图表示
    total = data['feat_count'] + data['bug_count']
    if total > 0:
        feat_percent = (data['feat_count'] / total) * 100
        bug_percent = (data['bug_count'] / total) * 100
        
        # 功能开发
        draw.rectangle([50, y, 250, y + 100], fill='#4CAF50', outline='#333')
        draw.text((60, y + 10), "功能开发", fill='white', font=header_font)
        draw.text((60, y + 40), f"{data['feat_count']} 次", fill='white', font=normal_font)
        draw.text((60, y + 65), f"{feat_percent:.1f}%", fill='white', font=normal_font)
        
        # Bug修复
        draw.rectangle([300, y, 500, y + 100], fill='#F44336', outline='#333')
        draw.text((310, y + 10), "Bug修复", fill='white', font=header_font)
        draw.text((310, y + 40), f"{data['bug_count']} 次", fill='white', font=normal_font)
        draw.text((310, y + 65), f"{bug_percent:.1f}%", fill='white', font=normal_font)
    
    y += 150
    
    # 项目提交数量对比（柱状图）
    draw.text((50, y), "项目提交数量对比", fill='#667eea', font=header_font)
    y += 50
    
    if data['projects']:
        max_commits = max([p['commits'] for p in data['projects']])
        bar_width = 200
        bar_spacing = 100
        bar_height = 300
        start_x = 100
        
        for i, project in enumerate(data['projects']):
            x_pos = start_x + i * (bar_width + bar_spacing)
            bar_item_height = (project['commits'] / max_commits) * bar_height if max_commits > 0 else 0
            
            # 绘制柱状图
            draw.rectangle([x_pos, y + bar_height - bar_item_height, 
                          x_pos + bar_width, y + bar_height], 
                         fill='#2196F3', outline='#333')
            
            # 标签
            bbox = draw.textbbox((0, 0), project['name'], font=small_font)
            text_width = bbox[2] - bbox[0]
            draw.text((x_pos + bar_width//2 - text_width//2, y + bar_height + 10), 
                     project['name'], fill='#333', font=small_font)
            
            # 数值
            draw.text((x_pos + bar_width//2 - 10, y + bar_height - bar_item_height - 25), 
                     str(project['commits']), fill='#333', font=normal_font)
        
        y += bar_height + 80
    
    # 工作时间线
    if data.get('timeline') and len(data['timeline']) > 0:
        draw.text((50, y), "工作时间线", fill='#667eea', font=header_font)
        y += 40
        y = draw_timeline(draw, 50, y, data['timeline'], normal_font, small_font, 1500)
        y += 20
    
    # 裁剪图片到实际内容高度（确保至少有一定高度）
    final_height = max(y + 50, 500)
    img = img.crop((0, 0, width, min(final_height, height)))
    
    # 保存图片
    img.save(output_file, 'PNG', quality=95)
    print(f'日报图片已生成: {output_file} (包含完整时间线，尺寸: {img.size[0]}x{img.size[1]})')

if __name__ == '__main__':
    try:
        data = parse_daily_report('2025-12-12_daily_report.md')
        generate_image(data, '2025-12-12_daily_report.png')
    except ImportError:
        print("需要安装 Pillow: pip3 install Pillow")
    except Exception as e:
        print(f"生成图片时出错: {str(e)}")
        print("已生成HTML文件，请在浏览器中打开 2025-12-12_daily_report.html 并截图")

