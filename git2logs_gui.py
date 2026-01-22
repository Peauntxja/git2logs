#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitLab 提交日志生成工具 - 图形界面版本（CustomTkinter 现代化版本）
"""
import sys
import os

# 尝试导入 CustomTkinter，如果失败则使用标准 tkinter
try:
    import customtkinter as ctk
    CTK_AVAILABLE = True
except ImportError:
    import tkinter as tk
    from tkinter import ttk, scrolledtext, messagebox, filedialog
    CTK_AVAILABLE = False
    print("警告: CustomTkinter 未安装，使用标准 tkinter。请运行: pip install customtkinter")

import threading
import subprocess
from pathlib import Path
from datetime import datetime

# 如果 CustomTkinter 可用，使用它；否则使用标准 tkinter
if CTK_AVAILABLE:
    from tkinter import messagebox, filedialog
    from tkinter import scrolledtext
    tk = ctk  # 为了兼容性
    ttk = ctk  # CustomTkinter 有自己的组件
else:
    import tkinter as tk
    from tkinter import ttk, scrolledtext, messagebox, filedialog

# 获取资源路径（支持打包后的环境）
def resource_path(relative_path):
    """获取资源文件的绝对路径，支持 PyInstaller 打包后的环境"""
    try:
        # PyInstaller 创建的临时文件夹路径
        base_path = sys._MEIPASS
    except Exception:
        # 开发环境，使用当前文件所在目录
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

# 获取脚本路径
def get_script_path(script_name):
    """获取脚本文件的路径，优先使用打包后的路径，否则使用当前目录"""
    # 尝试打包后的路径
    if hasattr(sys, '_MEIPASS'):
        script_path = os.path.join(sys._MEIPASS, script_name)
        if os.path.exists(script_path):
            return script_path
    
    # 尝试当前目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(current_dir, script_name)
    if os.path.exists(script_path):
        return script_path
    
    # 尝试使用系统 PATH
    return script_name

class Git2LogsGUI:
    def __init__(self, root):
        try:
            self.root = root
            self.root.title("GitLab 提交日志生成工具")
            # 增大窗口尺寸，使用更好的默认大小
            self.root.geometry("900x750")
            self.root.minsize(800, 600)
            
            # 保存待处理的AI分析数据
            self._pending_ai_data = None
            
            # 优化界面响应性能
            self.root.option_add('*tearOff', False)  # 禁用菜单的 tearoff 功能
            self._log_count = 0  # 日志计数器，用于控制更新频率
            
            # 配置现代化样式 - 暗黑主题，参考GitHub Dark模式
            style = ttk.Style()
            try:
                style.theme_use('clam')
            except:
                pass
            
            # 暗黑主题配色方案 - GitHub Dark风格
            try:
                # 主色调 - GitHub绿色
                primary_color = '#238636'  # GitHub绿色
                primary_hover = '#2ea043'
                primary_dark = '#1a7f37'
                
                # 暗黑背景色
                bg_main = '#0D1117'         # GitHub深色背景
                bg_card = '#161B22'         # 卡片深色背景
                bg_secondary = '#21262D'    # 次要背景
                
                # 文字颜色（暗黑主题）
                text_primary = '#C9D1D9'    # 主要文字（浅色）
                text_secondary = '#8B949E'  # 次要文字
                text_hint = '#6E7681'       # 提示文字
                
                # 边框和分割线（暗黑主题）
                border_color = '#30363D'     # 深色边框
                border_light = '#21262D'    # 浅边框
                
                # 输入框背景
                entry_bg = '#0D1117'        # 输入框深色背景
                
                # 设置窗口背景为暗黑
                root.configure(bg=bg_main)
                
                # 配置标签样式（暗黑主题）
                style.configure('TLabel',
                               font=('Helvetica Neue', 11),
                               background=bg_card,
                               foreground=text_primary,
                               padding=(0, 2))
                
                # 配置输入框样式 - 暗黑主题，使用更暗的边框
                style.configure('TEntry',
                               font=('Helvetica Neue', 13),
                               fieldbackground=entry_bg,
                               foreground=text_primary,
                               borderwidth=1,
                               relief='solid',
                               padding=(10, 8),
                               bordercolor='#30363D')  # 使用更暗的边框色
                style.map('TEntry',
                         bordercolor=[('focus', primary_color),
                                    ('!focus', '#30363D')],  # 非聚焦时使用暗色边框
                         lightcolor=[('focus', primary_color),
                                   ('!focus', '#30363D')],
                         darkcolor=[('focus', primary_color),
                                  ('!focus', '#30363D')],
                         fieldbackground=[('focus', entry_bg),
                                        ('!focus', entry_bg)])
                
                # 配置按钮样式 - 暗黑主题
                style.configure('TButton',
                               font=('Helvetica Neue', 12),
                               background=primary_color,
                               foreground='white',
                               borderwidth=0,
                               relief='flat',
                               padding=(16, 10),
                               focuscolor='none')
                style.map('TButton',
                         background=[('active', primary_hover),
                                   ('pressed', primary_dark)])
                
                # 次要按钮（暗黑主题）
                style.configure('Secondary.TButton',
                               background=bg_secondary,
                               foreground=text_primary,
                               borderwidth=1,
                               bordercolor=border_color,
                               padding=(16, 10))
                style.map('Secondary.TButton',
                         background=[('active', '#30363D')],
                         bordercolor=[('active', border_color)])
                
                # 配置复选框和单选按钮（暗黑主题）
                style.configure('TCheckbutton',
                               font=('Helvetica Neue', 11),
                               background=bg_card,
                               foreground=text_primary,
                               padding=(0, 4))
                
                style.configure('TRadiobutton',
                               font=('Helvetica Neue', 11),
                               background=bg_card,
                               foreground=text_primary,
                               padding=(0, 4))
                
                # 配置下拉框（暗黑主题）
                style.configure('TCombobox',
                               font=('Helvetica Neue', 13),
                               fieldbackground=entry_bg,
                               foreground=text_primary,
                               borderwidth=1,
                               relief='solid',
                               padding=(10, 8),
                               bordercolor='#30363D')  # 使用更暗的边框色
                style.map('TCombobox',
                         bordercolor=[('focus', primary_color),
                                    ('!focus', '#30363D')],
                         fieldbackground=[('focus', entry_bg),
                                        ('!focus', entry_bg)])
                
                # 配置标签页 - 自定义实现以修复对齐问题
                style.configure('TNotebook',
                               background=bg_main,
                               borderwidth=0)
                # 关键修复：统一所有标签页的高度和位置
                style.configure('TNotebook.Tab',
                               font=('Helvetica Neue', 12),
                               background=bg_secondary,
                               foreground=text_secondary,
                               padding=(24, 14),
                               borderwidth=0)
                style.map('TNotebook.Tab',
                         background=[('selected', bg_card)],
                         foreground=[('selected', text_primary)],
                         # 关键：禁用expand，保持统一高度
                         expand=[('', [0, 0, 0, 0]),
                               ('selected', [0, 0, 0, 0])])
                
                # 配置框架（暗黑主题）
                style.configure('TFrame',
                               background=bg_card,
                               relief='flat')
                
                # 配置LabelFrame（暗黑主题）
                style.configure('TLabelframe',
                               background=bg_card,
                               foreground=text_primary,
                               borderwidth=0,
                               relief='flat')
                style.configure('TLabelframe.Label',
                               font=('Helvetica Neue', 13, 'bold'),
                               background=bg_card,
                               foreground=text_primary)
                
            except Exception as e:
                print(f"样式配置警告: {e}")
                pass
            
            # 创建主容器 - 暗黑主题
            main_container = tk.Frame(root, bg='#0D1117')
            main_container.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
            
            # 配置网格权重
            root.columnconfigure(0, weight=1)
            root.rowconfigure(0, weight=1)
            
            # 创建标题区域 - 暗黑主题
            title_frame = tk.Frame(main_container, bg='#0D1117', height=70)
            title_frame.pack(fill=tk.X, pady=(0, 0))
            title_frame.pack_propagate(False)
            
            title_label = tk.Label(title_frame, 
                                text="MIZUKI-GITLAB工具箱", 
                                font=("Helvetica Neue", 20, "bold"),
                                bg='#0D1117',
                                fg='#C9D1D9')
            title_label.pack(pady=(18, 4))
            
            subtitle_label = tk.Label(title_frame,
                                     text="轻松生成和管理您的代码提交报告",
                                     font=("Helvetica Neue", 12),
                                     bg='#0D1117',
                                     fg='#8B949E')
            subtitle_label.pack()
            
            # 创建自定义标签页容器 - 修复对齐问题
            # 使用Frame + Button实现自定义标签页，确保完全对齐
            tab_container = tk.Frame(main_container, bg='#0D1117', height=50)
            tab_container.pack(fill=tk.X, padx=0, pady=(0, 0))
            tab_container.pack_propagate(False)
            
            # 创建标签按钮容器
            tab_button_frame = tk.Frame(tab_container, bg='#0D1117')
            tab_button_frame.pack(side=tk.LEFT, padx=20, pady=12)  # 增加垂直padding使标签更居中
            
            # 存储标签页引用
            self.tabs = {}
            self.current_tab = None
            
            # 创建标签按钮 - 使用更柔和的颜色
            tab_names = ["GitLab配置", "日期和输出", "AI分析"]
            self.tab_buttons = []
            for i, name in enumerate(tab_names):
                btn = tk.Button(tab_button_frame, text=name,
                              font=("Helvetica Neue", 12),
                              bg='#21262D', fg='#6E7681',  # 使用更暗的灰色文字
                              activebackground='#161B22',
                              activeforeground='#8B949E',  # 悬停时使用稍亮的灰色
                              borderwidth=0,
                              relief='flat',
                              padx=24, pady=14,
                              cursor='hand2',
                              command=lambda n=name: self._switch_tab(n))
                btn.pack(side=tk.LEFT, padx=(0, 2))
                self.tab_buttons.append((name, btn))
            
            # 创建可滚动的内容容器
            # 使用Canvas + Scrollbar实现滚动
            canvas_frame = tk.Frame(main_container, bg='#0D1117')
            canvas_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
            
            # 创建Canvas和Scrollbar
            self.scroll_canvas = tk.Canvas(canvas_frame, bg='#0D1117', highlightthickness=0)
            scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.scroll_canvas.yview)
            self.content_container = tk.Frame(self.scroll_canvas, bg='#0D1117')
            
            # 将内容容器添加到Canvas
            canvas_window = self.scroll_canvas.create_window((0, 0), window=self.content_container, anchor="nw")
            
            # 配置滚动
            def configure_scroll_region(event):
                self.scroll_canvas.configure(scrollregion=self.scroll_canvas.bbox("all"))
            
            def configure_canvas_width(event):
                canvas_width = event.width
                self.scroll_canvas.itemconfig(canvas_window, width=canvas_width)
            
            self.content_container.bind('<Configure>', configure_scroll_region)
            self.scroll_canvas.bind('<Configure>', configure_canvas_width)
            
            # 绑定鼠标滚轮（macOS和Windows/Linux不同）
            def on_mousewheel(event):
                # macOS使用delta，Windows/Linux使用delta/120
                if sys.platform == 'darwin':
                    self.scroll_canvas.yview_scroll(int(-1 * (event.delta)), "units")
                else:
                    self.scroll_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            
            # 绑定滚轮事件
            if sys.platform == 'darwin':
                self.scroll_canvas.bind_all("<MouseWheel>", on_mousewheel)
            else:
                self.scroll_canvas.bind_all("<MouseWheel>", on_mousewheel)
                self.scroll_canvas.bind_all("<Button-4>", lambda e: self.scroll_canvas.yview_scroll(-1, "units"))
                self.scroll_canvas.bind_all("<Button-5>", lambda e: self.scroll_canvas.yview_scroll(1, "units"))
            
            # 布局Canvas和Scrollbar
            self.scroll_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            self.scroll_canvas.configure(yscrollcommand=scrollbar.set)
            
            # 创建所有标签页内容（初始隐藏）
            self.tab_frames = {}
            
            # ========== 标签页1: GitLab配置 ==========
            tab1 = tk.Frame(self.content_container, bg='#161B22', padx=40, pady=35)
            self.tab_frames["GitLab配置"] = tab1
            
            # 创建内容容器 - 暗黑主题
            content_frame = tk.Frame(tab1, bg='#161B22')
            content_frame.pack(fill=tk.BOTH, expand=True)
            content_frame.columnconfigure(1, weight=1, minsize=450)
            
            row = 0
            
            # GitLab URL - 暗黑主题输入组
            url_label = tk.Label(content_frame, text="GitLab URL", 
                               font=("Helvetica Neue", 13, "bold"),
                               bg='#161B22', fg='#C9D1D9',
                               anchor='w')
            url_label.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(0, 6))
            row += 1
            
            self.gitlab_url = tk.StringVar()
            gitlab_entry = ttk.Entry(content_frame, textvariable=self.gitlab_url, width=50)
            gitlab_entry.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 24))
            # 添加提示文本（使用灰色占位符效果）
            placeholder_text = "https://gitlab.com 或 http://gitlab.yourcompany.com"
            self.gitlab_url.set(placeholder_text)
            gitlab_entry.config(foreground="gray")
            def on_gitlab_focus_in(event):
                current_value = self.gitlab_url.get()
                if current_value == placeholder_text:
                    self.gitlab_url.set("")
                    gitlab_entry.config(foreground="black")
            def on_gitlab_focus_out(event):
                current_value = self.gitlab_url.get()
                if not current_value.strip():
                    self.gitlab_url.set(placeholder_text)
                    gitlab_entry.config(foreground="gray")
            gitlab_entry.bind('<FocusIn>', on_gitlab_focus_in)
            gitlab_entry.bind('<FocusOut>', on_gitlab_focus_out)
            row += 1
        
            row += 1
            
            # 仓库地址（单项目模式）
            repo_label = tk.Label(content_frame, text="仓库地址", 
                                font=("Helvetica Neue", 13, "bold"),
                                bg='#161B22', fg='#C9D1D9',
                                anchor='w')
            repo_label.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(0, 6))
            row += 1
            
            self.repo = tk.StringVar()
            repo_entry = ttk.Entry(content_frame, textvariable=self.repo, width=50)
            repo_entry.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 16))
            row += 1
            
            # 扫描所有项目选项
            self.scan_all = tk.BooleanVar()
            scan_check = ttk.Checkbutton(content_frame, 
                        text="自动扫描所有项目（不填仓库地址时启用）", 
                        variable=self.scan_all)
            scan_check.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(0, 24))
            row += 1
            
            # 分支
            branch_label = tk.Label(content_frame, text="分支", 
                                  font=("Helvetica Neue", 13, "bold"),
                                  bg='#161B22', fg='#C9D1D9',
                                  anchor='w')
            branch_label.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(0, 6))
            row += 1
            
            self.branch = tk.StringVar()
            ttk.Entry(content_frame, textvariable=self.branch, width=50).grid(
                row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 24))
            row += 1
            
            # 提交者
            author_label = tk.Label(content_frame, text="提交者", 
                                  font=("Helvetica Neue", 13, "bold"),
                                  bg='#161B22', fg='#C9D1D9',
                                  anchor='w')
            author_label.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(0, 6))
            row += 1
            
            self.author = tk.StringVar(value="MIZUKI")
            ttk.Entry(content_frame, textvariable=self.author, width=50).grid(
                row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 24))
            row += 1
            
            # 访问令牌
            token_label = tk.Label(content_frame, text="访问令牌", 
                                 font=("Helvetica Neue", 13, "bold"),
                                 bg='#161B22', fg='#C9D1D9',
                                 anchor='w')
            token_label.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(0, 6))
            row += 1
            
            self.token = tk.StringVar()
            token_frame = tk.Frame(content_frame, bg='#161B22')
            token_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 24))
            token_frame.columnconfigure(0, weight=1)
            token_entry = ttk.Entry(token_frame, textvariable=self.token, width=50, show="*")
            token_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 8))
            show_btn = ttk.Button(token_frame, text="显示", width=10,
                  command=lambda: self.toggle_token_visibility(token_entry))
            show_btn.grid(row=0, column=1)
            row += 1
            
            # 添加提示信息 - 暗黑主题
            hint_frame = tk.Frame(content_frame, bg='#21262D', relief='flat', 
                                borderwidth=1, highlightbackground='#30363D',
                                padx=16, pady=14)
            hint_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(8, 0))
            hint_title = tk.Label(hint_frame, text="使用提示", 
                                font=("Helvetica Neue", 12, "bold"),
                                bg='#21262D', fg='#C9D1D9',
                                anchor='w')
            hint_title.pack(anchor='w', pady=(0, 8))
            hint_text = "• GitLab URL 是您的GitLab实例地址\n• 仓库地址留空时，勾选'自动扫描所有项目'可扫描所有项目\n• 访问令牌用于身份验证，可在GitLab设置中生成"
            hint_label = tk.Label(hint_frame, text=hint_text,
                                font=("Helvetica Neue", 12),
                                bg='#21262D', fg='#8B949E',
                                justify=tk.LEFT,
                                anchor='w')
            hint_label.pack(anchor='w')
            
            # ========== 标签页2: 日期和输出设置 ==========
            tab2 = tk.Frame(self.content_container, bg='#161B22', padx=40, pady=35)
            self.tab_frames["日期和输出"] = tab2
            
            content_frame2 = tk.Frame(tab2, bg='#161B22')
            content_frame2.pack(fill=tk.BOTH, expand=True)
            content_frame2.columnconfigure(0, weight=1)
            
            row = 0
            
            # 日期选择区域 - 暗黑主题
            date_card = tk.Frame(content_frame2, bg='#21262D', relief='flat', 
                               borderwidth=1, highlightbackground='#30363D',
                               padx=24, pady=24)
            date_card.grid(row=row, column=0, sticky=(tk.W, tk.E), pady=(0, 24))
            date_card.columnconfigure(1, weight=1)
            
            date_title = tk.Label(date_card, text="日期范围", 
                                font=("Helvetica Neue", 13, "bold"),
                                bg='#21262D', fg='#C9D1D9',
                                anchor='w')
            date_title.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 16))
            
            date_row = 1
            self.use_today = tk.BooleanVar(value=True)
            today_check = ttk.Checkbutton(date_card, text="今天", variable=self.use_today,
                       command=self.toggle_date_inputs)
            today_check.grid(row=date_row, column=0, sticky=tk.W, pady=8)
            
            date_input_frame = tk.Frame(date_card, bg='#21262D')
            date_input_frame.grid(row=date_row, column=1, sticky=(tk.W, tk.E), padx=(30, 0))
            
            tk.Label(date_input_frame, text="起始日期", 
                    font=("Helvetica Neue", 12),
                    bg='#21262D', fg='#8B949E').grid(row=0, column=0, padx=(0, 8), sticky=tk.W)
            self.since_date = tk.StringVar()
            self.since_entry = ttk.Entry(date_input_frame, textvariable=self.since_date, width=16)
            self.since_entry.grid(row=1, column=0, padx=(0, 24), pady=(6, 0))
            
            tk.Label(date_input_frame, text="结束日期", 
                    font=("Helvetica Neue", 12),
                    bg='#21262D', fg='#8B949E').grid(row=0, column=1, padx=(0, 8), sticky=tk.W)
            self.until_date = tk.StringVar()
            self.until_entry = ttk.Entry(date_input_frame, textvariable=self.until_date, width=16)
            self.until_entry.grid(row=1, column=1, pady=(6, 0))
            
            # 添加日期格式提示
            date_hint = tk.Label(date_card, 
                               text="提示: 日期格式为 YYYY-MM-DD，例如: 2025-12-12", 
                               font=("Helvetica Neue", 12),
                               bg='#21262D', fg='#6E7681',
                               anchor='w')
            date_hint.grid(row=2, column=0, columnspan=2, pady=(16, 0), sticky=tk.W)
            
            self.toggle_date_inputs()
            row += 1
            
            # 输出格式选择 - 暗黑主题
            format_card = tk.Frame(content_frame2, bg='#21262D', relief='flat',
                                 borderwidth=1, highlightbackground='#30363D',
                                 padx=24, pady=24)
            format_card.grid(row=row, column=0, sticky=(tk.W, tk.E), pady=(0, 24))
            format_card.columnconfigure(0, weight=1)
            
            format_title = tk.Label(format_card, text="输出格式", 
                                  font=("Helvetica Neue", 13, "bold"),
                                  bg='#21262D', fg='#C9D1D9',
                                  anchor='w')
            format_title.grid(row=0, column=0, sticky=tk.W, pady=(0, 16))
            
            self.output_format = tk.StringVar(value="daily_report")
            format_options = [
                ("Markdown 提交日志", "commits"),
                ("开发日报 (Markdown)", "daily_report"),
                ("统计报告 (代码统计与评分)", "statistics"),
                ("HTML 格式", "html"),
                ("PNG 图片", "png"),
                ("批量生成所有格式 (统计报告+日报+HTML+PNG)", "all")
            ]
            
            for i, (text, value) in enumerate(format_options):
                rb = ttk.Radiobutton(format_card, text=text, 
                           variable=self.output_format, value=value)
                rb.grid(row=i+1, column=0, sticky=tk.W, pady=8)
            
            row += 1
            
            # 输出文件/目录路径 - 暗黑主题
            output_card = tk.Frame(content_frame2, bg='#21262D', relief='flat',
                                 borderwidth=1, highlightbackground='#30363D',
                                 padx=24, pady=24)
            output_card.grid(row=row, column=0, sticky=(tk.W, tk.E), pady=(0, 0))
            output_card.columnconfigure(0, weight=1)
            
            output_title = tk.Label(output_card, text="输出设置", 
                                  font=("Helvetica Neue", 13, "bold"),
                                  bg='#21262D', fg='#C9D1D9',
                                  anchor='w')
            output_title.grid(row=0, column=0, sticky=tk.W, pady=(0, 16))
            
            output_label_text = "输出目录" if self.output_format.get() == "all" else "输出文件"
            self.output_label = tk.Label(output_card, text=output_label_text,
                                        font=("Helvetica Neue", 13, "bold"),
                                        bg='#21262D', fg='#C9D1D9',
                                        anchor='w')
            self.output_label.grid(row=1, column=0, sticky=tk.W, pady=(0, 6))
            
            self.output_file = tk.StringVar()
            output_frame = tk.Frame(output_card, bg='#21262D')
            output_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 8))
            output_frame.columnconfigure(0, weight=1)
            output_entry = ttk.Entry(output_frame, textvariable=self.output_file, width=40)
            output_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 8))
            browse_btn = ttk.Button(output_frame, text="浏览", width=12,
                  command=self.browse_output_file)
            browse_btn.grid(row=0, column=1)
            
            # 添加提示标签
            self.output_hint = tk.Label(output_card, text="提示: 批量生成时请选择目录", 
                                     font=("Helvetica Neue", 12),
                                     bg='#21262D', fg='#6E7681',
                                     anchor='w')
            self.output_hint.grid(row=3, column=0, sticky=tk.W, pady=(0, 0))
        
            # 绑定输出格式变化事件（延迟绑定，避免初始化时调用）
            def setup_output_format_trace():
                try:
                    self.output_format.trace('w', self.on_output_format_changed)
                except Exception:
                    pass
            # 在下一帧执行，确保所有初始化完成
            root.after(100, setup_output_format_trace)
            
            # ========== 标签页3: AI分析配置 ==========
            tab3 = tk.Frame(self.content_container, bg='#161B22', padx=40, pady=35)
            self.tab_frames["AI分析"] = tab3
            
            content_frame3 = tk.Frame(tab3, bg='#161B22')
            content_frame3.pack(fill=tk.BOTH, expand=True)
            content_frame3.columnconfigure(1, weight=1)
            
            row = 0
            
            # AI分析开关
            self.ai_enabled = tk.BooleanVar(value=False)
            ai_enable_check = ttk.Checkbutton(content_frame3, 
                        text="启用AI分析", 
                        variable=self.ai_enabled,
                        command=self.toggle_ai_config)
            ai_enable_check.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(0, 24))
            row += 1
            
            # AI配置区域（默认隐藏）- 暗黑主题
            self.ai_config_frame = tk.Frame(content_frame3, bg='#21262D', relief='flat',
                                          borderwidth=1, highlightbackground='#30363D',
                                          padx=24, pady=24)
            self.ai_config_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 0))
            self.ai_config_frame.columnconfigure(1, weight=1)
            
            ai_title = tk.Label(self.ai_config_frame, text="AI配置", 
                              font=("Helvetica Neue", 13, "bold"),
                              bg='#21262D', fg='#C9D1D9',
                              anchor='w')
            ai_title.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 20))
        
            config_row = 0
        
            # AI服务选择
            ttk.Label(self.ai_config_frame, text="AI服务:").grid(
                row=config_row, column=0, sticky=tk.W, pady=8, padx=(0, 10))
            self.ai_service = tk.StringVar(value="openai")
            ai_service_combo = ttk.Combobox(self.ai_config_frame, textvariable=self.ai_service, 
                                       values=["openai", "anthropic", "gemini", "doubao", "deepseek"], 
                                       state="readonly", width=20)
            ai_service_combo.grid(row=config_row, column=1, sticky=tk.W, pady=8)
            config_row += 1
        
            # 模型选择
            ttk.Label(self.ai_config_frame, text="模型:").grid(
                row=config_row, column=0, sticky=tk.W, pady=8, padx=(0, 10))
            self.ai_model = tk.StringVar(value="gpt-4")
            ai_model_combo = ttk.Combobox(self.ai_config_frame, textvariable=self.ai_model, 
                                     width=30)
            ai_model_combo.grid(row=config_row, column=1, sticky=(tk.W, tk.E), pady=8, padx=(0, 5))
        
            # 根据服务更新模型选项
            def update_models(*args):
                service = self.ai_service.get()
                if service == "openai":
                    ai_model_combo['values'] = ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo"]
                    if self.ai_model.get() not in ai_model_combo['values']:
                        self.ai_model.set("gpt-4o-mini")
                elif service == "anthropic":
                    ai_model_combo['values'] = ["claude-3-5-sonnet-20241022", "claude-3-opus-20240229", "claude-3-sonnet-20240229"]
                    if self.ai_model.get() not in ai_model_combo['values']:
                        self.ai_model.set("claude-3-5-sonnet-20241022")
                elif service == "gemini":
                    ai_model_combo['values'] = [
                        "gemini-3-flash-preview",
                        "gemini-3-pro-preview",
                        "gemini-2.5-pro",
                        "gemini-2.5-flash",
                        "gemini-2.5-flash-lite",
                        "gemini-2.5",
                        "gemini-1.5-pro",
                        "gemini-1.5-flash"
                    ]
                    if self.ai_model.get() not in ai_model_combo['values']:
                        self.ai_model.set("gemini-3-flash-preview")
                elif service == "doubao":
                    ai_model_combo['values'] = ["doubao-pro-128k", "doubao-lite-128k"]
                    if self.ai_model.get() not in ai_model_combo['values']:
                        self.ai_model.set("doubao-pro-128k")
                elif service == "deepseek":
                    ai_model_combo['values'] = ["deepseek-chat", "deepseek-coder", "deepseek-reasoner"]
                    if self.ai_model.get() not in ai_model_combo['values']:
                        self.ai_model.set("deepseek-chat")
            
            self.ai_service.trace('w', update_models)
            update_models()
            config_row += 1
            
            # API Key
            key_label = tk.Label(self.ai_config_frame, text="API Key", 
                               font=("Helvetica Neue", 13, "bold"),
                               bg='#21262D', fg='#C9D1D9',
                               anchor='w')
            key_label.grid(row=config_row, column=0, sticky=tk.W, pady=(0, 6), padx=(0, 20))
            self.ai_api_key = tk.StringVar()
            key_frame = tk.Frame(self.ai_config_frame, bg='#21262D')
            key_frame.grid(row=config_row, column=1, sticky=(tk.W, tk.E), pady=(0, 24))
            key_frame.columnconfigure(0, weight=1)
            ai_key_entry = ttk.Entry(key_frame, textvariable=self.ai_api_key, width=40, 
                                show="*")
            ai_key_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 8))
            key_show_btn = ttk.Button(key_frame, text="显示", width=10,
                  command=lambda: self.toggle_key_visibility(ai_key_entry))
            key_show_btn.grid(row=0, column=1)
            config_row += 1
            
            # 测试连接按钮
            test_btn_frame = tk.Frame(self.ai_config_frame, bg='#21262D')
            test_btn_frame.grid(row=config_row, column=0, columnspan=2, pady=(8, 0), sticky=tk.W)
            test_btn = ttk.Button(test_btn_frame, text="测试连接", width=16,
                  command=self.test_ai_connection)
            test_btn.pack(side=tk.LEFT, padx=(0, 12))
            self.test_status_label = tk.Label(test_btn_frame, text="", 
                                            font=("Helvetica Neue", 12),
                                            bg='#21262D', fg='#8B949E')
            self.test_status_label.pack(side=tk.LEFT)
        
            # 初始隐藏AI配置
            self.ai_config_frame.grid_remove()
            
            # ========== 底部操作区域（添加到可滚动容器中） ==========
            # 执行按钮区域 - 暗黑主题
            button_container = tk.Frame(self.content_container, bg='#0D1117', 
                                      borderwidth=1, highlightbackground='#30363D',
                                      height=70)
            button_container.pack(fill=tk.X, padx=0, pady=(20, 0))
            button_container.pack_propagate(False)
            
            button_frame = tk.Frame(button_container, bg='#0D1117')
            button_frame.pack(pady=16)
            
            # 主按钮 - GitHub绿色
            self.generate_btn = ttk.Button(button_frame, text="生成日志", 
                                       command=self.generate_logs, width=18)
            self.generate_btn.pack(side=tk.LEFT, padx=6)
            
            # 次要按钮
            clear_btn = ttk.Button(button_frame, text="清空日志", 
                  command=self.clear_logs, width=18, style='Secondary.TButton')
            clear_btn.pack(side=tk.LEFT, padx=6)
            
            # AI分析按钮
            self.ai_analysis_btn = ttk.Button(button_frame, text="执行AI分析", 
                                          command=self._manual_ai_analysis, width=18, 
                                          state='normal', style='Secondary.TButton')
            self.ai_analysis_btn.pack(side=tk.LEFT, padx=6)
            
            # 日志输出区域 - 暗黑主题
            log_container = tk.Frame(self.content_container, bg='#0D1117')
            log_container.pack(fill=tk.BOTH, expand=True, padx=0, pady=(0, 20))
            
            log_title_frame = tk.Frame(log_container, bg='#0D1117', 
                                     borderwidth=0, highlightbackground='#30363D',
                                     height=50)
            log_title_frame.pack(fill=tk.X, padx=0, pady=0)
            log_title_frame.pack_propagate(False)
            
            log_title = tk.Label(log_title_frame, text="执行日志", 
                               font=("Helvetica Neue", 13, "bold"),
                               bg='#0D1117', fg='#C9D1D9',
                               anchor='w')
            log_title.pack(side=tk.LEFT, padx=20, pady=14)
            
            log_card = tk.Frame(log_container, bg='#161B22', 
                              borderwidth=1, highlightbackground='#30363D',
                              relief='flat')
            log_card.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
            
            # 配置日志文本区域样式 - 暗黑主题
            self.log_text = scrolledtext.ScrolledText(log_card, height=12, width=80, 
                                                  font=("Menlo", 11), 
                                                  wrap=tk.WORD,
                                                  bg='#0D1117',
                                                  fg='#C9D1D9',
                                                  insertbackground='#238636',
                                                  selectbackground='#238636',
                                                  selectforeground='white',
                                                  borderwidth=0,
                                                  relief='flat',
                                                  padx=20,
                                                  pady=20)
            self.log_text.pack(fill=tk.BOTH, expand=True)
            
            # 默认显示第一个标签页
            self._switch_tab("GitLab配置")
            
            # 初始日志
            self.log("欢迎使用 GitLab 提交日志生成工具！")
            self.log("请填写参数后点击'生成日志'按钮。")
        except Exception as e:
            import traceback
            error_msg = f"界面初始化失败: {str(e)}\n\n{traceback.format_exc()}"
            print(error_msg)
            # 尝试显示错误
            try:
                messagebox.showerror("初始化错误", error_msg)
            except:
                pass
            raise
    
    def _switch_tab(self, tab_name):
        """切换标签页（自定义实现，确保对齐）"""
        try:
            # 隐藏所有标签页
            for name, frame in self.tab_frames.items():
                frame.pack_forget()
            
            # 显示选中的标签页
            if tab_name in self.tab_frames:
                self.tab_frames[tab_name].pack(fill=tk.BOTH, expand=True)
                self.current_tab = tab_name
            
            # 更新按钮样式 - 使用更柔和的颜色
            for name, btn in self.tab_buttons:
                if name == tab_name:
                    # 选中状态 - 使用更柔和的颜色
                    btn.config(bg='#161B22', fg='#8B949E',  # 选中时使用中等灰色，不要太亮
                              activebackground='#161B22',
                              activeforeground='#8B949E')
                else:
                    # 未选中状态 - 使用更暗的颜色
                    btn.config(bg='#21262D', fg='#6E7681',  # 未选中时使用更暗的灰色
                              activebackground='#21262D',
                              activeforeground='#6E7681')
            
            self.root.update_idletasks()
        except Exception as e:
            print(f"切换标签页错误: {e}")
    
    def toggle_token_visibility(self, entry):
        """切换令牌显示/隐藏（优化响应速度）"""
        try:
            if entry.cget('show') == '*':
                entry.config(show='')
            else:
                entry.config(show='*')
            # 立即更新界面并设置焦点
            entry.focus_set()
            self.root.update_idletasks()
        except Exception:
            pass  # 忽略异常，避免界面卡顿
    
    def toggle_key_visibility(self, entry):
        """切换API Key显示/隐藏"""
        try:
            if entry.cget('show') == '*':
                entry.config(show='')
            else:
                entry.config(show='*')
            # 立即更新界面并设置焦点
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
                self.since_entry.config(state='disabled')
                self.until_entry.config(state='disabled')
            else:
                self.since_entry.config(state='normal')
                self.until_entry.config(state='normal')
            self.root.update_idletasks()
        except Exception:
            pass
    
    def on_output_format_changed(self, *args):
        """输出格式变化时的回调"""
        try:
            format_value = self.output_format.get()
            if format_value == "all":
                self.output_label.config(text="输出目录:")
                self.output_hint.config(text="提示: 批量生成时请选择目录，所有文件将保存到该目录")
            else:
                self.output_label.config(text="输出文件:")
                self.output_hint.config(text="提示: 批量生成时请选择目录")
            self.root.update_idletasks()
        except Exception:
            pass
    
    def browse_output_file(self):
        """浏览输出文件/目录"""
        try:
            format_value = self.output_format.get()
            if format_value == "all":
                # 选择目录
                directory = filedialog.askdirectory(
                    title="选择输出目录",
                    initialdir=self.output_file.get().strip() or os.getcwd()
                )
                if directory:
                    self.output_file.set(directory)
            else:
                # 选择文件
                filename = filedialog.asksaveasfilename(
                    title="选择输出文件",
                    initialdir=self.output_file.get().strip() or os.getcwd(),
                    defaultextension=".md",
                    filetypes=[("Markdown文件", "*.md"), ("所有文件", "*.*")]
                )
                if filename:
                    self.output_file.set(filename)
            self.root.update_idletasks()
        except Exception as e:
            messagebox.showerror("错误", f"选择文件/目录失败: {str(e)}")
    
    def log(self, message):
        """添加日志消息"""
        try:
            # Tk 不是线程安全的：任何 UI 更新必须在主线程执行。
            import threading
            if threading.current_thread() is not threading.main_thread():
                try:
                    self.root.after(0, lambda: self.log(message))
                except Exception:
                    pass
                return

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            log_message = f"{timestamp} - {message}\n"
            self.log_text.insert(tk.END, log_message)
            self.log_text.see(tk.END)
            self._log_count += 1
            # 限制日志长度，避免内存占用过大
            if self._log_count > 1000:
                self.log_text.delete(1.0, "100.0")
                self._log_count = 900
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

            self.log_text.delete(1.0, tk.END)
            self._log_count = 0
            self.log("日志已清空")
        except Exception:
            pass
    
    def generate_logs(self):
        """生成日志的主函数"""
        try:
            self.generate_btn.config(state='disabled')
            thread = threading.Thread(target=self._run_git2logs_direct)
            thread.daemon = True
            thread.start()
        except Exception as e:
            self.log(f"✗ 启动生成任务失败: {str(e)}")
            self.generate_btn.config(state='normal')
    
    def _run_git2logs_direct(self):
        """在后台线程中执行git2logs"""
        root_logger = None
        gui_handler = None
        try:
            from datetime import datetime
            
            from git2logs import (
                create_gitlab_client, scan_all_projects, get_commits_by_author,
                group_commits_by_date, generate_markdown_log, generate_multi_project_markdown,
                generate_daily_report, generate_statistics_report, generate_all_reports,
                analyze_with_ai, generate_ai_analysis_report, generate_local_analysis_report,
                extract_gitlab_url, parse_project_identifier
            )
            import logging
            
            # 重定向日志输出到 GUI
            # 使用自定义的日志处理器来捕获 git2logs.py 的输出
            class GUILogHandler(logging.Handler):
                def __init__(self, gui_log_func):
                    super().__init__()
                    self.gui_log_func = gui_log_func
                
                def emit(self, record):
                    try:
                        msg = self.format(record)
                        self.gui_log_func(msg)
                    except Exception:
                        pass
            
            gui_handler = GUILogHandler(self.log)
            gui_handler.setLevel(logging.INFO)
            formatter = logging.Formatter('%(levelname)s - %(message)s')
            gui_handler.setFormatter(formatter)
            
            # 获取根日志记录器并添加处理器
            root_logger = logging.getLogger()
            # 避免重复添加 handler（多次生成会叠加，导致日志倍增/线程问题更明显）
            try:
                if hasattr(self, "_gui_log_handler") and self._gui_log_handler in root_logger.handlers:
                    root_logger.removeHandler(self._gui_log_handler)
            except Exception:
                pass
            root_logger.addHandler(gui_handler)
            self._gui_log_handler = gui_handler
            root_logger.setLevel(logging.INFO)
            
            self.log("=" * 60)
            self.log("开始生成日志...")
            
            # 获取配置
            gitlab_url = self.gitlab_url.get().strip()
            token = self.token.get().strip()
            author = self.author.get().strip()
            repo = self.repo.get().strip()
            branch = self.branch.get().strip() if hasattr(self, 'branch') and self.branch.get().strip() else None
            
            # 检查占位符
            placeholder_text = "https://gitlab.com 或 http://gitlab.yourcompany.com"
            if gitlab_url == placeholder_text:
                gitlab_url = ""
            
            # 验证必要参数
            if not gitlab_url or not token or not author:
                self.log("✗ 错误: 请填写GitLab URL、访问令牌和提交者")
                self.root.after(0, lambda: messagebox.showerror("错误", "请填写GitLab URL、访问令牌和提交者"))
                self.root.after(0, lambda: self.generate_btn.config(state='normal'))
                return
            
            # 日期处理
            since_date = None
            until_date = None
            if not self.use_today.get():
                since_date = self.since_date.get().strip()
                until_date = self.until_date.get().strip()
                if not since_date or not until_date:
                    self.log("✗ 错误: 请填写起始日期和结束日期")
                    self.root.after(0, lambda: messagebox.showerror("错误", "请填写起始日期和结束日期"))
                    self.root.after(0, lambda: self.generate_btn.config(state='normal'))
                    return
            
            # 创建GitLab客户端
            self.log(f"正在连接到 GitLab: {gitlab_url}")
            gl = create_gitlab_client(gitlab_url, token)
            
            # 获取提交记录
            all_results = {}
            
            if self.scan_all.get() or not repo:
                # 自动扫描所有项目
                self.log("正在扫描所有项目...")
                all_results = scan_all_projects(
                    gl, author,
                    since_date=since_date,
                    until_date=until_date,
                    branch=branch
                )
                self.log(f"扫描完成，共在 {len(all_results)} 个项目中找到提交记录")
            else:
                # 单项目模式
                extracted_url = extract_gitlab_url(repo)
                if extracted_url:
                    gitlab_url = extracted_url
                    self.log(f"从仓库 URL 提取 GitLab 实例: {gitlab_url}")
                    gl = create_gitlab_client(gitlab_url, token)
                
                project_identifier = parse_project_identifier(repo)
                self.log(f"正在获取项目: {project_identifier}")
                
                try:
                    project = gl.projects.get(project_identifier)
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
                        self.log(f"✓ 找到 {len(commits)} 条提交记录")
                except Exception as e:
                    self.log(f"✗ 获取项目失败: {str(e)}")
            
            if not all_results:
                self.log("✗ 未找到任何提交记录")
                self.root.after(0, lambda: messagebox.showwarning("提示", "未找到任何提交记录"))
                self.root.after(0, lambda: self.generate_btn.config(state='normal'))
                return
            
            # 确定输出路径
            output_path = self.output_file.get().strip()
            if not output_path:
                output_path = os.getcwd()
                self.log(f"未指定输出路径，使用当前目录: {output_path}")
            
            # 根据输出格式生成报告
            output_format = self.output_format.get()
            self.log(f"输出格式: {output_format}")
            
            generated_files = {}
            
            if output_format == "statistics":
                # 生成统计报告
                self.log("正在生成统计报告...")
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
                self.log(f"✓ 统计报告已保存: {output_file}")
                self.log("💡 提示: 统计报告包含本地多维度评价，AI分析需要手动触发")
                
                # 如果AI已启用，保存数据供手动分析
                if self.ai_enabled.get() and self.ai_api_key.get().strip():
                    self._pending_ai_data = {
                        'all_results': all_results,
                        'author': author,
                        'output_dir': os.path.dirname(output_file),
                        'since_date': since_date,
                        'until_date': until_date,
                        'generated_files': generated_files
                    }
                    self.log("💡 提示: 数据已保存，可以点击'执行AI分析'按钮进行AI分析")
            elif output_format == "all":
                # 批量生成所有格式
                self.log("正在批量生成所有格式...")
                generated_files = generate_all_reports(
                    all_results, author, output_path,
                    since_date=since_date, until_date=until_date
                )
                self.log(f"✓ 批量生成完成，共生成 {len(generated_files)} 个文件")
                for file_type, file_path in generated_files.items():
                    self.log(f"  - {file_type}: {file_path}")
            else:
                # 其他格式（commits, daily_report, html, png）
                self.log(f"正在生成 {output_format} 格式...")
                if output_format == "commits":
                    if len(all_results) == 1:
                        report_content = generate_markdown_log(list(all_results.values())[0]['commits'])
                    else:
                        report_content = generate_multi_project_markdown(all_results)
                elif output_format == "daily_report":
                    report_content = generate_daily_report(
                        all_results, author,
                        since_date=since_date, until_date=until_date
                    )
                else:
                    # html 和 png 格式需要特殊处理
                    self.log(f"✗ 暂不支持 {output_format} 格式的直接生成")
                    self.root.after(0, lambda: self.generate_btn.config(state='normal'))
                    return
                
                if os.path.isdir(output_path):
                    date_prefix = since_date if since_date and until_date and since_date == until_date else datetime.now().strftime('%Y-%m-%d')
                    output_file = os.path.join(output_path, f"{date_prefix}_{output_format}.md")
                else:
                    output_file = output_path
                
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(report_content)
                
                generated_files[output_format] = output_file
                self.log(f"✓ 报告已保存: {output_file}")
            
            self.log("=" * 60)
            self.log("✓ 生成完成！")
            
            # 重新启用按钮
            self.root.after(0, lambda: self.generate_btn.config(state='normal'))
            
        except Exception as e:
            self.log(f"✗ 生成失败: {str(e)}")
            import traceback
            self.log(traceback.format_exc())
            self.root.after(0, lambda: messagebox.showerror("错误", f"生成失败: {str(e)}"))
            self.root.after(0, lambda: self.generate_btn.config(state='normal'))
        finally:
            # 清理本次 handler，防止多次运行堆积
            try:
                import logging
                if root_logger is None:
                    root_logger = logging.getLogger()
                if gui_handler is not None and gui_handler in root_logger.handlers:
                    root_logger.removeHandler(gui_handler)
            except Exception:
                pass
    
    def _manual_ai_analysis(self):
        """手动触发AI分析"""
        try:
            if not self.ai_enabled.get() or not self.ai_api_key.get().strip():
                messagebox.showwarning("提示", "请先启用AI分析并配置API Key")
                return
            
            # 检查是否有待处理的数据
            if self._pending_ai_data:
                result = messagebox.askyesno(
                    "AI分析",
                    "检测到当前会话的数据，是否使用当前会话的数据进行分析？\n\n"
                    "选择'是'：使用当前会话的数据\n"
                    "选择'否'：选择已生成的报告文件",
                    icon='question'
                )
                if result:
                    # 使用当前会话数据
                    self.root.after(0, self._perform_ai_analysis)
                    return
            
            # 让用户选择报告文件
            report_file = filedialog.askopenfilename(
                title="选择报告文件（统计报告或日报）",
                initialdir=self.output_file.get().strip() or os.getcwd(),
                filetypes=[
                    ("Markdown文件", "*.md"),
                    ("所有文件", "*.*")
                ]
            )
            
            if not report_file:
                return
            
            # 直接基于报告文件内容进行AI分析
            self.log("=" * 60)
            self.log(f"选择的报告文件: {report_file}")
            self.log("正在读取报告文件并发送给AI分析...")
            
            thread = threading.Thread(target=self._analyze_report_file_direct, args=(report_file,))
            thread.daemon = True
            thread.start()
            
        except Exception as e:
            self.log(f"✗ 启动AI分析失败: {str(e)}")
            messagebox.showerror("错误", f"启动AI分析失败: {str(e)}")
    
    def _analyze_report_file_direct(self, report_file):
        """直接基于报告文件内容进行AI分析（不需要GitLab数据）"""
        import re
        
        try:
            # 读取报告文件
            with open(report_file, 'r', encoding='utf-8') as f:
                report_content = f.read()
            
            self.log(f"✓ 报告文件读取成功，文件大小: {len(report_content)} 字符")
            
            # 从报告中提取作者和日期信息（用于生成报告）
            author_match = re.search(r'\*\*提交者\*\*: (.+)', report_content)
            author = author_match.group(1).strip() if author_match else "未知作者"
            
            # 提取日期范围
            date_range_match = re.search(r'\*\*统计时间范围\*\*: (.+?) 至 (.+?)(?:\n|$)', report_content)
            if date_range_match:
                since_date = date_range_match.group(1).strip()
                until_date = date_range_match.group(2).strip()
            else:
                # 尝试其他格式
                since_match = re.search(r'\*\*起始日期\*\*: (.+?)(?:\n|$)', report_content)
                until_match = re.search(r'\*\*结束日期\*\*: (.+?)(?:\n|$)', report_content)
                since_date = since_match.group(1).strip() if since_match else None
                until_date = until_match.group(1).strip() if until_match else None
            
            # 检查AI配置
            if not self.ai_enabled.get() or not self.ai_api_key.get().strip():
                self.log("✗ 错误: 请先配置AI服务并输入API Key")
                self.root.after(0, lambda: messagebox.showerror("错误", "请先配置AI服务并输入API Key"))
                return
            
            # 构建AI配置
            ai_config = {
                'service': self.ai_service.get(),
                'api_key': self.ai_api_key.get().strip(),
                'model': self.ai_model.get()
            }
            
            self.log("")
            self.log("=" * 60)
            self.log("🤖 开始AI分析（基于报告文件内容）...")
            self.log(f"提示: AI分析可能需要30秒到2分钟，超时时间: 120秒")
            self.log(f"AI服务: {self.ai_service.get()}, 模型: {self.ai_model.get()}")
            self.log(f"作者: {author}")
            if since_date and until_date:
                self.log(f"日期范围: {since_date} 至 {until_date}")
            
            # 调用AI分析
            from ai_analysis import analyze_report_file
            from git2logs import generate_ai_analysis_report
            
            analysis_result = analyze_report_file(report_content, ai_config, timeout=120)
            
            self.log("✓ AI分析完成，正在生成报告...")
            
            # 生成AI分析报告
            ai_report_content = generate_ai_analysis_report(
                analysis_result, author,
                since_date=since_date, until_date=until_date
            )
            
            # 保存AI分析报告到报告文件所在目录
            report_dir = os.path.dirname(report_file)
            date_prefix = since_date if since_date and until_date and since_date == until_date else datetime.now().strftime('%Y-%m-%d')
            ai_report_file = os.path.join(report_dir, f"{date_prefix}_ai_analysis.md")
            
            with open(ai_report_file, 'w', encoding='utf-8') as f:
                f.write(ai_report_content)
            
            self.log(f"✓ AI分析报告已保存: {ai_report_file}")
            self.log(f"📄 文件大小: {len(ai_report_content)} 字符")
            self.log("💡 提示: 文件名包含 '_ai_analysis' 表示这是AI分析报告")
            self.log("=" * 60)
            self.log("✓ AI分析完成！")
            
        except ImportError as e:
            self.log(f"⚠ AI分析功能不可用: {str(e)}")
            self.log("提示: 请运行 'pip install openai anthropic google-generativeai' 安装AI服务库")
            self.root.after(0, lambda: messagebox.showerror("错误", f"AI分析功能不可用: {str(e)}"))
        except TimeoutError as e:
            self.log(f"⏱️ AI分析超时: {str(e)}")
            self.log("可能的原因:")
            self.log("  1. 网络连接较慢或不稳定")
            self.log("  2. AI服务响应较慢")
            self.log("  3. 报告文件内容较大，处理时间较长")
            self.log("建议: 请检查网络连接，或稍后重试")
            self.root.after(0, lambda: messagebox.showerror("错误", f"AI分析超时: {str(e)}"))
        except ValueError as e:
            error_msg = str(e)
            self.log(f"🔑 AI分析失败（API密钥或配置问题）:")
            self.log(f"   {error_msg}")
            self.root.after(0, lambda: messagebox.showerror("错误", f"AI分析失败: {error_msg}"))
        except ConnectionError as e:
            error_msg = str(e)
            self.log(f"🌐 AI分析失败（网络连接问题）:")
            self.log(f"   {error_msg}")
            self.root.after(0, lambda: messagebox.showerror("错误", f"网络连接失败: {error_msg}"))
        except Exception as e:
            self.log(f"⚠ AI分析失败: {str(e)}")
            import traceback
            self.log(traceback.format_exc())
            self.root.after(0, lambda: messagebox.showerror("错误", f"AI分析失败: {str(e)}"))
        finally:
            # 重新启用按钮
            self.root.after(0, lambda: self.generate_btn.config(state='normal'))
    
    def _perform_ai_analysis(self):
        """执行AI分析（使用待处理的数据）"""
        try:
            if not self._pending_ai_data:
                messagebox.showwarning("提示", "没有可用的数据进行分析")
                return
            
            # 构建AI配置
            ai_config = {
                'service': self.ai_service.get(),
                'api_key': self.ai_api_key.get().strip(),
                'model': self.ai_model.get()
            }
            
            self.log("")
            self.log("=" * 60)
            self.log("🤖 开始AI分析...")
            self.log(f"提示: AI分析可能需要30秒到2分钟，超时时间: 120秒")
            self.log(f"AI服务: {self.ai_service.get()}, 模型: {self.ai_model.get()}")
            
            thread = threading.Thread(target=self._perform_ai_analysis_thread, args=(ai_config,))
            thread.daemon = True
            thread.start()
            
        except Exception as e:
            self.log(f"✗ 启动AI分析失败: {str(e)}")
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
            
            self.log("✓ AI分析完成，正在生成报告...")
            
            # 生成AI分析报告
            ai_report_content = generate_ai_analysis_report(
                analysis_result, author,
                since_date=since_date, until_date=until_date
            )
            
            # 保存报告
            output_dir = self._pending_ai_data.get('output_dir', os.getcwd())
            date_prefix = since_date if since_date and until_date and since_date == until_date else datetime.now().strftime('%Y-%m-%d')
            ai_report_file = os.path.join(output_dir, f"{date_prefix}_ai_analysis.md")
            
            with open(ai_report_file, 'w', encoding='utf-8') as f:
                f.write(ai_report_content)
            
            self.log(f"✓ AI分析报告已保存: {ai_report_file}")
            self.log("=" * 60)
            self.log("✓ AI分析完成！")
            
        except Exception as e:
            self.log(f"✗ AI分析失败: {str(e)}")
            import traceback
            self.log(traceback.format_exc())
            self.root.after(0, lambda: messagebox.showerror("错误", f"AI分析失败: {str(e)}"))
        finally:
            self.root.after(0, lambda: self.generate_btn.config(state='normal'))
    
    def test_ai_connection(self):
        """测试AI连接"""
        try:
            if not self.ai_api_key.get().strip():
                self.test_status_label.config(text="请先输入API Key", foreground="red")
                return
            
            self.test_status_label.config(text="测试中...", foreground="blue")
            thread = threading.Thread(target=self._test_ai_connection_thread)
            thread.daemon = True
            thread.start()
        except Exception as e:
            self.test_status_label.config(text=f"测试失败: {str(e)}", foreground="red")
    
    def _test_ai_connection_thread(self):
        """在后台线程中测试AI连接"""
        try:
            from ai_analysis import analyze_with_ai
            import google.generativeai as genai
            from google.api_core import exceptions as google_exceptions
            
            service = self.ai_service.get()
            api_key = self.ai_api_key.get().strip()
            model = self.ai_model.get()
            
            if service == "gemini":
                genai.configure(api_key=api_key)
                models = genai.list_models()
                available_models = []
                for m in models:
                    # 过滤掉embedding模型
                    if 'embedding' not in m.name.lower():
                        # 检查是否支持generateContent
                        if hasattr(m, 'supported_generation_methods'):
                            if 'generateContent' in m.supported_generation_methods:
                                available_models.append(m.name.split('/')[-1])
                        else:
                            available_models.append(m.name.split('/')[-1])
                
                if model in available_models:
                    self.root.after(0, lambda: self.test_status_label.config(
                        text=f"连接成功，模型 {model} 可用", foreground="green"))
                else:
                    self.root.after(0, lambda: self.test_status_label.config(
                        text=f"连接成功，但模型 {model} 不可用\n可用模型: {','.join(available_models[:5])}", 
                        foreground="orange"))
            else:
                # OpenAI和Anthropic的测试逻辑
                self.root.after(0, lambda: self.test_status_label.config(
                    text="连接测试成功", foreground="green"))
                
        except Exception as e:
            error_msg = str(e)
            if "401" in error_msg or "unauthorized" in error_msg.lower() or "invalid" in error_msg.lower():
                self.root.after(0, lambda: self.test_status_label.config(
                    text="API密钥无效", foreground="red"))
            elif "connection" in error_msg.lower() or "network" in error_msg.lower():
                self.root.after(0, lambda: self.test_status_label.config(
                    text="网络连接失败", foreground="red"))
            else:
                self.root.after(0, lambda: self.test_status_label.config(
                    text=f"测试失败: {error_msg[:50]}", foreground="red"))


def main():
    """主函数 - 优先使用 CustomTkinter 版本"""
    # 检查是否存在 CustomTkinter 版本
    ctk_gui_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'git2logs_gui_ctk.py')
    if os.path.exists(ctk_gui_path):
        try:
            # 尝试导入 CustomTkinter
            import customtkinter as ctk
            # 如果成功，使用 CustomTkinter 版本
            import importlib.util
            spec = importlib.util.spec_from_file_location("git2logs_gui_ctk", ctk_gui_path)
            ctk_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(ctk_module)
            ctk_module.main()
            return
        except ImportError:
            print("警告: CustomTkinter 未安装，使用标准 tkinter 版本")
            print("要使用现代化界面，请运行: pip install customtkinter")
        except Exception as e:
            print(f"加载 CustomTkinter 版本失败: {e}，使用标准版本")
    
    # 使用标准 tkinter 版本
    root = None
    try:
        root = tk.Tk()
        root.withdraw()
        app = Git2LogsGUI(root)
        root.update_idletasks()
        root.update()
        root.deiconify()
        root.update_idletasks()
        width = root.winfo_width()
        height = root.winfo_height()
        x = (root.winfo_screenwidth() // 2) - (width // 2)
        y = (root.winfo_screenheight() // 2) - (height // 2)
        root.geometry(f'{width}x{height}+{x}+{y}')
        root.mainloop()
    except Exception as e:
        import traceback
        error_msg = f"程序启动失败: {str(e)}\n\n{traceback.format_exc()}"
        print(error_msg)
        try:
            if root:
                root.withdraw()
            error_root = tk.Tk()
            error_root.withdraw()
            messagebox.showerror("启动错误", error_msg)
            error_root.destroy()
        except:
            pass
        if root:
            root.destroy()
        raise

if __name__ == '__main__':
    main()
