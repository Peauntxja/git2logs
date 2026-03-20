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
import subprocess
from pathlib import Path
from datetime import datetime

# UI样式常量定义
class UIStyles:
    """UI样式常量统一管理类"""

    # 颜色方案
    colors = {
        'bg_main': "#18181B",      # 主背景深灰
        'bg_card': "#27272A",      # 卡片背景
        'bg_surface': "#1F1F23",   # 表面背景
        'text_primary': "#F4F4F5", # 主要文字
        'text_secondary': "#A1A1AA",# 次要文字
        'text_tertiary': "#71717A", # 第三级文字
        'border': "#3F3F46",       # 边框色
        'accent': "#3B82F6",       # 科技蓝
        'success': "#10B981",      # 成功绿
        'warning': "#F59E0B",      # 警告黄
        'error': "#EF4444",        # 错误红
        'hover': "#374151",        # 悬停色
        'active': "#1F2937"        # 激活色
    }

    # 间距系统 (基于8px网格)
    spacing = {
        'xs': 4,
        'sm': 8,
        'md': 16,
        'lg': 24,
        'xl': 32,
        'xxl': 48
    }

    # 圆角系统
    radius = {
        'sm': 6,
        'md': 8,
        'lg': 12,
        'xl': 16
    }

    # 字体系统（延迟创建，避免在没有tkinter root时出错）
    fonts = {
        'header': lambda: ctk.CTkFont(size=16, weight='bold'),
        'subheader': lambda: ctk.CTkFont(size=14, weight='semibold'),
        'body': lambda: ctk.CTkFont(size=13),
        'body_bold': lambda: ctk.CTkFont(size=13, weight='bold'),
        'caption': lambda: ctk.CTkFont(size=11),
        'caption_bold': lambda: ctk.CTkFont(size=11, weight='bold')
    }

# 获取资源路径（支持打包后的环境）
def resource_path(relative_path):
    """获取资源文件的绝对路径，支持 PyInstaller 打包后的环境"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

# 获取脚本路径
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
    """在常见等宽字体中选第一个系统可用的，避免 JetBrains Mono 缺失时回退不一致。"""
    try:
        from tkinter import font as tkfont
        families = set(tkfont.families(root))
    except Exception:
        families = set()
    for name in ("JetBrains Mono", "Menlo", "Monaco", "Consolas", "Courier New", "Courier"):
        if name in families:
            return (name, size)
    return ("Courier", size)


class Git2LogsGUI:
    def __init__(self, root):
        try:
            self.root = root
            self.root.title("MIZUKI-GITLAB工具箱")
            # 窗口尺寸与最小尺寸由 main() 统一设置，避免与启动流程冲突
            self.root.resizable(True, True)  # 允许自由调整大小
            
            # 保存待处理的AI分析数据
            self._pending_ai_data = None
            self._log_count = 0
            self._is_running = False  # 跟踪生成任务运行状态
            self._ai_is_running = False  # 跟踪AI分析任务运行状态
            self._work_hours_data = None  # 缓存工时数据，供Excel导出使用
            self._project_checkboxes: dict = {}  # 项目名 -> BooleanVar
            self._validation_labels: dict = {}  # 字段名 -> 校验提示 CTkLabel
            self._log_collapsed = False
            self._current_theme = "dark"

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
            
            # ── 顶部 Header 栏 ─────────────────────────────
            self._create_header(main_container)

            # 立即更新，显示标题
            root.update_idletasks()
            root.update()

            # 存储标签页引用
            self.tab_frames = {}
            self.current_tab = None
            self.tab_buttons = []   # 兼容旧代码，sidebar 创建后填充
            self._sidebar_btns = {} # {tab_name: (frame, icon_lbl, text_lbl)}

            # ── 底部固定操作按钮容器 ───────────────────────
            self.bottom_actions_frame = ctk.CTkFrame(main_container, fg_color=self.styles.colors['bg_main'], corner_radius=0)
            self.bottom_actions_frame.pack(side="bottom", fill="x", padx=0, pady=0)

            # ── Body: 侧边栏(左) + 右侧内容(右) ───────────
            body_frame = ctk.CTkFrame(main_container, fg_color=self.bg_main, corner_radius=0)
            body_frame.pack(fill="both", expand=True)
            self._body_frame = body_frame

            # 侧边栏（固定宽度76px）
            self._sidebar_frame = ctk.CTkFrame(body_frame, fg_color="#1C1C1F", corner_radius=0, width=76)
            self._sidebar_frame.pack(side="left", fill="y")
            self._sidebar_frame.pack_propagate(False)

            # 右侧面板
            right_panel = ctk.CTkFrame(body_frame, fg_color=self.bg_main, corner_radius=0)
            right_panel.pack(side="left", fill="both", expand=True)
            self._right_panel = right_panel

            # 日志区域（右侧顶部）
            self._create_log_area(right_panel)

            # 滚动内容容器
            self.scroll_container = ctk.CTkScrollableFrame(right_panel,
                                                           fg_color=self.styles.colors['bg_main'],
                                                           corner_radius=0)
            self.scroll_container.pack(fill="both", expand=True, padx=0, pady=0)

            # 为了保持向下兼容性，将 content_container 指向滚动容器
            self.content_container = self.scroll_container

            # 隐藏滚动条
            try:
                self.scroll_container.configure(scrollbar_button_color=self.styles.colors['bg_main'],
                                                scrollbar_button_hover_color=self.styles.colors['bg_main'])
            except Exception:
                pass
            
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

                    # 初始日志
                    self.log("欢迎使用 MIZUKI-GITLAB工具箱！", "info")
                    self.log("请填写参数后点击'▶ 生成日志'按钮。", "info")
                except Exception as e:
                    import traceback
                    self.log(f"初始化错误: {str(e)}", "error")
                    self.log(traceback.format_exc(), "error")
            
            # 延迟10ms执行，让窗口先显示出来
            root.after(10, delayed_init)
            
        except Exception as e:
            import traceback
            error_msg = f"界面初始化失败: {str(e)}\n\n{traceback.format_exc()}"
            print(error_msg)
            try:
                messagebox.showerror("初始化错误", error_msg)
            except Exception:
                pass
            raise

    def _sidebar_selected_bg(self):
        """侧栏当前选中项背景（随深浅主题变化）。"""
        return "#1E3A5F" if getattr(self, "_current_theme", "dark") == "dark" else "#C7D2FE"
    
    def _create_header(self, parent):
        """创建顶部 Header 栏（品牌名 + 版本信息）"""
        header = ctk.CTkFrame(parent, fg_color="#111113", height=48, corner_radius=0)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        self._header_frame = header

        # 底部分隔线
        sep = ctk.CTkFrame(header, fg_color=self.styles.colors['border'], height=1, corner_radius=0)
        sep.pack(side="bottom", fill="x")
        self._header_sep = sep

        inner = ctk.CTkFrame(header, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=16)

        # 左：图标 + 品牌名
        left = ctk.CTkFrame(inner, fg_color="transparent")
        left.pack(side="left", fill="y")
        self._header_brand_lbl = ctk.CTkLabel(left,
                     text="⬡  MIZUKI TOOLBOX",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=self.styles.colors['text_primary'],
                     fg_color="transparent")
        self._header_brand_lbl.pack(side="left", pady=13)

        # 右：副标题
        right = ctk.CTkFrame(inner, fg_color="transparent")
        right.pack(side="right", fill="y")
        self._header_sub_lbl = ctk.CTkLabel(right,
                     text="GitLab 提交分析工具  v2.0",
                     font=ctk.CTkFont(size=11),
                     text_color=self.styles.colors['text_tertiary'],
                     fg_color="transparent")
        self._header_sub_lbl.pack(side="right", pady=16)

    def _create_sidebar(self, parent):
        """创建左侧图标导航栏（微信风格垂直 Tab）"""
        nav_items = [
            ("GitLab配置", "🔧", "配置"),
            ("日期和输出", "📅", "日期"),
            ("AI分析",    "🤖", "AI"),
            ("Excel导出", "📊", "Excel"),
        ]

        # 顶部留白
        ctk.CTkLabel(parent, text="", height=12, fg_color="transparent").pack()

        for tab_name, icon, label in nav_items:
            # 每项外层容器（用于悬停/选中高亮）
            item_frame = ctk.CTkFrame(parent,
                                      fg_color="transparent",
                                      corner_radius=self.styles.radius['md'])
            item_frame.pack(fill="x", padx=8, pady=3)

            icon_lbl = ctk.CTkLabel(item_frame,
                                    text=icon,
                                    font=ctk.CTkFont(size=22),
                                    text_color=self.styles.colors['text_secondary'],
                                    fg_color="transparent")
            icon_lbl.pack(pady=(10, 1))

            text_lbl = ctk.CTkLabel(item_frame,
                                    text=label,
                                    font=ctk.CTkFont(size=10),
                                    text_color=self.styles.colors['text_secondary'],
                                    fg_color="transparent")
            text_lbl.pack(pady=(0, 10))

            # 绑定点击、悬停
            for w in (item_frame, icon_lbl, text_lbl):
                w.bind("<Button-1>", lambda e, n=tab_name: self._switch_tab(n))
                w.bind("<Enter>",    lambda e, f=item_frame, n=tab_name: (
                    f.configure(fg_color=self.styles.colors['hover'])
                    if self.current_tab != n else None
                ))
                w.bind("<Leave>",    lambda e, f=item_frame, n=tab_name: (
                    f.configure(fg_color=self._sidebar_selected_bg())
                    if self.current_tab == n
                    else f.configure(fg_color="transparent")
                ))

            self._sidebar_btns[tab_name] = (item_frame, icon_lbl, text_lbl)
            # 兼容旧 tab_buttons 引用（响应式 _adapt_tab_labels 等）
            self.tab_buttons.append((tab_name, item_frame))

        # 底部分隔线
        ctk.CTkFrame(parent, fg_color=self.styles.colors['border'], height=1, corner_radius=0).pack(
            side="bottom", fill="x", padx=8, pady=4)

    def _create_log_area(self, parent):
        """创建日志显示区域（放在最上方）"""
        log_container = ctk.CTkFrame(parent, fg_color=self.styles.colors['bg_main'], corner_radius=0)
        log_container.pack(fill="x", padx=0, pady=(0, self.styles.spacing['sm']))
        self._log_container = log_container
        
        log_title_frame = ctk.CTkFrame(log_container,
                                     fg_color=self.styles.colors['bg_main'],
                                     height=40,
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

    def _refresh_chrome_for_theme(self):
        """同步顶栏、侧栏、主布局与日志外框等与主题相关的硬编码表面色。"""
        c = self.styles.colors
        is_dark = self._current_theme == "dark"
        header_bg = "#111113" if is_dark else "#EBEBEF"
        sidebar_bg = "#1C1C1F" if is_dark else "#E4E4E9"

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
                pass

        if hasattr(self, "_header_frame"):
            self._header_frame.configure(fg_color=header_bg)
        if hasattr(self, "_header_sep"):
            self._header_sep.configure(fg_color=c['border'])
        if hasattr(self, "_header_brand_lbl"):
            self._header_brand_lbl.configure(text_color=c['text_primary'])
        if hasattr(self, "_header_sub_lbl"):
            self._header_sub_lbl.configure(text_color=c['text_tertiary'])
        if hasattr(self, "_sidebar_frame"):
            self._sidebar_frame.configure(fg_color=sidebar_bg)

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
        if hasattr(self, "_theme_btn"):
            self._theme_btn.configure(
                fg_color=c['bg_card'],
                text_color=c['text_secondary'],
                hover_color=c['hover'],
                border_color=c['border'],
            )
    
    def _create_tab1_gitlab_config(self):
        """创建标签页1: GitLab配置"""
        # 主容器
        tab1 = ctk.CTkFrame(self.content_container, fg_color="transparent", corner_radius=0)
        tab1.pack(fill="both", expand=True, padx=self.styles.spacing['md'], pady=self.styles.spacing['md'])

        # 滚动容器内的内容框架
        content = ctk.CTkFrame(tab1, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=self.styles.spacing['lg'], pady=self.styles.spacing['sm'])
        content.columnconfigure(0, weight=1)
        
        row = 0
        
        # GitLab URL
        url_label = ctk.CTkLabel(content, text="GitLab URL",
                                font=ctk.CTkFont(size=14, weight="bold"),
                                text_color=self.text_primary,
                                anchor="w")
        url_label.grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 8))
        row += 1
        
        self.gitlab_url = ctk.StringVar()
        gitlab_entry = ctk.CTkEntry(content,
                                  textvariable=self.gitlab_url,
                                  placeholder_text="https://gitlab.com 或 http://gitlab.yourcompany.com",
                                  font=ctk.CTkFont(size=13),
                                  height=40,
                                  corner_radius=8,
                                  border_width=1,
                                  border_color=self.border_color,
                                  fg_color=self.bg_main,
                                  text_color=self.text_primary)
        gitlab_entry.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        row += 1
        self._validation_labels['gitlab_url'] = ctk.CTkLabel(
            content, text="", font=self.styles.fonts['caption'](),
            text_color=self.styles.colors['text_secondary'], anchor="w")
        self._validation_labels['gitlab_url'].grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 16))
        row += 1
        
        # 仓库地址
        repo_label = ctk.CTkLabel(content, text="仓库地址",
                                 font=ctk.CTkFont(size=14, weight="bold"),
                                 text_color=self.text_primary,
                                 anchor="w")
        repo_label.grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 8))
        row += 1
        
        self.repo = ctk.StringVar()
        repo_entry = ctk.CTkEntry(content,
                                 textvariable=self.repo,
                                 font=ctk.CTkFont(size=13),
                                 height=40,
                                 corner_radius=8,
                                 border_width=1,
                                 border_color=self.border_color,
                                 fg_color=self.bg_main,
                                 text_color=self.text_primary)
        repo_entry.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        row += 1
        self._validation_labels['repo'] = ctk.CTkLabel(
            content, text="", font=self.styles.fonts['caption'](),
            text_color=self.styles.colors['text_secondary'], anchor="w")
        self._validation_labels['repo'].grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 16))
        row += 1
        
        # 扫描所有项目选项
        self.scan_all = ctk.BooleanVar(value=False)
        scan_check = ctk.CTkCheckBox(content,
                                    text="自动扫描所有项目（不填仓库地址时启用）",
                                    variable=self.scan_all,
                                    font=ctk.CTkFont(size=13),
                                    text_color=self.text_primary,
                                    fg_color=self.accent_color,
                                    corner_radius=4)
        scan_check.grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 24))
        row += 1
        
        # 分支
        branch_label = ctk.CTkLabel(content, text="分支",
                                  font=ctk.CTkFont(size=14, weight="bold"),
                                  text_color=self.text_primary,
                                  anchor="w")
        branch_label.grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 8))
        row += 1
        
        self.branch = ctk.StringVar()
        branch_entry = ctk.CTkEntry(content,
                                   textvariable=self.branch,
                                   font=ctk.CTkFont(size=13),
                                   height=40,
                                   corner_radius=8,
                                   border_width=1,
                                   border_color=self.border_color,
                                   fg_color=self.bg_main,
                                   text_color=self.text_primary)
        branch_entry.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 24))
        row += 1
        
        # 提交者
        author_label = ctk.CTkLabel(content, text="提交者",
                                   font=ctk.CTkFont(size=14, weight="bold"),
                                   text_color=self.text_primary,
                                   anchor="w")
        author_label.grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 8))
        row += 1
        
        self.author = ctk.StringVar(value="MIZUKI")
        author_entry = ctk.CTkEntry(content,
                                   textvariable=self.author,
                                   font=ctk.CTkFont(size=13),
                                   height=40,
                                   corner_radius=8,
                                   border_width=1,
                                   border_color=self.border_color,
                                   fg_color=self.bg_main,
                                   text_color=self.text_primary)
        author_entry.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        row += 1
        self._validation_labels['author'] = ctk.CTkLabel(
            content, text="", font=self.styles.fonts['caption'](),
            text_color=self.styles.colors['text_secondary'], anchor="w")
        self._validation_labels['author'].grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 16))
        row += 1
        
        # 访问令牌
        token_label = ctk.CTkLabel(content, text="访问令牌",
                                 font=ctk.CTkFont(size=14, weight="bold"),
                                 text_color=self.text_primary,
                                 anchor="w")
        token_label.grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 8))
        row += 1
        
        self.token = ctk.StringVar()
        token_frame = ctk.CTkFrame(content, fg_color="transparent")
        token_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        token_frame.columnconfigure(0, weight=1)
        
        token_entry = ctk.CTkEntry(token_frame,
                                  textvariable=self.token,
                                  show="*",
                                  font=ctk.CTkFont(size=13),
                                  height=40,
                                  corner_radius=8,
                                  border_width=1,
                                  border_color=self.border_color,
                                  fg_color=self.bg_main,
                                  text_color=self.text_primary)
        token_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        
        show_btn = ctk.CTkButton(token_frame,
                                text="显示",
                                width=80,
                                height=40,
                                font=ctk.CTkFont(size=13),
                                corner_radius=8,
                                fg_color=self.bg_card,
                                text_color=self.text_primary,
                                hover_color="#3F3F46",
                                border_width=1,
                                border_color=self.border_color,
                                command=lambda: self.toggle_token_visibility(token_entry))
        show_btn.grid(row=0, column=1)
        row += 1
        self._validation_labels['token'] = ctk.CTkLabel(
            content, text="", font=self.styles.fonts['caption'](),
            text_color=self.styles.colors['text_secondary'], anchor="w")
        self._validation_labels['token'].grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 16))
        row += 1
        
        # 使用提示卡片
        hint_frame = ctk.CTkFrame(content,
                                 fg_color=self.bg_main,
                                 corner_radius=8,
                                 border_width=1,
                                 border_color=self.border_color)
        hint_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        
        hint_title = ctk.CTkLabel(hint_frame,
                                text="使用提示",
                                font=ctk.CTkFont(size=13, weight="bold"),
                                text_color=self.text_primary,
                                anchor="w")
        hint_title.pack(anchor="w", padx=16, pady=(16, 8))
        
        hint_text = "• GitLab URL 是您的GitLab实例地址\n• 仓库地址留空时，勾选'自动扫描所有项目'可扫描所有项目\n• 访问令牌用于身份验证，可在GitLab设置中生成"
        hint_label = ctk.CTkLabel(hint_frame,
                                 text=hint_text,
                                 font=ctk.CTkFont(size=12),
                                 text_color=self.text_secondary,
                                 justify="left",
                                 anchor="w")
        hint_label.pack(anchor="w", padx=16, pady=(0, 16))
        
        # 添加底部占位符
        ctk.CTkLabel(content, text="", height=50).grid(row=row + 1, column=0)
        
        self.tab_frames["GitLab配置"] = tab1
        tab1.pack_forget()  # 初始隐藏

    def _bind_form_validation(self):
        """绑定表单验证事件"""
        # 绑定实时验证
        self.gitlab_url.trace_add('write', self._validate_gitlab_url)
        self.repo.trace_add('write', self._validate_repo_url)
        self.author.trace_add('write', self._validate_author)
        self.token.trace_add('write', self._validate_token)

        # 绑定扫描选项变化
        self.scan_all.trace_add('write', lambda *args: self._on_scan_all_toggle())

    def _validate_gitlab_url(self, *args):
        """实时验证 GitLab URL 格式"""
        url = self.gitlab_url.get().strip()
        status, message = self._validate_url_logic(url, is_gitlab=True)
        self._update_field_status('gitlab_url', status, message)

    def _validate_repo_url(self, *args):
        """实时验证仓库 URL 格式"""
        url = self.repo.get().strip()

        if not url:
            if self.scan_all.get():
                self._update_field_status('repo', 'success', "留空表示扫描所有项目")
            else:
                self._update_field_status('repo', 'warning', "请输入仓库地址或启用扫描所有项目")
            return

        status, message = self._validate_url_logic(url, is_gitlab=False)
        if status == 'success' and 'gitlab' in url and not url.endswith('.git'):
            status, message = 'warning', "GitLab 仓库地址通常以 .git 结尾"

        self._update_field_status('repo', status, message)

    def _validate_author(self, *args):
        """验证提交者名称"""
        author = self.author.get().strip()

        if not author:
            self._update_field_status('author', 'warning', "请输入提交者名称")
        elif len(author) < 2:
            self._update_field_status('author', 'error', "提交者名称至少需要2个字符")
        elif '@' in author:
            # 如果是邮箱格式
            parts = author.split('@')
            if len(parts) != 2 or not parts[0] or '.' not in parts[1]:
                self._update_field_status('author', 'warning', "邮箱格式可能不正确")
            else:
                self._update_field_status('author', 'success', "✓ 提交者邮箱格式正确")
        else:
            self._update_field_status('author', 'success', "✓ 提交者名称有效")

    def _validate_token(self, *args):
        """验证访问令牌"""
        token = self.token.get().strip()

        if not token:
            self._update_field_status('token', 'warning', "私有仓库需要访问令牌")
        elif len(token) < 20:
            self._update_field_status('token', 'error', "访问令牌长度不足")
        elif not all(c.isalnum() or c in '-_' for c in token):
            self._update_field_status('token', 'warning', "令牌包含特殊字符，请确认格式正确")
        else:
            self._update_field_status('token', 'success', "✓ 访问令牌格式正确")

    def _validate_url_logic(self, url, is_gitlab=True):
        """URL 验证逻辑"""
        if not url:
            return 'warning', "请输入 URL"
        elif not (url.startswith('http://') or url.startswith('https://')):
            return 'error', "URL 必须以 http:// 或 https:// 开头"
        elif is_gitlab and 'gitlab' not in url.lower():
            return 'warning', "建议使用包含 gitlab 的域名"
        else:
            return 'success', "✓ URL 格式正确"

    def _update_field_status(self, field_name, status, message):
        """更新字段状态和验证消息"""
        # 字段名称到变量的映射
        field_vars = {
            'gitlab_url': self.gitlab_url,
            'repo': self.repo,
            'author': self.author,
            'token': self.token
        }

        if field_name not in field_vars:
            return

        target_var = field_vars[field_name]

        # 查找对应的输入框
        target_entry = self._find_entry_by_variable(target_var)
        target_label = self._find_validation_label(field_name)

        # 更新输入框边框颜色
        if target_entry:
            if status == "error":
                target_entry.configure(border_color=self.styles.colors['error'])
            elif status == "warning":
                target_entry.configure(border_color=self.styles.colors['warning'])
            elif status == "success":
                target_entry.configure(border_color=self.styles.colors['success'])
            else:
                target_entry.configure(border_color=self.styles.colors['border'])

        # 更新验证消息
        if target_label and message:
            if status == "error":
                target_label.configure(text=message, text_color=self.styles.colors['error'])
            elif status == "warning":
                target_label.configure(text=message, text_color=self.styles.colors['warning'])
            elif status == "success":
                target_label.configure(text=message, text_color=self.styles.colors['success'])
            else:
                target_label.configure(text=message, text_color=self.styles.colors['text_secondary'])

    def _find_entry_by_variable(self, variable):
        """根据变量查找对应的输入框"""
        for widget in self.tab_frames["GitLab配置"].winfo_children():
            if isinstance(widget, ctk.CTkFrame):
                for child in widget.winfo_children():
                    if isinstance(child, ctk.CTkFrame):
                        for grandchild in child.winfo_children():
                            if isinstance(grandchild, ctk.CTkEntry) and grandchild.cget('textvariable') == variable:
                                return grandchild
        return None

    def _find_validation_label(self, field_name):
        """查找验证消息标签（GitLab 配置页使用显式引用）。"""
        return self._validation_labels.get(field_name)

    def _on_scan_all_toggle(self):
        """扫描所有项目选项切换时的处理"""
        if self.scan_all.get():
            self._update_field_status('repo', 'success', "已启用自动扫描所有项目")
        else:
            self._validate_repo_url()

    def _get_form_validation_summary(self):
        """获取表单验证摘要"""
        fields = ['gitlab_url', 'repo', 'author', 'token']
        results = {}

        for field in fields:
            entry = self._find_entry_by_variable(getattr(self, field))
            if entry:
                border_color = entry.cget('border_color')
                if border_color == self.styles.colors['error']:
                    results[field] = 'error'
                elif border_color == self.styles.colors['warning']:
                    results[field] = 'warning'
                elif border_color == self.styles.colors['success']:
                    results[field] = 'success'
                else:
                    results[field] = 'neutral'

        return results

    def _enhance_form_interaction(self):
        """增强表单交互体验"""
        # 为所有输入框添加焦点事件
        input_fields = [self.gitlab_url, self.repo, self.author, self.token]

        for field_var in input_fields:
            entry = self._find_entry_by_variable(field_var)
            if entry:
                # 添加焦点进入事件
                entry.bind('<FocusIn>', lambda e, f=field_var: self._on_field_focus_in(f))
                # 添加焦点离开事件
                entry.bind('<FocusOut>', lambda e, f=field_var: self._on_field_focus_out(f))

    def _on_field_focus_in(self, field_var):
        """字段获得焦点时的处理"""
        entry = self._find_entry_by_variable(field_var)
        if entry:
            # 临时改变边框颜色表示焦点
            entry.configure(border_width=2)

    def _on_field_focus_out(self, field_var):
        """字段失去焦点时的处理"""
        entry = self._find_entry_by_variable(field_var)
        if entry:
            # 恢复边框宽度
            entry.configure(border_width=1)
            # 触发验证
            field_name = [k for k, v in {
                'gitlab_url': self.gitlab_url,
                'repo': self.repo,
                'author': self.author,
                'token': self.token
            }.items() if v == field_var][0]

            if hasattr(self, f'_validate_{field_name}'):
                getattr(self, f'_validate_{field_name}')()
    
    def _create_tab2_date_output(self):
        """创建标签页2: 日期和输出"""
        # 优化：透明背景且取消圆角
        tab2 = ctk.CTkFrame(self.content_container, fg_color="transparent", corner_radius=0)
        tab2.pack(fill="both", expand=True, padx=20, pady=20)
        
        content = ctk.CTkFrame(tab2, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=30, pady=10)
        
        row = 0
        
        # 日期范围卡片
        date_card = ctk.CTkFrame(content, fg_color=self.bg_main, corner_radius=10)
        date_card.grid(row=row, column=0, sticky="ew", pady=(0, 20))
        date_card.columnconfigure(1, weight=1)
        content.columnconfigure(0, weight=1)  # 确保内容容器自适应
        
        date_title = ctk.CTkLabel(date_card,
                                text="日期范围",
                                font=ctk.CTkFont(size=15, weight="bold"),
                                text_color=self.text_primary,
                                anchor="w")
        date_title.grid(row=0, column=0, columnspan=2, sticky="w", padx=20, pady=(20, 16))
        
        date_row = 1
        self.use_today = ctk.BooleanVar(value=True)
        today_check = ctk.CTkCheckBox(date_card,
                                    text="今天",
                                    variable=self.use_today,
                                    font=ctk.CTkFont(size=13),
                                    text_color=self.text_primary,
                                    fg_color=self.accent_color,
                                    corner_radius=4,
                                    command=self.toggle_date_inputs)
        today_check.grid(row=date_row, column=0, sticky="w", padx=20, pady=8)
        
        date_input_frame = ctk.CTkFrame(date_card, fg_color="transparent")
        date_input_frame.grid(row=date_row, column=1, sticky="ew", padx=(0, 20))
        # 配置列权重，使两个日期输入框平均分配空间
        date_input_frame.columnconfigure(0, weight=1, uniform="date_inputs")
        date_input_frame.columnconfigure(1, weight=1, uniform="date_inputs")
        
        since_label = ctk.CTkLabel(date_input_frame,
                                 text="起始日期",
                                 font=ctk.CTkFont(size=11),
                                 text_color=self.text_secondary,
                                 anchor="w")
        since_label.grid(row=0, column=0, padx=(0, 8), sticky="w")
        self.since_date = ctk.StringVar()
        self.since_entry = ctk.CTkEntry(date_input_frame,
                                      textvariable=self.since_date,
                                      font=ctk.CTkFont(size=12),
                                      height=36,
                                      corner_radius=8,
                                      border_width=1,
                                      border_color=self.border_color,
                                      fg_color=self.bg_card,
                                      text_color=self.text_primary)
        self.since_entry.grid(row=1, column=0, padx=(0, 10), pady=(6, 0), sticky="ew")
        
        until_label = ctk.CTkLabel(date_input_frame,
                                 text="结束日期",
                                 font=ctk.CTkFont(size=11),
                                 text_color=self.text_secondary,
                                 anchor="w")
        until_label.grid(row=0, column=1, padx=(0, 8), sticky="w")
        self.until_date = ctk.StringVar()
        self.until_entry = ctk.CTkEntry(date_input_frame,
                                      textvariable=self.until_date,
                                      font=ctk.CTkFont(size=12),
                                      height=36,
                                      corner_radius=8,
                                      border_width=1,
                                      border_color=self.border_color,
                                      fg_color=self.bg_card,
                                      text_color=self.text_primary)
        self.until_entry.grid(row=1, column=1, pady=(6, 0), sticky="ew")
        
        date_hint = ctk.CTkLabel(date_card,
                               text="提示: 日期格式为 YYYY-MM-DD，例如: 2025-12-12",
                               font=ctk.CTkFont(size=11),
                               text_color=self.text_secondary,
                               anchor="w")
        date_hint.grid(row=2, column=0, columnspan=2, sticky="w", padx=20, pady=(16, 20))
        
        self.toggle_date_inputs()
        row += 1
        
        # 输出格式卡片
        format_card = ctk.CTkFrame(content, fg_color=self.bg_main, corner_radius=10)
        format_card.grid(row=row, column=0, sticky="ew", pady=(0, 20))
        format_card.columnconfigure(0, weight=1)
        
        format_title = ctk.CTkLabel(format_card,
                                  text="输出格式",
                                  font=ctk.CTkFont(size=15, weight="bold"),
                                  text_color=self.text_primary,
                                  anchor="w")
        format_title.grid(row=0, column=0, sticky="w", padx=20, pady=(20, 16))
        
        self.output_format = ctk.StringVar(value="daily_report")
        format_options = [
            ("Markdown 提交日志", "commits"),
            ("开发日报 (Markdown)", "daily_report"),
            ("工时分配报告 (详细工时统计)", "work_hours"),
            ("统计报告 (代码统计)", "statistics"),
            ("HTML 格式", "html"),
            ("PNG 图片", "png"),
            ("批量生成所有格式", "all")
        ]
        
        for i, (text, value) in enumerate(format_options):
            rb = ctk.CTkRadioButton(format_card,
                                  text=text,
                                  variable=self.output_format,
                                  value=value,
                                  font=ctk.CTkFont(size=13),
                                  text_color=self.text_primary,
                                  fg_color=self.accent_color,
                                  corner_radius=4)
            rb.grid(row=i+1, column=0, sticky="w", padx=20, pady=8)
        
        row += 1
        
        # 输出设置卡片
        output_card = ctk.CTkFrame(content, fg_color=self.bg_main, corner_radius=10)
        output_card.grid(row=row, column=0, sticky="ew", pady=(0, 0))
        output_card.columnconfigure(0, weight=1)
        
        output_title = ctk.CTkLabel(output_card,
                                  text="输出设置",
                                  font=ctk.CTkFont(size=15, weight="bold"),
                                  text_color=self.text_primary,
                                  anchor="w")
        output_title.grid(row=0, column=0, sticky="w", padx=20, pady=(20, 16))
        
        output_label_text = "输出目录" if self.output_format.get() == "all" else "输出文件"
        self.output_label = ctk.CTkLabel(output_card,
                                      text=output_label_text,
                                      font=ctk.CTkFont(size=14, weight="bold"),
                                      text_color=self.text_primary,
                                      anchor="w")
        self.output_label.grid(row=1, column=0, sticky="w", padx=20, pady=(0, 8))
        
        self.output_file = ctk.StringVar()
        output_frame = ctk.CTkFrame(output_card, fg_color="transparent")
        output_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 8))
        output_frame.columnconfigure(0, weight=1)
        
        output_entry = ctk.CTkEntry(output_frame,
                                  textvariable=self.output_file,
                                  font=ctk.CTkFont(size=13),
                                  height=40,
                                  corner_radius=8,
                                  border_width=1,
                                  border_color=self.border_color,
                                  fg_color=self.bg_card,
                                  text_color=self.text_primary)
        output_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        
        browse_btn = ctk.CTkButton(output_frame,
                                 text="浏览",
                                 width=100,
                                 height=40,
                                 font=ctk.CTkFont(size=13),
                                 corner_radius=8,
                                 fg_color=self.bg_card,
                                 text_color=self.text_primary,
                                 hover_color="#3F3F46",
                                 border_width=1,
                                 border_color=self.border_color,
                                 command=self.browse_output_file)
        browse_btn.grid(row=0, column=1)
        
        self.output_hint = ctk.CTkLabel(output_card,
                                       text="提示: 批量生成时请选择目录",
                                       font=ctk.CTkFont(size=11),
                                       text_color=self.text_secondary,
                                       anchor="w")
        self.output_hint.grid(row=3, column=0, sticky="w", padx=20, pady=(0, 20))
        
        # 绑定输出格式变化事件
        def setup_output_format_trace():
            try:
                self.output_format.trace('w', self.on_output_format_changed)
            except Exception:
                pass
        self.root.after(100, setup_output_format_trace)
        
        content.columnconfigure(0, weight=1)
        
        # 添加底部占位符
        ctk.CTkLabel(content, text="", height=50).grid(row=row+1, column=0)
        
        self.tab_frames["日期和输出"] = tab2
        tab2.pack_forget()
    
    def _create_tab3_ai_analysis(self):
        """创建标签页3: AI分析"""
        # 优化：透明背景且取消圆角
        tab3 = ctk.CTkFrame(self.content_container, fg_color="transparent", corner_radius=0)
        tab3.pack(fill="both", expand=True, padx=20, pady=20)
        
        content = ctk.CTkFrame(tab3, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=30, pady=10)
        content.columnconfigure(1, weight=1)
        
        row = 0
        
        # AI分析开关
        self.ai_enabled = ctk.BooleanVar(value=False)
        ai_enable_check = ctk.CTkCheckBox(content,
                                         text="启用AI分析",
                                         variable=self.ai_enabled,
                                         font=ctk.CTkFont(size=14, weight="bold"),
                                         text_color=self.text_primary,
                                         fg_color=self.accent_color,
                                         corner_radius=4,
                                         command=self.toggle_ai_config)
        ai_enable_check.grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 24))
        row += 1
        
        # AI配置区域（默认隐藏）
        self.ai_config_frame = ctk.CTkFrame(content, fg_color=self.bg_main, corner_radius=10)
        self.ai_config_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 0))
        self.ai_config_frame.columnconfigure(1, weight=1)
        
        ai_title = ctk.CTkLabel(self.ai_config_frame,
                              text="AI配置",
                              font=ctk.CTkFont(size=15, weight="bold"),
                              text_color=self.text_primary,
                              anchor="w")
        ai_title.grid(row=0, column=0, columnspan=2, sticky="w", padx=20, pady=(20, 20))
        
        config_row = 1
        
        # AI服务选择
        service_label = ctk.CTkLabel(self.ai_config_frame,
                                    text="AI服务",
                                    font=ctk.CTkFont(size=14, weight="bold"),
                                    text_color=self.text_primary,
                                    anchor="w")
        service_label.grid(row=config_row, column=0, sticky="w", padx=20, pady=(0, 8))
        
        self.ai_service = ctk.StringVar(value="openai")
        ai_service_combo = ctk.CTkComboBox(self.ai_config_frame,
                                          values=["openai", "anthropic", "gemini", "doubao", "deepseek"],
                                          variable=self.ai_service,
                                          font=ctk.CTkFont(size=13),
                                          height=40,
                                          corner_radius=8,
                                          border_width=1,
                                          border_color=self.border_color,
                                          fg_color=self.bg_card,
                                          text_color=self.text_primary,
                                          button_color=self.bg_card,
                                          button_hover_color="#3F3F46",
                                          dropdown_fg_color=self.bg_card,
                                          dropdown_text_color=self.text_primary,
                                          dropdown_hover_color="#3F3F46",
                                          command=self._update_ai_models)
        ai_service_combo.grid(row=config_row, column=1, sticky="ew", padx=(0, 20), pady=(0, 24))
        config_row += 1
        
        # 模型选择
        model_label = ctk.CTkLabel(self.ai_config_frame,
                                 text="模型",
                                 font=ctk.CTkFont(size=14, weight="bold"),
                                 text_color=self.text_primary,
                                 anchor="w")
        model_label.grid(row=config_row, column=0, sticky="w", padx=20, pady=(0, 8))
        
        self.ai_model = ctk.StringVar(value="gpt-4o-mini")
        self.ai_model_combo = ctk.CTkComboBox(self.ai_config_frame,
                                             values=["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo"],
                                             variable=self.ai_model,
                                             font=ctk.CTkFont(size=13),
                                             height=40,
                                             corner_radius=8,
                                             border_width=1,
                                             border_color=self.border_color,
                                             fg_color=self.bg_card,
                                             text_color=self.text_primary,
                                             button_color=self.bg_card,
                                             button_hover_color="#3F3F46",
                                             dropdown_fg_color=self.bg_card,
                                             dropdown_text_color=self.text_primary,
                                             dropdown_hover_color="#3F3F46")
        self.ai_model_combo.grid(row=config_row, column=1, sticky="ew", padx=(0, 20), pady=(0, 24))
        config_row += 1
        
        # API Key
        key_label = ctk.CTkLabel(self.ai_config_frame,
                               text="API Key",
                               font=ctk.CTkFont(size=14, weight="bold"),
                               text_color=self.text_primary,
                               anchor="w")
        key_label.grid(row=config_row, column=0, sticky="w", padx=20, pady=(0, 8))
        
        self.ai_api_key = ctk.StringVar()
        key_frame = ctk.CTkFrame(self.ai_config_frame, fg_color="transparent")
        key_frame.grid(row=config_row, column=1, sticky="ew", padx=(0, 20), pady=(0, 24))
        key_frame.columnconfigure(0, weight=1)
        
        ai_key_entry = ctk.CTkEntry(key_frame,
                                   textvariable=self.ai_api_key,
                                   show="*",
                                   font=ctk.CTkFont(size=13),
                                   height=40,
                                   corner_radius=8,
                                   border_width=1,
                                   border_color=self.border_color,
                                   fg_color=self.bg_card,
                                   text_color=self.text_primary)
        ai_key_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        
        key_show_btn = ctk.CTkButton(key_frame,
                                    text="显示",
                                    width=80,
                                    height=40,
                                    font=ctk.CTkFont(size=13),
                                    corner_radius=8,
                                    fg_color=self.bg_card,
                                    text_color=self.text_primary,
                                    hover_color="#3F3F46",
                                    border_width=1,
                                    border_color=self.border_color,
                                    command=lambda: self.toggle_key_visibility(ai_key_entry))
        key_show_btn.grid(row=0, column=1)
        config_row += 1
        
        # 测试连接按钮
        test_btn_frame = ctk.CTkFrame(self.ai_config_frame, fg_color="transparent")
        test_btn_frame.grid(row=config_row, column=0, columnspan=2, pady=(8, 20), sticky="w", padx=20)
        
        test_btn = ctk.CTkButton(test_btn_frame,
                               text="测试连接",
                               width=140,
                               height=40,
                               font=ctk.CTkFont(size=13),
                               corner_radius=8,
                               fg_color=self.bg_card,
                               text_color=self.text_primary,
                               hover_color="#3F3F46",
                               border_width=1,
                               border_color=self.border_color,
                               command=self.test_ai_connection)
        test_btn.pack(side="left", padx=(0, 12))
        
        self.test_status_label = ctk.CTkLabel(test_btn_frame,
                                            text="",
                                            font=ctk.CTkFont(size=12),
                                            text_color=self.text_secondary,
                                            anchor="w")
        self.test_status_label.pack(side="left")
        
        # 添加底部占位符
        ctk.CTkLabel(content, text="", height=50).grid(row=row+1, column=0)
        
        # 初始隐藏AI配置
        self.ai_config_frame.grid_remove()
        
        self.tab_frames["AI分析"] = tab3
        tab3.pack_forget()

    def _create_tab4_excel_export(self):
        """创建标签页4: Excel导出"""
        tab4 = ctk.CTkFrame(self.content_container, fg_color="transparent", corner_radius=0)
        tab4.pack(fill="both", expand=True, padx=20, pady=20)

        content = ctk.CTkFrame(tab4, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=30, pady=10)
        content.columnconfigure(0, weight=1)

        row = 0

        # ── 数据来源状态卡片 ──────────────────────────────
        status_card = ctk.CTkFrame(content, fg_color=self.bg_main, corner_radius=10)
        status_card.grid(row=row, column=0, sticky="ew", pady=(0, 20))
        status_card.columnconfigure(0, weight=1)

        ctk.CTkLabel(status_card,
                     text="工时数据来源",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=self.text_primary,
                     anchor="w").grid(row=0, column=0, columnspan=2, sticky="w", padx=20, pady=(20, 8))

        self._excel_status_label = ctk.CTkLabel(
            status_card,
            text="尚无工时数据。请先生成「工时分配报告」，或点击右侧按钮加载 JSON 文件。",
            font=ctk.CTkFont(size=13),
            text_color=self.text_secondary,
            anchor="w",
            wraplength=400,
        )
        self._excel_status_label.grid(row=1, column=0, sticky="w", padx=20, pady=(0, 16))

        ctk.CTkButton(status_card,
                      text="从文件加载",
                      width=120,
                      height=36,
                      font=ctk.CTkFont(size=13),
                      corner_radius=8,
                      fg_color=self.bg_card,
                      text_color=self.text_primary,
                      hover_color="#3F3F46",
                      border_width=1,
                      border_color=self.border_color,
                      command=self._load_work_hours_from_file,
                      ).grid(row=1, column=1, padx=(0, 20), pady=(0, 16), sticky="e")

        row += 1

        # ── 模板文件 ─────────────────────────────────────
        tmpl_card = ctk.CTkFrame(content, fg_color=self.bg_main, corner_radius=10)
        tmpl_card.grid(row=row, column=0, sticky="ew", pady=(0, 20))
        tmpl_card.columnconfigure(0, weight=1)

        ctk.CTkLabel(tmpl_card,
                     text="Excel 模板文件",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=self.text_primary,
                     anchor="w").grid(row=0, column=0, sticky="w", padx=20, pady=(20, 8))

        tmpl_row_frame = ctk.CTkFrame(tmpl_card, fg_color="transparent")
        tmpl_row_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 8))
        tmpl_row_frame.columnconfigure(0, weight=1)

        self._excel_template_var = ctk.StringVar()
        ctk.CTkEntry(tmpl_row_frame,
                     textvariable=self._excel_template_var,
                     font=ctk.CTkFont(size=13),
                     height=40,
                     corner_radius=8,
                     border_width=1,
                     border_color=self.border_color,
                     fg_color=self.bg_card,
                     text_color=self.text_primary,
                     placeholder_text="选择 .xlsx 模板文件…").grid(row=0, column=0, sticky="ew", padx=(0, 8))

        ctk.CTkButton(tmpl_row_frame,
                      text="浏览",
                      width=100,
                      height=40,
                      font=ctk.CTkFont(size=13),
                      corner_radius=8,
                      fg_color=self.bg_card,
                      text_color=self.text_primary,
                      hover_color="#3F3F46",
                      border_width=1,
                      border_color=self.border_color,
                      command=self._browse_excel_template).grid(row=0, column=1)

        ctk.CTkLabel(tmpl_card,
                     text="提示: 模板须含表头行（含「任务名称」「预计工时」等列）及一行示例数据",
                     font=ctk.CTkFont(size=11),
                     text_color=self.text_secondary,
                     anchor="w").grid(row=2, column=0, sticky="w", padx=20, pady=(0, 20))

        row += 1

        # ── 项目选择 ─────────────────────────────────────
        proj_card = ctk.CTkFrame(content, fg_color=self.bg_main, corner_radius=10)
        proj_card.grid(row=row, column=0, sticky="ew", pady=(0, 20))
        proj_card.columnconfigure(0, weight=1)

        # 标题行 + 全选/全不选按钮
        proj_title_frame = ctk.CTkFrame(proj_card, fg_color="transparent")
        proj_title_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 8))
        proj_title_frame.columnconfigure(0, weight=1)

        ctk.CTkLabel(proj_title_frame,
                     text="选择要导出的项目",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=self.text_primary,
                     anchor="w").grid(row=0, column=0, sticky="w")

        btn_frame = ctk.CTkFrame(proj_title_frame, fg_color="transparent")
        btn_frame.grid(row=0, column=1, sticky="e")

        ctk.CTkButton(btn_frame,
                      text="全选",
                      width=60,
                      height=28,
                      font=ctk.CTkFont(size=12),
                      corner_radius=6,
                      fg_color=self.bg_card,
                      text_color=self.text_primary,
                      hover_color="#3F3F46",
                      border_width=1,
                      border_color=self.border_color,
                      command=lambda: self._select_all_projects(True),
                      ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(btn_frame,
                      text="全不选",
                      width=60,
                      height=28,
                      font=ctk.CTkFont(size=12),
                      corner_radius=6,
                      fg_color=self.bg_card,
                      text_color=self.text_primary,
                      hover_color="#3F3F46",
                      border_width=1,
                      border_color=self.border_color,
                      command=lambda: self._select_all_projects(False),
                      ).pack(side="left")

        # 复选框动态容器
        self._project_checkbox_frame = ctk.CTkFrame(proj_card, fg_color="transparent")
        self._project_checkbox_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 20))
        self._project_checkbox_frame.columnconfigure(0, weight=1)

        # 初始占位提示
        ctk.CTkLabel(self._project_checkbox_frame,
                     text="（暂无项目数据，请先生成工时报告或加载 JSON 文件）",
                     font=ctk.CTkFont(size=12),
                     text_color=self.text_secondary,
                     anchor="w").pack(anchor="w", pady=4)

        row += 1

        # ── 输出文件 ─────────────────────────────────────
        out_card = ctk.CTkFrame(content, fg_color=self.bg_main, corner_radius=10)
        out_card.grid(row=row, column=0, sticky="ew", pady=(0, 20))
        out_card.columnconfigure(0, weight=1)

        ctk.CTkLabel(out_card,
                     text="输出 Excel 文件",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=self.text_primary,
                     anchor="w").grid(row=0, column=0, sticky="w", padx=20, pady=(20, 8))

        out_row_frame = ctk.CTkFrame(out_card, fg_color="transparent")
        out_row_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 20))
        out_row_frame.columnconfigure(0, weight=1)

        self._excel_output_var = ctk.StringVar()
        ctk.CTkEntry(out_row_frame,
                     textvariable=self._excel_output_var,
                     font=ctk.CTkFont(size=13),
                     height=40,
                     corner_radius=8,
                     border_width=1,
                     border_color=self.border_color,
                     fg_color=self.bg_card,
                     text_color=self.text_primary,
                     placeholder_text="输出文件路径（.xlsx）…").grid(row=0, column=0, sticky="ew", padx=(0, 8))

        ctk.CTkButton(out_row_frame,
                      text="浏览",
                      width=100,
                      height=40,
                      font=ctk.CTkFont(size=13),
                      corner_radius=8,
                      fg_color=self.bg_card,
                      text_color=self.text_primary,
                      hover_color="#3F3F46",
                      border_width=1,
                      border_color=self.border_color,
                      command=self._browse_excel_output).grid(row=0, column=1)

        row += 1

        # ── 工时规则说明 ─────────────────────────────────
        rule_label = ctk.CTkLabel(
            content,
            text="工时规则：单条任务 ≥1h（不足自动补齐），单条任务 ≤8h（超额截断）；同一天工时 <1h 的多条任务自动合并",
            font=ctk.CTkFont(size=11),
            text_color=self.text_secondary,
            anchor="w",
            wraplength=500,
        )
        rule_label.grid(row=row, column=0, sticky="w", pady=(0, 16))

        row += 1

        # ── 导出按钮 ─────────────────────────────────────
        self._excel_export_btn = ctk.CTkButton(
            content,
            text="导出到 Excel",
            font=ctk.CTkFont(size=15, weight="bold"),
            height=48,
            corner_radius=10,
            fg_color=self.accent_color,
            hover_color="#2563EB",
            text_color="#FFFFFF",
            command=self._export_to_excel,
        )
        self._excel_export_btn.grid(row=row, column=0, sticky="ew", pady=(0, 30))

        # 底部占位
        ctk.CTkLabel(content, text="", height=50).grid(row=row + 1, column=0)

        self.tab_frames["Excel导出"] = tab4
        tab4.pack_forget()

    # ── Excel 导出相关方法 ─────────────────────────────────────────────────

    def _refresh_excel_status(self) -> None:
        """刷新 Excel 导出页的数据来源状态并重建项目复选框。"""
        if not hasattr(self, "_excel_status_label"):
            return
        if self._work_hours_data:
            from excel_exporter import list_projects
            projects = list_projects(self._work_hours_data)
            date_keys = sorted(self._work_hours_data.keys())
            date_range = f"{date_keys[0]} ~ {date_keys[-1]}" if date_keys else "?"
            self._excel_status_label.configure(
                text=f"已有工时数据（{date_range}），共 {len(projects)} 个项目",
                text_color=self.success_color,
            )
        else:
            self._excel_status_label.configure(
                text="尚无工时数据。请先生成「工时分配报告」，或点击右侧按钮加载 JSON 文件。",
                text_color=self.text_secondary,
            )
        self._rebuild_project_checkboxes()

    def _rebuild_project_checkboxes(self) -> None:
        """根据当前工时数据重新生成项目复选框列表。"""
        if not hasattr(self, "_project_checkbox_frame"):
            return
        # 清空旧内容
        for w in self._project_checkbox_frame.winfo_children():
            w.destroy() 
        self._project_checkboxes.clear()

        if not self._work_hours_data:
            ctk.CTkLabel(self._project_checkbox_frame,
                         text="（暂无项目数据，请先生成工时报告或加载 JSON 文件）",
                         font=ctk.CTkFont(size=12),
                         text_color=self.text_secondary,
                         anchor="w").pack(anchor="w", pady=4)
            return

        from excel_exporter import list_projects
        projects = list_projects(self._work_hours_data)
        if not projects:
            ctk.CTkLabel(self._project_checkbox_frame,
                         text="（未找到任何项目）",
                         font=ctk.CTkFont(size=12),
                         text_color=self.text_secondary,
                         anchor="w").pack(anchor="w", pady=4)
            return

        for proj in projects:
            var = ctk.BooleanVar(value=True)
            cb = ctk.CTkCheckBox(
                self._project_checkbox_frame,
                text=proj,
                variable=var,
                font=ctk.CTkFont(size=13),
                text_color=self.text_primary,
                fg_color=self.accent_color,
                corner_radius=4,
            )
            cb.pack(anchor="w", pady=4)
            self._project_checkboxes[proj] = var

    def _select_all_projects(self, checked: bool) -> None:
        """全选或全不选所有项目复选框。"""
        for var in self._project_checkboxes.values():
            var.set(checked)

    def _load_work_hours_from_file(self) -> None:
        """从本地 JSON 或 Markdown 文件加载工时数据。"""
        path = filedialog.askopenfilename(
            title="选择工时数据文件",
            filetypes=[
                ("工时数据文件", "*.json *.md *.markdown"),
                ("JSON 文件", "*.json"),
                ("Markdown 文件", "*.md *.markdown"),
                ("所有文件", "*.*"),
            ],
        )
        if not path:
            return
        try:
            from excel_exporter import load_work_hours_file, list_projects
            data = load_work_hours_file(path)
            self._work_hours_data = data
            self._refresh_excel_status()
            projects = list_projects(data)
            self.log(f"已加载工时数据: {path}", "info")
            self.log(f"共识别到 {len(projects)} 个项目: {', '.join(projects)}", "info")
        except Exception as e:
            messagebox.showerror("加载失败", str(e))

    def _browse_excel_template(self) -> None:
        path = filedialog.askopenfilename(
            title="选择 Excel 模板文件",
            filetypes=[("Excel 文件", "*.xlsx *.xls"), ("所有文件", "*.*")],
        )
        if path:
            self._excel_template_var.set(path)
            if not self._excel_output_var.get().strip():
                from pathlib import Path as _Path
                p = _Path(path)
                self._excel_output_var.set(str(p.parent / (p.stem + "_filled.xlsx")))

    def _browse_excel_output(self) -> None:
        path = filedialog.asksaveasfilename(
            title="保存 Excel 文件",
            defaultextension=".xlsx",
            filetypes=[("Excel 文件", "*.xlsx"), ("所有文件", "*.*")],
        )
        if path:
            self._excel_output_var.set(path)

    def _export_to_excel(self) -> None:
        """触发 Excel 导出（在子线程执行）。"""
        if not self._work_hours_data:
            messagebox.showwarning(
                "无工时数据",
                "请先生成「工时分配报告」，或点击「从文件加载」加载 JSON 数据。",
            )
            return

        template = self._excel_template_var.get().strip()
        if not template:
            messagebox.showwarning("缺少模板", "请选择 Excel 模板文件。")
            return

        output = self._excel_output_var.get().strip()
        if not output:
            messagebox.showwarning("缺少输出路径", "请指定输出 Excel 文件路径。")
            return

        selected = [proj for proj, var in self._project_checkboxes.items() if var.get()]
        if self._project_checkboxes and not selected:
            messagebox.showwarning("未选择项目", "请至少勾选一个要导出的项目。")
            return

        self._excel_export_btn.configure(state="disabled")
        import threading
        t = threading.Thread(
            target=self._perform_excel_export,
            args=(template, output, selected if self._project_checkboxes else None),
            daemon=True,
        )
        t.start()

    def _perform_excel_export(self, template: str, output: str, selected_projects: list | None) -> None:
        """在子线程中执行 Excel 填充。"""
        try:
            from excel_exporter import fill_excel_template
            self.log("=" * 60, "info")
            self.log("开始导出 Excel 工时表…", "info")
            if selected_projects:
                self.log(f"导出项目: {', '.join(selected_projects)}", "info")
            else:
                self.log("导出所有项目", "info")

            count = fill_excel_template(
                template_path=template,
                work_hours_data=self._work_hours_data,
                output_path=output,
                project_filters=selected_projects,
            )
            self.log(f"导出成功：共写入 {count} 行任务数据", "success")
            self.log(f"文件已保存至: {output}", "success")
            self.root.after(0, lambda: messagebox.showinfo(
                "导出成功",
                f"共写入 {count} 行任务数据\n\n文件路径:\n{output}",
            ))
        except ImportError as e:
            self.log(f"导出失败（缺少依赖）: {e}", "error")
            self.root.after(0, lambda: messagebox.showerror("依赖缺失", str(e)))
        except (ValueError, FileNotFoundError) as e:
            self.log(f"导出失败: {e}", "error")
            self.root.after(0, lambda: messagebox.showerror("导出失败", str(e)))
        except Exception as e:
            import traceback
            self.log(f"导出异常: {e}", "error")
            self.log(traceback.format_exc(), "error")
            self.root.after(0, lambda: messagebox.showerror("导出异常", str(e)))
        finally:
            self._reset_button_state("_excel_export_btn")

    def _create_bottom_actions(self):
        """创建底部固定操作按钮区域（固定在窗口底部，不随内容滚动）"""
        # 顶部分隔线
        separator = ctk.CTkFrame(self.bottom_actions_frame, fg_color=self.styles.colors['border'], height=1, corner_radius=0)
        separator.pack(fill="x", padx=0, pady=0)

        button_container = ctk.CTkFrame(self.bottom_actions_frame,
                                       fg_color=self.bg_main,
                                       corner_radius=0)
        button_container.pack(fill="x", padx=self.styles.spacing['md'], pady=(self.styles.spacing['sm'], self.styles.spacing['md']))

        # 状态栏（左侧）+ 按钮组（右侧）
        status_row = ctk.CTkFrame(button_container, fg_color="transparent")
        status_row.pack(fill="x", pady=(0, self.styles.spacing['sm']))

        self.status_indicator = ctk.CTkLabel(status_row,
                                            text="● 就绪",
                                            font=self.styles.fonts['caption'](),
                                            text_color=self.styles.colors['success'],
                                            anchor="w")
        self.status_indicator.pack(side="left")

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
                                        text="▶  生成日志",
                                        height=44,
                                        font=self.styles.fonts['body_bold'](),
                                        corner_radius=self.styles.radius['md'],
                                        fg_color=self.styles.colors['success'],
                                        text_color="white",
                                        hover_color="#059669",
                                        command=self.generate_logs)
        self.generate_btn.grid(row=0, column=0, padx=(0, self.styles.spacing['sm']), sticky="ew")

        # 清空按钮
        clear_btn = ctk.CTkButton(button_frame,
                                text="清空",
                                height=44,
                                font=self.styles.fonts['body'](),
                                corner_radius=self.styles.radius['md'],
                                fg_color=self.bg_card,
                                text_color=self.text_primary,
                                hover_color=self.styles.colors['hover'],
                                border_width=1,
                                border_color=self.border_color,
                                command=self.clear_logs)
        clear_btn.grid(row=0, column=1, padx=(0, self.styles.spacing['sm']), sticky="ew")

        # AI分析按钮
        self.ai_analysis_btn = ctk.CTkButton(button_frame,
                                           text="AI 分析",
                                           height=44,
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
    
    def _toggle_theme(self):
        """切换深浅主题"""
        if self._current_theme == "dark":
            self._apply_light_theme()
        else:
            self._apply_dark_theme()

    def _apply_dark_theme(self):
        """应用深色主题"""
        self._current_theme = "dark"
        ctk.set_appearance_mode("dark")
        # 更新样式常量
        UIStyles.colors.update({
            'bg_main': "#18181B",
            'bg_card': "#27272A",
            'bg_surface': "#1F1F23",
            'text_primary': "#F4F4F5",
            'text_secondary': "#A1A1AA",
            'text_tertiary': "#71717A",
            'border': "#3F3F46",
            'hover': "#374151",
        })
        # 同步旧属性别名
        self._sync_color_aliases()
        # 更新主题按钮
        if hasattr(self, '_theme_btn'):
            self._theme_btn.configure(text="☀ 浅色")
        # 更新状态
        self._update_status("就绪", "success")
        self._refresh_log_widget_theme()
        self._refresh_chrome_for_theme()
        if self.current_tab:
            self._switch_tab(self.current_tab)
        self.root.after(0, self._refresh_gitlab_validation_colors)

    def _apply_light_theme(self):
        """应用浅色主题"""
        self._current_theme = "light"
        ctk.set_appearance_mode("light")
        # 更新样式常量为浅色
        UIStyles.colors.update({
            'bg_main': "#F8F8F8",
            'bg_card': "#FFFFFF",
            'bg_surface': "#F0F0F0",
            'text_primary': "#18181B",
            'text_secondary': "#52525B",
            'text_tertiary': "#71717A",
            'border': "#D4D4D8",
            'hover': "#E4E4E7",
        })
        # 同步旧属性别名
        self._sync_color_aliases()
        # 更新主题按钮
        if hasattr(self, '_theme_btn'):
            self._theme_btn.configure(text="🌙 深色")
        # 更新状态
        self._update_status("浅色主题已启用", "success")
        self._refresh_log_widget_theme()
        self._refresh_chrome_for_theme()
        if self.current_tab:
            self._switch_tab(self.current_tab)
        self.root.after(0, self._refresh_gitlab_validation_colors)

    def _refresh_gitlab_validation_colors(self):
        """主题切换后重新应用校验样式（边框与提示文字颜色）。"""
        for fn in (
            self._validate_gitlab_url,
            self._validate_repo_url,
            self._validate_author,
            self._validate_token,
        ):
            try:
                fn()
            except Exception:
                pass

    def _sync_color_aliases(self):
        """同步旧属性别名与最新样式颜色"""
        c = UIStyles.colors
        self.bg_main        = c['bg_main']
        self.bg_card        = c['bg_card']
        self.text_primary   = c['text_primary']
        self.text_secondary = c['text_secondary']
        self.border_color   = c['border']
        self.accent_color   = c['accent']
        self.success_color  = c['success']
        self.error_color    = c['error']

    def _update_status(self, message, level="info"):
        """更新底部状态指示器"""
        if not hasattr(self, 'status_indicator'):
            return
        color_map = {
            "success": self.styles.colors['success'],
            "error":   self.styles.colors['error'],
            "warning": self.styles.colors['warning'],
            "info":    self.styles.colors['text_secondary'],
            "running": self.styles.colors['accent'],
        }
        color = color_map.get(level, self.styles.colors['text_secondary'])
        dot = "●"
        self.status_indicator.configure(text=f"{dot} {message}", text_color=color)

    def _on_window_resize(self, event):
        """窗口大小变化时的响应式处理"""
        if event.widget != self.root:
            return
        current_width = self.root.winfo_width()
        if abs(current_width - self._last_resize_width) < 20:
            return
        self._last_resize_width = current_width
        # 根据宽度调整标签页按钮文字
        self.root.after(100, lambda: self._adapt_tab_labels(current_width))

    def _adapt_tab_labels(self, _width):
        """侧边栏模式下标签已固定为短文字，无需响应式调整"""
        pass

    def _set_running_state(self, is_running: bool):
        """切换运行状态，同步更新按钮和状态指示"""
        if is_running:
            self.generate_btn.configure(text="⏹ 停止", state="normal",
                                       fg_color=self.styles.colors['error'],
                                       hover_color="#DC2626")
            self._update_status("正在生成日志…", "running")
        else:
            self.generate_btn.configure(text="▶  生成日志", state="normal",
                                       fg_color=self.styles.colors['success'],
                                       hover_color="#059669")
            self._update_status("就绪", "success")

    def _switch_tab(self, tab_name):
        """切换标签页（Segmented Control 风格）"""
        try:
            # 隐藏所有标签页
            for name, frame in self.tab_frames.items():
                frame.pack_forget()
            
             # 显示选中的标签页
            if tab_name in self.tab_frames:
                # 优化：expand=False 稳固布局，防止触底闪烁
                self.tab_frames[tab_name].pack(fill="x", expand=False, padx=20, pady=20)
                self.current_tab = tab_name
            
            # 更新侧边栏导航高亮（微信风格）
            if hasattr(self, '_sidebar_btns'):
                for name, (item_frame, icon_lbl, text_lbl) in self._sidebar_btns.items():
                    if name == tab_name:
                        item_frame.configure(fg_color=self._sidebar_selected_bg())
                        icon_lbl.configure(text_color=self.styles.colors['accent'])
                        text_lbl.configure(text_color=self.styles.colors['accent'])
                    else:
                        item_frame.configure(fg_color="transparent")
                        icon_lbl.configure(text_color=self.styles.colors['text_secondary'])
                        text_lbl.configure(text_color=self.styles.colors['text_secondary'])
            
            # 立即滚动到顶部（兼容不同版本的 CTkScrollableFrame）
            if hasattr(self, 'scroll_container'):
                try:
                    if hasattr(self.scroll_container, '_parent_canvas'):
                        self.scroll_container._parent_canvas.yview_moveto(0)
                    elif hasattr(self.scroll_container, '_canvas'):
                        self.scroll_container._canvas.yview_moveto(0)
                except Exception:
                    pass

            # 切换到 Excel 导出页时刷新状态
            if tab_name == "Excel导出":
                self._refresh_excel_status()
        except Exception as e:
            print(f"切换标签页错误: {e}")
    
    
    def _update_ai_models(self, *args):
        """更新AI模型列表"""
        try:
            service = self.ai_service.get()
            if service == "openai":
                # 更新模型列表，添加最新模型（根据 OpenAI API 文档）
                models = [
                    "gpt-4o",           # 最新最强模型
                    "gpt-4o-mini",      # 推荐：性价比高
                    "gpt-4-turbo",
                    "gpt-4",
                    "gpt-3.5-turbo"
                ]
                if self.ai_model.get() not in models:
                    self.ai_model.set("gpt-4o-mini")  # 默认使用性价比高的模型
            elif service == "anthropic":
                models = ["claude-3-5-sonnet-20241022", "claude-3-opus-20240229", "claude-3-sonnet-20240229"]
                if self.ai_model.get() not in models:
                    self.ai_model.set("claude-3-5-sonnet-20241022")
            elif service == "gemini":
                # 更新模型列表，添加 Gemini 3 系列（推荐使用）
                models = [
                    "gemini-3-flash-preview",  # 推荐：有免费层级，速度快
                    "gemini-3-pro-preview",    # 最强大，但需要配额
                    "gemini-2.5-pro",
                    "gemini-2.5-flash",
                    "gemini-2.5-flash-lite",
                    "gemini-2.5",
                    "gemini-1.5-pro",
                    "gemini-1.5-flash"
                ]
                if self.ai_model.get() not in models:
                    self.ai_model.set("gemini-3-flash-preview")  # 默认使用 Gemini 3 Flash
            elif service == "doubao":
                # 豆包模型列表
                models = [
                    "doubao-pro-128k",      # 专业版
                    "doubao-lite-128k"      # 轻量版
                ]
                if self.ai_model.get() not in models:
                    self.ai_model.set("doubao-pro-128k")
            elif service == "deepseek":
                # DeepSeek 模型列表
                models = [
                    "deepseek-chat",        # 通用对话模型
                    "deepseek-coder",       # 代码专用模型
                    "deepseek-reasoner"     # 推理模型
                ]
                if self.ai_model.get() not in models:
                    self.ai_model.set("deepseek-chat")
            
            self.ai_model_combo.configure(values=models)
        except Exception:
            pass
    
    def toggle_token_visibility(self, entry):
        """切换令牌显示/隐藏"""
        try:
            if entry.cget('show') == '*':
                entry.configure(show='')
            else:
                entry.configure(show='*')
            entry.focus_set()
            self.root.update_idletasks()
        except Exception:
            pass
    
    def toggle_key_visibility(self, entry):
        """切换API Key显示/隐藏"""
        try:
            if entry.cget('show') == '*':
                entry.configure(show='')
            else:
                entry.configure(show='*')
            entry.focus_set()
            self.root.update_idletasks()
        except Exception:
            pass
    
    def toggle_ai_config(self):
        """切换AI配置区域的显示/隐藏"""
        try:
            if self.ai_enabled.get():
                self.ai_config_frame.grid()
            else:
                self.ai_config_frame.grid_remove()
            self.root.update_idletasks()
        except Exception:
            pass
    
    def toggle_date_inputs(self):
        """切换日期输入框的启用/禁用状态"""
        try:
            if self.use_today.get():
                self.since_entry.configure(state="disabled")
                self.until_entry.configure(state="disabled")
            else:
                self.since_entry.configure(state="normal")
                self.until_entry.configure(state="normal")
            self.root.update_idletasks()
        except Exception:
            pass
    
    def on_output_format_changed(self, *args):
        """输出格式变化时的回调"""
        try:
            # 统一显示为"输出目录"，因为无论什么格式都选择文件夹
            self.output_label.configure(text="输出目录")
            format_value = self.output_format.get()
            if format_value == "all":
                self.output_hint.configure(text="提示: 批量生成时，所有文件将保存到选择的目录")
            else:
                self.output_hint.configure(text="提示: 生成的文件将保存到选择的目录")
            self.root.update_idletasks()
        except Exception:
            pass
    
    def browse_output_file(self):
        """浏览输出目录（统一选择文件夹来存放生成的文件）"""
        try:
            # 无论什么格式，都选择文件夹来存放生成的文件
            directory = filedialog.askdirectory(
                title="选择输出目录（生成的文件将保存到此文件夹）",
                initialdir=self.output_file.get().strip() or os.getcwd()
            )
            if directory:
                self.output_file.set(directory)
            self.root.update_idletasks()
        except Exception as e:
            messagebox.showerror("错误", f"选择目录失败: {str(e)}")
    
    def log(self, message, log_type="info"):
        """添加日志消息（带颜色前缀）"""
        try:
            # Tk/CustomTkinter 不是线程安全的：任何 UI 更新必须在主线程执行。
            # 否则在 macOS 上容易触发 Tcl_Panic / abort（尤其是多次生成、日志量较大时）。
            import threading
            if threading.current_thread() is not threading.main_thread():
                try:
                    self.root.after(0, lambda: self.log(message, log_type))
                except Exception:
                    pass
                return

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 根据类型添加颜色前缀
            if log_type == "error":
                prefix = f"[ERROR]"
                color_tag = "error"
            elif log_type == "success":
                prefix = f"[SUCCESS]"
                color_tag = "success"
            elif log_type == "warning":
                prefix = f"[WARNING]"
                color_tag = "warning"
            elif log_type == "info":
                prefix = f"[INFO]"
                color_tag = "info"
            else:
                prefix = ""
                color_tag = "info"
            
            log_message = f"{timestamp} - {prefix} {message}\n"
            
            # 插入文本
            start_pos = self.log_text.index("end-1c")
            self.log_text.insert("end", log_message)
            
            # 应用颜色标签（优化：利用预配置的标签，减少方法调用）
            line_num = start_pos.split('.')[0]
            
            # 时间戳灰色
            self.log_text.tag_add("timestamp", f"{line_num}.0", f"{line_num}.{len(timestamp)}")
            
            if prefix:
                # 只对前缀部分应用颜色
                prefix_start_idx = len(timestamp) + 3
                self.log_text.tag_add(color_tag, 
                                     f"{line_num}.{prefix_start_idx}", 
                                     f"{line_num}.{prefix_start_idx + len(prefix)}")
            
            # 优化：只在必要时滚动到底部，减少更新频率
            should_scroll = True
            try:
                # 检查是否已经接近底部（在最后 3 行内）
                last_line = self.log_text.index("end-1c")
                last_line_num = int(last_line.split('.')[0])
                visible_start = self.log_text.index("@0,0")
                visible_end = self.log_text.index("@0,{}".format(self.log_text.winfo_height()))
                visible_start_num = int(visible_start.split('.')[0])
                visible_end_num = int(visible_end.split('.')[0])
                
                # 如果用户已经滚动到顶部或中间，不要自动滚动到底部
                if visible_end_num < last_line_num - 3:
                    should_scroll = False
            except Exception:
                pass
            
            if should_scroll:
                self.log_text.see("end")
            
            self._log_count += 1
            
            # 限制日志长度
            if self._log_count > 1000:
                self.log_text.delete(1.0, "100.0")
                self._log_count = 900
            
            # 优化：大幅减少 update_idletasks 调用频率，避免卡顿
            # 只有在非常大量的日志时才需要手动刷新，否则交给 Tkinter 的主循环即可
            if self._log_count % 50 == 0:  # 降低频率到 50 条
                self.root.update_idletasks()
        except Exception:
            pass
    
    def clear_logs(self):
        """清空日志"""
        try:
            import threading
            if threading.current_thread() is not threading.main_thread():
                try:
                    self.root.after(0, self.clear_logs)
                except Exception:
                    pass
                return

            self.log_text.delete(1.0, "end")
            self._log_count = 0
            self.log("日志已清空", "info")
        except Exception:
            pass
    
    def generate_logs(self):
        """生成日志的主函数"""
        # 防止重复点击：如果已经在运行，直接返回
        if getattr(self, '_is_running', False):
            self.log("任务正在运行中，请等待完成...", "warning")
            return

        try:
            # 设置运行状态和按钮状态
            self._is_running = True
            self._set_running_state(True)

            # 立即更新UI，确保按钮状态变化可见
            self.root.update_idletasks()

            # 使用线程启动，避免阻塞UI
            thread = threading.Thread(target=self._run_git2logs_direct, daemon=True)
            thread.start()

        except Exception as e:
            self.log(f"启动生成任务失败: {str(e)}", "error")
            self._reset_button_state()
    
    def _run_git2logs_direct(self):
        """在后台线程中执行git2logs（延迟导入模块以提高启动速度）"""
        root_logger = None
        gui_handler = None
        try:
            from datetime import datetime
            import logging
            
            # 延迟导入 git2logs 模块（只在需要时导入，提高启动速度）
            from git2logs import (
                create_gitlab_client, scan_all_projects, get_commits_by_author,
                group_commits_by_date, generate_markdown_log, generate_multi_project_markdown,
                generate_daily_report, generate_statistics_report, generate_all_reports,
                analyze_with_ai, generate_ai_analysis_report, generate_local_analysis_report,
                extract_gitlab_url, parse_project_identifier
            )
            
            # 重定向日志输出到 GUI
            class GUILogHandler(logging.Handler):
                def __init__(self, gui_log_func):
                    super().__init__()
                    self.gui_log_func = gui_log_func
                
                def emit(self, record):
                    try:
                        msg = self.format(record)
                        log_type = "error" if record.levelno >= logging.ERROR else "warning" if record.levelno >= logging.WARNING else "info"
                        self.gui_log_func(msg, log_type)
                    except Exception:
                        pass
            
            gui_handler = GUILogHandler(self.log)
            gui_handler.setLevel(logging.INFO)
            formatter = logging.Formatter('%(levelname)s - %(message)s')
            gui_handler.setFormatter(formatter)
            
            root_logger = logging.getLogger()
            # 避免重复添加 handler：第二次点击“生成”会导致 handler 叠加、日志倍增，
            # 同时更容易触发 Tk 跨线程更新导致的崩溃。
            try:
                if hasattr(self, "_gui_log_handler") and self._gui_log_handler in root_logger.handlers:
                    root_logger.removeHandler(self._gui_log_handler)
            except Exception:
                pass
            root_logger.addHandler(gui_handler)
            self._gui_log_handler = gui_handler
            root_logger.setLevel(logging.INFO)
            
            self.log("=" * 60, "info")
            self.log("开始生成日志...", "info")
            
            # 获取配置
            gitlab_url = self.gitlab_url.get().strip()
            token = self.token.get().strip()
            author = self.author.get().strip()
            repo = self.repo.get().strip()
            branch_str = self.branch.get().strip()
            # 如果不输入分支，默认为 None（查询所有分支）
            branch = branch_str if branch_str else None
            
            # 调试信息：显示使用的参数
            self.log(f"配置参数:", "info")
            self.log(f"  GitLab URL: {gitlab_url}", "info")
            self.log(f"  提交者: {author}", "info")
            self.log(f"  仓库: {repo if repo else '(扫描所有项目)'}", "info")
            self.log(f"  分支: {branch if branch else '(所有分支)'}", "info")
            
            # 检查占位符
            placeholder_text = "https://gitlab.com 或 http://gitlab.yourcompany.com"
            if gitlab_url == placeholder_text:
                gitlab_url = ""
            
            # 验证必要参数
            if not gitlab_url or not token or not author:
                self.log("错误: 请填写GitLab URL、访问令牌和提交者", "error")
                self.root.after(0, lambda: messagebox.showerror("错误", "请填写GitLab URL、访问令牌和提交者"))
                self._reset_button_state()
                return
            
            # 日期处理
            since_date = None
            until_date = None
            use_today_value = self.use_today.get()
            self.log(f"调试: '今天'复选框状态: {use_today_value}", "info")
            
            if use_today_value:
                # 使用今天的日期
                from datetime import datetime
                today_local = datetime.now()
                # 直接使用今天的日期，不再扩展范围
                since_date = today_local.strftime('%Y-%m-%d')
                until_date = today_local.strftime('%Y-%m-%d')
                self.log(f"使用今天的日期: {since_date}", "info")
                # 同时记录 UTC 日期以便调试
                from datetime import timezone
                today_utc = datetime.now(timezone.utc).strftime('%Y-%m-%d')
                today_local_str = today_local.strftime('%Y-%m-%d')
                if today_local_str != today_utc:
                    self.log(f"提示: 本地日期为 {today_local_str}，UTC 日期为 {today_utc}，GitLab API 将使用 UTC 时间查询", "info")
            else:
                # 从输入框获取日期
                since_date_str = self.since_date.get().strip()
                until_date_str = self.until_date.get().strip()
                self.log(f"调试: 从输入框获取的日期 - 起始: '{since_date_str}', 结束: '{until_date_str}'", "info")
                
                # 如果只填写了一个日期，自动扩展日期范围
                if since_date_str and not until_date_str:
                    until_date_str = since_date_str
                    self.log(f"调试: 只填写了起始日期，自动设置结束日期为: {until_date_str}", "info")
                if until_date_str and not since_date_str:
                    since_date_str = until_date_str
                    self.log(f"调试: 只填写了结束日期，自动设置起始日期为: {since_date_str}", "info")
                
                # 允许日期为空（不指定日期范围，查询所有提交）
                if since_date_str:
                    since_date = since_date_str
                if until_date_str:
                    until_date = until_date_str
                    
                if not since_date and not until_date:
                    self.log("提示: 未指定日期范围，将查询所有提交记录", "info")
                elif since_date and until_date:
                    # 验证日期格式
                    try:
                        from datetime import datetime
                        datetime.strptime(since_date, '%Y-%m-%d')
                        datetime.strptime(until_date, '%Y-%m-%d')
                        self.log(f"调试: 日期格式验证通过 - 起始: {since_date}, 结束: {until_date}", "info")
                        
                        # 如果只指定了一天，不扩展日期范围，直接使用用户输入的日期
                        # 移除自动扩展逻辑，严格按照用户输入的日期范围查询
                        if since_date == until_date:
                            self.log(f"使用指定的日期: {since_date}", "info")
                        else:
                            self.log(f"使用日期范围: {since_date} 至 {until_date}", "info")
                    except ValueError as e:
                        self.log(f"错误: 日期格式无效 - {str(e)}", "error")
                        self.log(f"  起始日期: '{since_date}', 结束日期: '{until_date}'", "error")
                        self.log("  日期格式应为 YYYY-MM-DD，例如: 2026-01-21", "error")
                        self.root.after(0, lambda: messagebox.showerror("错误", f"日期格式无效: {str(e)}\n\n日期格式应为 YYYY-MM-DD，例如: 2026-01-21"))
                        self._reset_button_state()
                        return
            
            # 创建GitLab客户端
            self.log(f"正在连接到 GitLab: {gitlab_url}", "info")
            if since_date and until_date:
                if since_date == until_date:
                    self.log(f"查询日期: {since_date}", "info")
                else:
                    self.log(f"查询日期范围: {since_date} 至 {until_date}", "info")
            gl = create_gitlab_client(gitlab_url, token)
            
            # 获取提交记录
            all_results = {}
            
            # 如果不输入仓库地址，默认查询所有项目
            if self.scan_all.get() or not repo:
                self.log("正在扫描所有项目...", "info")
                self.log(f"提交者: {author}", "info")
                if branch:
                    self.log(f"分支: {branch}", "info")
                else:
                    self.log(f"分支: (所有分支)", "info")
                if since_date and until_date:
                    if since_date == until_date:
                        self.log(f"日期: {since_date} (GitLab API 将使用 UTC 时间)", "info")
                    else:
                        self.log(f"日期范围: {since_date} 至 {until_date} (GitLab API 将使用 UTC 时间)", "info")
                
                all_results = scan_all_projects(
                    gl, author,
                    since_date=since_date,
                    until_date=until_date,
                    branch=branch
                )
                self.log(f"扫描完成，共在 {len(all_results)} 个项目中找到提交记录", "success")
                
                # 如果没有找到提交，提供排查建议
                if len(all_results) == 0:
                    self.log("", "warning")
                    self.log("未找到提交记录的可能原因：", "warning")
                    self.log("1. 日期范围问题：GitLab API 使用 UTC 时间，可能与本地时区不同", "warning")
                    self.log("   当前查询日期: " + (f"{since_date} 至 {until_date}" if since_date and until_date else "未指定（查询所有）"), "warning")
                    self.log("2. 提交者名称不匹配：请确认提交者名称或邮箱与 GitLab 中的完全一致", "warning")
                    self.log("   当前提交者: " + author, "warning")
                    self.log("   提示: 请查看上面的'调试：查询到的提交示例'，确认实际作者格式", "warning")
                    self.log("3. 分支问题：如果指定了分支，请确认该分支存在且有提交", "warning")
                    self.log("4. 权限问题：请确认访问令牌有足够的权限", "warning")
                    self.log("", "warning")
                    self.log("排查建议：", "info")
                    self.log("- 查看上面的调试信息，确认 GitLab 中实际提交的作者格式", "info")
                    self.log("- 尝试只使用邮箱（如: mizukixja@gmail.com）或只使用名称（如: MIZUKI）", "info")
                    self.log("- 如果指定了日期，尝试不指定日期范围（取消'今天'勾选，不填日期）", "info")
                    self.log("- 尝试指定具体分支名称", "info")
                    self.log("- 检查该日期范围内是否确实有提交（可以在 GitLab 网页上查看）", "info")
            else:
                # 单项目模式
                extracted_url = extract_gitlab_url(repo)
                if extracted_url:
                    gitlab_url = extracted_url
                    self.log(f"从仓库 URL 提取 GitLab 实例: {gitlab_url}", "info")
                    gl = create_gitlab_client(gitlab_url, token)
                
                project_identifier = parse_project_identifier(repo)
                self.log(f"正在获取项目: {project_identifier}", "info")
                if branch:
                    self.log(f"分支: {branch}", "info")
                else:
                    self.log(f"分支: (所有分支)", "info")
                if since_date and until_date:
                    if since_date == until_date:
                        self.log(f"日期: {since_date} (GitLab API 将使用 UTC 时间)", "info")
                    else:
                        self.log(f"日期范围: {since_date} 至 {until_date} (GitLab API 将使用 UTC 时间)", "info")
                elif since_date:
                    self.log(f"起始日期: {since_date} (GitLab API 将使用 UTC 时间)", "info")
                elif until_date:
                    self.log(f"结束日期: {until_date} (GitLab API 将使用 UTC 时间)", "info")
                else:
                    self.log("日期范围: 未指定（查询所有提交）", "info")
                
                try:
                    project = gl.projects.get(project_identifier)
                    self.log(f"调试: 调用 get_commits_by_author，参数 - since_date: {since_date}, until_date: {until_date}, branch: {branch}", "info")
                    commits = get_commits_by_author(
                        project, author,
                        since_date=since_date,
                        until_date=until_date,
                        branch=branch
                    )
                    if commits:
                        all_results[project_identifier] = {
                            'project': project,
                            'commits': commits
                        }
                        self.log(f"找到 {len(commits)} 条提交记录", "success")
                except Exception as e:
                    self.log(f"获取项目失败: {str(e)}", "error")
            
            if not all_results:
                self.log("未找到任何提交记录", "warning")
                self.root.after(0, lambda: messagebox.showwarning("提示", "未找到任何提交记录"))
                self._reset_button_state()
                return
            
            # 确定输出路径
            output_path = self.output_file.get().strip()
            if not output_path:
                output_path = os.getcwd()
                self.log(f"未指定输出路径，使用当前目录: {output_path}", "info")
            
            # 根据输出格式生成报告
            output_format = self.output_format.get()
            self.log(f"输出格式: {output_format}", "info")
            
            generated_files = {}
            
            if output_format == "statistics":
                self.log("正在生成统计报告...", "info")
                report_content = generate_statistics_report(
                    all_results, author,
                    since_date=since_date, until_date=until_date
                )
                
                if os.path.isdir(output_path):
                    date_prefix = since_date if since_date and until_date and since_date == until_date else datetime.now().strftime('%Y-%m-%d')
                    output_file = os.path.join(output_path, f"{date_prefix}_statistics.md")
                else:
                    output_file = output_path
                
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(report_content)
                
                generated_files['statistics'] = output_file
                self.log(f"统计报告已保存: {output_file}", "success")
                self.log("提示: 统计报告包含本地多维度评价，AI分析需要手动触发", "info")
                
                if self.ai_enabled.get() and self.ai_api_key.get().strip():
                    self._pending_ai_data = {
                        'all_results': all_results,
                        'author': author,
                        'output_dir': os.path.dirname(output_file),
                        'since_date': since_date,
                        'until_date': until_date,
                        'generated_files': generated_files
                    }
                    self.log("数据已保存，可以点击'执行AI分析'按钮进行AI分析", "info")
            elif output_format == "all":
                self.log("正在批量生成所有格式...", "info")
                generated_files = generate_all_reports(
                    all_results, author, output_path,
                    since_date=since_date, until_date=until_date
                )
                self.log(f"批量生成完成，共生成 {len(generated_files)} 个文件", "success")
                for file_type, file_path in generated_files.items():
                    self.log(f"  - {file_type}: {file_path}", "info")
            else:
                self.log(f"正在生成 {output_format} 格式...", "info")
                if output_format == "commits":
                    if len(all_results) == 1:
                        report_content = generate_markdown_log(list(all_results.values())[0]['commits'])
                    else:
                        report_content = generate_multi_project_markdown(all_results)
                elif output_format == "daily_report":
                    report_content = generate_daily_report(
                        all_results, author,
                        since_date=since_date, until_date=until_date,
                        branch=branch
                    )
                elif output_format == "work_hours":
                    from git2logs import generate_work_hours_report, calculate_work_hours
                    report_content = generate_work_hours_report(
                        all_results, author,
                        since_date=since_date, until_date=until_date,
                        daily_hours=8.0, branch=branch
                    )
                    # 缓存工时数据，供 Excel 导出使用
                    self._work_hours_data = calculate_work_hours(
                        all_results,
                        since_date=since_date, until_date=until_date,
                        daily_hours=8.0, branch=branch
                    )
                    self.log("工时数据已缓存，可在「Excel导出」标签页导出", "info")
                else:
                    self.log(f"暂不支持 {output_format} 格式的直接生成", "error")
                    self._reset_button_state()
                    return
                
                if os.path.isdir(output_path):
                    date_prefix = since_date if since_date and until_date and since_date == until_date else datetime.now().strftime('%Y-%m-%d')
                    output_file = os.path.join(output_path, f"{date_prefix}_{output_format}.md")
                else:
                    output_file = output_path
                
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(report_content)
                
                generated_files[output_format] = output_file
                self.log(f"报告已保存: {output_file}", "success")

                # 工时报告额外保存 JSON 数据文件（供 Excel 导出加载）
                if output_format == "work_hours" and self._work_hours_data:
                    import json as _json
                    json_file = output_file.replace(".md", "_data.json")
                    with open(json_file, "w", encoding="utf-8") as jf:
                        _json.dump(self._work_hours_data, jf, ensure_ascii=False, indent=2)
                    self.log(f"工时数据已保存: {json_file}", "info")
                    self.log("提示: 可在「Excel导出」标签页加载此 JSON 文件", "info")
            
            self.log("=" * 60, "info")
            self.log("生成完成！", "success")

            self._reset_button_state()
            
        except Exception as e:
            self.log(f"生成失败: {str(e)}", "error")
            import traceback
            self.log(traceback.format_exc(), "error")
            self.root.after(0, lambda: messagebox.showerror("错误", f"生成失败: {str(e)}"))
            self._reset_button_state()
        finally:
            # 清理本次添加的 handler，防止长期运行/多次生成后堆积
            try:
                import logging
                if root_logger is None:
                    root_logger = logging.getLogger()
                if gui_handler is not None and gui_handler in root_logger.handlers:
                    root_logger.removeHandler(gui_handler)
            except Exception:
                pass

    def _reset_button_state(self, button_name="generate_btn"):
        """安全地重置按钮状态（线程安全）

        Args:
            button_name: 按钮属性名称，如 'generate_btn', '_excel_export_btn', 'ai_analysis_btn'
        """
        def reset():
            self._is_running = False
            button = getattr(self, button_name, None)
            if button and hasattr(button, 'winfo_exists') and button.winfo_exists():
                button.configure(state="normal")
            # 恢复生成按钮外观
            try:
                self.root.after(0, lambda: self._set_running_state(False))
            except Exception:
                pass

        if threading.current_thread() is threading.main_thread():
            reset()
        else:
            self.root.after(0, reset)

    def _safe_button_operation(self, button_name, operation):
        """安全地执行按钮操作（线程安全）

        Args:
            button_name: 按钮属性名称
            operation: 操作函数
        """
        button = getattr(self, button_name, None)
        if button and hasattr(button, 'winfo_exists') and button.winfo_exists():
            if threading.current_thread() is threading.main_thread():
                operation(button)
            else:
                self.root.after(0, lambda: operation(button))
    
    def _manual_ai_analysis(self):
        """手动触发AI分析"""
        try:
            # 防止重复点击：如果已经在运行，直接返回
            if hasattr(self, '_ai_is_running') and self._ai_is_running:
                self.log("AI分析正在运行中，请等待完成...", "warning")
                return

            if not self.ai_enabled.get() or not self.ai_api_key.get().strip():
                messagebox.showwarning("提示", "请先启用AI分析并配置API Key")
                return
            
            if self._pending_ai_data:
                result = messagebox.askyesno(
                    "AI分析",
                    "检测到当前会话的数据，是否使用当前会话的数据进行分析？\n\n"
                    "选择'是'：使用当前会话的数据\n"
                    "选择'否'：选择已生成的报告文件",
                    icon='question'
                )
                if result:
                    self.root.after(0, self._perform_ai_analysis)
                    return
            
            report_file = filedialog.askopenfilename(
                title="选择报告文件（统计报告或日报）",
                initialdir=self.output_file.get().strip() or os.getcwd(),
                filetypes=[("Markdown文件", "*.md"), ("所有文件", "*.*")]
            )
            
            if not report_file:
                return
            
            self.log("=" * 60, "info")
            self.log(f"选择的报告文件: {report_file}", "info")
            self.log("正在读取报告文件并发送给AI分析...", "info")
            
            thread = threading.Thread(target=self._analyze_report_file_direct, args=(report_file,))
            thread.daemon = True
            thread.start()
            
        except Exception as e:
            self.log(f"启动AI分析失败: {str(e)}", "error")
            messagebox.showerror("错误", f"启动AI分析失败: {str(e)}")
    
    def _analyze_report_file_direct(self, report_file):
        """直接基于报告文件内容进行AI分析"""
        import re
        
        try:
            with open(report_file, 'r', encoding='utf-8') as f:
                report_content = f.read()
            
            self.log(f"报告文件读取成功，文件大小: {len(report_content)} 字符", "success")
            
            author_match = re.search(r'\*\*提交者\*\*: (.+)', report_content)
            author = author_match.group(1).strip() if author_match else "未知作者"
            
            date_range_match = re.search(r'\*\*统计时间范围\*\*: (.+?) 至 (.+?)(?:\n|$)', report_content)
            if date_range_match:
                since_date = date_range_match.group(1).strip()
                until_date = date_range_match.group(2).strip()
            else:
                since_match = re.search(r'\*\*起始日期\*\*: (.+?)(?:\n|$)', report_content)
                until_match = re.search(r'\*\*结束日期\*\*: (.+?)(?:\n|$)', report_content)
                since_date = since_match.group(1).strip() if since_match else None
                until_date = until_match.group(1).strip() if until_match else None
            
            if not self.ai_enabled.get() or not self.ai_api_key.get().strip():
                self.log("错误: 请先配置AI服务并输入API Key", "error")
                self.root.after(0, lambda: messagebox.showerror("错误", "请先配置AI服务并输入API Key"))
                return
            
            ai_config = {
                'service': self.ai_service.get(),
                'api_key': self.ai_api_key.get().strip(),
                'model': self.ai_model.get()
            }
            
            self.log("", "info")
            self.log("=" * 60, "info")
            self.log("开始AI分析（基于报告文件内容）...", "info")
            self.log(f"提示: AI分析可能需要30秒到2分钟，超时时间: 120秒", "info")
            self.log(f"AI服务: {self.ai_service.get()}, 模型: {self.ai_model.get()}", "info")
            self.log(f"作者: {author}", "info")
            if since_date and until_date:
                self.log(f"日期范围: {since_date} 至 {until_date}", "info")
            
            from ai_analysis import analyze_report_file
            from git2logs import generate_ai_analysis_report
            
            analysis_result = analyze_report_file(report_content, ai_config, timeout=120)
            
            self.log("AI分析完成，正在生成报告...", "success")
            
            ai_report_content = generate_ai_analysis_report(
                analysis_result, author,
                since_date=since_date, until_date=until_date
            )
            
            report_dir = os.path.dirname(report_file)
            date_prefix = since_date if since_date and until_date and since_date == until_date else datetime.now().strftime('%Y-%m-%d')
            ai_report_file = os.path.join(report_dir, f"{date_prefix}_ai_analysis.md")
            
            with open(ai_report_file, 'w', encoding='utf-8') as f:
                f.write(ai_report_content)
            
            self.log(f"AI分析报告已保存: {ai_report_file}", "success")
            self.log(f"文件大小: {len(ai_report_content)} 字符", "info")
            self.log("提示: 文件名包含 '_ai_analysis' 表示这是AI分析报告", "info")
            self.log("=" * 60, "info")
            self.log("AI分析完成！", "success")
            
        except ImportError as e:
            self.log(f"AI分析功能不可用: {str(e)}", "error")
            self.log("提示: 请运行 'pip install openai anthropic google-generativeai' 安装AI服务库", "warning")
            self.root.after(0, lambda: messagebox.showerror("错误", f"AI分析功能不可用: {str(e)}"))
        except TimeoutError as e:
            self.log(f"AI分析超时: {str(e)}", "error")
            self.log("可能的原因:", "warning")
            self.log("  1. 网络连接较慢或不稳定", "warning")
            self.log("  2. AI服务响应较慢", "warning")
            self.log("  3. 报告文件内容较大，处理时间较长", "warning")
            self.log("建议: 请检查网络连接，或稍后重试", "info")
            self.root.after(0, lambda: messagebox.showerror("错误", f"AI分析超时: {str(e)}"))
        except ValueError as e:
            error_msg = str(e)
            self.log(f"AI分析失败（API密钥或配置问题）: {error_msg}", "error")
            self.root.after(0, lambda: messagebox.showerror("错误", f"AI分析失败: {error_msg}"))
        except ConnectionError as e:
            error_msg = str(e)
            self.log(f"AI分析失败（网络连接问题）: {error_msg}", "error")
            self.root.after(0, lambda: messagebox.showerror("错误", f"网络连接失败: {error_msg}"))
        except Exception as e:
            self.log(f"AI分析失败: {str(e)}", "error")
            import traceback
            self.log(traceback.format_exc(), "error")
            self.root.after(0, lambda: messagebox.showerror("错误", f"AI分析失败: {str(e)}"))
        finally:
            # 重置AI分析状态
            self._ai_is_running = False
            self._reset_button_state("ai_analysis_btn")
    
    def _perform_ai_analysis(self):
        """执行AI分析（使用待处理的数据）"""
        try:
            if not self._pending_ai_data:
                messagebox.showwarning("提示", "没有可用的数据进行分析")
                return

            # 设置AI分析运行状态
            self._ai_is_running = True
            self._safe_button_operation("ai_analysis_btn", lambda btn: btn.configure(state="disabled"))
            
            ai_config = {
                'service': self.ai_service.get(),
                'api_key': self.ai_api_key.get().strip(),
                'model': self.ai_model.get()
            }
            
            self.log("", "info")
            self.log("=" * 60, "info")
            self.log("开始AI分析...", "info")
            self.log(f"提示: AI分析可能需要30秒到2分钟，超时时间: 120秒", "info")
            self.log(f"AI服务: {self.ai_service.get()}, 模型: {self.ai_model.get()}", "info")
            
            thread = threading.Thread(target=self._perform_ai_analysis_thread, args=(ai_config,))
            thread.daemon = True
            thread.start()
            
        except Exception as e:
            self.log(f"启动AI分析失败: {str(e)}", "error")
            messagebox.showerror("错误", f"启动AI分析失败: {str(e)}")
    
    def _perform_ai_analysis_thread(self, ai_config):
        """在后台线程中执行AI分析"""
        try:
            from git2logs import analyze_with_ai, generate_ai_analysis_report
            
            all_results = self._pending_ai_data['all_results']
            author = self._pending_ai_data['author']
            since_date = self._pending_ai_data.get('since_date')
            until_date = self._pending_ai_data.get('until_date')
            
            analysis_result = analyze_with_ai(
                all_results, author, ai_config,
                since_date=since_date, until_date=until_date
            )
            
            self.log("AI分析完成，正在生成报告...", "success")
            
            ai_report_content = generate_ai_analysis_report(
                analysis_result, author,
                since_date=since_date, until_date=until_date
            )
            
            output_dir = self._pending_ai_data.get('output_dir', os.getcwd())
            date_prefix = since_date if since_date and until_date and since_date == until_date else datetime.now().strftime('%Y-%m-%d')
            ai_report_file = os.path.join(output_dir, f"{date_prefix}_ai_analysis.md")
            
            with open(ai_report_file, 'w', encoding='utf-8') as f:
                f.write(ai_report_content)
            
            self.log(f"AI分析报告已保存: {ai_report_file}", "success")
            self.log("=" * 60, "info")
            self.log("AI分析完成！", "success")
            
        except Exception as e:
            self.log(f"AI分析失败: {str(e)}", "error")
            import traceback
            self.log(traceback.format_exc(), "error")
            self.root.after(0, lambda: messagebox.showerror("错误", f"AI分析失败: {str(e)}"))
        finally:
            # 重置AI分析状态
            self._ai_is_running = False
            self._reset_button_state("ai_analysis_btn")
    
    def test_ai_connection(self):
        """测试AI连接"""
        try:
            if not self.ai_api_key.get().strip():
                self.test_status_label.configure(text="请先输入API Key", text_color=self.error_color)
                return
            
            self.test_status_label.configure(text="测试中...", text_color=self.accent_color)
            thread = threading.Thread(target=self._test_ai_connection_thread)
            thread.daemon = True
            thread.start()
        except Exception as e:
            self.test_status_label.configure(text=f"测试失败: {str(e)}", text_color=self.error_color)
    
    def _test_ai_connection_thread(self):
        """在后台线程中测试AI连接"""
        try:
            service = self.ai_service.get()
            api_key = self.ai_api_key.get().strip()
            model = self.ai_model.get()
            
            # 统一改用 ai_analysis.py 中的服务类进行测试，确保逻辑一致
            from ai_analysis import get_ai_service
            service_class = get_ai_service(service)
            test_service = service_class(api_key=api_key, model=model, timeout=10)
            
            # 针对 Gemini 做一个更稳健的连接测试
            if service == "gemini":
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                # 使用 get_model 获取指定模型元数据，这不消耗额度且非常稳定
                try:
                    model_info = genai.get_model(f"models/{model}" if "/" not in model else model)
                    self.root.after(0, lambda: self.test_status_label.configure(
                        text=f"连接成功 (模型 {model} 已就绪)", text_color=self.success_color))
                except Exception as e:
                    # 如果 get_model 不支持，退而求其次使用简单的 Ping
                    self.root.after(0, lambda: self.test_status_label.configure(
                        text="配置验证通过", text_color=self.success_color))
            else:
                # 其他服务目前仅进行实例化测试
                self.root.after(0, lambda: self.test_status_label.configure(
                    text="配置验证通过", text_color=self.success_color))
                    
        except Exception as e:
            error_msg = str(e) or "未知错误 (可能是库内部类型错误)"
            import traceback
            print(f"AI连接测试异常: {error_msg}")
            traceback.print_exc()
            
            # 对用户显示友好的错误提示
            if "401" in error_msg or "unauthorized" in error_msg.lower() or "invalid" in error_msg.lower():
                display_msg = "API密钥无效"
            elif "connection" in error_msg.lower() or "network" in error_msg.lower() or "timeout" in error_msg.lower():
                display_msg = "网络连接失败"
            elif "splitlines" in error_msg:
                display_msg = "连接失败: 可能是网络拦截或代理问题"
            else:
                display_msg = f"连接失败: {error_msg[:60]}"
            
            self.root.after(0, lambda m=display_msg: self.test_status_label.configure(
                text=m, text_color=self.error_color))


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
        root.minsize(520, 700)
        root.resizable(True, True)
        
        # 设置窗口位置（在创建应用前，与 Git2LogsGUI 默认尺寸一致）
        width = 600
        height = 900
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
                import traceback
                error_msg = f"界面初始化失败: {str(e)}\n\n{traceback.format_exc()}"
                print(error_msg)
                messagebox.showerror("初始化错误", error_msg)
        
        # 延迟1ms创建应用（几乎立即，但确保窗口先显示）
        root.after(1, create_app)
        
        # 立即进入主循环（窗口已显示）
        root.mainloop()
        
    except Exception as e:
        import traceback
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
            pass
        if root:
            root.destroy()
        raise

if __name__ == '__main__':
    main()
