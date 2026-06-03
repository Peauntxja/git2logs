#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
已废弃的兼容入口：HTML → PNG 请使用 image_converter。

  python3 image_converter.py <html> [png] [width]
  python3 generate_report_image.py <daily_report.md>
"""
import sys

from image_converter import convert_html_to_image


def html_to_image(html_file, output_file, width=1600, height=None):
    """向后兼容别名，委托 convert_html_to_image（height 参数已忽略）。"""
    if height is not None:
        print("提示: height 参数已废弃，使用 image_converter 默认全页截图")
    return convert_html_to_image(html_file, output_file, width=width)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 image_converter.py <html_file> [output.png] [width]")
        print("（本文件 html_to_image.py 仅为兼容保留）")
        sys.exit(1)
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else __import__("pathlib").Path(src).with_suffix(".png")
    w = int(sys.argv[3]) if len(sys.argv) > 3 else 1600
    sys.exit(0 if convert_html_to_image(src, dst, w) else 1)
