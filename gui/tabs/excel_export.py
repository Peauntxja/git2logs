"""Excel 导出标签页 Mixin"""

import os
import threading
import customtkinter as ctk
from tkinter import messagebox, filedialog
import logging

logger = logging.getLogger(__name__)


class ExcelExportMixin:

    def _create_tab4_excel_export(self):
        """创建标签页4: Excel导出"""
        tab4 = ctk.CTkFrame(self.content_container, fg_color="transparent", corner_radius=0)
        tab4.pack(fill="both", expand=True, padx=20, pady=20)

        content = ctk.CTkFrame(tab4, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=30, pady=10)
        content.columnconfigure(0, weight=1)

        row = 0

        # ── 数据来源状态卡片 ──────────────────────────────
        status_card = ctk.CTkFrame(
            content,
            fg_color=self.bg_card,
            corner_radius=12,
            border_width=1,
            border_color=self.border_color,
        )
        status_card.grid(row=row, column=0, sticky="ew", pady=(0, 20))
        status_card.columnconfigure(0, weight=1)
        self._track_panel_card(status_card)

        excel_status_hdr = ctk.CTkLabel(status_card,
                     text="工时数据来源",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=self.text_primary,
                     anchor="w")
        excel_status_hdr.grid(row=0, column=0, columnspan=2, sticky="w", padx=20, pady=(20, 8))
        self._track_label_primary(excel_status_hdr)

        self._excel_status_label = ctk.CTkLabel(
            status_card,
            text="尚无工时数据。请先生成「工时分配报告」，或点击右侧按钮加载 JSON 文件。",
            font=ctk.CTkFont(size=13),
            text_color=self.text_secondary,
            anchor="w",
            wraplength=400,
        )
        self._excel_status_label.grid(row=1, column=0, sticky="w", padx=20, pady=(0, 16))
        self._track_responsive_wrap(self._excel_status_label)

        load_wh_btn = ctk.CTkButton(status_card,
                      text="从文件加载",
                      width=120,
                      height=36,
                      font=ctk.CTkFont(size=13),
                      corner_radius=8,
                      fg_color=self.bg_card,
                      text_color=self.text_primary,
                      hover_color=self.styles.colors['hover'],
                      border_width=1,
                      border_color=self.border_color,
                      command=self._load_work_hours_from_file,
                      )
        load_wh_btn.grid(row=1, column=1, padx=(0, 20), pady=(0, 16), sticky="e")
        self._track_outline_button(load_wh_btn)

        row += 1

        # ── 模板文件 ─────────────────────────────────────
        tmpl_card = ctk.CTkFrame(
            content,
            fg_color=self.bg_card,
            corner_radius=12,
            border_width=1,
            border_color=self.border_color,
        )
        tmpl_card.grid(row=row, column=0, sticky="ew", pady=(0, 20))
        tmpl_card.columnconfigure(0, weight=1)
        self._track_panel_card(tmpl_card)

        tmpl_hdr = ctk.CTkLabel(tmpl_card,
                     text="Excel 模板文件",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=self.text_primary,
                     anchor="w")
        tmpl_hdr.grid(row=0, column=0, sticky="w", padx=20, pady=(20, 8))
        self._track_label_primary(tmpl_hdr)

        tmpl_row_frame = ctk.CTkFrame(tmpl_card, fg_color="transparent")
        tmpl_row_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 8))
        tmpl_row_frame.columnconfigure(0, weight=1)

        self._excel_template_var = ctk.StringVar()
        self._excel_template_entry = ctk.CTkEntry(tmpl_row_frame,
                     textvariable=self._excel_template_var,
                     font=ctk.CTkFont(size=13),
                     height=40,
                     corner_radius=8,
                     border_width=1,
                     border_color=self.border_color,
                     fg_color=self.bg_card,
                     text_color=self.text_primary,
                     placeholder_text="选择 .xlsx 模板文件…")
        self._excel_template_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._track_entry(self._excel_template_entry, 'card')

        tmpl_browse_btn = ctk.CTkButton(tmpl_row_frame,
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
                      command=self._browse_excel_template)
        tmpl_browse_btn.grid(row=0, column=1)
        self._track_outline_button(tmpl_browse_btn)

        tmpl_hint_lbl = ctk.CTkLabel(tmpl_card,
                     text="提示: 模板须含表头行（含「任务名称」「预计工时」等列）及一行示例数据",
                     font=ctk.CTkFont(size=11),
                     text_color=self.text_secondary,
                     anchor="w")
        tmpl_hint_lbl.grid(row=2, column=0, sticky="w", padx=20, pady=(0, 20))
        self._track_label_secondary(tmpl_hint_lbl)

        row += 1

        # ── 项目选择 ─────────────────────────────────────
        proj_card = ctk.CTkFrame(
            content,
            fg_color=self.bg_card,
            corner_radius=12,
            border_width=1,
            border_color=self.border_color,
        )
        proj_card.grid(row=row, column=0, sticky="ew", pady=(0, 20))
        proj_card.columnconfigure(0, weight=1)
        self._track_panel_card(proj_card)

        # 标题行 + 全选/全不选按钮
        proj_title_frame = ctk.CTkFrame(proj_card, fg_color="transparent")
        proj_title_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 8))
        proj_title_frame.columnconfigure(0, weight=1)

        proj_hdr = ctk.CTkLabel(proj_title_frame,
                     text="选择要导出的项目",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=self.text_primary,
                     anchor="w")
        proj_hdr.grid(row=0, column=0, sticky="w")
        self._track_label_primary(proj_hdr)

        btn_frame = ctk.CTkFrame(proj_title_frame, fg_color="transparent")
        btn_frame.grid(row=0, column=1, sticky="e")

        sel_all_btn = ctk.CTkButton(btn_frame,
                      text="全选",
                      width=60,
                      height=28,
                      font=ctk.CTkFont(size=12),
                      corner_radius=6,
                      fg_color=self.bg_card,
                      text_color=self.text_primary,
                      hover_color=self.styles.colors['hover'],
                      border_width=1,
                      border_color=self.border_color,
                      command=lambda: self._select_all_projects(True),
                      )
        sel_all_btn.pack(side="left", padx=(0, 6))
        self._track_outline_button(sel_all_btn)

        sel_none_btn = ctk.CTkButton(btn_frame,
                      text="全不选",
                      width=60,
                      height=28,
                      font=ctk.CTkFont(size=12),
                      corner_radius=6,
                      fg_color=self.bg_card,
                      text_color=self.text_primary,
                      hover_color=self.styles.colors['hover'],
                      border_width=1,
                      border_color=self.border_color,
                      command=lambda: self._select_all_projects(False),
                      )
        sel_none_btn.pack(side="left")
        self._track_outline_button(sel_none_btn)

        # 复选框动态容器
        self._project_checkbox_frame = ctk.CTkFrame(proj_card, fg_color="transparent")
        self._project_checkbox_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 20))
        self._project_checkbox_frame.columnconfigure(0, weight=1)

        # 初始占位提示
        ctk.CTkLabel(self._project_checkbox_frame,
                     text="（暂无项目数据，请先生成工时报告或加载 JSON 文件）",
                     font=ctk.CTkFont(size=12),
                     text_color=self.text_secondary,
                     anchor="w").pack(anchor="w", pady=4)

        row += 1

        # ── 输出文件 ─────────────────────────────────────
        out_card = ctk.CTkFrame(
            content,
            fg_color=self.bg_card,
            corner_radius=12,
            border_width=1,
            border_color=self.border_color,
        )
        out_card.grid(row=row, column=0, sticky="ew", pady=(0, 20))
        out_card.columnconfigure(0, weight=1)
        self._track_panel_card(out_card)

        out_hdr = ctk.CTkLabel(out_card,
                     text="输出 Excel 文件",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=self.text_primary,
                     anchor="w")
        out_hdr.grid(row=0, column=0, sticky="w", padx=20, pady=(20, 8))
        self._track_label_primary(out_hdr)

        out_row_frame = ctk.CTkFrame(out_card, fg_color="transparent")
        out_row_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 20))
        out_row_frame.columnconfigure(0, weight=1)

        self._excel_output_var = ctk.StringVar()
        self._excel_output_entry = ctk.CTkEntry(out_row_frame,
                     textvariable=self._excel_output_var,
                     font=ctk.CTkFont(size=13),
                     height=40,
                     corner_radius=8,
                     border_width=1,
                     border_color=self.border_color,
                     fg_color=self.bg_card,
                     text_color=self.text_primary,
                     placeholder_text="输出文件路径（.xlsx）…")
        self._excel_output_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._track_entry(self._excel_output_entry, 'card')

        out_browse_btn = ctk.CTkButton(out_row_frame,
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
                      command=self._browse_excel_output)
        out_browse_btn.grid(row=0, column=1)
        self._track_outline_button(out_browse_btn)

        row += 1

        # ── 工时规则说明 ─────────────────────────────────
        self._excel_rule_label = ctk.CTkLabel(
            content,
            text="工时规则：单条任务 ≥2h（不足自动汇总），单条任务 ≤8h（超额截断）；同一天小任务（<2h）会压缩为\u201c任务汇总\u201d条目，且导出工时为整数",
            font=ctk.CTkFont(size=11),
            text_color=self.text_secondary,
            anchor="w",
            wraplength=500,
        )
        self._excel_rule_label.grid(row=row, column=0, sticky="w", pady=(0, 16))
        self._track_label_secondary(self._excel_rule_label)
        self._track_responsive_wrap(self._excel_rule_label)

        row += 1

        # ── 导出按钮 ─────────────────────────────────────
        self._excel_export_btn = ctk.CTkButton(
            content,
            text="导出到 Excel",
            font=ctk.CTkFont(size=15, weight="bold"),
            height=48,
            corner_radius=10,
            fg_color=self.accent_color,
            hover_color=self.styles.colors['accent_hover'],
            text_color="#FFFFFF",
            command=self._export_to_excel,
        )
        self._excel_export_btn.grid(row=row, column=0, sticky="ew", pady=(0, 30))

        # 底部占位
        ctk.CTkLabel(content, text="", height=50).grid(row=row + 1, column=0)

        self.tab_frames["Excel导出"] = tab4
        tab4.pack_forget()

    # ── Excel 导出相关方法 ─────────────────────────────────────────────────

    def _refresh_excel_status(self) -> None:
        """刷新 Excel 导出页的数据来源状态并重建项目复选框。"""
        if not hasattr(self, "_excel_status_label"):
            return
        if self._work_hours_data:
            from excel_exporter import list_projects
            projects = list_projects(self._work_hours_data)
            date_keys = sorted(self._work_hours_data.keys())
            date_range = f"{date_keys[0]} ~ {date_keys[-1]}" if date_keys else "?"
            self._excel_status_label.configure(
                text=f"已有工时数据（{date_range}），共 {len(projects)} 个项目",
                text_color=self.success_color,
            )
        else:
            self._excel_status_label.configure(
                text="尚无工时数据。请先生成「工时分配报告」，或点击右侧按钮加载 JSON 文件。",
                text_color=self.text_secondary,
            )
        self._rebuild_project_checkboxes()

    def _rebuild_project_checkboxes(self) -> None:
        """根据当前工时数据重新生成项目复选框列表。"""
        if not hasattr(self, "_project_checkbox_frame"):
            return
        # 清空旧内容
        for w in self._project_checkbox_frame.winfo_children():
            w.destroy() 
        self._project_checkboxes.clear()

        if not self._work_hours_data:
            ctk.CTkLabel(self._project_checkbox_frame,
                         text="（暂无项目数据，请先生成工时报告或加载 JSON 文件）",
                         font=ctk.CTkFont(size=12),
                         text_color=self.text_secondary,
                         anchor="w").pack(anchor="w", pady=4)
            return

        from excel_exporter import list_projects
        projects = list_projects(self._work_hours_data)
        if not projects:
            ctk.CTkLabel(self._project_checkbox_frame,
                         text="（未找到任何项目）",
                         font=ctk.CTkFont(size=12),
                         text_color=self.text_secondary,
                         anchor="w").pack(anchor="w", pady=4)
            return

        for proj in projects:
            var = ctk.BooleanVar(value=True)
            cb = ctk.CTkCheckBox(
                self._project_checkbox_frame,
                text=proj,
                variable=var,
                font=ctk.CTkFont(size=13),
                text_color=self.text_primary,
                fg_color=self.accent_color,
                corner_radius=4,
            )
            cb.pack(anchor="w", pady=4)
            self._project_checkboxes[proj] = var

    def _select_all_projects(self, checked: bool) -> None:
        """全选或全不选所有项目复选框。"""
        for var in self._project_checkboxes.values():
            var.set(checked)

    def _load_work_hours_from_file(self) -> None:
        """从本地 JSON 或 Markdown 文件加载工时数据。"""
        path = filedialog.askopenfilename(
            title="选择工时数据文件",
            filetypes=[
                ("工时数据文件", "*.json *.md *.markdown"),
                ("JSON 文件", "*.json"),
                ("Markdown 文件", "*.md *.markdown"),
                ("所有文件", "*.*"),
            ],
        )
        if not path:
            return
        try:
            from excel_exporter import load_work_hours_file, list_projects
            data = load_work_hours_file(path)
            self._work_hours_data = data
            self._refresh_excel_status()
            projects = list_projects(data)
            self.log(f"已加载工时数据: {path}", "info")
            self.log(f"共识别到 {len(projects)} 个项目: {', '.join(projects)}", "info")
        except Exception as e:
            messagebox.showerror("加载失败", str(e))

    def _browse_excel_template(self) -> None:
        path = filedialog.askopenfilename(
            title="选择 Excel 模板文件",
            filetypes=[("Excel 文件", "*.xlsx *.xls"), ("所有文件", "*.*")],
        )
        if path:
            self._excel_template_var.set(path)
            if not self._excel_output_var.get().strip():
                from pathlib import Path as _Path
                p = _Path(path)
                self._excel_output_var.set(str(p.parent / (p.stem + "_filled.xlsx")))

    def _browse_excel_output(self) -> None:
        path = filedialog.asksaveasfilename(
            title="保存 Excel 文件",
            defaultextension=".xlsx",
            filetypes=[("Excel 文件", "*.xlsx"), ("所有文件", "*.*")],
        )
        if path:
            self._excel_output_var.set(path)

    def _export_to_excel(self) -> None:
        """触发 Excel 导出（在子线程执行）。"""
        if not self._work_hours_data:
            messagebox.showwarning(
                "无工时数据",
                "请先生成「工时分配报告」，或点击「从文件加载」加载 JSON 数据。",
            )
            return

        template = self._excel_template_var.get().strip()
        if not template:
            messagebox.showwarning("缺少模板", "请选择 Excel 模板文件。")
            return

        output = self._excel_output_var.get().strip()
        if not output:
            messagebox.showwarning("缺少输出路径", "请指定输出 Excel 文件路径。")
            return

        selected = [proj for proj, var in self._project_checkboxes.items() if var.get()]
        if self._project_checkboxes and not selected:
            messagebox.showwarning("未选择项目", "请至少勾选一个要导出的项目。")
            return

        self._excel_export_btn.configure(state="disabled")
        t = threading.Thread(
            target=self._perform_excel_export,
            args=(template, output, selected if self._project_checkboxes else None),
            daemon=True,
        )
        t.start()

    def _perform_excel_export(self, template: str, output: str, selected_projects: list | None) -> None:
        """在子线程中执行 Excel 填充。"""
        try:
            from excel_exporter import fill_excel_template
            self.log("=" * 60, "info")
            self.log("开始导出 Excel 工时表…", "info")
            if selected_projects:
                self.log(f"导出项目: {', '.join(selected_projects)}", "info")
            else:
                self.log("导出所有项目", "info")

            count = fill_excel_template(
                template_path=template,
                work_hours_data=self._work_hours_data,
                output_path=output,
                project_filters=selected_projects,
            )
            self.log(f"导出成功：共写入 {count} 行任务数据", "success")
            self.log(f"文件已保存至: {output}", "success")
            self._show_toast(f"Excel 导出成功（{count} 行）", "success")
            self.root.after(0, lambda: messagebox.showinfo(
                "导出成功",
                f"共写入 {count} 行任务数据\n\n文件路径:\n{output}",
            ))
        except ImportError as e:
            self.log(f"导出失败（缺少依赖）: {e}", "error")
            self._show_toast("Excel 导出失败", "error")
            self.root.after(0, lambda: messagebox.showerror("依赖缺失", str(e)))
        except (ValueError, FileNotFoundError) as e:
            self.log(f"导出失败: {e}", "error")
            self._show_toast("Excel 导出失败", "error")
            self.root.after(0, lambda: messagebox.showerror("导出失败", str(e)))
        except Exception as e:
            import traceback
            self.log(f"导出异常: {e}", "error")
            self.log(traceback.format_exc(), "error")
            self._show_toast("Excel 导出异常", "error")
            self.root.after(0, lambda: messagebox.showerror("导出异常", str(e)))
        finally:
            self._safe_button_operation("_excel_export_btn", lambda btn: btn.configure(text="导出到 Excel"))
            self._reset_button_state("_excel_export_btn")
