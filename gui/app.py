#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitLab 提交日志生成工具 - CustomTkinter 现代化版本
"""
import sys
import os

# 尝试导入 CustomTkinter
try:
    import customtkinter as ctk
    CTK_AVAILABLE = True
except ImportError:
    CTK_AVAILABLE = False
    print("错误: 需要安装 CustomTkinter。请运行: pip install customtkinter")
    sys.exit(1)

from tkinter import messagebox, filedialog
import threading
import queue
import traceback
from datetime import datetime

import logging

from config import AIConfig, ReportConfig, GUIConfig
from service import Git2LogsService
from models import (
    ReportParams,
    AIParams,
    ExcelParams,
    GitLabConnectionError,
    ReportGenerationError,
    AIAnalysisError,
    Git2LogsError,
)

logger = logging.getLogger(__name__)

from gui.styles import UIStyles, resource_path, get_script_path, _resolve_monospace_font, _ctk_ui_font
from gui.service_bridge import ServiceBridgeMixin

from gui.layout_mixin import LayoutMixin
from gui.handlers_mixin import HandlersMixin
from gui.tabs.gitlab_tab import GitlabTabMixin
from gui.tabs.date_output_tab import DateOutputTabMixin
from gui.tabs.ai_tab import AiTabMixin
from gui.tabs.excel_tab import ExcelTabMixin
from gui.tabs.actions_tab import ActionsTabMixin

class Git2LogsGUI(
    ServiceBridgeMixin,
    LayoutMixin,
    GitlabTabMixin,
    DateOutputTabMixin,
    AiTabMixin,
    ExcelTabMixin,
    ActionsTabMixin,
    HandlersMixin,
):
    def __init__(self, root):
        try:
            self.root = root
            self.root.title("MIZUKI-GITLAB工具箱")
            # 窗口尺寸与最小尺寸由 main() 统一设置，避免与启动流程冲突
            self.root.resizable(True, True)  # 允许自由调整大小
            
            # 保存待处理的AI分析数据
            self._pending_ai_data = None
            self._log_count = 0
            self._log_queue = queue.Queue()
            self._is_running = False  # 跟踪生成任务运行状态
            self._ai_is_running = False  # 跟踪AI分析任务运行状态
            self._work_hours_data = None  # 缓存工时数据，供Excel导出使用
            self._service = Git2LogsService()
            self._project_checkboxes: dict = {}  # 项目名 -> BooleanVar
            self._validation_labels: dict = {}  # 字段名 -> 校验提示 CTkLabel
            self._log_collapsed = False
            self._log_filter_level = "全部"
            self._log_pending = []
            self._log_flush_scheduled = False
            self._log_omitted_total = 0
            self._current_theme = "dark"
            # 主题切换时需同步的控件（由各 Tab 构建时登记）
            self._theme_panels_main: list = []
            self._theme_panels_card: list = []
            self._theme_entries_typed: list = []  # (widget, 'main'|'card')
            self._theme_comboboxes: list = []
            self._theme_outline_buttons: list = []
            self._theme_labels_primary: list = []
            self._theme_labels_secondary: list = []
            self._theme_check_radio: list = []
            self._theme_radio_buttons: list = []
            self._responsive_wrap_labels: list = []
            self._resize_wrap_job = None
            self._sidebar_pill_by_tab: dict = {}

            # 配置 CustomTkinter 主题
            ctk.set_appearance_mode("dark")  # 强制暗黑模式
            ctk.set_default_color_theme("blue")  # 使用蓝色主题
            
            # 应用统一UI样式
            self.styles = UIStyles

            # 兼容旧代码的别名（指向集中式样式，避免大范围改动）
            c = self.styles.colors
            self.bg_main        = c['bg_main']
            self.bg_card        = c['bg_card']
            self.text_primary   = c['text_primary']
            self.text_secondary = c['text_secondary']
            self.border_color   = c['border']
            self.accent_color   = c['accent']
            self.success_color  = c['success']
            self.error_color    = c['error']

            # 设置窗口背景
            self.root.configure(bg=self.bg_main)
            
            # 创建主容器（立即显示）
            main_container = ctk.CTkFrame(root, fg_color=self.bg_main, corner_radius=0)
            main_container.pack(fill="both", expand=True, padx=0, pady=0)
            self._main_container = main_container
            
            # 立即更新，显示框架
            root.update_idletasks()
            root.update()

            # 存储标签页引用
            self.tab_frames = {}
            self.current_tab = None
            self._sidebar_btns = {}

            # ── 底部固定操作按钮容器 ───────────────────────
            self.bottom_actions_frame = ctk.CTkFrame(main_container, fg_color=self.styles.colors['bg_main'], corner_radius=0)
            self.bottom_actions_frame.pack(side="bottom", fill="x", padx=0, pady=0)

            # ── Body: 侧边栏(左) + 右侧内容(右) ───────────
            body_frame = ctk.CTkFrame(main_container, fg_color=self.bg_main, corner_radius=0)
            body_frame.pack(fill="both", expand=True)
            self._body_frame = body_frame

            # 侧边栏（208px 宽，CodexPlusPlus 风格）
            sidebar_wrapper = ctk.CTkFrame(body_frame, fg_color=self.styles.colors['sidebar_bg'], corner_radius=0)
            sidebar_wrapper.pack(side="left", fill="y")
            self._sidebar_frame = ctk.CTkFrame(
                sidebar_wrapper,
                fg_color=self.styles.colors['sidebar_bg'],
                corner_radius=0,
                width=GUIConfig.SIDEBAR_FRAME_WIDTH,
            )
            self._sidebar_frame.pack(side="left", fill="both", expand=True)
            self._sidebar_frame.pack_propagate(False)
            self._sidebar_border = ctk.CTkFrame(sidebar_wrapper, fg_color=self.styles.colors['border'], width=1, corner_radius=0)
            self._sidebar_border.pack(side="right", fill="y")
            self._sidebar_wrapper = sidebar_wrapper

            # 右侧面板（workspace 区域）
            right_panel = ctk.CTkFrame(body_frame, fg_color=self.bg_main, corner_radius=0)
            right_panel.pack(side="left", fill="both", expand=True)
            self._right_panel = right_panel

            # Topbar（页面标题区域，CodexPlusPlus 风格）
            topbar = ctk.CTkFrame(right_panel, fg_color=self.styles.colors['bg_card'], height=72, corner_radius=0)
            topbar.pack(fill="x", side="top")
            topbar.pack_propagate(False)
            self._topbar_frame = topbar

            topbar_inner = ctk.CTkFrame(topbar, fg_color="transparent")
            topbar_inner.pack(fill="both", expand=True, padx=20)

            topbar_text = ctk.CTkFrame(topbar_inner, fg_color="transparent")
            topbar_text.pack(side="left", fill="y", expand=False)

            self._topbar_title = ctk.CTkLabel(topbar_text,
                                              text="GitLab 配置",
                                              font=_ctk_ui_font(18, "bold"),
                                              text_color=self.styles.colors['text_primary'],
                                              anchor="w")
            self._topbar_title.pack(anchor="w", pady=(16, 2))

            self._topbar_subtitle = ctk.CTkLabel(topbar_text,
                                                 text="配置 GitLab 连接参数",
                                                 font=_ctk_ui_font(12),
                                                 text_color=self.styles.colors['text_secondary'],
                                                 anchor="w")
            self._topbar_subtitle.pack(anchor="w")

            topbar_sep = ctk.CTkFrame(right_panel, fg_color=self.styles.colors['border'], height=1, corner_radius=0)
            topbar_sep.pack(fill="x", side="top")
            self._topbar_sep = topbar_sep

            # 滚动内容容器
            self.scroll_container = ctk.CTkScrollableFrame(right_panel,
                                                           fg_color=self.styles.colors['bg_main'],
                                                           corner_radius=0)
            self.scroll_container.pack(fill="both", expand=True, padx=0, pady=0)

            self.content_container = self.scroll_container

            try:
                self.scroll_container.configure(scrollbar_button_color=self.styles.colors['bg_main'],
                                                scrollbar_button_hover_color=self.styles.colors['bg_main'])
            except Exception:
                logger.debug("配置滚动容器滚动条颜色失败")

            # 日志区域（底部）
            self._create_log_area(right_panel)
            
            # 延迟并批量创建标签页内容（消除渲染毛刺）
            def delayed_init():
                try:
                    # 分步构建 UI 组件，但不执行强制 update
                    self._create_tab1_gitlab_config()
                    self._create_tab2_date_output()
                    self._create_tab3_ai_analysis()
                    self._create_tab4_excel_export()
                    self._create_bottom_actions()
                    # 侧边栏（Tab内容建立后创建，确保 tab_frames 存在）
                    self._create_sidebar(self._sidebar_frame)

                    # 默认显示第一个标签页
                    self._switch_tab("GitLab配置")

                    # 关键一次性静默同步
                    self.root.update_idletasks()

                    # 绑定表单验证（在控件创建完成后）
                    self._bind_form_validation()
                    self._enhance_form_interaction()

                    # 启动日志队列轮询（后台线程通过 queue 安全传递日志）
                    self._poll_log_queue()

                    # 初始日志
                    self.log("欢迎使用 MIZUKI-GITLAB工具箱！", "info")
                    self.log("请填写参数后点击'▶ 生成日志'按钮。", "info")
                    self.root.after(GUIConfig.WRAPLENGTH_SYNC_DELAY_MS, self._sync_responsive_wraplengths)
                except Exception as e:
                    self.log(f"初始化错误: {str(e)}", "error")
                    self.log(traceback.format_exc(), "error")
            
            # 延迟10ms执行，让窗口先显示出来
            root.after(GUIConfig.INIT_DELAY_MS, delayed_init)
            
        except Exception as e:
            error_msg = f"界面初始化失败: {str(e)}\n\n{traceback.format_exc()}"
            print(error_msg)
            try:
                messagebox.showerror("初始化错误", error_msg)
            except Exception:
                logger.debug("显示初始化错误对话框失败")
            raise


def main():
    """主函数 - 优化启动速度，立即显示窗口"""
    root = None
    try:
        if not CTK_AVAILABLE:
            print("错误: 需要安装 CustomTkinter")
            print("请运行: pip install customtkinter")
            sys.exit(1)
        
        # 创建根窗口（立即显示）
        root = ctk.CTk()
        root.title("MIZUKI-GITLAB工具箱")
        root.minsize(GUIConfig.WINDOW_MIN_WIDTH, GUIConfig.WINDOW_MIN_HEIGHT)
        root.resizable(True, True)

        width = GUIConfig.WINDOW_DEFAULT_WIDTH
        height = GUIConfig.WINDOW_DEFAULT_HEIGHT
        x = (root.winfo_screenwidth() // 2) - (width // 2)
        y = (root.winfo_screenheight() // 2) - (height // 2)
        root.geometry(f'{width}x{height}+{x}+{y}')
        
        # 强制显示窗口（关键：确保窗口立即可见）
        root.deiconify()
        root.lift()
        root.focus_force()
        
        # 立即更新窗口，让用户看到界面正在加载
        root.update_idletasks()
        root.update()
        
        # 创建应用实例（延迟加载非关键模块）
        # 使用 after 延迟创建，确保窗口先显示
        def create_app():
            try:
                app = Git2LogsGUI(root)
            except Exception as e:
                error_msg = f"界面初始化失败: {str(e)}\n\n{traceback.format_exc()}"
                print(error_msg)
                messagebox.showerror("初始化错误", error_msg)
        
        # 延迟1ms创建应用（几乎立即，但确保窗口先显示）
        root.after(1, create_app)
        
        # 立即进入主循环（窗口已显示）
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
