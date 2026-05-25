"""GitLab 配置标签页 Mixin"""
import customtkinter as ctk
import logging

logger = logging.getLogger(__name__)


class GitLabConfigMixin:
    """GitLab 配置标签页创建及表单验证方法"""

    def _create_tab1_gitlab_config(self):
        """创建标签页1: GitLab配置"""
        tab1 = ctk.CTkFrame(self.content_container, fg_color="transparent", corner_radius=0)
        tab1.pack(fill="both", expand=True, padx=self.styles.spacing['md'], pady=self.styles.spacing['md'])

        content = ctk.CTkFrame(tab1, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=self.styles.spacing['lg'], pady=self.styles.spacing['sm'])
        content.columnconfigure(0, weight=1)

        row = 0

        # GitLab URL
        url_label = ctk.CTkLabel(content, text="GitLab URL",
                                font=ctk.CTkFont(size=14, weight="bold"),
                                text_color=self.text_primary, anchor="w")
        url_label.grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 8))
        self._track_label_primary(url_label)
        row += 1

        self.gitlab_url = ctk.StringVar()
        gitlab_entry = ctk.CTkEntry(content,
                                  textvariable=self.gitlab_url,
                                  placeholder_text="https://gitlab.com 或 http://gitlab.yourcompany.com",
                                  font=ctk.CTkFont(size=13), height=40, corner_radius=8,
                                  border_width=1, border_color=self.border_color,
                                  fg_color=self.bg_main, text_color=self.text_primary)
        gitlab_entry.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        self._track_entry(gitlab_entry, 'main')
        row += 1
        self._validation_labels['gitlab_url'] = ctk.CTkLabel(
            content, text="", font=self.styles.fonts['caption'](),
            text_color=self.styles.colors['text_secondary'], anchor="w")
        self._validation_labels['gitlab_url'].grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 16))
        row += 1

        # 仓库地址
        repo_label = ctk.CTkLabel(content, text="仓库地址",
                                 font=ctk.CTkFont(size=14, weight="bold"),
                                 text_color=self.text_primary, anchor="w")
        repo_label.grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 8))
        self._track_label_primary(repo_label)
        row += 1

        self.repo = ctk.StringVar()
        repo_entry = ctk.CTkEntry(content,
                                 textvariable=self.repo,
                                 font=ctk.CTkFont(size=13), height=40, corner_radius=8,
                                 border_width=1, border_color=self.border_color,
                                 fg_color=self.bg_main, text_color=self.text_primary)
        repo_entry.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        self._track_entry(repo_entry, 'main')
        row += 1
        self._validation_labels['repo'] = ctk.CTkLabel(
            content, text="", font=self.styles.fonts['caption'](),
            text_color=self.styles.colors['text_secondary'], anchor="w")
        self._validation_labels['repo'].grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 16))
        row += 1

        # 扫描所有项目选项
        self.scan_all = ctk.BooleanVar(value=False)
        scan_check = ctk.CTkCheckBox(content,
                                    text="自动扫描所有项目（不填仓库地址时启用）",
                                    variable=self.scan_all,
                                    font=ctk.CTkFont(size=13),
                                    text_color=self.text_primary,
                                    fg_color=self.accent_color, corner_radius=4)
        scan_check.grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 24))
        self._track_check_or_radio(scan_check)
        row += 1

        # 分支
        branch_label = ctk.CTkLabel(content, text="分支",
                                  font=ctk.CTkFont(size=14, weight="bold"),
                                  text_color=self.text_primary, anchor="w")
        branch_label.grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 8))
        self._track_label_primary(branch_label)
        row += 1

        self.branch = ctk.StringVar()
        branch_entry = ctk.CTkEntry(content,
                                   textvariable=self.branch,
                                   font=ctk.CTkFont(size=13), height=40, corner_radius=8,
                                   border_width=1, border_color=self.border_color,
                                   fg_color=self.bg_main, text_color=self.text_primary)
        branch_entry.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 24))
        self._track_entry(branch_entry, 'main')
        row += 1

        # 提交者
        author_label = ctk.CTkLabel(content, text="提交者",
                                   font=ctk.CTkFont(size=14, weight="bold"),
                                   text_color=self.text_primary, anchor="w")
        author_label.grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 8))
        self._track_label_primary(author_label)
        row += 1

        self.author = ctk.StringVar(value="MIZUKI")
        author_entry = ctk.CTkEntry(content,
                                   textvariable=self.author,
                                   font=ctk.CTkFont(size=13), height=40, corner_radius=8,
                                   border_width=1, border_color=self.border_color,
                                   fg_color=self.bg_main, text_color=self.text_primary)
        author_entry.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        self._track_entry(author_entry, 'main')
        row += 1
        self._validation_labels['author'] = ctk.CTkLabel(
            content, text="", font=self.styles.fonts['caption'](),
            text_color=self.styles.colors['text_secondary'], anchor="w")
        self._validation_labels['author'].grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 16))
        row += 1

        # 访问令牌
        token_label = ctk.CTkLabel(content, text="访问令牌",
                                 font=ctk.CTkFont(size=14, weight="bold"),
                                 text_color=self.text_primary, anchor="w")
        token_label.grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 8))
        self._track_label_primary(token_label)
        row += 1

        self.token = ctk.StringVar()
        token_frame = ctk.CTkFrame(content, fg_color="transparent")
        token_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        token_frame.columnconfigure(0, weight=1)

        token_entry = ctk.CTkEntry(token_frame,
                                  textvariable=self.token, show="*",
                                  font=ctk.CTkFont(size=13), height=40, corner_radius=8,
                                  border_width=1, border_color=self.border_color,
                                  fg_color=self.bg_main, text_color=self.text_primary)
        token_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._track_entry(token_entry, 'main')

        show_btn = ctk.CTkButton(token_frame, text="显示", width=80, height=40,
                                font=ctk.CTkFont(size=13), corner_radius=8,
                                fg_color=self.bg_card, text_color=self.text_primary,
                                hover_color=self.styles.colors['hover'],
                                border_width=1, border_color=self.border_color,
                                command=lambda: self.toggle_token_visibility(token_entry))
        show_btn.grid(row=0, column=1)
        self._track_outline_button(show_btn)
        row += 1
        self._validation_labels['token'] = ctk.CTkLabel(
            content, text="", font=self.styles.fonts['caption'](),
            text_color=self.styles.colors['text_secondary'], anchor="w")
        self._validation_labels['token'].grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 16))
        row += 1

        # 使用提示卡片
        hint_frame = ctk.CTkFrame(content, fg_color=self.bg_main, corner_radius=8,
                                 border_width=1, border_color=self.border_color)
        hint_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self._tab1_hint_frame = hint_frame

        hint_title = ctk.CTkLabel(hint_frame, text="使用提示",
                                font=ctk.CTkFont(size=13, weight="bold"),
                                text_color=self.text_primary, anchor="w")
        hint_title.pack(anchor="w", padx=16, pady=(16, 8))
        self._track_label_primary(hint_title)

        hint_text = "• GitLab URL 是您的GitLab实例地址\n• 仓库地址留空时，勾选'自动扫描所有项目'可扫描所有项目\n• 访问令牌用于身份验证，可在GitLab设置中生成"
        hint_label = ctk.CTkLabel(hint_frame, text=hint_text, font=ctk.CTkFont(size=12),
                                 text_color=self.text_secondary, justify="left", anchor="w")
        hint_label.pack(anchor="w", padx=16, pady=(0, 16))
        self._track_label_secondary(hint_label)

        ctk.CTkLabel(content, text="", height=50).grid(row=row + 1, column=0)

        self.tab_frames["GitLab配置"] = tab1
        tab1.pack_forget()

    def _bind_form_validation(self):
        """绑定表单验证事件"""
        self.gitlab_url.trace_add('write', self._validate_gitlab_url)
        self.repo.trace_add('write', self._validate_repo_url)
        self.author.trace_add('write', self._validate_author)
        self.token.trace_add('write', self._validate_token)
        self.scan_all.trace_add('write', lambda *args: self._on_scan_all_toggle())

    def _validate_gitlab_url(self, *args):
        """实时验证 GitLab URL 格式"""
        url = self.gitlab_url.get().strip()
        status, message = self._validate_url_logic(url, is_gitlab=True)
        self._update_field_status('gitlab_url', status, message)

    def _validate_repo_url(self, *args):
        """实时验证仓库 URL 格式"""
        url = self.repo.get().strip()
        if not url:
            if self.scan_all.get():
                self._update_field_status('repo', 'success', "留空表示扫描所有项目")
            else:
                self._update_field_status('repo', 'warning', "请输入仓库地址或启用扫描所有项目")
            return
        status, message = self._validate_url_logic(url, is_gitlab=False)
        if status == 'success' and 'gitlab' in url and not url.endswith('.git'):
            status, message = 'warning', "GitLab 仓库地址通常以 .git 结尾"
        self._update_field_status('repo', status, message)

    def _validate_author(self, *args):
        """验证提交者名称"""
        author = self.author.get().strip()
        if not author:
            self._update_field_status('author', 'warning', "请输入提交者名称")
        elif len(author) < 2:
            self._update_field_status('author', 'error', "提交者名称至少需要2个字符")
        elif '@' in author:
            parts = author.split('@')
            if len(parts) != 2 or not parts[0] or '.' not in parts[1]:
                self._update_field_status('author', 'warning', "邮箱格式可能不正确")
            else:
                self._update_field_status('author', 'success', "✓ 提交者邮箱格式正确")
        else:
            self._update_field_status('author', 'success', "✓ 提交者名称有效")

    def _validate_token(self, *args):
        """验证访问令牌"""
        token = self.token.get().strip()
        if not token:
            self._update_field_status('token', 'warning', "私有仓库需要访问令牌")
        elif len(token) < 20:
            self._update_field_status('token', 'error', "访问令牌长度不足")
        elif not all(c.isalnum() or c in '-_' for c in token):
            self._update_field_status('token', 'warning', "令牌包含特殊字符，请确认格式正确")
        else:
            self._update_field_status('token', 'success', "✓ 访问令牌格式正确")

    def _validate_url_logic(self, url, is_gitlab=True):
        """URL 验证逻辑"""
        if not url:
            return 'warning', "请输入 URL"
        elif not (url.startswith('http://') or url.startswith('https://')):
            return 'error', "URL 必须以 http:// 或 https:// 开头"
        elif is_gitlab and 'gitlab' not in url.lower():
            return 'warning', "建议使用包含 gitlab 的域名"
        else:
            return 'success', "✓ URL 格式正确"

    def _update_field_status(self, field_name, status, message):
        """更新字段状态和验证消息"""
        field_vars = {
            'gitlab_url': self.gitlab_url,
            'repo': self.repo,
            'author': self.author,
            'token': self.token
        }
        if field_name not in field_vars:
            return

        target_entry = self._find_entry_by_variable(field_vars[field_name])
        target_label = self._find_validation_label(field_name)

        if target_entry:
            if status == "error":
                target_entry.configure(border_color=self.styles.colors['error'])
            elif status == "warning":
                target_entry.configure(border_color=self.styles.colors['warning'])
            elif status == "success":
                target_entry.configure(border_color=self.styles.colors['success'])
            else:
                target_entry.configure(border_color=self.styles.colors['border'])

        if target_label and message:
            if status == "error":
                target_label.configure(text=message, text_color=self.styles.colors['error'])
            elif status == "warning":
                target_label.configure(text=message, text_color=self.styles.colors['warning'])
            elif status == "success":
                target_label.configure(text=message, text_color=self.styles.colors['success'])
            else:
                target_label.configure(text=message, text_color=self.styles.colors['text_secondary'])

    def _find_entry_by_variable(self, variable):
        """根据变量查找对应的输入框"""
        for widget in self.tab_frames["GitLab配置"].winfo_children():
            if isinstance(widget, ctk.CTkFrame):
                for child in widget.winfo_children():
                    if isinstance(child, ctk.CTkFrame):
                        for grandchild in child.winfo_children():
                            if isinstance(grandchild, ctk.CTkEntry) and grandchild.cget('textvariable') == variable:
                                return grandchild
        return None

    def _find_validation_label(self, field_name):
        """查找验证消息标签。"""
        return self._validation_labels.get(field_name)

    def _on_scan_all_toggle(self):
        """扫描所有项目选项切换时的处理"""
        if self.scan_all.get():
            self._update_field_status('repo', 'success', "已启用自动扫描所有项目")
        else:
            self._validate_repo_url()

    def _get_form_validation_summary(self):
        """获取表单验证摘要"""
        fields = ['gitlab_url', 'repo', 'author', 'token']
        results = {}
        for field in fields:
            entry = self._find_entry_by_variable(getattr(self, field))
            if entry:
                border_color = entry.cget('border_color')
                if border_color == self.styles.colors['error']:
                    results[field] = 'error'
                elif border_color == self.styles.colors['warning']:
                    results[field] = 'warning'
                elif border_color == self.styles.colors['success']:
                    results[field] = 'success'
                else:
                    results[field] = 'neutral'
        return results

    def _enhance_form_interaction(self):
        """增强表单交互体验"""
        input_fields = [self.gitlab_url, self.repo, self.author, self.token]
        for field_var in input_fields:
            entry = self._find_entry_by_variable(field_var)
            if entry:
                entry.bind('<FocusIn>', lambda e, f=field_var: self._on_field_focus_in(f))
                entry.bind('<FocusOut>', lambda e, f=field_var: self._on_field_focus_out(f))

    def _on_field_focus_in(self, field_var):
        """字段获得焦点时的处理"""
        entry = self._find_entry_by_variable(field_var)
        if entry:
            entry.configure(border_width=2)

    def _on_field_focus_out(self, field_var):
        """字段失去焦点时的处理"""
        entry = self._find_entry_by_variable(field_var)
        if entry:
            entry.configure(border_width=1)
            field_name = [k for k, v in {
                'gitlab_url': self.gitlab_url,
                'repo': self.repo,
                'author': self.author,
                'token': self.token
            }.items() if v == field_var][0]
            if hasattr(self, f'_validate_{field_name}'):
                getattr(self, f'_validate_{field_name}')()
