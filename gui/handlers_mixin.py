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

class HandlersMixin:
    def _toggle_theme(self):
        """切换深浅主题"""
        if self._current_theme == "dark":
            self._apply_light_theme()
        else:
            self._apply_dark_theme()

    def _apply_dark_theme(self):
        """应用深色主题（CodexPlusPlus shadcn/ui 深色风格）"""
        self._current_theme = "dark"
        ctk.set_appearance_mode("dark")
        UIStyles.colors.update({
            'bg_main': "#0A0A0F",
            'bg_card': "#0A0A0F",
            'bg_surface': "#1A1A23",
            'text_primary': "#FAFAFA",
            'text_secondary': "#8B8B9E",
            'text_tertiary': "#5A5A6E",
            'border': "#1A1A23",
            'hover': "#141419",
            'success_hover': "#2BA882",
            'error_hover': "#B91C1C",
            'accent_hover': "#2BA882",
            'sidebar_bg': "#0A0A0F",
            'sidebar_active': "#1A1A23",
            'chrome_border_light': "#1A1A23",
            'chrome_border_dark': "#141419",
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
        """应用浅色主题（CodexPlusPlus .light 变量体系）"""
        self._current_theme = "light"
        ctk.set_appearance_mode("light")
        UIStyles.colors.update({
            'bg_main': "#FAFAFA",
            'bg_card': "#FFFFFF",
            'bg_surface': "#F4F4F8",
            'text_primary': "#0A0A0F",
            'text_secondary': "#6B6B7B",
            'text_tertiary': "#9B9BAA",
            'border': "#E4E4EA",
            'hover': "#F4F4F8",
            'success_hover': "#2BA882",
            'error_hover': "#B91C1C",
            'accent_hover': "#2BA882",
            'sidebar_bg': "#FFFFFF",
            'sidebar_active': "#F4F4F8",
            'chrome_border_light': "#E4E4EA",
            'chrome_border_dark': "#DDDDE5",
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
                logger.debug(f"执行验证函数 {fn.__name__} 失败")

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

    def _show_toast(self, message: str, toast_type: str = "success"):
        """显示顶部临时通知（线程安全）"""
        if threading.current_thread() is not threading.main_thread():
            self.root.after(0, lambda: self._show_toast(message, toast_type))
            return

        c = self.styles.colors
        color_map = {
            "success": c['success'],
            "error": c['error'],
            "warning": c['warning'],
        }
        bg = color_map.get(toast_type, c['success'])

        toast = ctk.CTkFrame(self.root, fg_color=bg, corner_radius=self.styles.radius['md'])
        label = ctk.CTkLabel(
            toast, text=f"  {message}  ",
            font=self.styles.fonts['body'](),
            text_color="#FFFFFF",
        )
        label.pack(padx=16, pady=8)
        toast.place(relx=0.5, rely=0, anchor="n", y=10)
        toast.lift()

        def _destroy():
            try:
                toast.place_forget()
                toast.destroy()
            except Exception:
                pass

        self.root.after(3000, _destroy)

    def _on_window_resize(self, event):
        """窗口大小变化时的响应式处理"""
        if event.widget != self.root:
            return
        current_width = self.root.winfo_width()
        if abs(current_width - self._last_resize_width) < 20:
            return
        self._last_resize_width = current_width
        if self._resize_wrap_job is not None:
            try:
                self.root.after_cancel(self._resize_wrap_job)
            except Exception:
                logger.debug("取消延迟布局任务失败")
        self._resize_wrap_job = self.root.after(
            GUIConfig.RESIZE_DEBOUNCE_MS, self._deferred_resize_layout,
        )

    def _deferred_resize_layout(self):
        """防抖：窗口缩放后的文案换行宽度"""
        self._resize_wrap_job = None
        self._sync_responsive_wraplengths()

    def _set_running_state(self, is_running: bool):
        """切换运行状态，同步更新按钮和状态指示"""
        c = self.styles.colors
        if is_running:
            self.generate_btn.configure(text="⏳ 生成中...", state="disabled",
                                       fg_color=c['accent'],
                                       hover_color=c['accent_hover'])
            self._update_status("正在生成日志…", "running")
            if hasattr(self, "_run_progress"):
                try:
                    self._run_progress.pack(side="left", padx=(12, 0), pady=0)
                    self._run_progress.start()
                except Exception:
                    logger.debug("启动进度条动画失败")
        else:
            self.generate_btn.configure(text="▶  开始生成", state="normal",
                                       fg_color=c['success'],
                                       hover_color=c['success_hover'])
            self._update_status("就绪", "success")
            if hasattr(self, "_run_progress"):
                try:
                    self._run_progress.stop()
                    self._run_progress.pack_forget()
                except Exception:
                    logger.debug("停止进度条动画失败")

    _TOPBAR_META = {
        "GitLab配置": ("GitLab 配置", "配置 GitLab 连接参数"),
        "日期和输出": ("日期和输出", "设置日期范围与输出格式"),
        "AI分析": ("AI 分析", "配置 AI 分析引擎"),
        "Excel导出": ("Excel 导出", "生成工时报表"),
    }

    def _switch_tab(self, tab_name):
        """切换标签页"""
        try:
            for name, frame in self.tab_frames.items():
                frame.pack_forget()

            if tab_name in self.tab_frames:
                self.tab_frames[tab_name].pack(fill="x", expand=False, padx=20, pady=20)
                self.current_tab = tab_name

            # 更新 topbar 标题
            if hasattr(self, '_topbar_title'):
                meta = self._TOPBAR_META.get(tab_name, (tab_name, ""))
                self._topbar_title.configure(text=meta[0])
                self._topbar_subtitle.configure(text=meta[1])

            # 更新侧边栏导航项选中态
            if hasattr(self, '_sidebar_btns'):
                self._apply_sidebar_pill_style()
            
            # 立即滚动到顶部（兼容不同版本的 CTkScrollableFrame）
            if hasattr(self, 'scroll_container'):
                try:
                    if hasattr(self.scroll_container, '_parent_canvas'):
                        self.scroll_container._parent_canvas.yview_moveto(0)
                    elif hasattr(self.scroll_container, '_canvas'):
                        self.scroll_container._canvas.yview_moveto(0)
                except Exception:
                    logger.debug("滚动容器滚动到顶部失败")

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
            logger.debug("更新AI模型下拉列表失败")
    
    def toggle_token_visibility(self, entry):
        """切换令牌显示/隐藏"""
        try:
            if entry.cget('show') == '*':
                entry.configure(show='')
            else:
                entry.configure(show='*')
            entry.focus_set()
        except Exception:
            logger.debug("切换令牌可见性失败")
    
    def toggle_key_visibility(self, entry):
        """切换API Key显示/隐藏"""
        try:
            if entry.cget('show') == '*':
                entry.configure(show='')
            else:
                entry.configure(show='*')
            entry.focus_set()
        except Exception:
            logger.debug("切换API Key可见性失败")
    
    def toggle_ai_config(self):
        """切换AI配置区域的显示/隐藏"""
        try:
            if self.ai_enabled.get():
                self.ai_config_frame.grid()
            else:
                self.ai_config_frame.grid_remove()
        except Exception:
            logger.debug("切换AI配置区域显示失败")
    
    def toggle_date_inputs(self):
        """切换日期输入框的启用/禁用状态"""
        try:
            if self.use_today.get():
                self.since_entry.configure(state="disabled")
                self.until_entry.configure(state="disabled")
            else:
                self.since_entry.configure(state="normal")
                self.until_entry.configure(state="normal")
        except Exception:
            logger.debug("切换日期输入框状态失败")
    
    def on_output_format_changed(self, *args):
        """输出格式变化时的回调"""
        try:
            self.output_label.configure(text="输出目录")
            format_value = self.output_format.get()
            if format_value == "all":
                self.output_hint.configure(text="提示: 批量生成时，所有文件将保存到选择的目录")
            else:
                self.output_hint.configure(text="提示: 生成的文件将保存到选择的目录")
        except Exception:
            logger.debug("更新输出格式提示失败")
    
    def browse_output_file(self):
        """浏览输出目录（统一选择文件夹来存放生成的文件）"""
        try:
            directory = filedialog.askdirectory(
                title="选择输出目录（生成的文件将保存到此文件夹）",
                initialdir=self.output_file.get().strip() or os.getcwd()
            )
            if directory:
                self.output_file.set(directory)
        except Exception as e:
            messagebox.showerror("错误", f"选择目录失败: {str(e)}")
    
    def _poll_log_queue(self):
        """定时从队列批量取出日志，降低主线程事件循环压力。"""
        try:
            batch = []
            while len(batch) < GUIConfig.LOG_BATCH_MAX:
                try:
                    batch.append(self._log_queue.get_nowait())
                except queue.Empty:
                    break

            if batch:
                for message, log_type in batch:
                    self._enqueue_log_entry(message, log_type)
                if not self._log_flush_scheduled:
                    self._log_flush_scheduled = True
                    self.root.after(GUIConfig.LOG_FLUSH_DELAY_MS, self._flush_logs)
        except Exception:
            logger.debug("轮询日志队列失败")
        finally:
            self.root.after(GUIConfig.LOG_POLL_INTERVAL_MS, self._poll_log_queue)

    def log(self, message, log_type="info"):
        """添加日志消息。后台线程通过 queue 传递，主线程直接入待写列表。"""
        try:
            if threading.current_thread() is not threading.main_thread():
                self._log_queue.put((message, log_type))
                return

            self._enqueue_log_entry(message, log_type)

            if not self._log_flush_scheduled:
                self._log_flush_scheduled = True
                self.root.after(GUIConfig.LOG_FLUSH_DELAY_MS, self._flush_logs)
        except Exception:
            logger.debug("写入GUI日志失败")

    def _enqueue_log_entry(self, message, log_type):
        """将一条日志格式化后加入待写列表（仅主线程调用）。"""
        filter_level = self._log_filter_level
        if filter_level == "警告+错误" and log_type not in ("warning", "error"):
            return
        if filter_level == "仅错误" and log_type != "error":
            return

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        _PREFIX_MAP = {
            "error": ("[ERROR]", "error"),
            "success": ("[SUCCESS]", "success"),
            "warning": ("[WARNING]", "warning"),
            "info": ("[INFO]", "info"),
        }
        prefix, color_tag = _PREFIX_MAP.get(log_type, ("", "info"))
        log_message = f"{timestamp} - {prefix} {message}\n"

        self._log_pending.append((log_message, timestamp, prefix, color_tag))

    def _flush_logs(self):
        """批量写入所有待处理的日志消息，合并 insert 减少 UI 开销。"""
        self._log_flush_scheduled = False
        if not self._log_pending:
            return
        try:
            if not hasattr(self, "log_text"):
                return

            pending = self._log_pending[:]
            self._log_pending.clear()

            should_scroll = True
            try:
                last_line_num = int(self.log_text.index("end-1c").split('.')[0])
                visible_end_num = int(
                    self.log_text.index("@0,{}".format(self.log_text.winfo_height())).split('.')[0]
                )
                if visible_end_num < last_line_num - 3:
                    should_scroll = False
            except Exception:
                pass

            combined_text = "".join(msg for msg, _, _, _ in pending)
            base_line = int(self.log_text.index("end-1c").split('.')[0])
            self.log_text.insert("end", combined_text)

            for i, (log_message, timestamp, prefix, color_tag) in enumerate(pending):
                line_num = str(base_line + i)
                self.log_text.tag_add("timestamp", f"{line_num}.0", f"{line_num}.{len(timestamp)}")

                if prefix:
                    prefix_start_idx = len(timestamp) + 3
                    self.log_text.tag_add(
                        color_tag,
                        f"{line_num}.{prefix_start_idx}",
                        f"{line_num}.{prefix_start_idx + len(prefix)}",
                    )
                self._log_count += 1

            if self._log_count > GUIConfig.LOG_LINE_LIMIT:
                lines_to_delete = GUIConfig.LOG_TRUNCATE_DELETE
                self.log_text.delete("1.0", f"{lines_to_delete + 1}.0")
                self._log_count -= lines_to_delete
                self._log_omitted_total += lines_to_delete

                separator = f"─── 已省略 {self._log_omitted_total} 条日志 ───\n"
                self.log_text.insert("1.0", separator)
                self.log_text.tag_add("truncated", "1.0", "1.end")
                self._log_count += 1

            if should_scroll:
                self.log_text.see("end")
        except Exception:
            logger.debug("批量写入GUI日志失败")
    
    def clear_logs(self):
        """清空日志"""
        try:
            if threading.current_thread() is not threading.main_thread():
                self.root.after(0, self.clear_logs)
                return

            self.log_text.delete(1.0, "end")
            self._log_count = 0
            self._log_omitted_total = 0
            self._log_pending.clear()
            # 清空队列中残留的消息
            while not self._log_queue.empty():
                try:
                    self._log_queue.get_nowait()
                except queue.Empty:
                    break
            self.log("日志已清空", "info")
        except Exception:
            logger.debug("清空日志文本失败")

        self.log("=" * 60, "info")

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

            # 预收集 GUI 参数（主线程安全读取 Tk 变量）
            self._cached_params = {
                'gitlab_url': self.gitlab_url.get().strip(),
                'token': self.token.get().strip(),
                'author': self.author.get().strip(),
                'repo': self.repo.get().strip(),
                'branch': self.branch.get().strip() or None,
                'use_today': self.use_today.get(),
                'since_date': self.since_date.get().strip(),
                'until_date': self.until_date.get().strip(),
                'output_format': self.output_format.get() if hasattr(self, 'output_format') else "daily_report",
                'output_path': self.output_file.get().strip() if hasattr(self, 'output_file') else '',
                'scan_all': self.scan_all.get() if hasattr(self, 'scan_all') else True,
                'ai_enabled': self.ai_enabled.get() if hasattr(self, 'ai_enabled') else False,
                'ai_service': self.ai_service.get() if hasattr(self, 'ai_service') else 'openai',
                'ai_model': self.ai_model.get() if hasattr(self, 'ai_model') else '',
                'ai_api_key': self.ai_api_key.get().strip() if hasattr(self, 'ai_api_key') else '',
                'ai_base_url': self.ai_base_url.get().strip() if hasattr(self, 'ai_base_url') else '',
            }

            # 使用线程启动，避免阻塞UI
            thread = threading.Thread(target=self._run_git2logs_direct, daemon=True)
            thread.start()

        except Exception as e:
            self.log(f"启动生成任务失败: {str(e)}", "error")
            self._reset_button_state()
    

    def _run_git2logs_direct(self):
        """在后台线程中通过 Git2LogsService 生成报告。"""
        gui_handler = None
        try:
            gui_handler = self._attach_gui_log_handler()
            self.log("=" * 60, "info")

            params = self._cached_params
            report_params = self._build_report_params(params)
            if report_params is None:
                return

            result = self._service.generate_report(
                report_params,
                self._service_log_callback,
            )
            self._apply_generate_report_result(result, params, report_params)

        except GitLabConnectionError as e:
            self.log(f"连接 GitLab 失败: {e}", "error")
            self.root.after(0, lambda: messagebox.showerror("错误", f"连接 GitLab 失败: {e}"))
        except ReportGenerationError as e:
            self.log(f"生成失败: {e}", "error")
            self.root.after(0, lambda: messagebox.showerror("错误", f"生成失败: {e}"))
        except Exception as e:
            self.log(f"生成失败: {str(e)}", "error")
            self.log(traceback.format_exc(), "error")
            self.root.after(0, lambda: messagebox.showerror("错误", f"生成失败: {str(e)}"))
        finally:
            self._detach_gui_log_handler(gui_handler)
            self._reset_button_state()

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
                logger.debug("调度重置运行状态失败")

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

            self._ai_is_running = True
            self._safe_button_operation("ai_analysis_btn", lambda btn: btn.configure(state="disabled", text="分析中..."))

            ai_params = self._build_ai_params()
            thread = threading.Thread(
                target=self._analyze_report_file_direct,
                args=(report_file, ai_params),
            )
            thread.daemon = True
            thread.start()
            
        except Exception as e:
            self.log(f"启动AI分析失败: {str(e)}", "error")
            messagebox.showerror("错误", f"启动AI分析失败: {str(e)}")
    
    def _analyze_report_file_direct(self, report_file, ai_params: AIParams):
        """直接基于报告文件内容进行AI分析"""
        import re

        try:
            with open(report_file, 'r', encoding='utf-8') as f:
                report_content = f.read()

            self.log(f"报告文件读取成功，文件大小: {len(report_content)} 字符", "success")

            if not ai_params.api_key:
                self.log("错误: 请先配置AI服务并输入API Key", "error")
                self.root.after(0, lambda: messagebox.showerror("错误", "请先配置AI服务并输入API Key"))
                return

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

            self.log("", "info")
            self.log("=" * 60, "info")
            self.log(f"提示: AI分析可能需要30秒到2分钟，超时时间: {AIConfig.TIMEOUT}秒", "info")
            self.log(f"AI服务: {ai_params.service}, 模型: {ai_params.model}", "info")
            self.log(f"作者: {author}", "info")
            if since_date and until_date:
                self.log(f"日期范围: {since_date} 至 {until_date}", "info")

            result = self._service.analyze_ai_from_file(
                report_content,
                ai_params,
                log_callback=self._service_log_callback,
            )
            ai_report_content = result['report_content']

            report_dir = os.path.dirname(report_file)
            date_prefix = (
                since_date
                if since_date and until_date and since_date == until_date
                else datetime.now().strftime('%Y-%m-%d')
            )
            ai_report_file = os.path.join(report_dir, f"{date_prefix}_ai_analysis.md")

            with open(ai_report_file, 'w', encoding='utf-8') as f:
                f.write(ai_report_content)

            self.log(f"AI分析报告已保存: {ai_report_file}", "success")
            self.log(f"文件大小: {len(ai_report_content)} 字符", "info")
            self.log("提示: 文件名包含 '_ai_analysis' 表示这是AI分析报告", "info")
            self.log("=" * 60, "info")
            self.log("AI分析完成！", "success")
            self._show_toast("AI 分析完成", "success")

        except ImportError as e:
            self.log(f"AI分析功能不可用: {str(e)}", "error")
            self.log("提示: 请运行 'pip install openai anthropic google-generativeai' 安装AI服务库", "warning")
            self._show_toast("AI 分析失败", "error")
            self.root.after(0, lambda: messagebox.showerror("错误", f"AI分析功能不可用: {str(e)}"))
        except TimeoutError as e:
            self.log(f"AI分析超时: {str(e)}", "error")
            self.log("可能的原因:", "warning")
            self.log("  1. 网络连接较慢或不稳定", "warning")
            self.log("  2. AI服务响应较慢", "warning")
            self.log("  3. 报告文件内容较大，处理时间较长", "warning")
            self.log("建议: 请检查网络连接，或稍后重试", "info")
            self._show_toast("AI 分析超时", "error")
            self.root.after(0, lambda: messagebox.showerror("错误", f"AI分析超时: {str(e)}"))
        except AIAnalysisError as e:
            error_msg = str(e)
            self.log(f"AI分析失败: {error_msg}", "error")
            self._show_toast("AI 分析失败", "error")
            self.root.after(0, lambda: messagebox.showerror("错误", error_msg))
        except Exception as e:
            self.log(f"AI分析失败: {str(e)}", "error")
            self.log(traceback.format_exc(), "error")
            self._show_toast("AI 分析失败", "error")
            self.root.after(0, lambda: messagebox.showerror("错误", f"AI分析失败: {str(e)}"))
        finally:
            self._ai_is_running = False
            self._safe_button_operation("ai_analysis_btn", lambda btn: btn.configure(text="AI 分析"))
            self._reset_button_state("ai_analysis_btn")

    def _perform_ai_analysis(self):
        """执行AI分析（使用待处理的数据）"""
        try:
            if not self._pending_ai_data:
                messagebox.showwarning("提示", "没有可用的数据进行分析")
                return

            self._ai_is_running = True
            self._safe_button_operation("ai_analysis_btn", lambda btn: btn.configure(state="disabled", text="分析中..."))

            ai_params = self._build_ai_params()

            self.log("", "info")
            self.log("=" * 60, "info")
            self.log(f"提示: AI分析可能需要30秒到2分钟，超时时间: {AIConfig.TIMEOUT}秒", "info")
            self.log(f"AI服务: {ai_params.service}, 模型: {ai_params.model}", "info")

            thread = threading.Thread(target=self._perform_ai_analysis_thread, args=(ai_params,))
            thread.daemon = True
            thread.start()
            
        except Exception as e:
            self.log(f"启动AI分析失败: {str(e)}", "error")
            messagebox.showerror("错误", f"启动AI分析失败: {str(e)}")
    
    def _perform_ai_analysis_thread(self, ai_params: AIParams):
        """在后台线程中执行AI分析"""
        try:
            pending = self._pending_ai_data
            result = self._service.analyze_ai(
                pending['all_results'],
                pending['author'],
                ai_params,
                since_date=pending.get('since_date'),
                until_date=pending.get('until_date'),
                log_callback=self._service_log_callback,
            )
            ai_report_content = result['report_content']

            since_date = pending.get('since_date')
            until_date = pending.get('until_date')
            output_dir = pending.get('output_dir', os.getcwd())
            date_prefix = (
                since_date
                if since_date and until_date and since_date == until_date
                else datetime.now().strftime('%Y-%m-%d')
            )
            ai_report_file = os.path.join(output_dir, f"{date_prefix}_ai_analysis.md")

            with open(ai_report_file, 'w', encoding='utf-8') as f:
                f.write(ai_report_content)

            self.log(f"AI分析报告已保存: {ai_report_file}", "success")
            self.log("=" * 60, "info")
            self.log("AI分析完成！", "success")
            self._show_toast("AI 分析完成", "success")

        except AIAnalysisError as e:
            self.log(f"AI分析失败: {str(e)}", "error")
            self._show_toast("AI 分析失败", "error")
            self.root.after(0, lambda: messagebox.showerror("错误", str(e)))
        except Exception as e:
            self.log(f"AI分析失败: {str(e)}", "error")
            self.log(traceback.format_exc(), "error")
            self._show_toast("AI 分析失败", "error")
            self.root.after(0, lambda: messagebox.showerror("错误", f"AI分析失败: {str(e)}"))
        finally:
            self._ai_is_running = False
            self._safe_button_operation("ai_analysis_btn", lambda btn: btn.configure(text="AI 分析"))
            self._reset_button_state("ai_analysis_btn")

    def test_ai_connection(self):
        """测试AI连接"""
        try:
            if not self.ai_api_key.get().strip():
                self.test_status_label.configure(text="请先输入API Key", text_color=self.error_color)
                return
            
            self.test_status_label.configure(text="测试中...", text_color=self.accent_color)
            ai_params = self._build_ai_params()
            thread = threading.Thread(
                target=self._test_ai_connection_thread,
                args=(ai_params,),
            )
            thread.daemon = True
            thread.start()
        except Exception as e:
            self.test_status_label.configure(text=f"测试失败: {str(e)}", text_color=self.error_color)
    
    def _test_ai_connection_thread(self, ai_params: AIParams):
        """在后台线程中测试AI连接"""
        try:
            self._service.test_ai_connection(ai_params)
            if ai_params.service == "gemini" and ai_params.model:
                msg = f"连接成功 (模型 {ai_params.model} 已就绪)"
            else:
                msg = "配置验证通过"
            self.root.after(0, lambda: self.test_status_label.configure(
                text=msg, text_color=self.success_color,
            ))

        except AIAnalysisError as e:
            error_msg = str(e) or "连接失败"
            self.root.after(0, lambda: self.test_status_label.configure(
                text=error_msg[:80], text_color=self.error_color,
            ))
        except Exception as e:
            error_msg = str(e) or "未知错误 (可能是库内部类型错误)"
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

