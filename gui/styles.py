#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GUI 样式常量与字体/资源路径工具。"""
import os
import sys

try:
    import customtkinter as ctk
except ImportError:
    ctk = None

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _ui_font_family():
    """与 cc-switch 一致的系统无衬线栈在 Tk 中的首选族名。"""
    if sys.platform == "darwin":
        return ".SF NS Text"
    if sys.platform == "win32":
        return "Segoe UI"
    return "DejaVu Sans"


def _ctk_ui_font(size: int, weight: str = "normal"):
    fam = _ui_font_family()
    if weight in ("bold", "semibold"):
        return ctk.CTkFont(family=fam, size=size, weight="bold")
    return ctk.CTkFont(family=fam, size=size)


class UIStyles:
    """UI样式常量统一管理类 — 对齐 CodexPlusPlus shadcn/ui 深色风格"""

    colors = {
        'bg_main': "#0A0A0F",
        'bg_card': "#0A0A0F",
        'bg_surface': "#1A1A23",
        'text_primary': "#FAFAFA",
        'text_secondary': "#8B8B9E",
        'text_tertiary': "#5A5A6E",
        'border': "#1A1A23",
        'accent': "#3ECFA5",
        'success': "#3ECFA5",
        'warning': "#EAB308",
        'error': "#DC2626",
        'hover': "#141419",
        'active': "#1A1A23",
        'success_hover': "#2BA882",
        'error_hover': "#B91C1C",
        'accent_hover': "#2BA882",
        'sidebar_bg': "#0A0A0F",
        'sidebar_active': "#1A1A23",
        'chrome_border_light': "#E4E4E7",
        'chrome_border_dark': "#1A1A23",
    }

    spacing = {
        'xs': 4,
        'sm': 8,
        'md': 12,
        'lg': 16,
        'xl': 20,
        'xxl': 24,
    }

    radius = {
        'sm': 6,
        'md': 7,
        'lg': 8,
        'xl': 10,
    }

    fonts = {
        'header': lambda: _ctk_ui_font(18, "bold"),
        'subheader': lambda: _ctk_ui_font(14, "bold"),
        'body': lambda: _ctk_ui_font(13),
        'body_bold': lambda: _ctk_ui_font(13, "bold"),
        'caption': lambda: _ctk_ui_font(11),
        'caption_bold': lambda: _ctk_ui_font(11, "bold"),
    }


def resource_path(relative_path):
    """获取资源文件的绝对路径，支持 PyInstaller 打包后的环境。"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = _PROJECT_ROOT
    return os.path.join(base_path, relative_path)


def get_script_path(script_name):
    """获取脚本文件的路径，优先使用打包后的路径，否则使用项目根目录。"""
    if hasattr(sys, '_MEIPASS'):
        script_path = os.path.join(sys._MEIPASS, script_name)
        if os.path.exists(script_path):
            return script_path

    script_path = os.path.join(_PROJECT_ROOT, script_name)
    if os.path.exists(script_path):
        return script_path

    return script_name


def _resolve_monospace_font(root, size=10):
    """在常见等宽字体中选第一个系统可用的。"""
    try:
        from tkinter import font as tkfont
        families = set(tkfont.families(root))
    except Exception:
        families = set()
    for name in ("JetBrains Mono", "Menlo", "Monaco", "Consolas", "Courier New", "Courier"):
        if name in families:
            return (name, size)
    return ("Courier", size)
