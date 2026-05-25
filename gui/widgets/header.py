"""顶部标题栏组件 Mixin"""

import customtkinter as ctk
import logging

logger = logging.getLogger(__name__)


class HeaderMixin:

    def _create_header(self, parent):
        """创建顶部 Header 栏（品牌名 + 版本信息）"""
        header = ctk.CTkFrame(parent, fg_color=self.styles.colors["bg_main"], height=48, corner_radius=0)
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
                     text="MIZUKI TOOLBOX",
                     font=_ctk_ui_font(15, "bold"),
                     text_color=self.styles.colors['text_primary'],
                     fg_color="transparent")
        self._header_brand_lbl.pack(side="left", pady=13)

        # 右：副标题
        right = ctk.CTkFrame(inner, fg_color="transparent")
        right.pack(side="right", fill="y")
        self._header_sub_lbl = ctk.CTkLabel(right,
                     text="GitLab 提交分析工具  v2.0",
                     font=_ctk_ui_font(11),
                     text_color=self.styles.colors['text_tertiary'],
                     fg_color="transparent")
        self._header_sub_lbl.pack(side="right", pady=16)
