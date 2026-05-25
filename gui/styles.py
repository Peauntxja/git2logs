"""UI 样式常量、字体、工具函数"""
import sys
import os
import math

import customtkinter as ctk


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
    """UI样式常量统一管理类"""

    colors = {
        'bg_main': "#1D1D20",
        'bg_card': "#26262A",
        'bg_surface': "#2B2B30",
        'text_primary': "#FAFAFA",
        'text_secondary': "#A1A1AA",
        'text_tertiary': "#71717A",
        'border': "#3D3D44",
        'accent': "#2E9CFF",
        'success': "#10B981",
        'warning': "#F59E0B",
        'error': "#EF4444",
        'hover': "#34343A",
        'active': "#2C2C32",
        'success_hover': "#059669",
        'error_hover': "#DC2626",
        'accent_hover': "#1E88E5",
        'sidebar_bg': "#1C1C1F",
        'sidebar_active': "#2C2C30",
        'chrome_border_light': "#EBEBEF",
        'chrome_border_dark': "#E4E4E9",
    }

    spacing = {
        'xs': 4,
        'sm': 8,
        'md': 16,
        'lg': 24,
        'xl': 32,
        'xxl': 48
    }

    radius = {
        'sm': 6,
        'md': 8,
        'lg': 12,
        'xl': 16
    }

    fonts = {
        'header': lambda: _ctk_ui_font(16, "bold"),
        'subheader': lambda: _ctk_ui_font(14, "bold"),
        'body': lambda: _ctk_ui_font(13),
        'body_bold': lambda: _ctk_ui_font(13, "bold"),
        'caption': lambda: _ctk_ui_font(11),
        'caption_bold': lambda: _ctk_ui_font(11, "bold"),
    }


def resource_path(relative_path):
    """获取资源文件的绝对路径，支持 PyInstaller 打包后的环境"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


def get_script_path(script_name):
    """获取脚本文件的路径，优先使用打包后的路径，否则使用当前目录"""
    if hasattr(sys, '_MEIPASS'):
        script_path = os.path.join(sys._MEIPASS, script_name)
        if os.path.exists(script_path):
            return script_path

    current_dir = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(current_dir, script_name)
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


_SIDEBAR_TAB_GLYPHS = {
    "GitLab配置": "配",
    "日期和输出": "日",
    "AI分析": "A",
    "Excel导出": "表",
}


def _hex_to_rgb(color_hex: str):
    h = color_hex.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def _pil_sidebar_icon(kind: str, color_hex: str, size: int = 24):
    """单色线框风侧栏图标。"""
    from PIL import Image, ImageDraw

    rgb = _hex_to_rgb(color_hex)
    fill = rgb + (255,)
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    lw = max(1, round(size / 13))
    s = float(size)
    m = round(s * 0.14)

    def rr(xy, radius, **kw):
        try:
            dr.rounded_rectangle(xy, radius=radius, **kw)
        except Exception:
            dr.rectangle(xy, **kw)

    if kind == "gear":
        cx, cy = s / 2, s / 2
        r_outer = s * 0.34
        r_inner = s * 0.17
        dr.ellipse(
            [cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer],
            outline=fill, width=lw,
        )
        dr.ellipse(
            [cx - r_inner, cy - r_inner, cx + r_inner, cy + r_inner],
            outline=fill, width=lw,
        )
        n = 6
        tooth = s * 0.11
        for i in range(n):
            a = (i * 2 * math.pi / n) - math.pi / 2
            x0 = cx + (r_outer - lw * 0.5) * math.cos(a)
            y0 = cy + (r_outer - lw * 0.5) * math.sin(a)
            x1 = cx + (r_outer + tooth) * math.cos(a)
            y1 = cy + (r_outer + tooth) * math.sin(a)
            dr.line([(x0, y0), (x1, y1)], fill=fill, width=lw)

    elif kind == "calendar":
        x0, y0 = m, round(s * 0.24)
        x1, y1 = size - m, size - m
        rr([x0, y0, x1, y1], radius=max(2, lw), outline=fill, width=lw)
        y_split = y0 + round(s * 0.15)
        dr.line([(x0 + lw, y_split), (x1 - lw, y_split)], fill=fill, width=lw)
        dr.line([(round(s * 0.34), y0), (round(s * 0.34), y0 - round(s * 0.09))], fill=fill, width=lw)
        dr.line([(round(s * 0.66), y0), (round(s * 0.66), y0 - round(s * 0.09))], fill=fill, width=lw)
        dot_r = max(1, round(s * 0.045))
        for gx, gy in (
            (0.30, 0.58), (0.50, 0.58), (0.70, 0.58),
            (0.30, 0.74), (0.50, 0.74), (0.70, 0.74),
        ):
            cx, cy = round(s * gx), round(s * gy)
            dr.ellipse([cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r], outline=fill, width=1)

    elif kind == "chip":
        body = [round(s * 0.26), round(s * 0.30), round(s * 0.74), round(s * 0.70)]
        rr(body, radius=max(2, lw + 1), outline=fill, width=lw)
        pin_h = max(2, round(s * 0.055))
        for py in (round(s * 0.40), round(s * 0.48), round(s * 0.56)):
            dr.rectangle(
                [round(s * 0.14), py, round(s * 0.24), py + pin_h],
                outline=fill, width=1,
            )
            dr.rectangle(
                [round(s * 0.76), py, round(s * 0.86), py + pin_h],
                outline=fill, width=1,
            )
        mid_y = round(s * 0.50)
        dr.line(
            [(round(s * 0.34), mid_y), (round(s * 0.66), mid_y)],
            fill=fill, width=max(1, lw - 1),
        )

    elif kind == "chart":
        base = size - m
        dr.line([(m, base), (size - m, base)], fill=fill, width=lw)
        bars = [
            [round(s * 0.24), round(s * 0.56), round(s * 0.33), base - lw],
            [round(s * 0.42), round(s * 0.40), round(s * 0.51), base - lw],
            [round(s * 0.60), round(s * 0.28), round(s * 0.69), base - lw],
        ]
        for bx in bars:
            rr(bx, radius=2, outline=fill, width=lw)
    else:
        dr.ellipse([m, m, size - m, size - m], outline=fill, width=lw)

    return im
