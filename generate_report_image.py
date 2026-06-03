#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CLI：将 Markdown 日报转为 HTML / PNG（实现见 report_html、image_converter）。

用法:
  python3 generate_report_image.py <markdown文件或目录>
"""
import sys
import traceback
from datetime import datetime
from pathlib import Path

from image_converter import convert_html_to_image
from report_html import find_markdown_files, generate_html_report, parse_daily_report

# 向后兼容 re-export
__all__ = [
    "parse_daily_report",
    "generate_html_report",
    "find_markdown_files",
    "html_to_image_chrome",
]


def html_to_image_chrome(html_file, output_file):
    """薄封装，调用 image_converter。"""
    return convert_html_to_image(html_file, output_file)


if __name__ == "__main__":
    input_path = None
    md_files = []

    if len(sys.argv) > 1:
        input_path = sys.argv[1]
        md_files = find_markdown_files(input_path)
    else:
        today = datetime.now().strftime("%Y-%m-%d")
        default_files = [
            Path(f"{today}_daily_report.md"),
            Path(f"{today}_commits.md"),
            Path(f"{today}_all_projects.md"),
        ]
        md_files = [f for f in default_files if f.exists()]

    if not md_files:
        if input_path:
            if Path(input_path).is_dir():
                print(f"错误: 在目录 '{input_path}' 中未找到 Markdown 文件")
            else:
                print(f"错误: 文件 '{input_path}' 不存在或不是 Markdown 文件")
        else:
            print("错误: 未找到 Markdown 文件")
            print("使用方法:")
            print("  python3 generate_report_image.py <markdown文件或目录>")
        sys.exit(1)

    for md_file in md_files:
        print(f"\n处理文件: {md_file}")
        print("=" * 60)
        try:
            data = parse_daily_report(str(md_file))
            base_name = md_file.stem
            html_file = md_file.parent / f"{base_name}.html"
            png_file = md_file.parent / f"{base_name}.png"
            generate_html_report(data, str(html_file))
            print("\n正在将 HTML 转换为图片...")
            if html_to_image_chrome(str(html_file), str(png_file)):
                print(f"✓ 图片已生成: {png_file}")
            else:
                print(f"⚠ HTML 转图片失败，HTML 已生成: {html_file}")
        except Exception as e:
            print(f"✗ 处理文件 {md_file} 时出错: {e}")
            traceback.print_exc()

    print("\n" + "=" * 60)
    print(f"处理完成，共处理 {len(md_files)} 个文件")
