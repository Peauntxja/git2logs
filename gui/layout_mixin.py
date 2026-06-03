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

class LayoutMixin:
    def _apply_sidebar_pill_style(self, tab_name=None):
        """侧栏导航项：选中态有 border + muted 背景（CodexPlusPlus .nav-item.active 风格）。"""
        pills = getattr(self, "_sidebar_pill_by_tab", None) or {}
        if not pills:
            return
        c = self.styles.colors
        ct = getattr(self, "current_tab", None)
        names = [tab_name] if tab_name is not None and tab_name in pills else list(pills.keys())
        for name in names:
            pill = pills.get(name)
            if not pill:
                continue
            sel = name == ct
            try:
                pill.configure(
                    fg_color=c["bg_surface"] if sel else c["sidebar_bg"],
                    border_color=c["border"] if sel else c["sidebar_bg"],
                    border_width=1,
                )
            except Exception:
                logger.debug("配置侧栏导航项样式失败")
            tpl = self._sidebar_btns.get(name)
            if tpl and len(tpl) >= 3:
                icon_col = c["text_primary"] if sel else c["text_secondary"]
                try:
                    tpl[1].configure(text_color=icon_col)
                except Exception:
                    pass

    def _on_sidebar_enter_pill(self, tab_name):
        if getattr(self, "current_tab", None) == tab_name:
            return
        pill = self._sidebar_pill_by_tab.get(tab_name)
        if not pill:
            return
        try:
            pill.configure(fg_color=self.styles.colors["hover"])
        except Exception:
            logger.debug("配置侧栏悬停样式失败")

    def _on_sidebar_leave_pill(self, tab_name):
        self._apply_sidebar_pill_style(tab_name)

    

    def _create_sidebar(self, parent):
        """创建左侧导航：CodexPlusPlus 风格横向文字导航，208px 宽。"""
        nav_items = [
            ("GitLab配置", "⚙", "GitLab 配置"),
            ("日期和输出", "📅", "日期和输出"),
            ("AI分析", "🤖", "AI 分析"),
            ("Excel导出", "📊", "Excel 导出"),
        ]

        self._sidebar_pill_by_tab.clear()

        # 品牌区
        brand_frame = ctk.CTkFrame(parent, fg_color="transparent")
        brand_frame.pack(fill="x", padx=10, pady=(14, 12))

        brand_row = ctk.CTkFrame(brand_frame, fg_color="transparent")
        brand_row.pack(fill="x")

        brand_mark = ctk.CTkFrame(brand_row,
                                  fg_color=self.styles.colors['text_primary'],
                                  width=36, height=36,
                                  corner_radius=6)
        brand_mark.pack(side="left", padx=(8, 10))
        brand_mark.pack_propagate(False)
        brand_mark_lbl = ctk.CTkLabel(brand_mark, text="M",
                                      font=_ctk_ui_font(16, "bold"),
                                      text_color=self.styles.colors['bg_main'])
        brand_mark_lbl.pack(expand=True)
        self._sidebar_brand_mark = brand_mark
        self._sidebar_brand_mark_lbl = brand_mark_lbl

        brand_text = ctk.CTkFrame(brand_row, fg_color="transparent")
        brand_text.pack(side="left", fill="y")
        self._sidebar_brand_title = ctk.CTkLabel(brand_text,
                                                 text="MIZUKI",
                                                 font=_ctk_ui_font(14, "bold"),
                                                 text_color=self.styles.colors['text_primary'],
                                                 anchor="w")
        self._sidebar_brand_title.pack(anchor="w")
        self._sidebar_brand_sub = ctk.CTkLabel(brand_text,
                                               text="GitLab 工具箱",
                                               font=_ctk_ui_font(11),
                                               text_color=self.styles.colors['text_secondary'],
                                               anchor="w")
        self._sidebar_brand_sub.pack(anchor="w")

        # 品牌区底部分隔线
        ctk.CTkFrame(parent, fg_color=self.styles.colors['border'], height=1, corner_radius=0).pack(
            fill="x", padx=10, pady=(0, 12))

        # 导航项列表
        for tab_name, glyph, label in nav_items:
            nav_btn = ctk.CTkFrame(parent,
                                   fg_color=self.styles.colors['sidebar_bg'],
                                   corner_radius=self.styles.radius['md'],
                                   height=38,
                                   border_width=1,
                                   border_color=self.styles.colors['sidebar_bg'])
            nav_btn.pack(fill="x", padx=10, pady=2)
            nav_btn.pack_propagate(False)

            inner = ctk.CTkFrame(nav_btn, fg_color="transparent")
            inner.pack(fill="both", expand=True, padx=9)

            icon_lbl = ctk.CTkLabel(inner,
                                    text=glyph,
                                    font=_ctk_ui_font(13),
                                    text_color=self.styles.colors['text_secondary'],
                                    fg_color="transparent",
                                    width=24)
            icon_lbl.pack(side="left", pady=0)

            text_lbl = ctk.CTkLabel(inner,
                                    text=label,
                                    font=_ctk_ui_font(13, "bold"),
                                    text_color=self.styles.colors['text_primary'],
                                    fg_color="transparent",
                                    anchor="w")
            text_lbl.pack(side="left", padx=(8, 0), fill="y")

            self._sidebar_pill_by_tab[tab_name] = nav_btn

            for w in (nav_btn, inner, icon_lbl, text_lbl):
                w.bind("<Button-1>", lambda e, n=tab_name: self._switch_tab(n))
                w.bind("<Enter>", lambda e, n=tab_name: self._on_sidebar_enter_pill(n))
                w.bind("<Leave>", lambda e, n=tab_name: self._on_sidebar_leave_pill(n))

            self._sidebar_btns[tab_name] = (nav_btn, icon_lbl, text_lbl, glyph)

    def _create_log_area(self, parent):
        """创建日志显示区域（放在最上方）"""
        log_container = ctk.CTkFrame(parent, fg_color=self.styles.colors['bg_main'], corner_radius=0)
        log_container.pack(fill="x", side="bottom", padx=0, pady=0)
        self._log_container = log_container
        
        log_title_frame = ctk.CTkFrame(log_container,
                                     fg_color=self.styles.colors['bg_main'],
                                     height=34,
                                     corner_radius=0)
        log_title_frame.pack(fill="x", padx=20, pady=(0, 8))
        log_title_frame.pack_propagate(False)
        self._log_title_frame = log_title_frame
        
        self._log_title_lbl = ctk.CTkLabel(log_title_frame,
                              text="执行日志",
                              font=self.styles.fonts['body_bold'](),
                              text_color=self.styles.colors['text_primary'],
                              anchor="w")
        self._log_title_lbl.pack(side="left", padx=0, pady=10)

        tf_right = ctk.CTkFrame(log_title_frame, fg_color="transparent")
        tf_right.pack(side="right", padx=0, pady=4)

        self._log_filter_btn = ctk.CTkSegmentedButton(
            tf_right,
            values=["全部", "警告+错误", "仅错误"],
            command=self._on_log_filter_change,
            width=200,
            height=28,
            font=self.styles.fonts['caption'](),
            corner_radius=self.styles.radius['sm'],
            fg_color=self.styles.colors['bg_card'],
            selected_color=self.styles.colors['accent'],
            selected_hover_color=self.styles.colors['accent'],
            unselected_color=self.styles.colors['bg_card'],
            unselected_hover_color=self.styles.colors['hover'],
            text_color=self.styles.colors['text_primary'],
        )
        self._log_filter_btn.set("全部")
        self._log_filter_btn.pack(side="right", padx=(0, 8))

        self._log_toggle_btn = ctk.CTkButton(
            tf_right,
            text="收起",
            width=56,
            height=28,
            font=self.styles.fonts['caption'](),
            corner_radius=self.styles.radius['sm'],
            fg_color=self.styles.colors['bg_card'],
            text_color=self.styles.colors['text_secondary'],
            hover_color=self.styles.colors['hover'],
            border_width=1,
            border_color=self.styles.colors['border'],
            command=self._toggle_log_collapsed,
        )
        self._log_toggle_btn.pack(side="right")
        
        log_card = ctk.CTkFrame(log_container,
                              fg_color=self.styles.colors['bg_card'],
                              corner_radius=self.styles.radius['lg'])
        log_card.pack(fill="x", padx=20, pady=(0, 0))
        self._log_card = log_card
        
        text_container = ctk.CTkFrame(log_card, fg_color=self.styles.colors['bg_main'], corner_radius=self.styles.radius['md'])
        text_container.pack(fill="x", padx=10, pady=10)
        self._log_text_container = text_container
        
        from tkinter import scrolledtext
        mono = _resolve_monospace_font(self.root, 10)
        self.log_text = scrolledtext.ScrolledText(text_container,
                                             height=6,
                                             width=80,
                                             font=mono,
                                             wrap="word",
                                             bg=self.styles.colors['bg_main'],
                                             fg=self.styles.colors['text_primary'],
                                             insertbackground=self.styles.colors['accent'],
                                             selectbackground=self.styles.colors['accent'],
                                             selectforeground="white",
                                             borderwidth=0,
                                             relief="flat",
                                             padx=12,
                                             pady=12)
        self.log_text.pack(fill="both", expand=False)
        
        self.log_text.tag_config("error", foreground=self.styles.colors['error'])
        self.log_text.tag_config("success", foreground=self.styles.colors['success'])
        self.log_text.tag_config("warning", foreground=self.styles.colors['warning'])
        self.log_text.tag_config("info", foreground=self.styles.colors['text_primary'])
        self.log_text.tag_config("timestamp", foreground=self.styles.colors['text_secondary'])

    def _toggle_log_collapsed(self):
        """折叠/展开执行日志区域（仅影响布局，不改变业务逻辑）。"""
        if not hasattr(self, "_log_card") or not hasattr(self, "_log_toggle_btn"):
            return
        self._log_collapsed = not self._log_collapsed
        if self._log_collapsed:
            self._log_card.pack_forget()
            self._log_toggle_btn.configure(text="展开")
        else:
            self._log_card.pack(fill="x", padx=20, pady=(0, 0))
            self._log_toggle_btn.configure(text="收起")

    def _on_log_filter_change(self, value):
        """日志等级筛选按钮回调，更新筛选级别。"""
        self._log_filter_level = value

    def _refresh_log_widget_theme(self):
        """根据当前 UIStyles 同步 Tk 日志控件与标签颜色。"""
        if not hasattr(self, "log_text"):
            return
        c = self.styles.colors
        sel_fg = "#FFFFFF" if self._current_theme == "dark" else "#18181B"
        self.log_text.configure(
            bg=c['bg_main'],
            fg=c['text_primary'],
            insertbackground=c['accent'],
            selectbackground=c['accent'],
            selectforeground=sel_fg,
        )
        self.log_text.tag_config("error", foreground=c['error'])
        self.log_text.tag_config("success", foreground=c['success'])
        self.log_text.tag_config("warning", foreground=c['warning'])
        self.log_text.tag_config("info", foreground=c['text_primary'])
        self.log_text.tag_config("timestamp", foreground=c['text_secondary'])
        self.log_text.tag_config("truncated", foreground=c['text_secondary'], justify="center")

    def _refresh_chrome_for_theme(self):
        """同步顶栏、侧栏、主布局与日志外框等与主题相关的硬编码表面色。"""
        c = self.styles.colors
        is_dark = self._current_theme == "dark"
        header_bg = c["bg_main"] if is_dark else c["chrome_border_light"]
        sidebar_bg = c["sidebar_bg"]

        self.root.configure(bg=c['bg_main'])
        if hasattr(self, "_main_container"):
            self._main_container.configure(fg_color=c['bg_main'])
        if hasattr(self, "_body_frame"):
            self._body_frame.configure(fg_color=c['bg_main'])
        if hasattr(self, "bottom_actions_frame"):
            self.bottom_actions_frame.configure(fg_color=c['bg_main'])
        if hasattr(self, "_right_panel"):
            self._right_panel.configure(fg_color=c['bg_main'])
        if hasattr(self, "scroll_container"):
            self.scroll_container.configure(fg_color=c['bg_main'])
            try:
                self.scroll_container.configure(
                    scrollbar_button_color=c['bg_main'],
                    scrollbar_button_hover_color=c['bg_main'],
                )
            except Exception:
                logger.debug("主题更新: 配置滚动条颜色失败")

        if hasattr(self, "_topbar_frame"):
            self._topbar_frame.configure(fg_color=c['bg_card'])
        if hasattr(self, "_topbar_title"):
            self._topbar_title.configure(text_color=c['text_primary'])
        if hasattr(self, "_topbar_subtitle"):
            self._topbar_subtitle.configure(text_color=c['text_secondary'])
        if hasattr(self, "_topbar_sep"):
            self._topbar_sep.configure(fg_color=c['border'])
        try:
            if hasattr(self, "_sidebar_wrapper"):
                self._sidebar_wrapper.configure(fg_color=sidebar_bg)
            if hasattr(self, "_sidebar_frame"):
                self._sidebar_frame.configure(fg_color=sidebar_bg)
            if hasattr(self, "_sidebar_border"):
                self._sidebar_border.configure(fg_color=c['border'])
            if hasattr(self, "_sidebar_brand_mark"):
                self._sidebar_brand_mark.configure(fg_color=c['text_primary'])
            if hasattr(self, "_sidebar_brand_mark_lbl"):
                self._sidebar_brand_mark_lbl.configure(text_color=c['bg_main'])
            if hasattr(self, "_sidebar_brand_title"):
                self._sidebar_brand_title.configure(text_color=c['text_primary'])
            if hasattr(self, "_sidebar_brand_sub"):
                self._sidebar_brand_sub.configure(text_color=c['text_secondary'])
        except (AttributeError, Exception):
            logger.debug("主题切换: 侧栏部分组件样式更新失败")
        self._apply_sidebar_pill_style()

        if hasattr(self, "_log_container"):
            self._log_container.configure(fg_color=c['bg_main'])
        if hasattr(self, "_log_title_frame"):
            self._log_title_frame.configure(fg_color=c['bg_main'])
        if hasattr(self, "_log_title_lbl"):
            self._log_title_lbl.configure(text_color=c['text_primary'])
        if hasattr(self, "_log_card"):
            self._log_card.configure(fg_color=c['bg_card'])
        if hasattr(self, "_log_text_container"):
            self._log_text_container.configure(fg_color=c['bg_main'])
        if hasattr(self, "_log_toggle_btn"):
            self._log_toggle_btn.configure(
                fg_color=c['bg_card'],
                text_color=c['text_secondary'],
                hover_color=c['hover'],
                border_color=c['border'],
            )
        if hasattr(self, "_log_filter_btn"):
            self._log_filter_btn.configure(
                fg_color=c['bg_card'],
                selected_color=c['accent'],
                selected_hover_color=c['accent'],
                unselected_color=c['bg_card'],
                unselected_hover_color=c['hover'],
                text_color=c['text_primary'],
            )
        if hasattr(self, "_theme_btn"):
            self._theme_btn.configure(
                fg_color=c['bg_card'],
                text_color=c['text_secondary'],
                hover_color=c['hover'],
                border_color=c['border'],
            )
        if hasattr(self, "_run_progress"):
            try:
                self._run_progress.configure(progress_color=c['accent'])
            except Exception:
                logger.debug("主题更新: 配置进度条颜色失败")
        self._refresh_content_theme()

    def _track_panel_main(self, w):
        if w is not None:
            self._theme_panels_main.append(w)

    def _track_panel_card(self, w):
        if w is not None:
            self._theme_panels_card.append(w)

    def _track_entry(self, w, surface='card'):
        if w is not None:
            self._theme_entries_typed.append((w, surface))

    def _track_combo(self, w):
        if w is not None:
            self._theme_comboboxes.append(w)

    def _track_outline_button(self, w):
        if w is not None:
            self._theme_outline_buttons.append(w)

    def _track_label_primary(self, w):
        if w is not None:
            self._theme_labels_primary.append(w)

    def _track_label_secondary(self, w):
        if w is not None:
            self._theme_labels_secondary.append(w)

    def _track_check_or_radio(self, w):
        if w is not None:
            self._theme_check_radio.append(w)

    def _track_format_radio(self, w):
        if w is not None:
            self._theme_radio_buttons.append(w)

    def _track_responsive_wrap(self, w):
        if w is not None:
            self._responsive_wrap_labels.append(w)

    def _refresh_project_cb_theme(self):
        if not hasattr(self, "_project_checkbox_frame"):
            return
        c = self.styles.colors
        for w in self._project_checkbox_frame.winfo_children():
            if isinstance(w, ctk.CTkCheckBox):
                try:
                    w.configure(text_color=c['text_primary'], fg_color=c['accent'])
                except Exception:
                    logger.debug("主题更新: 配置项目复选框样式失败")

    def _refresh_content_theme(self):
        """同步各 Tab 内卡片、输入框、次要按钮等与当前主题一致。"""
        c = self.styles.colors
        ho = c['hover']
        for w in self._theme_panels_main:
            try:
                w.configure(fg_color=c['bg_main'])
            except Exception:
                logger.debug("主题更新: 配置主面板背景失败")
        for w in self._theme_panels_card:
            try:
                w.configure(fg_color=c['bg_card'], border_color=c['border'])
            except Exception:
                logger.debug("主题更新: 配置卡片面板样式失败")
        if hasattr(self, "_tab1_hint_frame"):
            try:
                self._tab1_hint_frame.configure(fg_color=c['bg_main'], border_color=c['border'])
            except Exception:
                logger.debug("主题更新: 配置提示框样式失败")
        for w, surf in self._theme_entries_typed:
            try:
                fg = c['bg_main'] if surf == 'main' else c['bg_card']
                w.configure(fg_color=fg, border_color=c['border'], text_color=c['text_primary'])
            except Exception:
                logger.debug("主题更新: 配置输入框样式失败")
        for w in self._theme_comboboxes:
            try:
                w.configure(
                    fg_color=c['bg_card'],
                    border_color=c['border'],
                    text_color=c['text_primary'],
                    button_color=c['bg_card'],
                    button_hover_color=ho,
                    dropdown_fg_color=c['bg_card'],
                    dropdown_text_color=c['text_primary'],
                    dropdown_hover_color=ho,
                )
            except Exception:
                logger.debug("主题更新: 配置下拉框样式失败")
        for w in self._theme_outline_buttons:
            try:
                w.configure(
                    fg_color=c['bg_card'],
                    text_color=c['text_primary'],
                    hover_color=ho,
                    border_color=c['border'],
                )
            except Exception:
                logger.debug("主题更新: 配置轮廓按钮样式失败")
        for w in self._theme_labels_primary:
            try:
                w.configure(text_color=c['text_primary'])
            except Exception:
                logger.debug("主题更新: 配置主标签文字颜色失败")
        for w in self._theme_labels_secondary:
            try:
                w.configure(text_color=c['text_secondary'])
            except Exception:
                logger.debug("主题更新: 配置次要标签文字颜色失败")
        for w in self._theme_check_radio:
            try:
                w.configure(text_color=c['text_primary'], fg_color=c['accent'])
            except Exception:
                logger.debug("主题更新: 配置选择控件样式失败")
        surf = c['bg_surface']
        for w in self._theme_radio_buttons:
            try:
                w.configure(
                    text_color=c['text_primary'],
                    fg_color=c['accent'],
                    hover_color=c['accent_hover'],
                    bg_color=surf,
                )
            except Exception:
                logger.debug("主题更新: 配置单选按钮样式失败")
        if hasattr(self, "_project_checkbox_frame"):
            for w in self._project_checkbox_frame.winfo_children():
                if isinstance(w, ctk.CTkLabel):
                    try:
                        w.configure(text_color=c['text_secondary'])
                    except Exception:
                        logger.debug("主题更新: 配置项目标签文字颜色失败")
        self._refresh_project_cb_theme()
        if hasattr(self, "_format_options_scroll"):
            try:
                self._format_options_scroll.configure(
                    fg_color=c['bg_surface'],
                    scrollbar_fg_color=c['bg_card'],
                    scrollbar_button_color=c['bg_surface'],
                    scrollbar_button_hover_color=c['hover'],
                )
            except Exception:
                logger.debug("主题更新: 配置格式选项滚动区域样式失败")
        if hasattr(self, "_bottom_separator"):
            try:
                self._bottom_separator.configure(fg_color=c['border'])
            except Exception:
                logger.debug("主题更新: 配置底部分隔线颜色失败")
        if hasattr(self, "_button_container_ref"):
            try:
                self._button_container_ref.configure(fg_color=c['bg_main'])
            except Exception:
                logger.debug("主题更新: 配置按钮容器背景失败")
        if hasattr(self, "clear_btn"):
            try:
                self.clear_btn.configure(
                    fg_color=c['bg_card'],
                    text_color=c['text_primary'],
                    hover_color=ho,
                    border_color=c['border'],
                )
            except Exception:
                logger.debug("主题更新: 配置清除按钮样式失败")
        if hasattr(self, "ai_analysis_btn"):
            try:
                self.ai_analysis_btn.configure(
                    fg_color=c['bg_card'],
                    text_color=c['text_primary'],
                    hover_color=ho,
                    border_color=c['border'],
                )
            except Exception:
                logger.debug("主题更新: 配置AI分析按钮样式失败")
        if hasattr(self, "generate_btn"):
            try:
                if getattr(self, "_is_running", False):
                    self.generate_btn.configure(
                        fg_color=c['error'],
                        hover_color=c['error_hover'],
                        text_color="white",
                    )
                else:
                    self.generate_btn.configure(
                        fg_color=c['success'],
                        hover_color=c['success_hover'],
                        text_color="white",
                    )
            except Exception:
                logger.debug("主题更新: 配置生成按钮样式失败")
        if hasattr(self, "_excel_export_btn"):
            try:
                self._excel_export_btn.configure(
                    fg_color=c['accent'],
                    hover_color=c['accent_hover'],
                    text_color="#FFFFFF",
                )
            except Exception:
                logger.debug("主题更新: 配置Excel导出按钮样式失败")
        self._sync_responsive_wraplengths()

    def _sync_responsive_wraplengths(self):
        """按窗口宽度更新长文案标签的 wraplength。"""
        try:
            ww = self.root.winfo_width()
            inner = max(220, ww - 140)
            for lbl in self._responsive_wrap_labels:
                try:
                    lbl.configure(wraplength=inner)
                except Exception:
                    logger.debug("配置标签换行宽度失败")
        except Exception:
            logger.debug("同步响应式换行宽度失败")

    def _on_keyboard_generate(self, event):
        """⌘+Return 触发生成（焦点在日志文本框内时不触发）。"""
        try:
            from tkinter import Text
            w = self.root.focus_get()
            if w is None:
                self.generate_logs()
                return
            if isinstance(w, Text):
                return
        except Exception:
            logger.debug("检测焦点控件类型失败")
        if getattr(self, "_is_running", False):
            return
        self.generate_logs()
    
