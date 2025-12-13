#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将 HTML 日报转换为图片
使用 Playwright 渲染 HTML 并截图，保证与浏览器显示一致
"""
import os
import sys
from pathlib import Path

def html_to_image(html_file, output_file, width=1600, height=None):
    """将 HTML 文件转换为图片"""
    try:
        from playwright.sync_api import sync_playwright
        
        html_path = Path(html_file).absolute()
        
        if not html_path.exists():
            print(f"错误: HTML 文件不存在: {html_file}")
            return False
        
        print(f"正在使用 Playwright 渲染 HTML: {html_path}")
        
        with sync_playwright() as p:
            # 启动浏览器
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            # 设置视口大小
            if height:
                page.set_viewport_size({"width": width, "height": height})
            else:
                page.set_viewport_size({"width": width, "height": 2400})
            
            # 加载 HTML 文件
            page.goto(f"file://{html_path}")
            
            # 等待页面加载完成
            page.wait_for_load_state("networkidle")
            
            # 等待一下确保所有内容都渲染完成
            page.wait_for_timeout(1000)
            
            # 截图
            page.screenshot(path=output_file, full_page=True)
            
            browser.close()
            
            print(f"✓ 图片已生成: {output_file}")
            return True
            
    except ImportError:
        print("错误: 未安装 playwright")
        print("请运行以下命令安装:")
        print("  pip3 install playwright")
        print("  playwright install chromium")
        return False
    except Exception as e:
        print(f"错误: {str(e)}")
        return False

if __name__ == '__main__':
    html_file = '2025-12-12_daily_report.html'
    output_file = '2025-12-12_daily_report.png'
    
    if len(sys.argv) > 1:
        html_file = sys.argv[1]
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    
    success = html_to_image(html_file, output_file)
    if not success:
        sys.exit(1)

