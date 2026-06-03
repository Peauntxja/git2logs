#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将 HTML 日报转换为图片（薄封装，实现见 image_converter.convert_html_to_image）。

保留 html_to_image(html, out, width, height) 签名以兼容旧调用；height 非空时仍走 Playwright 视口逻辑。
"""
import sys
from pathlib import Path


def html_to_image(html_file, output_file, width=1600, height=None):
    """将 HTML 文件转换为图片。"""
    if height is not None:
        return _html_to_image_playwright_viewport(html_file, output_file, width, height)

    from image_converter import convert_html_to_image
    return convert_html_to_image(html_file, output_file, width=width)


def _html_to_image_playwright_viewport(html_file, output_file, width, height):
    """height 指定时沿用原 Playwright 固定视口行为。"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("错误: 未安装 playwright")
        print("请运行: pip3 install playwright && playwright install chromium")
        return False

    html_path = Path(html_file).absolute()
    if not html_path.exists():
        print(f"错误: HTML 文件不存在: {html_file}")
        return False

    print(f"正在使用 Playwright 渲染 HTML: {html_path}")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_viewport_size({"width": width, "height": height})
            page.goto(f"file://{html_path}")
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(1000)
            page.screenshot(path=output_file, full_page=True)
            browser.close()
        print(f"✓ 图片已生成: {output_file}")
        return True
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

    if not html_to_image(html_file, output_file):
        sys.exit(1)
