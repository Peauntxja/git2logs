#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitLab 提交日志生成工具 - 图形界面版本
"""
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime

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
        self.root = root
        self.root.title("GitLab 提交日志生成工具")
        self.root.geometry("800x700")
        
        # 优化界面响应性能
        self.root.option_add('*tearOff', False)  # 禁用菜单的 tearoff 功能
        self._log_count = 0  # 日志计数器，用于控制更新频率
        
        # 创建主框架
        main_frame = ttk.Frame(root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置网格权重
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        row = 0
        
        # 标题
        title_label = ttk.Label(main_frame, text="GitLab 提交日志生成工具", 
                               font=("Arial", 16, "bold"))
        title_label.grid(row=row, column=0, columnspan=3, pady=(0, 20))
        row += 1
        
        # GitLab URL
        ttk.Label(main_frame, text="GitLab URL:").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.gitlab_url = tk.StringVar(value="http://gitlab.example.com")
        ttk.Entry(main_frame, textvariable=self.gitlab_url, width=50).grid(
            row=row, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        row += 1
        
        # 仓库地址（单项目模式）
        ttk.Label(main_frame, text="仓库地址:").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.repo = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.repo, width=50).grid(
            row=row, column=1, sticky=(tk.W, tk.E), pady=5)
        row += 1
        
        # 扫描所有项目选项
        self.scan_all = tk.BooleanVar()
        ttk.Checkbutton(main_frame, text="自动扫描所有项目（不填仓库地址时启用）", 
                        variable=self.scan_all).grid(
            row=row, column=1, sticky=tk.W, pady=5)
        row += 1
        
        # 分支
        ttk.Label(main_frame, text="分支:").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.branch = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.branch, width=50).grid(
            row=row, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        row += 1
        
        # 提交者
        ttk.Label(main_frame, text="提交者:").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.author = tk.StringVar(value="MIZUKI")
        ttk.Entry(main_frame, textvariable=self.author, width=50).grid(
            row=row, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        row += 1
        
        # 访问令牌
        ttk.Label(main_frame, text="访问令牌:").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.token = tk.StringVar()
        token_entry = ttk.Entry(main_frame, textvariable=self.token, width=50, show="*")
        token_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5)
        ttk.Button(main_frame, text="显示", width=8,
                  command=lambda: self.toggle_token_visibility(token_entry)).grid(
            row=row, column=2, padx=(5, 0), pady=5)
        row += 1
        
        # 日期选择
        date_frame = ttk.Frame(main_frame)
        date_frame.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        
        self.use_today = tk.BooleanVar(value=True)
        ttk.Checkbutton(date_frame, text="今天", variable=self.use_today,
                       command=self.toggle_date_inputs).grid(row=0, column=0, sticky=tk.W)
        
        ttk.Label(date_frame, text="起始日期:").grid(row=0, column=1, padx=(20, 5))
        self.since_date = tk.StringVar()
        self.since_entry = ttk.Entry(date_frame, textvariable=self.since_date, width=12)
        self.since_entry.grid(row=0, column=2)
        ttk.Label(date_frame, text="(YYYY-MM-DD)").grid(row=0, column=3, padx=(5, 0))
        
        ttk.Label(date_frame, text="结束日期:").grid(row=0, column=4, padx=(20, 5))
        self.until_date = tk.StringVar()
        self.until_entry = ttk.Entry(date_frame, textvariable=self.until_date, width=12)
        self.until_entry.grid(row=0, column=5)
        ttk.Label(date_frame, text="(YYYY-MM-DD)").grid(row=0, column=6, padx=(5, 0))
        
        # 添加日期格式提示
        date_hint = ttk.Label(date_frame, text="提示: 日期格式为 YYYY-MM-DD，例如: 2025-12-12", 
                             font=("Arial", 9), foreground="gray")
        date_hint.grid(row=1, column=0, columnspan=7, pady=(5, 0), sticky=tk.W)
        
        self.toggle_date_inputs()
        row += 1
        
        # 输出格式选择
        format_frame = ttk.LabelFrame(main_frame, text="输出格式", padding="10")
        format_frame.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        format_frame.columnconfigure(0, weight=1)
        
        self.output_format = tk.StringVar(value="daily_report")
        ttk.Radiobutton(format_frame, text="Markdown 提交日志", 
                       variable=self.output_format, value="commits").grid(
            row=0, column=0, sticky=tk.W, pady=2)
        ttk.Radiobutton(format_frame, text="开发日报 (Markdown)", 
                       variable=self.output_format, value="daily_report").grid(
            row=1, column=0, sticky=tk.W, pady=2)
        ttk.Radiobutton(format_frame, text="HTML 格式", 
                       variable=self.output_format, value="html").grid(
            row=2, column=0, sticky=tk.W, pady=2)
        ttk.Radiobutton(format_frame, text="PNG 图片", 
                       variable=self.output_format, value="png").grid(
            row=3, column=0, sticky=tk.W, pady=2)
        row += 1
        
        # 输出文件路径
        ttk.Label(main_frame, text="输出文件:").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.output_file = tk.StringVar()
        output_frame = ttk.Frame(main_frame)
        output_frame.grid(row=row, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        output_frame.columnconfigure(0, weight=1)
        ttk.Entry(output_frame, textvariable=self.output_file, width=40).grid(
            row=0, column=0, sticky=(tk.W, tk.E))
        ttk.Button(output_frame, text="浏览", width=8,
                  command=self.browse_output_file).grid(row=0, column=1, padx=(5, 0))
        row += 1
        
        # 执行按钮
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=row, column=0, columnspan=3, pady=20)
        self.generate_btn = ttk.Button(button_frame, text="生成日志", 
                                       command=self.generate_logs, width=20)
        self.generate_btn.pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="清空日志", 
                  command=self.clear_logs, width=20).pack(side=tk.LEFT, padx=5)
        row += 1
        
        # 日志输出区域
        log_frame = ttk.LabelFrame(main_frame, text="执行日志", padding="5")
        log_frame.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(row, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, width=80)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 初始日志
        self.log("欢迎使用 GitLab 提交日志生成工具！")
        self.log("请填写参数后点击'生成日志'按钮。")
    
    def toggle_token_visibility(self, entry):
        """切换令牌显示/隐藏（优化响应速度）"""
        try:
            if entry.cget('show') == '*':
                entry.config(show='')
            else:
                entry.config(show='*')
            # 立即更新界面
            self.root.update_idletasks()
        except Exception:
            pass  # 忽略异常，避免界面卡顿
    
    def toggle_date_inputs(self):
        """切换日期输入框的启用状态（优化响应速度）"""
        try:
            state = 'disabled' if self.use_today.get() else 'normal'
            self.since_entry.config(state=state)
            self.until_entry.config(state=state)
            # 立即更新界面
            self.root.update_idletasks()
        except Exception:
            pass  # 忽略异常，避免界面卡顿
    
    def _validate_date_format(self, date_str):
        """验证日期格式是否为 YYYY-MM-DD"""
        try:
            from datetime import datetime
            datetime.strptime(date_str, '%Y-%m-%d')
            return True
        except ValueError:
            return False
    
    def browse_output_file(self):
        """浏览选择输出文件或目录（优化响应速度）"""
        # 立即更新界面，确保按钮点击响应
        self.root.update_idletasks()
        
        format_ext = {
            'commits': '.md',
            'daily_report': '.md',
            'html': '.html',
            'png': '.png'
        }
        ext = format_ext.get(self.output_format.get(), '.md')
        
        # 询问用户是选择文件还是目录
        try:
            choice = messagebox.askyesnocancel(
                "选择输出位置",
                "选择输出位置：\n\n是 = 选择文件\n否 = 选择目录（自动生成文件名）\n取消 = 取消"
            )
            
            if choice is None:  # 取消
                return
            elif choice:  # 选择文件
                filename = filedialog.asksaveasfilename(
                    defaultextension=ext,
                    filetypes=[("所有文件", "*.*"), 
                              ("Markdown", "*.md"),
                              ("HTML", "*.html"),
                              ("PNG", "*.png")])
                if filename:
                    self.output_file.set(filename)
            else:  # 选择目录
                directory = filedialog.askdirectory(title="选择输出目录")
                if directory:
                    self.output_file.set(directory)
        except Exception as e:
            # 捕获异常，避免对话框阻塞
            messagebox.showerror("错误", f"选择文件时出错: {str(e)}")
    
    def log(self, message):
        """添加日志（优化性能，减少界面更新频率）"""
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        # 减少 update_idletasks 调用频率，避免界面卡顿
        # 只在必要时更新界面（每10次调用更新一次，或重要操作时立即更新）
        if not hasattr(self, '_log_count'):
            self._log_count = 0
        self._log_count += 1
        if self._log_count % 10 == 0 or '错误' in message or '成功' in message or '完成' in message:
            self.root.update_idletasks()
    
    def clear_logs(self):
        """清空日志"""
        self.log_text.delete(1.0, tk.END)
    
    def validate_inputs(self):
        """验证输入"""
        if not self.gitlab_url.get().strip():
            messagebox.showerror("错误", "请输入 GitLab URL")
            return False
        
        if not self.scan_all.get() and not self.repo.get().strip():
            messagebox.showerror("错误", "请输入仓库地址或选择'自动扫描所有项目'")
            return False
        
        if not self.author.get().strip():
            messagebox.showerror("错误", "请输入提交者姓名")
            return False
        
        if not self.token.get().strip():
            messagebox.showerror("错误", "请输入访问令牌")
            return False
        
        return True
    
    def generate_logs(self):
        """生成日志"""
        if not self.validate_inputs():
            return
        
        # 禁用按钮
        self.generate_btn.config(state='disabled')
        self.clear_logs()
        
        # 在新线程中执行，避免界面冻结
        thread = threading.Thread(target=self._generate_logs_thread)
        thread.daemon = True
        thread.start()
    
    def _generate_logs_thread(self):
        """在后台线程中生成日志"""
        # 检查是否是打包后的环境
        is_frozen = hasattr(sys, '_MEIPASS')
        
        if is_frozen:
            # 打包后的环境：直接导入模块并调用
            self._run_git2logs_direct()
        else:
            # 开发环境：使用 subprocess 调用脚本
            self._run_git2logs_subprocess()
    
    def _run_git2logs_direct(self):
        """直接调用 git2logs 模块（打包后的环境）"""
        try:
            from git2logs import (
                create_gitlab_client, scan_all_projects, get_commits_by_author,
                group_commits_by_date, generate_markdown_log, generate_multi_project_markdown,
                generate_daily_report, extract_gitlab_url, parse_project_identifier
            )
            import logging
            
            # 重定向日志输出到 GUI
            # 使用自定义的日志处理器来捕获 git2logs.py 的输出
            class GUILogHandler(logging.Handler):
                def __init__(self, gui_log_func):
                    super().__init__()
                    self.gui_log_func = gui_log_func
                
                def emit(self, record):
                    msg = self.format(record)
                    self.gui_log_func(msg)
            
            # 获取根 logger（git2logs.py 使用根 logger）
            root_logger = logging.getLogger()
            gui_handler = GUILogHandler(self.log)
            gui_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
            root_logger.addHandler(gui_handler)
            root_logger.setLevel(logging.INFO)
            
            # 准备参数
            gitlab_url = self.gitlab_url.get().strip()
            
            # 处理提交者名称格式
            author_input = self.author.get().strip()
            if '<' in author_input and '>' in author_input:
                email_match = author_input.split('<')[1].split('>')[0]
                author_to_use = email_match.strip()
                self.log(f"从 '{author_input}' 中提取邮箱: {author_to_use}")
            else:
                author_to_use = author_input
            
            token = self.token.get().strip()
            
            # 日期参数
            if self.use_today.get():
                today = datetime.now().strftime('%Y-%m-%d')
                since_date = today
                until_date = today
            else:
                since_date = self.since_date.get().strip() if self.since_date.get().strip() else None
                until_date = self.until_date.get().strip() if self.until_date.get().strip() else None
            
            branch = self.branch.get().strip() if self.branch.get().strip() else None
            output_format = self.output_format.get()
            is_daily_report = (output_format == 'daily_report')
            
            # 输出文件
            output_file = self.output_file.get().strip()
            actual_output_file = None
            
            if output_file:
                if os.path.isdir(output_file):
                    today = datetime.now().strftime('%Y-%m-%d')
                    branch_suffix = f"_{branch}" if branch else ""
                    if is_daily_report:
                        filename = f"{today}_daily_report{branch_suffix}.md"
                    else:
                        filename = f"{today}_commits{branch_suffix}.md"
                    actual_output_file = os.path.join(output_file, filename)
                    self.log(f"输出路径是目录，自动生成文件名: {actual_output_file}")
                else:
                    actual_output_file = output_file
                    if not os.path.splitext(actual_output_file)[1]:
                        actual_output_file = actual_output_file + '.md'
            else:
                today = datetime.now().strftime('%Y-%m-%d')
                branch_suffix = f"_{branch}" if branch else ""
                if is_daily_report:
                    actual_output_file = f"{today}_daily_report{branch_suffix}.md"
                else:
                    actual_output_file = f"{today}_commits{branch_suffix}.md"
            
            self.log("=" * 60)
            
            # 创建 GitLab 客户端
            gl = create_gitlab_client(gitlab_url, token)
            
            found_commits = False
            no_commits_warning = False
            
            if self.scan_all.get():
                # 扫描所有项目
                self.log(f"使用自动扫描模式，GitLab 实例: {gitlab_url}")
                all_results = scan_all_projects(
                    gl, author_to_use,
                    since_date=since_date,
                    until_date=until_date,
                    branch=branch
                )
                
                if not all_results:
                    no_commits_warning = True
                    self.log("⚠ 未在任何项目中找到提交记录")
                else:
                    found_commits = True
                    # 生成 Markdown
                    if is_daily_report:
                        markdown_content = generate_daily_report(
                            all_results, author_to_use,
                            since_date=since_date, until_date=until_date
                        )
                    else:
                        markdown_content = generate_multi_project_markdown(
                            all_results, author_to_use,
                            since_date=since_date, until_date=until_date
                        )
                    
                    # 保存文件
                    with open(actual_output_file, 'w', encoding='utf-8') as f:
                        f.write(markdown_content)
                    self.log(f"日志已保存到: {actual_output_file}")
            else:
                # 单项目模式
                repo = self.repo.get().strip()
                extracted_url = extract_gitlab_url(repo)
                if extracted_url:
                    gitlab_url = extracted_url
                    self.log(f"从仓库 URL 提取 GitLab 实例: {gitlab_url}")
                    gl = create_gitlab_client(gitlab_url, token)
                
                project_id = parse_project_identifier(repo)
                self.log(f"项目标识符: {project_id}")
                
                project = gl.projects.get(project_id)
                self.log(f"成功获取项目: {project.name}")
                
                commits = get_commits_by_author(
                    project, author_to_use,
                    since_date=since_date,
                    until_date=until_date,
                    branch=branch
                )
                
                if not commits:
                    no_commits_warning = True
                    self.log("⚠ 未找到提交记录")
                else:
                    found_commits = True
                    grouped_commits = group_commits_by_date(commits)
                    markdown_content = generate_markdown_log(
                        grouped_commits, author_to_use, repo_name=project.name
                    )
                    
                    with open(actual_output_file, 'w', encoding='utf-8') as f:
                        f.write(markdown_content)
                    self.log(f"日志已保存到: {actual_output_file}")
            
            # 日志已经通过 GUI handler 实时输出，无需再次读取
            
            # 检查文件
            file_exists = os.path.exists(actual_output_file) if actual_output_file else False
            
            self.log("=" * 60)
            
            if no_commits_warning or not found_commits:
                self.log("⚠ 未找到提交记录")
                self.log("可能的原因：")
                self.log("  1. 指定日期范围内没有提交")
                self.log("  2. 提交者名称不匹配（请检查 GitLab 中的实际提交者名称）")
                self.log("  3. 指定的分支不存在或没有权限访问")
                self.log("  4. 访问令牌权限不足")
                messagebox.showwarning("警告", 
                    "未找到提交记录。\n\n请检查：\n"
                    "1. 日期范围是否正确\n"
                    "2. 提交者名称是否匹配\n"
                    "3. 分支名称是否正确\n"
                    "4. 访问令牌权限是否足够")
            elif file_exists:
                self.log("✓ 日志生成成功！")
                self.log(f"文件已保存: {actual_output_file}")
                
                # 如果需要生成 HTML 或 PNG
                output_format = self.output_format.get()
                if output_format in ['html', 'png']:
                    self.log("\n正在生成 HTML/PNG 格式...")
                    self._generate_html_or_png(actual_output_file)
            else:
                self.log("⚠ 命令执行成功，但未找到生成的文件")
                self.log(f"预期文件: {actual_output_file}")
                messagebox.showwarning("警告", 
                    f"命令执行成功，但未找到生成的文件。\n\n预期文件: {actual_output_file}")
        
        except Exception as e:
            self.log(f"错误: {str(e)}")
            import traceback
            self.log(traceback.format_exc())
            messagebox.showerror("错误", f"执行出错: {str(e)}")
        finally:
            # 移除 GUI handler
            root_logger.removeHandler(gui_handler)
            gui_handler.close()
            self.root.after(0, lambda: self.generate_btn.config(state='normal'))
    
    def _run_git2logs_subprocess(self):
        """使用 subprocess 调用 git2logs.py（开发环境）"""
        try:
            # 构建命令
            cmd = ['python3', 'git2logs.py']
            
            # 添加参数
            if self.scan_all.get():
                cmd.append('--scan-all')
            else:
                cmd.extend(['--repo', self.repo.get().strip()])
            
            cmd.extend(['--gitlab-url', self.gitlab_url.get().strip()])
            
            # 处理提交者名称格式（支持 "名称<邮箱>" 格式）
            author_input = self.author.get().strip()
            # 如果包含 < >，提取邮箱部分；否则使用原值
            if '<' in author_input and '>' in author_input:
                # 提取邮箱部分
                email_match = author_input.split('<')[1].split('>')[0]
                author_to_use = email_match.strip()
                self.log(f"从 '{author_input}' 中提取邮箱: {author_to_use}")
            else:
                author_to_use = author_input
            
            cmd.extend(['--author', author_to_use])
            cmd.extend(['--token', self.token.get().strip()])
            
            if self.branch.get().strip():
                cmd.extend(['--branch', self.branch.get().strip()])
            
            # 日期参数
            if self.use_today.get():
                cmd.append('--today')
            else:
                since = self.since_date.get().strip()
                until = self.until_date.get().strip()
                
                # 验证日期格式
                if since:
                    if not self._validate_date_format(since):
                        self.log(f"错误: 起始日期格式不正确: {since}，应为 YYYY-MM-DD")
                        messagebox.showerror("错误", f"起始日期格式不正确: {since}\n应为 YYYY-MM-DD 格式")
                        return
                    cmd.extend(['--since', since])
                
                if until:
                    if not self._validate_date_format(until):
                        self.log(f"错误: 结束日期格式不正确: {until}，应为 YYYY-MM-DD")
                        messagebox.showerror("错误", f"结束日期格式不正确: {until}\n应为 YYYY-MM-DD 格式")
                        return
                    cmd.extend(['--until', until])
                
                # 如果两个日期都填写了，检查起始日期是否早于结束日期
                if since and until:
                    try:
                        from datetime import datetime
                        since_dt = datetime.strptime(since, '%Y-%m-%d')
                        until_dt = datetime.strptime(until, '%Y-%m-%d')
                        if since_dt > until_dt:
                            self.log(f"警告: 起始日期 {since} 晚于结束日期 {until}")
                            messagebox.showwarning("警告", f"起始日期晚于结束日期\n起始: {since}\n结束: {until}")
                    except:
                        pass
            
            # 输出格式
            output_format = self.output_format.get()
            if output_format == 'daily_report':
                cmd.append('--daily-report')
            
            # 输出文件
            output_file = self.output_file.get().strip()
            actual_output_file = None  # 保存实际使用的输出文件路径
            
            if output_file:
                # 检查是否是目录
                if os.path.isdir(output_file):
                    # 如果是目录，自动生成文件名
                    today = datetime.now().strftime('%Y-%m-%d')
                    branch_suffix = f"_{self.branch.get().strip()}" if self.branch.get().strip() else ""
                    if output_format == 'daily_report':
                        filename = f"{today}_daily_report{branch_suffix}.md"
                    else:
                        filename = f"{today}_commits{branch_suffix}.md"
                    actual_output_file = os.path.join(output_file, filename)
                    self.log(f"输出路径是目录，自动生成文件名: {actual_output_file}")
                    cmd.extend(['--output', actual_output_file])
                else:
                    # 是文件路径，直接使用
                    actual_output_file = output_file
                    cmd.extend(['--output', actual_output_file])
            else:
                # 未指定输出文件，使用默认文件名（当前目录）
                today = datetime.now().strftime('%Y-%m-%d')
                branch_suffix = f"_{self.branch.get().strip()}" if self.branch.get().strip() else ""
                if output_format == 'daily_report':
                    actual_output_file = f"{today}_daily_report{branch_suffix}.md"
                else:
                    actual_output_file = f"{today}_commits{branch_suffix}.md"
                # 不传递 --output 参数，让 git2logs.py 使用默认文件名
            
            self.log(f"执行命令: {' '.join(cmd[:cmd.index('--token')+1])} [令牌已隐藏] ...")
            self.log("=" * 60)
            
            # 执行命令
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # 实时输出日志并检测是否有错误
            found_commits = False
            no_commits_warning = False
            import re
            
            # 批量处理日志，减少界面更新频率
            log_buffer = []
            buffer_size = 5  # 每5行更新一次界面
            
            for line in process.stdout:
                line_text = line.strip()
                log_buffer.append(line_text)
                
                # 检测是否找到提交
                if '找到' in line_text and ('条提交' in line_text or '个项目中找到' in line_text):
                    # 提取数字
                    numbers = re.findall(r'\d+', line_text)
                    if numbers and int(numbers[0]) > 0:
                        found_commits = True
                
                # 检测未找到提交的警告
                if '未找到' in line_text and '提交' in line_text:
                    no_commits_warning = True
                if '未在任何项目中找到' in line_text:
                    no_commits_warning = True
                
                # 批量输出日志
                if len(log_buffer) >= buffer_size or '错误' in line_text or '完成' in line_text or '成功' in line_text:
                    for log_line in log_buffer:
                        self.log_text.insert(tk.END, f"{log_line}\n")
                    self.log_text.see(tk.END)
                    log_buffer = []
                    # 重要消息立即更新界面
                    if '错误' in line_text or '完成' in line_text or '成功' in line_text:
                        self.root.update_idletasks()
            
            # 输出剩余的日志
            for log_line in log_buffer:
                self.log_text.insert(tk.END, f"{log_line}\n")
            self.log_text.see(tk.END)
            
            process.wait()
            
            # 检查是否生成了输出文件
            # 使用实际使用的输出文件路径
            output_file_path = actual_output_file if actual_output_file else None
            
            if output_file_path:
                # 如果文件不存在，尝试添加 .md 扩展名（因为 git2logs.py 会自动添加）
                if not os.path.exists(output_file_path):
                    # 检查是否有扩展名
                    if not os.path.splitext(output_file_path)[1]:
                        # 没有扩展名，尝试添加 .md
                        output_file_path_with_ext = output_file_path + '.md'
                        if os.path.exists(output_file_path_with_ext):
                            output_file_path = output_file_path_with_ext
                            self.log(f"找到文件（已添加扩展名）: {output_file_path}")
            else:
                # 使用默认文件名（当前目录）
                today = datetime.now().strftime('%Y-%m-%d')
                branch_suffix = f"_{self.branch.get().strip()}" if self.branch.get().strip() else ""
                if output_format == 'daily_report':
                    output_file_path = f"{today}_daily_report{branch_suffix}.md"
                else:
                    output_file_path = f"{today}_commits{branch_suffix}.md"
            
            file_exists = os.path.exists(output_file_path) if output_file_path else False
            
            self.log("=" * 60)
            
            if process.returncode == 0:
                if no_commits_warning or not found_commits:
                    self.log("⚠ 未找到提交记录")
                    self.log("可能的原因：")
                    self.log("  1. 指定日期范围内没有提交")
                    self.log("  2. 提交者名称不匹配（请检查 GitLab 中的实际提交者名称）")
                    self.log("  3. 指定的分支不存在或没有权限访问")
                    self.log("  4. 访问令牌权限不足")
                    messagebox.showwarning("警告", 
                        "未找到提交记录。\n\n请检查：\n"
                        "1. 日期范围是否正确\n"
                        "2. 提交者名称是否匹配\n"
                        "3. 分支名称是否正确\n"
                        "4. 访问令牌权限是否足够")
                elif file_exists:
                    self.log("✓ 日志生成成功！")
                    self.log(f"文件已保存: {output_file_path}")
                    
                    # 如果需要生成 HTML 或 PNG
                    if output_format in ['html', 'png']:
                        self.log("\n正在生成 HTML/PNG 格式...")
                        self._generate_html_or_png(output_file_path)
                else:
                    self.log("⚠ 命令执行成功，但未找到生成的文件")
                    self.log(f"预期文件: {output_file_path}")
                    messagebox.showwarning("警告", 
                        f"命令执行成功，但未找到生成的文件。\n\n预期文件: {output_file_path}")
            else:
                self.log("✗ 日志生成失败，请检查错误信息")
                messagebox.showerror("错误", "日志生成失败，请查看执行日志")
        
        except Exception as e:
            self.log(f"错误: {str(e)}")
            messagebox.showerror("错误", f"执行出错: {str(e)}")
        finally:
            # 重新启用按钮
            self.root.after(0, lambda: self.generate_btn.config(state='normal'))
    
    def _generate_html_or_png(self, md_file=None):
        """生成 HTML 或 PNG 格式"""
        try:
            # 先找到生成的 Markdown 文件
            if not md_file:
                output_format = self.output_format.get()
                output_file = self.output_file.get().strip()
                
                if output_file:
                    md_file = output_file
                else:
                    # 使用默认文件名
                    today = datetime.now().strftime('%Y-%m-%d')
                    branch_suffix = f"_{self.branch.get().strip()}" if self.branch.get().strip() else ""
                    if output_format == 'daily_report':
                        md_file = f"{today}_daily_report{branch_suffix}.md"
                    else:
                        md_file = f"{today}_commits{branch_suffix}.md"
            
            # 如果文件不存在，尝试添加 .md 扩展名
            if not os.path.exists(md_file):
                # 尝试添加 .md 扩展名
                if not md_file.endswith('.md'):
                    md_file_with_ext = md_file + '.md'
                    if os.path.exists(md_file_with_ext):
                        md_file = md_file_with_ext
                        self.log(f"找到文件（已添加扩展名）: {md_file}")
                    else:
                        self.log(f"✗ 错误: 找不到文件 {md_file} 或 {md_file_with_ext}")
                        self.log("无法生成 HTML/PNG，因为源 Markdown 文件不存在")
                        self.log("请先确保成功生成了 Markdown 格式的日报")
                        messagebox.showerror("错误", 
                            f"找不到文件: {md_file}\n\n"
                            "无法生成 HTML/PNG，因为源文件不存在。\n"
                            "请先确保成功生成了 Markdown 格式的日报。")
                        return
                else:
                    self.log(f"✗ 错误: 找不到文件 {md_file}")
                    self.log("无法生成 HTML/PNG，因为源 Markdown 文件不存在")
                    self.log("请先确保成功生成了 Markdown 格式的日报")
                    messagebox.showerror("错误", 
                        f"找不到文件: {md_file}\n\n"
                        "无法生成 HTML/PNG，因为源文件不存在。\n"
                        "请先确保成功生成了 Markdown 格式的日报。")
                    return
            
            # 检查是否是打包后的环境
            is_frozen = hasattr(sys, '_MEIPASS')
            
            if is_frozen:
                # 打包后的环境：直接导入模块
                try:
                    from generate_report_image import parse_daily_report, generate_html_report, html_to_image_chrome
                    
                    self.log(f"解析文件: {md_file}")
                    data = parse_daily_report(md_file)
                    
                    base_name = Path(md_file).stem
                    html_file = Path(md_file).parent / f"{base_name}.html"
                    png_file = Path(md_file).parent / f"{base_name}.png"
                    
                    generate_html_report(data, str(html_file))
                    self.log(f"HTML 已生成: {html_file}")
                    
                    if html_to_image_chrome(str(html_file), str(png_file)):
                        self.log(f"✓ PNG 图片已生成: {png_file}")
                    else:
                        self.log("⚠ HTML 转图片失败，但 HTML 文件已生成")
                        self.log("   您可以手动在浏览器中打开 HTML 文件并截图")
                except Exception as e:
                    self.log(f"错误: {str(e)}")
                    import traceback
                    self.log(traceback.format_exc())
            else:
                # 开发环境：使用 subprocess
                generate_script = get_script_path('generate_report_image.py')
                if os.path.exists(generate_script):
                    cmd = [sys.executable, generate_script, md_file]
                else:
                    cmd = ['python3', 'generate_report_image.py', md_file]
                self.log(f"执行: {' '.join(cmd)}")
                
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
                
                for line in process.stdout:
                    self.log(line.strip())
                
                process.wait()
                
                if process.returncode == 0:
                    self.log("✓ HTML/PNG 生成成功！")
                    
                    # 显示生成的文件
                    base_name = Path(md_file).stem
                    html_file = base_name + '.html'
                    png_file = base_name + '.png'
                    
                    if os.path.exists(html_file):
                        self.log(f"  - HTML: {html_file}")
                    if os.path.exists(png_file):
                        self.log(f"  - PNG:  {png_file}")
                else:
                    self.log("✗ HTML/PNG 生成失败")
        
        except Exception as e:
            self.log(f"错误: {str(e)}")

def main():
    root = tk.Tk()
    app = Git2LogsGUI(root)
    root.mainloop()

if __name__ == '__main__':
    main()

