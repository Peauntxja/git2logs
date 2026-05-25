"""日志面板组件 Mixin"""

import queue
import threading
import customtkinter as ctk
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class LogPanelMixin:

    def _create_log_area(self, parent):
        """创建日志显示区域（放在最上方）"""
        log_container = ctk.CTkFrame(parent, fg_color=self.styles.colors['bg_main'], corner_radius=0)
        log_container.pack(fill="x", padx=0, pady=(0, self.styles.spacing['sm']))
        self._log_container = log_container
        
        log_title_frame = ctk.CTkFrame(log_container,
                                     fg_color=self.styles.colors['bg_main'],
                                     height=40,
                                     corner_radius=0)
        log_title_frame.pack(fill="x", padx=20, pady=(0, 8))
        log_title_frame.pack_propagate(False)
        self._log_title_frame = log_title_frame
        
        self._log_title_lbl = ctk.CTkLabel(log_title_frame,
                              text="执行日志",
                              font=self.styles.fonts['body_bold'](),
                              text_color=self.styles.colors['text_primary'],
                              anchor="w")
        self._log_title_lbl.pack(side="left", padx=0, pady=10)

        tf_right = ctk.CTkFrame(log_title_frame, fg_color="transparent")
        tf_right.pack(side="right", padx=0, pady=4)

        self._log_filter_btn = ctk.CTkSegmentedButton(
            tf_right,
            values=["全部", "警告+错误", "仅错误"],
            command=self._on_log_filter_change,
            width=200,
            height=28,
            font=self.styles.fonts['caption'](),
            corner_radius=self.styles.radius['sm'],
            fg_color=self.styles.colors['bg_card'],
            selected_color=self.styles.colors['accent'],
            selected_hover_color=self.styles.colors['accent'],
            unselected_color=self.styles.colors['bg_card'],
            unselected_hover_color=self.styles.colors['hover'],
            text_color=self.styles.colors['text_primary'],
        )
        self._log_filter_btn.set("全部")
        self._log_filter_btn.pack(side="right", padx=(0, 8))

        self._log_toggle_btn = ctk.CTkButton(
            tf_right,
            text="收起",
            width=56,
            height=28,
            font=self.styles.fonts['caption'](),
            corner_radius=self.styles.radius['sm'],
            fg_color=self.styles.colors['bg_card'],
            text_color=self.styles.colors['text_secondary'],
            hover_color=self.styles.colors['hover'],
            border_width=1,
            border_color=self.styles.colors['border'],
            command=self._toggle_log_collapsed,
        )
        self._log_toggle_btn.pack(side="right")
        
        log_card = ctk.CTkFrame(log_container,
                              fg_color=self.styles.colors['bg_card'],
                              corner_radius=self.styles.radius['lg'])
        log_card.pack(fill="x", padx=20, pady=(0, 0))
        self._log_card = log_card
        
        text_container = ctk.CTkFrame(log_card, fg_color=self.styles.colors['bg_main'], corner_radius=self.styles.radius['md'])
        text_container.pack(fill="x", padx=10, pady=10)
        self._log_text_container = text_container
        
        from tkinter import scrolledtext
        mono = _resolve_monospace_font(self.root, 10)
        self.log_text = scrolledtext.ScrolledText(text_container,
                                             height=6,
                                             width=80,
                                             font=mono,
                                             wrap="word",
                                             bg=self.styles.colors['bg_main'],
                                             fg=self.styles.colors['text_primary'],
                                             insertbackground=self.styles.colors['accent'],
                                             selectbackground=self.styles.colors['accent'],
                                             selectforeground="white",
                                             borderwidth=0,
                                             relief="flat",
                                             padx=12,
                                             pady=12)
        self.log_text.pack(fill="both", expand=False)
        
        self.log_text.tag_config("error", foreground=self.styles.colors['error'])
        self.log_text.tag_config("success", foreground=self.styles.colors['success'])
        self.log_text.tag_config("warning", foreground=self.styles.colors['warning'])
        self.log_text.tag_config("info", foreground=self.styles.colors['text_primary'])
        self.log_text.tag_config("timestamp", foreground=self.styles.colors['text_secondary'])

    def _toggle_log_collapsed(self):
        """折叠/展开执行日志区域（仅影响布局，不改变业务逻辑）。"""
        if not hasattr(self, "_log_card") or not hasattr(self, "_log_toggle_btn"):
            return
        self._log_collapsed = not self._log_collapsed
        if self._log_collapsed:
            self._log_card.pack_forget()
            self._log_toggle_btn.configure(text="展开")
        else:
            self._log_card.pack(fill="x", padx=20, pady=(0, 0))
            self._log_toggle_btn.configure(text="收起")

    def _on_log_filter_change(self, value):
        """日志等级筛选按钮回调，更新筛选级别。"""
        self._log_filter_level = value

    def _refresh_log_widget_theme(self):
        """根据当前 UIStyles 同步 Tk 日志控件与标签颜色。"""
        if not hasattr(self, "log_text"):
            return
        c = self.styles.colors
        sel_fg = "#FFFFFF" if self._current_theme == "dark" else "#18181B"
        self.log_text.configure(
            bg=c['bg_main'],
            fg=c['text_primary'],
            insertbackground=c['accent'],
            selectbackground=c['accent'],
            selectforeground=sel_fg,
        )
        self.log_text.tag_config("error", foreground=c['error'])
        self.log_text.tag_config("success", foreground=c['success'])
        self.log_text.tag_config("warning", foreground=c['warning'])
        self.log_text.tag_config("info", foreground=c['text_primary'])

    def _poll_log_queue(self):
        """定时从队列批量取出日志，降低主线程事件循环压力。"""
        try:
            batch = []
            while len(batch) < 80:
                try:
                    batch.append(self._log_queue.get_nowait())
                except queue.Empty:
                    break

            if batch:
                for message, log_type in batch:
                    self._enqueue_log_entry(message, log_type)
                if not self._log_flush_scheduled:
                    self._log_flush_scheduled = True
                    self.root.after(150, self._flush_logs)
        except Exception:
            logger.debug("轮询日志队列失败")
        finally:
            self.root.after(80, self._poll_log_queue)

    def log(self, message, log_type="info"):
        """添加日志消息。后台线程通过 queue 传递，主线程直接入待写列表。"""
        try:
            if threading.current_thread() is not threading.main_thread():
                self._log_queue.put((message, log_type))
                return

            self._enqueue_log_entry(message, log_type)

            if not self._log_flush_scheduled:
                self._log_flush_scheduled = True
                self.root.after(150, self._flush_logs)
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

            if self._log_count > 800:
                lines_to_delete = 200
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
