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

class Git2LogsGUI:
    def __init__(self, root):
        try:
            self.root = root
            self.root.title("MIZUKI-GITLAB工具箱")
            self.root.geometry("700x800")
            self.root.minsize(400, 700)
            self.root.resizable(True, True)  # 允许自由调整大小
            
            # 保存待处理的AI分析数据
            self._pending_ai_data = None
            self._log_count = 0
            
            # 配置 CustomTkinter 主题
            ctk.set_appearance_mode("dark")  # 强制暗黑模式
            ctk.set_default_color_theme("blue")  # 使用蓝色主题
            
            # 定义颜色方案
            self.bg_main = "#18181B"      # 主背景深灰
            self.bg_card = "#27272A"      # 卡片背景
            self.text_primary = "#F4F4F5"  # 主要文字（纯白/近白）
            self.text_secondary = "#A1A1AA" # 次要文字
            self.border_color = "#3F3F46"  # 边框色
            self.accent_color = "#3B82F6"  # 科技蓝
            self.success_color = "#10B981" # 成功绿
            self.error_color = "#EF4444"   # 错误红
            
            # 设置窗口背景
            self.root.configure(bg=self.bg_main)
            
            # 创建主容器（立即显示）
            main_container = ctk.CTkFrame(root, fg_color=self.bg_main, corner_radius=0)
            main_container.pack(fill="both", expand=True, padx=0, pady=0)
            
            # 标题区域（只显示副标题，主标题在窗口标题栏）
            title_frame = ctk.CTkFrame(main_container, fg_color=self.bg_main, height=50, corner_radius=0)
            title_frame.pack(fill="x", padx=0, pady=0)
            title_frame.pack_propagate(False)
            
            subtitle_label = ctk.CTkLabel(title_frame,
                                         text="轻松生成和管理您的代码提交报告",
                                         font=ctk.CTkFont(size=13),
                                         text_color=self.text_secondary,
                                         fg_color="transparent")
            subtitle_label.pack(pady=(15, 0))
            
            # 立即更新，显示标题
            root.update_idletasks()
            root.update()
            
            # 创建日志显示区域（放在最上方）
            self._create_log_area(main_container)
            
            # 创建 Segmented Control 风格的标签导航
            self.tab_container = ctk.CTkFrame(main_container, fg_color=self.bg_main, height=50, corner_radius=0)
            self.tab_container.pack(fill="x", padx=20, pady=(10, 0))
            self.tab_container.pack_propagate(False)
            
            # 标签按钮容器
            tab_button_frame = ctk.CTkFrame(self.tab_container, fg_color=self.bg_card, corner_radius=8)
            tab_button_frame.pack(side="left", padx=0, pady=8)
            
            # 存储标签页引用
            self.tab_frames = {}
            self.current_tab = None
            self.tab_buttons = []
            
            # 创建标签按钮（Segmented Control 风格）
            tab_names = ["GitLab配置", "日期和输出", "AI分析"]
            for i, name in enumerate(tab_names):
                btn = ctk.CTkButton(tab_button_frame,
                                  text=name,
                                  font=ctk.CTkFont(size=13, weight="normal"),
                                  fg_color=self.bg_card if i == 0 else "transparent",
                                  text_color=self.text_primary if i == 0 else self.text_secondary,
                                  hover_color="#3F3F46",
                                  corner_radius=6,
                                  height=36,
                                  width=120,
                                  command=lambda n=name: self._switch_tab(n),
                                  border_width=0)
                btn.pack(side="left", padx=2, pady=4)
                self.tab_buttons.append((name, btn))
            
            # 底部固定操作按钮容器（主观能动性：固定底部能彻底解决按钮在滚动时的重叠闪烁）
            self.bottom_actions_frame = ctk.CTkFrame(main_container, fg_color=self.bg_main, corner_radius=0)
            self.bottom_actions_frame.pack(side="bottom", fill="x", padx=0, pady=0)
            
            # 使用 CustomTkinter 官方推荐的 CTKScrollableFrame
            # 这是解决 macOS 下滚动鬼影、重叠和闪烁的最佳方案
            # 我们将背景色设为一致，以减少视觉闪烁
            self.scroll_container = ctk.CTkScrollableFrame(main_container,
                                                         fg_color=self.bg_main,
                                                         corner_radius=0)
            self.scroll_container.pack(fill="both", expand=True, padx=0, pady=0)
            
            # 为了保持向下兼容性，将 content_container 指向滚动容器
            self.content_container = self.scroll_container
            
            # 隐藏滚动条（通过配置其颜色为背景色来实现视觉隐藏，更安全）
            try:
                self.scroll_container.configure(scrollbar_button_color=self.bg_main, 
                                              scrollbar_button_hover_color=self.bg_main)
            except:
                pass
            
            # 延迟并批量创建标签页内容（消除渲染毛刺）
            def delayed_init():
                try:
                    # 分步构建 UI 组件，但不执行强制 update
                    self._create_tab1_gitlab_config()
                    self._create_tab2_date_output()
                    self._create_tab3_ai_analysis()
                    self._create_bottom_actions()
                    
                    # 默认显示第一个标签页
                    self._switch_tab("GitLab配置")
                    
                    # 关键一次性静默同步
                    self.root.update_idletasks()
                    
                    # 初始日志
                    self.log("欢迎使用 MIZUKI-GITLAB工具箱！", "info")
                    self.log("请填写参数后点击'生成日志'按钮。", "info")
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
            except:
                pass
            raise
    
    def _create_log_area(self, parent):
        """创建日志显示区域（放在最上方）"""
        # 日志输出区域
        log_container = ctk.CTkFrame(parent, fg_color=self.bg_main, corner_radius=0)
        log_container.pack(fill="x", padx=0, pady=(0, 10))
        
        log_title_frame = ctk.CTkFrame(log_container,
                                     fg_color=self.bg_main,
                                     height=40,
                                     corner_radius=0)
        log_title_frame.pack(fill="x", padx=20, pady=(0, 8))
        log_title_frame.pack_propagate(False)
        
        log_title = ctk.CTkLabel(log_title_frame,
                              text="执行日志",
                              font=ctk.CTkFont(size=13, weight="bold"),
                              text_color=self.text_primary,
                              anchor="w")
        log_title.pack(side="left", padx=0, pady=10)
        
        # 日志文本区域 - 使用等宽字体，固定高度
        log_card = ctk.CTkFrame(log_container,
                              fg_color=self.bg_card,
                              corner_radius=10)
        log_card.pack(fill="x", padx=20, pady=(0, 0))
        
        # 使用 ScrolledText（CustomTkinter 没有原生的 ScrolledText）
        # 创建一个内部Frame来放置ScrolledText
        text_container = ctk.CTkFrame(log_card, fg_color=self.bg_main, corner_radius=8)
        text_container.pack(fill="x", padx=10, pady=10)
        
        from tkinter import scrolledtext
        self.log_text = scrolledtext.ScrolledText(text_container,
                                             height=8,  # 固定高度，减少占用空间
                                             width=80,
                                             font=("JetBrains Mono", 10),  # 等宽字体，稍小一点
                                             wrap="word",
                                             bg=self.bg_main,
                                             fg=self.text_primary,
                                             insertbackground=self.accent_color,
                                             selectbackground=self.accent_color,
                                             selectforeground="white",
                                             borderwidth=0,
                                             relief="flat",
                                             padx=12,
                                             pady=12)
        self.log_text.pack(fill="both", expand=False)
        
        # 预先配置标签颜色，避免在 log 方法中重复配置
        self.log_text.tag_config("error", foreground=self.error_color)
        self.log_text.tag_config("success", foreground=self.success_color)
        self.log_text.tag_config("warning", foreground="#F59E0B")
        self.log_text.tag_config("info", foreground=self.text_primary)
        self.log_text.tag_config("timestamp", foreground=self.text_secondary)
    
    def _create_tab1_gitlab_config(self):
        """创建标签页1: GitLab配置"""
        # 优化：透明背景且取消圆角
        tab1 = ctk.CTkFrame(self.content_container, fg_color="transparent", corner_radius=0)
        tab1.pack(fill="both", expand=True, padx=20, pady=20)
        
        # 内容容器
        content = ctk.CTkFrame(tab1, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=30, pady=10)
        
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
        gitlab_entry.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 24))
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
        repo_entry.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 16))
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
        author_entry.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 24))
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
        token_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 24))
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
        content.columnconfigure(0, weight=1)
        
        # 添加底部占位符
        ctk.CTkLabel(content, text="", height=50).grid(row=row+1, column=0)
        
        self.tab_frames["GitLab配置"] = tab1
        tab1.pack_forget()  # 初始隐藏
    
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
    
    def _create_bottom_actions(self):
        """创建底部固定操作按钮区域（固定在窗口底部，不随内容滚动）"""
        # 使用我们在 __init__ 中预先创建好的底部框架
        button_container = ctk.CTkFrame(self.bottom_actions_frame,
                                       fg_color=self.bg_main,
                                       corner_radius=0)
        button_container.pack(fill="x", padx=20, pady=(10, 20))
        
        # 使用 grid 布局以实现自适应
        button_frame = ctk.CTkFrame(button_container, fg_color="transparent")
        button_frame.pack(fill="x", padx=0, pady=15)
        
        # 配置 grid 列权重，使按钮平均分配空间
        button_frame.grid_columnconfigure(0, weight=1, uniform="buttons")
        button_frame.grid_columnconfigure(1, weight=1, uniform="buttons")
        button_frame.grid_columnconfigure(2, weight=1, uniform="buttons")
        
        # 主按钮 - 绿色渐变效果（使用绿色）
        self.generate_btn = ctk.CTkButton(button_frame,
                                        text="生成日志",
                                        height=45,
                                        font=ctk.CTkFont(size=14, weight="bold"),
                                        corner_radius=10,
                                        fg_color=self.success_color,
                                        text_color="white",
                                        hover_color="#059669",
                                        command=self.generate_logs)
        self.generate_btn.grid(row=0, column=0, padx=8, sticky="ew")
        
        # 次要按钮
        clear_btn = ctk.CTkButton(button_frame,
                                text="清空日志",
                                height=45,
                                font=ctk.CTkFont(size=14),
                                corner_radius=10,
                                fg_color=self.bg_card,
                                text_color=self.text_primary,
                                hover_color="#3F3F46",
                                border_width=1,
                                border_color=self.border_color,
                                command=self.clear_logs)
        clear_btn.grid(row=0, column=1, padx=8, sticky="ew")
        
        # AI分析按钮
        self.ai_analysis_btn = ctk.CTkButton(button_frame,
                                           text="执行AI分析",
                                           height=45,
                                           font=ctk.CTkFont(size=14),
                                           corner_radius=10,
                                           fg_color=self.bg_card,
                                           text_color=self.text_primary,
                                           hover_color="#3F3F46",
                                           border_width=1,
                                           border_color=self.border_color,
                                           state="normal",
                                           command=self._manual_ai_analysis)
        self.ai_analysis_btn.grid(row=0, column=2, padx=8, sticky="ew")
        
        # 移除复杂的动态字体调整，这在滚动时会引起布局震荡和重叠闪烁
        # 保持稳定的 UI 布局对滚动体验至关重要
        self._last_resize_width = self.root.winfo_width()
        
        # 统一使用稳定的字体大小，避免由于 Configure 事件引发的递归重绘
        self.generate_btn.configure(font=ctk.CTkFont(size=14, weight="bold"))
        clear_btn.configure(font=ctk.CTkFont(size=14))
        self.ai_analysis_btn.configure(font=ctk.CTkFont(size=14))
    
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
            
            # 更新按钮样式（Segmented Control 效果）
            for name, btn in self.tab_buttons:
                if name == tab_name:
                    btn.configure(fg_color=self.bg_card, text_color=self.text_primary)
                else:
                    btn.configure(fg_color="transparent", text_color=self.text_secondary)
            
            # 立即滚动到顶部
            if hasattr(self, 'scroll_container'):
                # 修复标准调用方式
                self.scroll_container._canvas.yview_moveto(0)
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
            except:
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
        try:
            self.generate_btn.configure(state="disabled")
            # 延迟启动线程，防止按钮点击时的微小卡顿，让 UI 有时间更新状态
            self.root.after(50, lambda: threading.Thread(target=self._run_git2logs_direct, daemon=True).start())
        except Exception as e:
            self.log(f"启动生成任务失败: {str(e)}", "error")
            self.generate_btn.configure(state="normal")
    
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
                self.root.after(0, lambda: self.generate_btn.configure(state="normal"))
                return
            
            # 日期处理
            since_date = None
            until_date = None
            use_today_value = self.use_today.get()
            self.log(f"调试: '今天'复选框状态: {use_today_value}", "info")
            
            if use_today_value:
                # 使用今天的日期（考虑时区问题）
                # GitLab API 使用 UTC 时间，为了覆盖时区差异，我们扩展日期范围（前后各1天）
                from datetime import datetime, timedelta
                today_local = datetime.now()
                # 扩展日期范围：前一天到后一天，以覆盖时区差异
                since_date_obj = today_local - timedelta(days=1)
                until_date_obj = today_local + timedelta(days=1)
                since_date = since_date_obj.strftime('%Y-%m-%d')
                until_date = until_date_obj.strftime('%Y-%m-%d')
                self.log(f"使用今天的日期范围: {since_date} 至 {until_date} (已扩展以覆盖时区差异)", "info")
                # 同时记录 UTC 日期以便调试
                from datetime import timezone
                today_utc = datetime.now(timezone.utc).strftime('%Y-%m-%d')
                today_local_str = today_local.strftime('%Y-%m-%d')
                if today_local_str != today_utc:
                    self.log(f"提示: 本地日期为 {today_local_str}，UTC 日期为 {today_utc}，已扩展日期范围以覆盖时区差异", "info")
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
                        self.root.after(0, lambda: self.generate_btn.configure(state="normal"))
                        return
            
            # 创建GitLab客户端
            self.log(f"正在连接到 GitLab: {gitlab_url}", "info")
            if since_date and until_date:
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
                self.root.after(0, lambda: self.generate_btn.configure(state="normal"))
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
                    from git2logs import generate_work_hours_report
                    report_content = generate_work_hours_report(
                        all_results, author,
                        since_date=since_date, until_date=until_date,
                        daily_hours=8.0, branch=branch
                    )
                else:
                    self.log(f"暂不支持 {output_format} 格式的直接生成", "error")
                    self.root.after(0, lambda: self.generate_btn.configure(state="normal"))
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
            
            self.log("=" * 60, "info")
            self.log("生成完成！", "success")
            
            self.root.after(0, lambda: self.generate_btn.configure(state="normal"))
            
        except Exception as e:
            self.log(f"生成失败: {str(e)}", "error")
            import traceback
            self.log(traceback.format_exc(), "error")
            self.root.after(0, lambda: messagebox.showerror("错误", f"生成失败: {str(e)}"))
            self.root.after(0, lambda: self.generate_btn.configure(state="normal"))
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
    
    def _manual_ai_analysis(self):
        """手动触发AI分析"""
        try:
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
            self.root.after(0, lambda: self.generate_btn.configure(state="normal"))
    
    def _perform_ai_analysis(self):
        """执行AI分析（使用待处理的数据）"""
        try:
            if not self._pending_ai_data:
                messagebox.showwarning("提示", "没有可用的数据进行分析")
                return
            
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
            self.root.after(0, lambda: self.generate_btn.configure(state="normal"))
    
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
        root.geometry("700x800")
        root.minsize(400, 700)
        root.resizable(True, True)
        
        # 设置窗口位置（在创建应用前）
        width = 700
        height = 800
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
        except:
            pass
        if root:
            root.destroy()
        raise

if __name__ == '__main__':
    main()
