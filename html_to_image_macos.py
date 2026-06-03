#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
已废弃：macOS 旧版多后端 HTML 转图脚本。

请改用:
  python3 image_converter.py <html> [png]
  python3 generate_report_image.py <markdown>
"""
import sys
from pathlib import Path

from image_converter import convert_html_to_image


def html_to_image_chrome_headless(html_file, output_file):
    """向后兼容，委托 image_converter。"""
    return convert_html_to_image(html_file, output_file)


if __name__ == "__main__":
    html_file = sys.argv[1] if len(sys.argv) > 1 else "2025-12-12_daily_report.html"
    output_file = sys.argv[2] if len(sys.argv) > 2 else str(Path(html_file).with_suffix(".png"))

    print("提示: html_to_image_macos.py 已废弃，请使用 image_converter.py")
    ok = convert_html_to_image(html_file, output_file)
    if ok:
        print(f"✓ 图片已生成: {output_file}")
    sys.exit(0 if ok else 1)
