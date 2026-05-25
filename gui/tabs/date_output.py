"""日期和输出标签页 Mixin"""

import customtkinter as ctk
import logging

logger = logging.getLogger(__name__)


class DateOutputMixin:

    def _create_tab2_date_output(self):
        """创建标签页2: 日期和输出"""
        # 优化：透明背景且取消圆角
        tab2 = ctk.CTkFrame(self.content_container, fg_color="transparent", corner_radius=0)
        tab2.pack(fill="both", expand=True, padx=20, pady=20)
        
        content = ctk.CTkFrame(tab2, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=30, pady=10)
        
        row = 0
        
        # 日期范围卡片（抬高卡片 + 细边框，对齐 cc-switch card）
        date_card = ctk.CTkFrame(
            content,
            fg_color=self.bg_card,
            corner_radius=12,
            border_width=1,
            border_color=self.border_color,
        )
        date_card.grid(row=row, column=0, sticky="ew", pady=(0, 20))
        date_card.columnconfigure(1, weight=1)
        self._track_panel_card(date_card)
        content.columnconfigure(0, weight=1)  # 确保内容容器自适应
        
        date_title = ctk.CTkLabel(date_card,
                                text="日期范围",
                                font=self.styles.fonts["subheader"](),
                                text_color=self.text_primary,
                                anchor="w")
        date_title.grid(row=0, column=0, columnspan=2, sticky="w", padx=20, pady=(20, 16))
        self._track_label_primary(date_title)
        
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
        self._track_check_or_radio(today_check)
        
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
        self._track_label_secondary(since_label)
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
        self._track_entry(self.since_entry, 'card')
        
        until_label = ctk.CTkLabel(date_input_frame,
                                 text="结束日期",
                                 font=ctk.CTkFont(size=11),
                                 text_color=self.text_secondary,
                                 anchor="w")
        until_label.grid(row=0, column=1, padx=(0, 8), sticky="w")
        self._track_label_secondary(until_label)
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
        self._track_entry(self.until_entry, 'card')
        
        date_hint = ctk.CTkLabel(date_card,
                               text="提示: 日期格式为 YYYY-MM-DD，例如: 2025-12-12",
                               font=ctk.CTkFont(size=11),
                               text_color=self.text_secondary,
                               anchor="w")
        date_hint.grid(row=2, column=0, columnspan=2, sticky="w", padx=20, pady=(16, 20))
        self._track_label_secondary(date_hint)
        
        self.toggle_date_inputs()
        row += 1
        
        # 输出格式卡片
        format_card = ctk.CTkFrame(
            content,
            fg_color=self.bg_card,
            corner_radius=12,
            border_width=1,
            border_color=self.border_color,
        )
        format_card.grid(row=row, column=0, sticky="ew", pady=(0, 20))
        format_card.columnconfigure(0, weight=1)
        format_card.rowconfigure(1, weight=0)
        self._track_panel_card(format_card)
        
        format_title = ctk.CTkLabel(format_card,
                                  text="输出格式",
                                  font=self.styles.fonts["subheader"](),
                                  text_color=self.text_primary,
                                  anchor="w")
        format_title.grid(row=0, column=0, sticky="w", padx=20, pady=(20, 16))
        self._track_label_primary(format_title)
        
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
        
        fmt_scroll = ctk.CTkScrollableFrame(
            format_card,
            fg_color=self.styles.colors["bg_surface"],
            height=220,
            corner_radius=8,
        )
        fmt_scroll.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 16))
        self._format_options_scroll = fmt_scroll
        try:
            fmt_scroll.configure(
                scrollbar_fg_color=self.styles.colors["bg_card"],
                scrollbar_button_color=self.styles.colors["bg_surface"],
                scrollbar_button_hover_color=self.styles.colors["hover"],
            )
        except Exception:
            logger.debug("配置格式选项滚动条样式失败")
        
        for text, value in format_options:
            rb = ctk.CTkRadioButton(
                fmt_scroll,
                text=text,
                variable=self.output_format,
                value=value,
                font=self.styles.fonts["body"](),
                text_color=self.text_primary,
                fg_color=self.accent_color,
                hover_color=self.styles.colors["accent_hover"],
                bg_color=self.styles.colors["bg_surface"],
                corner_radius=4,
            )
            rb.pack(anchor="w", padx=10, pady=5)
            self._track_format_radio(rb)
        
        row += 1
        
        # 输出设置卡片
        output_card = ctk.CTkFrame(
            content,
            fg_color=self.bg_card,
            corner_radius=12,
            border_width=1,
            border_color=self.border_color,
        )
        output_card.grid(row=row, column=0, sticky="ew", pady=(0, 0))
        output_card.columnconfigure(0, weight=1)
        self._track_panel_card(output_card)
        
        output_title = ctk.CTkLabel(output_card,
                                  text="输出设置",
                                  font=self.styles.fonts["subheader"](),
                                  text_color=self.text_primary,
                                  anchor="w")
        output_title.grid(row=0, column=0, sticky="w", padx=20, pady=(20, 16))
        self._track_label_primary(output_title)
        
        output_label_text = "输出目录" if self.output_format.get() == "all" else "输出文件"
        self.output_label = ctk.CTkLabel(output_card,
                                      text=output_label_text,
                                      font=ctk.CTkFont(size=14, weight="bold"),
                                      text_color=self.text_primary,
                                      anchor="w")
        self.output_label.grid(row=1, column=0, sticky="w", padx=20, pady=(0, 8))
        self._track_label_primary(self.output_label)
        
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
        self._track_entry(output_entry, 'card')
        
        browse_btn = ctk.CTkButton(output_frame,
                                 text="浏览",
                                 width=100,
                                 height=40,
                                 font=ctk.CTkFont(size=13),
                                 corner_radius=8,
                                 fg_color=self.bg_card,
                                 text_color=self.text_primary,
                                 hover_color=self.styles.colors['hover'],
                                 border_width=1,
                                 border_color=self.border_color,
                                 command=self.browse_output_file)
        browse_btn.grid(row=0, column=1)
        self._track_outline_button(browse_btn)
        
        self.output_hint = ctk.CTkLabel(output_card,
                                       text="提示: 批量生成时请选择目录",
                                       font=ctk.CTkFont(size=11),
                                       text_color=self.text_secondary,
                                       anchor="w")
        self.output_hint.grid(row=3, column=0, sticky="w", padx=20, pady=(0, 20))
        self._track_label_secondary(self.output_hint)
        
        # 绑定输出格式变化事件
        def setup_output_format_trace():
            try:
                self.output_format.trace_add('write', self.on_output_format_changed)
            except Exception:
                logger.debug("绑定输出格式变化追踪失败")
        self.root.after(100, setup_output_format_trace)
        
        content.columnconfigure(0, weight=1)
        
        # 添加底部占位符
        ctk.CTkLabel(content, text="", height=50).grid(row=row+1, column=0)
        
        self.tab_frames["日期和输出"] = tab2
        tab2.pack_forget()
