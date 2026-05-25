"""侧边栏导航组件 Mixin"""
import customtkinter as ctk
import logging

from gui.styles import _ctk_ui_font, _pil_sidebar_icon, _SIDEBAR_TAB_GLYPHS

logger = logging.getLogger(__name__)


class SidebarMixin:
    """侧边栏创建与图标管理方法"""

    def _create_sidebar(self, parent):
        """创建左侧导航：单色线框图标 + 圆角胶囊底。"""
        nav_items = [
            ("GitLab配置", "gear", "配置"),
            ("日期和输出", "calendar", "日期"),
            ("AI分析", "chip", "AI"),
            ("Excel导出", "chart", "Excel"),
        ]

        self._sidebar_icon_pills.clear()
        self._sidebar_pill_by_tab.clear()

        ctk.CTkLabel(parent, text="", height=12, fg_color="transparent").pack()

        for tab_name, kind, label in nav_items:
            item_frame = ctk.CTkFrame(parent,
                                      fg_color="transparent",
                                      corner_radius=self.styles.radius['md'])
            item_frame.pack(fill="x", padx=8, pady=3)

            icon_pill = ctk.CTkFrame(
                item_frame,
                fg_color=self.styles.colors['bg_card'],
                corner_radius=10,
                border_width=1,
                border_color=self.styles.colors['border'],
                width=44,
                height=36,
            )
            icon_pill.pack(pady=(8, 2))
            icon_pill.pack_propagate(False)
            self._sidebar_icon_pills.append(icon_pill)
            self._sidebar_pill_by_tab[tab_name] = icon_pill

            icon_lbl = ctk.CTkLabel(icon_pill, text="", fg_color="transparent")
            icon_lbl.pack(expand=True)

            text_lbl = ctk.CTkLabel(item_frame,
                                    text=label,
                                    font=_ctk_ui_font(10),
                                    text_color=self.styles.colors['text_secondary'],
                                    fg_color="transparent")
            text_lbl.pack(pady=(0, 10))

            for w in (item_frame, icon_pill, icon_lbl, text_lbl):
                w.bind("<Button-1>", lambda e, n=tab_name: self._switch_tab(n))
                w.bind("<Enter>", lambda e, n=tab_name: self._on_sidebar_enter_pill(n))
                w.bind("<Leave>", lambda e, n=tab_name: self._on_sidebar_leave_pill(n))

            self._sidebar_btns[tab_name] = (item_frame, icon_lbl, text_lbl, kind)
            self.tab_buttons.append((tab_name, item_frame))

        self._rebuild_sidebar_icons()
        self._apply_sidebar_pill_style()

        ctk.CTkFrame(parent, fg_color=self.styles.colors['border'], height=1, corner_radius=0).pack(
            side="bottom", fill="x", padx=8, pady=4)

    def _apply_sidebar_pill_style(self, tab_name=None):
        """侧栏图标胶囊：选中为细描边 + 微提亮的表面。"""
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
                    fg_color=c["bg_surface"] if sel else c["bg_card"],
                    border_color=c["accent"] if sel else c["border"],
                    border_width=2 if sel else 1,
                )
            except Exception:
                logger.debug("配置侧栏胶囊样式失败")

    def _on_sidebar_enter_pill(self, tab_name):
        if getattr(self, "current_tab", None) == tab_name:
            return
        pill = self._sidebar_pill_by_tab.get(tab_name)
        if not pill:
            return
        try:
            pill.configure(border_color=self.styles.colors["accent_hover"], border_width=2)
        except Exception:
            logger.debug("配置侧栏悬停胶囊样式失败")

    def _on_sidebar_leave_pill(self, tab_name):
        self._apply_sidebar_pill_style(tab_name)

    def _apply_sidebar_text_glyphs(self):
        """无 Pillow 时用单字占位。"""
        ct = getattr(self, "current_tab", None)
        c = self.styles.colors
        glyph_font = _ctk_ui_font(12, "bold")
        for name, tpl in self._sidebar_btns.items():
            if len(tpl) < 4:
                continue
            icon_lbl = tpl[1]
            g = _SIDEBAR_TAB_GLYPHS.get(name, "·")
            col = c["accent"] if name == ct else c["text_secondary"]
            try:
                icon_lbl.configure(text=g, text_color=col, font=glyph_font, image=None)
            except TypeError:
                try:
                    icon_lbl.configure(text=g, text_color=col, font=glyph_font)
                except Exception:
                    logger.debug("配置侧栏图标文字(降级)失败")
            except Exception:
                logger.debug("配置侧栏图标文字失败")

    def _apply_sidebar_icon_images(self):
        """按 current_tab 切换侧栏图标（灰 / 强调色）。"""
        if getattr(self, "_sidebar_icons_text_fallback", False):
            self._apply_sidebar_text_glyphs()
            return
        ct = getattr(self, "current_tab", None)
        if not getattr(self, "_sidebar_icon_by_tab", None):
            return
        for name, tpl in self._sidebar_btns.items():
            if len(tpl) < 4:
                continue
            icon_lbl = tpl[1]
            pair = self._sidebar_icon_by_tab.get(name)
            if not pair:
                continue
            img_m, img_a = pair
            try:
                icon_lbl.configure(image=img_a if name == ct else img_m, text="")
            except Exception:
                logger.debug("配置侧栏图标图片失败")

    def _rebuild_sidebar_icons(self):
        """按当前主题重绘侧栏矢量图标（PIL → CTkImage）。"""
        if not getattr(self, "_sidebar_btns", None):
            return
        try:
            px = getattr(self, "_sidebar_icon_px", 22)
            pil_sz = max(26, px + 4)
            c = self.styles.colors
            self._sidebar_icon_by_tab = {}
            self._sidebar_icon_assets = []
            for name, tpl in self._sidebar_btns.items():
                if len(tpl) < 4:
                    continue
                _frame, icon_lbl, _text, kind = tpl[:4]
                pil_m = _pil_sidebar_icon(kind, c["text_secondary"], size=pil_sz)
                pil_a = _pil_sidebar_icon(kind, c["accent"], size=pil_sz)
                img_m = ctk.CTkImage(light_image=pil_m, dark_image=pil_m, size=(px, px))
                img_a = ctk.CTkImage(light_image=pil_a, dark_image=pil_a, size=(px, px))
                self._sidebar_icon_assets.extend([img_m, img_a])
                self._sidebar_icon_by_tab[name] = (img_m, img_a)
            self._sidebar_icons_text_fallback = False
            self._apply_sidebar_icon_images()
        except Exception:
            self._sidebar_icons_text_fallback = True
            self._sidebar_icon_by_tab = {}
            self._sidebar_icon_assets = []
            self._apply_sidebar_text_glyphs()
