#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
集中配置管理模块

所有散落在各模块中的硬编码常量统一在此管理，
方便调整和维护，避免魔法数字。
"""


class GitLabConfig:
    """GitLab API 相关配置"""
    PER_PAGE = 100
    COMMIT_DETAIL_TIMEOUT = 10
    MAX_DISPLAY_FILES = 50
    MAX_MESSAGE_LENGTH = 5000
    CHROME_SCREENSHOT_TIMEOUT = 60
    SUBPROCESS_TIMEOUT = 30


class ReportConfig:
    """报告生成相关配置"""
    DEFAULT_DAILY_HOURS = 8.0
    DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'
    DATE_FORMAT = '%Y-%m-%d'
    GITLAB_DATE_SUFFIX_START = 'T00:00:00Z'
    GITLAB_DATE_SUFFIX_END = 'T23:59:59Z'


class AIConfig:
    """AI 分析相关配置"""
    TIMEOUT = 120
    MAX_REPORT_LENGTH = 10000
    MAX_RETRIES = 2
    MAX_TOKENS = 4000
    TEMPERATURE = 0.3
    TOP_P = 0.95
    CONNECTION_TEST_TIMEOUT = 10


class GUIConfig:
    """GUI 相关配置（数值与 git2logs_gui_ctk 当前行为一致）"""
    LOG_LINE_LIMIT = 800
    LOG_TRUNCATE_DELETE = 200
    LOG_POLL_INTERVAL_MS = 80
    LOG_FLUSH_DELAY_MS = 150
    LOG_BATCH_MAX = 80
    WINDOW_MIN_WIDTH = 760
    WINDOW_MIN_HEIGHT = 700
    WINDOW_DEFAULT_WIDTH = 900
    WINDOW_DEFAULT_HEIGHT = 820
    RESIZE_DEBOUNCE_MS = 150
    INIT_DELAY_MS = 10
    WRAPLENGTH_SYNC_DELAY_MS = 120
    SIDEBAR_FRAME_WIDTH = 208
    HEADER_HEIGHT = 48


class ImageConfig:
    """图片生成相关配置"""
    DEFAULT_WIDTH = 1600
    CHROME_VIRTUAL_TIME_BUDGET = 3000
    CHROME_WINDOW_HEIGHT = 6000
    CHROME_SCREENSHOT_TIMEOUT = 60
    PLAYWRIGHT_WAIT_MS = 1000
