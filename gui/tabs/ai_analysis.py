"""AI 分析标签页 Mixin"""

import customtkinter as ctk
import logging

logger = logging.getLogger(__name__)


class AIAnalysisMixin:

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
        self._track_check_or_radio(ai_enable_check)
        row += 1
        
        # AI配置区域（默认隐藏）
        self.ai_config_frame = ctk.CTkFrame(
            content,
            fg_color=self.bg_card,
            corner_radius=12,
            border_width=1,
            border_color=self.border_color,
        )
        self.ai_config_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 0))
        self.ai_config_frame.columnconfigure(1, weight=1)
        self._track_panel_card(self.ai_config_frame)
        
        ai_title = ctk.CTkLabel(self.ai_config_frame,
                              text="AI配置",
                              font=ctk.CTkFont(size=15, weight="bold"),
                              text_color=self.text_primary,
                              anchor="w")
        ai_title.grid(row=0, column=0, columnspan=2, sticky="w", padx=20, pady=(20, 20))
        self._track_label_primary(ai_title)
        
        config_row = 1
        
        # AI服务选择
        service_label = ctk.CTkLabel(self.ai_config_frame,
                                    text="AI服务",
                                    font=ctk.CTkFont(size=14, weight="bold"),
                                    text_color=self.text_primary,
                                    anchor="w")
        service_label.grid(row=config_row, column=0, sticky="w", padx=20, pady=(0, 8))
        self._track_label_primary(service_label)
        
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
                                          button_hover_color=self.styles.colors['hover'],
                                          dropdown_fg_color=self.bg_card,
                                          dropdown_text_color=self.text_primary,
                                          dropdown_hover_color=self.styles.colors['hover'],
                                          command=self._update_ai_models)
        ai_service_combo.grid(row=config_row, column=1, sticky="ew", padx=(0, 20), pady=(0, 24))
        self._track_combo(ai_service_combo)
        config_row += 1
        
        # 模型选择
        model_label = ctk.CTkLabel(self.ai_config_frame,
                                 text="模型",
                                 font=ctk.CTkFont(size=14, weight="bold"),
                                 text_color=self.text_primary,
                                 anchor="w")
        model_label.grid(row=config_row, column=0, sticky="w", padx=20, pady=(0, 8))
        self._track_label_primary(model_label)
        
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
                                             button_hover_color=self.styles.colors['hover'],
                                             dropdown_fg_color=self.bg_card,
                                             dropdown_text_color=self.text_primary,
                                             dropdown_hover_color=self.styles.colors['hover'])
        self.ai_model_combo.grid(row=config_row, column=1, sticky="ew", padx=(0, 20), pady=(0, 24))
        self._track_combo(self.ai_model_combo)
        config_row += 1
        
        # API Key
        key_label = ctk.CTkLabel(self.ai_config_frame,
                               text="API Key",
                               font=ctk.CTkFont(size=14, weight="bold"),
                               text_color=self.text_primary,
                               anchor="w")
        key_label.grid(row=config_row, column=0, sticky="w", padx=20, pady=(0, 8))
        self._track_label_primary(key_label)
        
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
        self._track_entry(ai_key_entry, 'card')
        
        key_show_btn = ctk.CTkButton(key_frame,
                                    text="显示",
                                    width=80,
                                    height=40,
                                    font=ctk.CTkFont(size=13),
                                    corner_radius=8,
                                    fg_color=self.bg_card,
                                    text_color=self.text_primary,
                                    hover_color=self.styles.colors['hover'],
                                    border_width=1,
                                    border_color=self.border_color,
                                    command=lambda: self.toggle_key_visibility(ai_key_entry))
        key_show_btn.grid(row=0, column=1)
        self._track_outline_button(key_show_btn)
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
                               hover_color=self.styles.colors['hover'],
                               border_width=1,
                               border_color=self.border_color,
                               command=self.test_ai_connection)
        test_btn.pack(side="left", padx=(0, 12))
        self._track_outline_button(test_btn)
        
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
