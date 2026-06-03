#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitLab 提交日志生成工具 - CustomTkinter 入口（薄壳）

主界面实现位于 gui.app，便于按模块维护样式与 Service 桥接逻辑。
"""
from gui.app import Git2LogsGUI, main

__all__ = ["Git2LogsGUI", "main"]

if __name__ == "__main__":
    main()
