"""
GUI 应用主入口 — 通过 Mixin 多重继承组装完整的 Git2LogsGUI 类。

原始单文件 git2logs_gui_ctk.py（3885 行）按功能拆分为：
- gui/styles.py       — UIStyles、字体、侧栏图标绘制
- gui/theme.py        — 主题管理（控件追踪、深浅切换、内容同步）
- gui/actions.py      — 底部操作栏、主题切换、窗口事件
- gui/tabs/           — 各标签页 UI 构建
- gui/widgets/        — 侧边栏、日志面板、Header 等组件
"""
import sys
import os
import queue
import threading

import customtkinter as ctk
from tkinter import messagebox

import logging

from config import AIConfig, GUIConfig, ReportConfig
from gui.styles import (
    UIStyles, _ctk_ui_font, _pil_sidebar_icon, _hex_to_rgb,
    _SIDEBAR_TAB_GLYPHS, _resolve_monospace_font, resource_path, get_script_path,
)
from gui.theme import ThemeMixin
from gui.actions import ActionsMixin
from gui.tabs.gitlab_config import GitLabConfigMixin
from gui.tabs.date_output import DateOutputMixin
from gui.tabs.ai_analysis import AIAnalysisMixin
from gui.tabs.excel_export import ExcelExportMixin
from gui.widgets.sidebar import SidebarMixin
from gui.widgets.log_panel import LogPanelMixin
from gui.widgets.header import HeaderMixin

logger = logging.getLogger(__name__)

CTK_AVAILABLE = True


class Git2LogsGUI(
    HeaderMixin,
    SidebarMixin,
    LogPanelMixin,
    GitLabConfigMixin,
    DateOutputMixin,
    AIAnalysisMixin,
    ExcelExportMixin,
    ActionsMixin,
    ThemeMixin,
):
    """MIZUKI-GITLAB工具箱 GUI 主类（由各 Mixin 组合而成）"""

    def __init__(self, root):
        try:
            self.styles = UIStyles
            self.root = root
            self.root.title("MIZUKI-GITLAB工具箱")
            self.root.resizable(True, True)

            # 共享状态初始化
            self._pending_ai_data = None
            self._log_count = 0
            self._log_queue = queue.Queue()
            self._is_running = False
            self._ai_is_running = False
            self._work_hours_data = None
            self._project_checkboxes: dict = {}
            self._validation_labels: dict = {}
            self._log_collapsed = False
            self._log_filter_level = "全部"
            self._log_pending = []
            self._log_flush_scheduled = False
            self._log_omitted_total = 0
            self._current_theme = "dark"
            self._theme_panels_main: list = []
            self._theme_panels_card: list = []
            self._theme_entries_typed: list = []
            self._theme_comboboxes: list = []
            self._theme_outline_buttons: list = []
            self._theme_labels_primary: list = []
            self._theme_labels_secondary: list = []
            self._theme_check_radio: list = []
            self._theme_radio_buttons: list = []
            self._responsive_wrap_labels: list = []
            self._resize_wrap_job = None
            self._sidebar_icon_by_tab: dict = {}
            self._sidebar_icon_assets: list = []
            self._sidebar_icon_pills: list = []
            self._sidebar_pill_by_tab: dict = {}
            self._sidebar_icon_px = 22
            self._sidebar_icons_text_fallback = False

            # 配置 CustomTkinter 主题
            ctk.set_appearance_mode("dark")

            # 颜色别名（兼容旧代码）
            c = self.styles.colors
            self.bg_main = c['bg_main']
            self.bg_card = c['bg_card']
            self.text_primary = c['text_primary']
            self.text_secondary = c['text_secondary']
            self.border_color = c['border']
            self.accent_color = c['accent']
            self.success_color = c['success']
            self.error_color = c['error']

            # 主容器
            main_container = ctk.CTkFrame(root, fg_color=self.bg_main, corner_radius=0)
            main_container.pack(fill="both", expand=True, padx=0, pady=0)
            self._main_container = main_container

            # 顶部 Header 栏
            self._create_header(main_container)

            root.update_idletasks()
            root.update()

            # 存储标签页引用
            self.tab_frames = {}
            self.current_tab = None
            self.tab_buttons = []

            # 布局：body（侧栏 + 内容区 + 日志）+ 底部操作
            body = ctk.CTkFrame(main_container, fg_color=self.bg_main, corner_radius=0)
            body.pack(fill="both", expand=True)
            self._body_frame = body

            # 侧栏容器
            self._sidebar_frame = ctk.CTkFrame(body,
                                              fg_color=self.styles.colors['sidebar_bg'],
                                              width=56, corner_radius=0)
            self._sidebar_frame.pack(side="left", fill="y")
            self._sidebar_frame.pack_propagate(False)

            # 右侧面板（内容 + 日志）
            right_panel = ctk.CTkFrame(body, fg_color=self.bg_main, corner_radius=0)
            right_panel.pack(side="left", fill="both", expand=True)
            self._right_panel = right_panel

            # 内容滚动区域
            self.scroll_container = ctk.CTkScrollableFrame(right_panel,
                                                          fg_color=self.bg_main,
                                                          corner_radius=0)
            self.scroll_container.pack(fill="both", expand=True)
            self.content_container = self.scroll_container
            try:
                self.scroll_container.configure(
                    scrollbar_button_color=self.styles.colors['bg_main'],
                    scrollbar_button_hover_color=self.styles.colors['bg_main'])
            except Exception:
                logger.debug("配置滚动容器滚动条颜色失败")

            # 日志区域
            self._create_log_area(right_panel)

            # 底部操作栏
            self.bottom_actions_frame = ctk.CTkFrame(main_container,
                                                    fg_color=self.bg_main,
                                                    corner_radius=0)
            self.bottom_actions_frame.pack(fill="x", side="bottom")

            # 延迟并批量创建标签页内容
            def delayed_init():
                try:
                    self._create_tab1_gitlab_config()
                    self._create_tab2_date_output()
                    self._create_tab3_ai_analysis()
                    self._create_tab4_excel_export()
                    self._create_bottom_actions()
                    self._create_sidebar(self._sidebar_frame)

                    self._switch_tab("GitLab配置")
                    self.root.update_idletasks()

                    self._bind_form_validation()
                    self._enhance_form_interaction()

                    # 启动日志队列轮询
                    self._poll_log_queue()

                    self.log("欢迎使用 MIZUKI-GITLAB工具箱！", "info")
                    self.log("请填写参数后点击'▶ 生成日志'按钮。", "info")
                    self.root.after(120, self._sync_responsive_wraplengths)
                except Exception as e:
                    import traceback
                    self.log(f"初始化错误: {str(e)}", "error")
                    self.log(traceback.format_exc(), "error")

            root.after(10, delayed_init)

        except Exception as e:
            import traceback
            error_msg = f"界面初始化失败: {str(e)}\n\n{traceback.format_exc()}"
            print(error_msg)
            try:
                messagebox.showerror("初始化错误", error_msg)
            except Exception:
                logger.debug("显示初始化错误对话框失败")
            raise

    # ── 业务逻辑方法保留在主类（涉及跨模块大量交互） ──
    # generate_logs, _run_git2logs_direct, _collect_report_params 等
    # 暂保留在原始 git2logs_gui_ctk.py 中，后续按需进一步拆分

    def generate_logs(self):
        """生成日志的主函数（占位 — 实际逻辑在旧文件中）"""
        raise NotImplementedError("业务逻辑应从原始文件继承")


def main():
    """主函数 - 优化启动速度，立即显示窗口"""
    root = None
    try:
        root = ctk.CTk()
        root.title("MIZUKI-GITLAB工具箱")
        root.minsize(520, 700)
        root.resizable(True, True)

        width = 600
        height = 900
        x = (root.winfo_screenwidth() // 2) - (width // 2)
        y = (root.winfo_screenheight() // 2) - (height // 2)
        root.geometry(f'{width}x{height}+{x}+{y}')

        root.deiconify()
        root.lift()
        root.focus_force()
        root.update_idletasks()
        root.update()

        def create_app():
            try:
                app = Git2LogsGUI(root)
            except Exception as e:
                import traceback
                error_msg = f"界面初始化失败: {str(e)}\n\n{traceback.format_exc()}"
                print(error_msg)
                messagebox.showerror("初始化错误", error_msg)

        root.after(1, create_app)
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
            logger.debug("显示启动错误对话框失败")
        if root:
            root.destroy()
        raise
