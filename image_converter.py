#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一的 HTML 转图片模块

整合 Chrome headless 和 Playwright 两种渲染方案，
按优先级自动选择可用的转换引擎。
"""
import os
import sys
import subprocess
import logging
from pathlib import Path

from config import ImageConfig

logger = logging.getLogger(__name__)

CHROME_CANDIDATES = [
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
]

if sys.platform == 'win32':
    CHROME_CANDIDATES = [
        os.path.expandvars(r'%ProgramFiles%\Google\Chrome\Application\chrome.exe'),
        os.path.expandvars(r'%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe'),
        os.path.expandvars(r'%LocalAppData%\Google\Chrome\Application\chrome.exe'),
    ]


def _find_chrome() -> str | None:
    """在常见路径中查找 Chrome/Chromium 可执行文件"""
    for path in CHROME_CANDIDATES:
        if os.path.exists(path):
            return path
    return None


def _convert_with_chrome(html_path: Path, output_path: Path, width: int) -> bool:
    """使用 Chrome headless 模式截图"""
    chrome = _find_chrome()
    if not chrome:
        logger.debug("未找到 Chrome/Chromium，跳过 Chrome 引擎")
        return False

    logger.info("正在使用 Chrome headless 渲染: %s", html_path.name)

    cmd = [
        chrome,
        '--headless',
        '--disable-gpu',
        f'--window-size={width},{ImageConfig.CHROME_WINDOW_HEIGHT}',
        f'--virtual-time-budget={ImageConfig.CHROME_VIRTUAL_TIME_BUDGET}',
        '--run-all-compositor-stages-before-draw',
        f'--screenshot={output_path}',
        f'file://{html_path}',
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=ImageConfig.CHROME_SCREENSHOT_TIMEOUT,
        )
        if result.returncode == 0 and output_path.exists():
            logger.info("Chrome 截图成功: %s", output_path.name)
            return True

        logger.warning("Chrome 返回码 %d，stderr: %s", result.returncode, result.stderr.strip())
        return False

    except subprocess.TimeoutExpired:
        logger.warning("Chrome 截图超时（%ds）", ImageConfig.CHROME_SCREENSHOT_TIMEOUT)
        return False
    except OSError as exc:
        logger.warning("Chrome 启动失败: %s", exc)
        return False


def _convert_with_playwright(html_path: Path, output_path: Path, width: int) -> bool:
    """使用 Playwright Chromium 截图"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.debug("未安装 Playwright，跳过 Playwright 引擎")
        return False

    logger.info("正在使用 Playwright 渲染: %s", html_path.name)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_viewport_size({"width": width, "height": 2400})
            page.goto(f"file://{html_path}")
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(ImageConfig.PLAYWRIGHT_WAIT_MS)
            page.screenshot(path=str(output_path), full_page=True)
            browser.close()

        logger.info("Playwright 截图成功: %s", output_path.name)
        return True

    except Exception as exc:
        logger.warning("Playwright 截图失败: %s", exc)
        return False


def convert_html_to_image(
    html_path: str | os.PathLike,
    output_path: str | os.PathLike,
    width: int = ImageConfig.DEFAULT_WIDTH,
) -> bool:
    """将 HTML 文件转换为 PNG 图片

    按以下优先级尝试可用的渲染引擎:
      1. Chrome headless（速度快、无额外依赖）
      2. Playwright Chromium（全页面截图质量更高）

    Args:
        html_path: 输入 HTML 文件路径
        output_path: 输出 PNG 文件路径
        width: 视口宽度（像素），默认从 ImageConfig.DEFAULT_WIDTH 读取

    Returns:
        True 表示成功，False 表示所有引擎均失败
    """
    html_abs = Path(html_path).absolute()
    out_abs = Path(output_path).absolute()

    if not html_abs.exists():
        logger.error("HTML 文件不存在: %s", html_abs)
        return False

    out_abs.parent.mkdir(parents=True, exist_ok=True)

    if _convert_with_chrome(html_abs, out_abs, width):
        return True

    if _convert_with_playwright(html_abs, out_abs, width):
        return True

    logger.error("所有渲染引擎均不可用，无法生成图片")
    return False


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    if len(sys.argv) < 2:
        print("用法: python image_converter.py <html_file> [output_file] [width]")
        sys.exit(1)

    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else Path(src).with_suffix('.png')
    w = int(sys.argv[3]) if len(sys.argv) > 3 else ImageConfig.DEFAULT_WIDTH

    ok = convert_html_to_image(src, dst, w)
    sys.exit(0 if ok else 1)
