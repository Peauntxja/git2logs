#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GUI 子模块（由 gui/app.py 拆分，逻辑未改）。"""
import json
import logging
import os
import queue
import sys
import threading
import traceback
from datetime import datetime
from tkinter import filedialog, messagebox

try:
    import customtkinter as ctk
except ImportError:
    ctk = None

from config import AIConfig, GUIConfig, ReportConfig
from models import (
    AIAnalysisError,
    AIParams,
    ExcelParams,
    Git2LogsError,
    GitLabConnectionError,
    ReportGenerationError,
    ReportParams,
)
from service import Git2LogsService
from gui.styles import (
    UIStyles,
    _ctk_ui_font,
    get_script_path,
    resource_path,
    _resolve_monospace_font,
)

logger = logging.getLogger(__name__)

class ActionsTabMixin:
    def _create_bottom_actions(self):
        """创建底部固定操作按钮区域（固定在窗口底部，不随内容滚动）"""
        # 顶部分隔线
        separator = ctk.CTkFrame(self.bottom_actions_frame, fg_color=self.styles.colors['border'], height=1, corner_radius=0)
        separator.pack(fill="x", padx=0, pady=0)
        self._bottom_separator = separator

        button_container = ctk.CTkFrame(self.bottom_actions_frame,
                                       fg_color=self.bg_main,
                                       corner_radius=0)
        button_container.pack(fill="x", padx=self.styles.spacing['md'], pady=(self.styles.spacing['sm'], self.styles.spacing['md']))
        self._button_container_ref = button_container

        # 状态栏（左侧）+ 按钮组（右侧）
        status_row = ctk.CTkFrame(button_container, fg_color="transparent")
        status_row.pack(fill="x", pady=(0, self.styles.spacing['sm']))

        self.status_indicator = ctk.CTkLabel(status_row,
                                            text="● 就绪",
                                            font=self.styles.fonts['caption'](),
                                            text_color=self.styles.colors['success'],
                                            anchor="w")
        self.status_indicator.pack(side="left")

        self._run_progress = ctk.CTkProgressBar(
            status_row,
            mode="indeterminate",
            width=140,
            height=6,
            progress_color=self.styles.colors['accent'],
        )

        # 主题切换按钮（右侧）
        theme_btn = ctk.CTkButton(status_row,
                                 text="☀ 浅色",
                                 width=80,
                                 height=26,
                                 font=self.styles.fonts['caption'](),
                                 corner_radius=self.styles.radius['sm'],
                                 fg_color=self.styles.colors['bg_card'],
                                 text_color=self.styles.colors['text_secondary'],
                                 hover_color=self.styles.colors['hover'],
                                 border_width=1,
                                 border_color=self.styles.colors['border'],
                                 command=self._toggle_theme)
        theme_btn.pack(side="right")
        self._theme_btn = theme_btn

        # 主操作按钮区域（grid 自适应布局）
        button_frame = ctk.CTkFrame(button_container, fg_color="transparent")
        button_frame.pack(fill="x")
        button_frame.grid_columnconfigure(0, weight=2, uniform="buttons")  # 主按钮更宽
        button_frame.grid_columnconfigure(1, weight=1, uniform="buttons")
        button_frame.grid_columnconfigure(2, weight=1, uniform="buttons")

        # 主按钮 - 生成日志
        self.generate_btn = ctk.CTkButton(button_frame,
                                        text="▶  开始生成",
                                        height=36,
                                        font=self.styles.fonts['body_bold'](),
                                        corner_radius=self.styles.radius['md'],
                                        fg_color=self.styles.colors['success'],
                                        text_color="white",
                                        hover_color=self.styles.colors['success_hover'],
                                        command=self.generate_logs)
        self.generate_btn.grid(row=0, column=0, padx=(0, self.styles.spacing['sm']), sticky="ew")

        # 清空按钮
        self.clear_btn = ctk.CTkButton(button_frame,
                                text="清空",
                                height=36,
                                font=self.styles.fonts['body'](),
                                corner_radius=self.styles.radius['md'],
                                fg_color=self.bg_card,
                                text_color=self.text_primary,
                                hover_color=self.styles.colors['hover'],
                                border_width=1,
                                border_color=self.border_color,
                                command=self.clear_logs)
        self.clear_btn.grid(row=0, column=1, padx=(0, self.styles.spacing['sm']), sticky="ew")

        # AI分析按钮
        self.ai_analysis_btn = ctk.CTkButton(button_frame,
                                           text="AI 分析",
                                           height=36,
                                           font=self.styles.fonts['body'](),
                                           corner_radius=self.styles.radius['md'],
                                           fg_color=self.bg_card,
                                           text_color=self.text_primary,
                                           hover_color=self.styles.colors['hover'],
                                           border_width=1,
                                           border_color=self.border_color,
                                           state="normal",
                                           command=self._manual_ai_analysis)
        self.ai_analysis_btn.grid(row=0, column=2, sticky="ew")

        # 绑定窗口大小变化响应式回调
        self.root.bind('<Configure>', self._on_window_resize)
        self._last_resize_width = self.root.winfo_width()
        self.root.bind_all('<Command-Return>', self._on_keyboard_generate)
    
