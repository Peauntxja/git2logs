#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CustomTkinter GUI 启动入口。"""
import logging
import sys
import traceback

try:
    import customtkinter as ctk
except ImportError:
    ctk = None

from tkinter import messagebox

from config import GUIConfig
from gui.app import Git2LogsGUI

logger = logging.getLogger(__name__)


def main():
    """主函数 - 优化启动速度，立即显示窗口"""
    root = None
    try:
        if ctk is None:
            print("错误: 需要安装 CustomTkinter")
            print("请运行: pip install customtkinter")
            sys.exit(1)

        root = ctk.CTk()
        root.title("MIZUKI-GITLAB工具箱")
        root.minsize(GUIConfig.WINDOW_MIN_WIDTH, GUIConfig.WINDOW_MIN_HEIGHT)
        root.resizable(True, True)

        width = GUIConfig.WINDOW_DEFAULT_WIDTH
        height = GUIConfig.WINDOW_DEFAULT_HEIGHT
        x = (root.winfo_screenwidth() // 2) - (width // 2)
        y = (root.winfo_screenheight() // 2) - (height // 2)
        root.geometry(f'{width}x{height}+{x}+{y}')

        root.deiconify()
        root.lift()
        root.focus_force()
        root.update_idletasks()
        root.update()

        def create_app():
            try:
                Git2LogsGUI(root)
            except Exception as e:
                error_msg = f"界面初始化失败: {str(e)}\n\n{traceback.format_exc()}"
                print(error_msg)
                messagebox.showerror("初始化错误", error_msg)

        root.after(1, create_app)
        root.mainloop()

    except Exception as e:
        error_msg = f"程序启动失败: {str(e)}\n\n{traceback.format_exc()}"
        print(error_msg)
        try:
            if root:
                root.withdraw()
            error_root = ctk.CTk()
            error_root.withdraw()
            messagebox.showerror("启动错误", error_msg)
            error_root.destroy()
        except Exception:
            logger.debug("显示启动错误对话框失败")
        if root:
            root.destroy()
        raise


if __name__ == '__main__':
    main()
