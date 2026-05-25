"""底部操作栏、主题切换、窗口事件 Mixin"""
import threading
import customtkinter as ctk
import logging

from gui.styles import UIStyles, _ctk_ui_font

logger = logging.getLogger(__name__)


class ActionsMixin:
    """底部操作区域、主题切换、窗口 resize 等方法"""

    def _create_bottom_actions(self):
        """创建底部固定操作按钮区域（固定在窗口底部，不随内容滚动）"""
        separator = ctk.CTkFrame(self.bottom_actions_frame, fg_color=self.styles.colors['border'], height=1, corner_radius=0)
        separator.pack(fill="x", padx=0, pady=0)
        self._bottom_separator = separator

        button_container = ctk.CTkFrame(self.bottom_actions_frame,
                                       fg_color=self.bg_main,
                                       corner_radius=0)
        button_container.pack(fill="x", padx=self.styles.spacing['md'], pady=(self.styles.spacing['sm'], self.styles.spacing['md']))
        self._button_container_ref = button_container

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

        button_frame = ctk.CTkFrame(button_container, fg_color="transparent")
        button_frame.pack(fill="x")
        button_frame.grid_columnconfigure(0, weight=2, uniform="buttons")
        button_frame.grid_columnconfigure(1, weight=1, uniform="buttons")
        button_frame.grid_columnconfigure(2, weight=1, uniform="buttons")

        self.generate_btn = ctk.CTkButton(button_frame,
                                        text="▶  开始生成",
                                        height=44,
                                        font=self.styles.fonts['body_bold'](),
                                        corner_radius=self.styles.radius['md'],
                                        fg_color=self.styles.colors['success'],
                                        text_color="white",
                                        hover_color=self.styles.colors['success_hover'],
                                        command=self.generate_logs)
        self.generate_btn.grid(row=0, column=0, padx=(0, self.styles.spacing['sm']), sticky="ew")

        self.clear_btn = ctk.CTkButton(button_frame,
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
        self.clear_btn.grid(row=0, column=1, padx=(0, self.styles.spacing['sm']), sticky="ew")

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

        self.root.bind('<Configure>', self._on_window_resize)
        self._last_resize_width = self.root.winfo_width()
        self.root.bind_all('<Command-Return>', self._on_keyboard_generate)

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
        UIStyles.colors.update({
            'bg_main': "#1D1D20",
            'bg_card': "#26262A",
            'bg_surface': "#2B2B30",
            'text_primary': "#FAFAFA",
            'text_secondary': "#A1A1AA",
            'text_tertiary': "#71717A",
            'border': "#3D3D44",
            'hover': "#34343A",
            'success_hover': "#059669",
            'error_hover': "#DC2626",
            'accent_hover': "#1E88E5",
            'sidebar_bg': "#1C1C1F",
            'sidebar_active': "#2C2C30",
            'chrome_border_light': "#3D3D44",
            'chrome_border_dark': "#34343A",
        })
        self._sync_color_aliases()
        if hasattr(self, '_theme_btn'):
            self._theme_btn.configure(text="☀ 浅色")
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
        UIStyles.colors.update({
            'bg_main': "#FFFFFF",
            'bg_card': "#FFFFFF",
            'bg_surface': "#F4F4F5",
            'text_primary': "#18181B",
            'text_secondary': "#71717A",
            'text_tertiary': "#A1A1AA",
            'border': "#E4E4E7",
            'hover': "#F4F4F5",
            'success_hover': "#047857",
            'error_hover': "#B91C1C",
            'accent_hover': "#1D4ED8",
            'sidebar_bg': "#F0F0F3",
            'sidebar_active': "#E4E4E9",
            'chrome_border_light': "#EBEBEF",
            'chrome_border_dark': "#E4E4E9",
        })
        self._sync_color_aliases()
        if hasattr(self, '_theme_btn'):
            self._theme_btn.configure(text="🌙 深色")
        self._update_status("浅色主题已启用", "success")
        self._refresh_log_widget_theme()
        self._refresh_chrome_for_theme()
        if self.current_tab:
            self._switch_tab(self.current_tab)
        self.root.after(0, self._refresh_gitlab_validation_colors)

    def _refresh_gitlab_validation_colors(self):
        """主题切换后重新应用校验样式。"""
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
        self.root.after(100, lambda w=current_width: self._adapt_tab_labels(w))
        if self._resize_wrap_job is not None:
            try:
                self.root.after_cancel(self._resize_wrap_job)
            except Exception:
                logger.debug("取消延迟布局任务失败")
        self._resize_wrap_job = self.root.after(150, self._deferred_resize_layout)

    def _deferred_resize_layout(self):
        """防抖：窗口缩放后的文案换行宽度"""
        self._resize_wrap_job = None
        self._sync_responsive_wraplengths()

    def _adapt_tab_labels(self, _width):
        """侧边栏模式下标签已固定为短文字，无需响应式调整"""
        pass

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

    def _switch_tab(self, tab_name):
        """切换标签页（Segmented Control 风格）"""
        try:
            for name, frame in self.tab_frames.items():
                frame.pack_forget()

            if tab_name in self.tab_frames:
                self.tab_frames[tab_name].pack(fill="x", expand=False, padx=20, pady=20)
                self.current_tab = tab_name

            if hasattr(self, '_sidebar_btns'):
                for name, tpl in self._sidebar_btns.items():
                    if len(tpl) < 3:
                        continue
                    item_frame, _icon_lbl, text_lbl = tpl[0], tpl[1], tpl[2]
                    item_frame.configure(fg_color="transparent")
                    if name == tab_name:
                        text_lbl.configure(text_color=self.styles.colors['accent'])
                    else:
                        text_lbl.configure(text_color=self.styles.colors['text_secondary'])
                self._apply_sidebar_icon_images()
                self._apply_sidebar_pill_style()
        except Exception:
            logger.debug(f"切换标签页到 {tab_name} 失败")

    def _on_keyboard_generate(self, event):
        """⌘+Return 触发生成。"""
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

    def _update_ai_models(self, *args):
        """AI 服务切换时更新模型列表"""
        try:
            service = self.ai_provider.get()
            if service == "openai":
                models = [
                    "gpt-4o", "gpt-4o-mini",
                    "gpt-4-turbo", "gpt-4",
                    "gpt-3.5-turbo"
                ]
                if self.ai_model.get() not in models:
                    self.ai_model.set("gpt-4o-mini")
            elif service == "anthropic":
                models = ["claude-3-5-sonnet-20241022", "claude-3-opus-20240229", "claude-3-sonnet-20240229"]
                if self.ai_model.get() not in models:
                    self.ai_model.set("claude-3-5-sonnet-20241022")
            elif service == "gemini":
                models = [
                    "gemini-3-flash-preview",
                    "gemini-2.5-flash-preview-05-20",
                    "gemini-2.0-flash",
                    "gemini-1.5-pro",
                    "gemini-1.5-flash"
                ]
                if self.ai_model.get() not in models:
                    self.ai_model.set("gemini-3-flash-preview")
            elif service == "doubao":
                models = [
                    "doubao-pro-128k",
                    "doubao-pro-32k",
                    "doubao-lite-128k"
                ]
                if self.ai_model.get() not in models:
                    self.ai_model.set("doubao-pro-128k")
            elif service == "deepseek":
                models = [
                    "deepseek-chat",
                    "deepseek-coder",
                    "deepseek-reasoner"
                ]
                if self.ai_model.get() not in models:
                    self.ai_model.set("deepseek-chat")

            if hasattr(self, 'ai_model_dropdown'):
                self.ai_model_dropdown.configure(values=models)
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
        """浏览输出目录"""
        from tkinter import filedialog
        import os
        try:
            directory = filedialog.askdirectory(
                title="选择输出目录（生成的文件将保存到此文件夹）",
                initialdir=self.output_file.get().strip() or os.getcwd()
            )
            if directory:
                self.output_file.set(directory)
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("错误", f"选择目录失败: {str(e)}")
