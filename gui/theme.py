"""主题管理 Mixin — 深浅切换、控件追踪、内容主题同步"""
import customtkinter as ctk
import logging

logger = logging.getLogger(__name__)


class ThemeMixin:
    """主题管理相关方法的 Mixin（含控件追踪、深浅切换、响应式布局）"""

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
        self._rebuild_sidebar_icons()
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
