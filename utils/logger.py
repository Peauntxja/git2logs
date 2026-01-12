"""统一日志处理模块

提供统一的日志接口，支持标准 logging 和 GUI 回调。
"""

import logging
import sys
from typing import Optional, Callable
from pathlib import Path


# 日志颜色代码（ANSI）
class LogColors:
    """日志颜色常量（用于终端输出）"""
    RESET = '\033[0m'
    RED = '\033[91m'       # 错误
    YELLOW = '\033[93m'    # 警告
    GREEN = '\033[92m'     # 成功
    BLUE = '\033[94m'      # 信息
    GRAY = '\033[90m'      # 调试


class UnifiedLogger:
    """
    统一的日志处理器

    同时支持标准 logging 输出和 GUI 回调，
    便于在命令行和 GUI 环境中使用统一的日志接口。

    Attributes:
        logger: 标准 Python logger 实例
        gui_callback: GUI 日志回调函数（可选）

    Examples:
        >>> # 命令行使用
        >>> logger = UnifiedLogger('myapp')
        >>> logger.info("处理中...")

        >>> # GUI 使用
        >>> def gui_log(message, log_type):
        ...     print(f"[{log_type}] {message}")
        >>> logger = UnifiedLogger('myapp', gui_callback=gui_log)
        >>> logger.info("GUI日志")  # 同时输出到控制台和GUI
    """

    def __init__(
        self,
        name: str = __name__,
        gui_callback: Optional[Callable[[str, str], None]] = None,
        level: int = logging.INFO
    ):
        """
        初始化统一日志处理器

        Args:
            name: logger 名称
            gui_callback: GUI 日志回调函数，签名为 (message: str, log_type: str)
            level: 日志级别，默认 INFO
        """
        self.logger = logging.getLogger(name)
        self.gui_callback = gui_callback

        # 避免重复添加 handler
        if not self.logger.handlers:
            self.logger.setLevel(level)

    def debug(self, message: str):
        """调试级别日志"""
        self.logger.debug(message)
        if self.gui_callback:
            self.gui_callback(message, "debug")

    def info(self, message: str):
        """信息级别日志"""
        self.logger.info(message)
        if self.gui_callback:
            self.gui_callback(message, "info")

    def success(self, message: str):
        """成功级别日志（映射到 INFO）"""
        self.logger.info(message)
        if self.gui_callback:
            self.gui_callback(message, "success")

    def warning(self, message: str):
        """警告级别日志"""
        self.logger.warning(message)
        if self.gui_callback:
            self.gui_callback(message, "warning")

    def error(self, message: str, exc_info: bool = False):
        """错误级别日志"""
        self.logger.error(message, exc_info=exc_info)
        if self.gui_callback:
            self.gui_callback(message, "error")

    def critical(self, message: str):
        """严重错误级别日志"""
        self.logger.critical(message)
        if self.gui_callback:
            self.gui_callback(message, "error")


def setup_logger(
    name: str = 'git2logs',
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    use_colors: bool = True
) -> logging.Logger:
    """
    配置标准 logger

    创建并配置一个标准的 Python logger，支持控制台和文件输出。

    Args:
        name: logger 名称
        level: 日志级别（DEBUG, INFO, WARNING, ERROR, CRITICAL）
        log_file: 日志文件路径（可选）
        use_colors: 是否在控制台使用颜色（默认 True）

    Returns:
        logging.Logger: 配置好的 logger 实例

    Examples:
        >>> logger = setup_logger('myapp', level=logging.DEBUG)
        >>> logger.info("应用启动")

        >>> # 输出到文件
        >>> logger = setup_logger('myapp', log_file='app.log')
    """
    logger = logging.getLogger(name)

    # 避免重复配置
    if logger.handlers:
        return logger

    logger.setLevel(level)

    # 创建控制台 handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    # 格式化器
    if use_colors and sys.stdout.isatty():
        # 终端支持颜色
        formatter = ColoredFormatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    else:
        # 不使用颜色
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 添加文件 handler（如果指定）
    if log_file:
        # 确保目录存在
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)

        # 文件输出不使用颜色
        file_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger


class ColoredFormatter(logging.Formatter):
    """彩色日志格式化器"""

    COLORS = {
        'DEBUG': LogColors.GRAY,
        'INFO': LogColors.BLUE,
        'WARNING': LogColors.YELLOW,
        'ERROR': LogColors.RED,
        'CRITICAL': LogColors.RED,
    }

    def format(self, record):
        # 添加颜色
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{LogColors.RESET}"

        return super().format(record)


def get_logger(
    name: str = 'git2logs',
    gui_callback: Optional[Callable] = None
) -> UnifiedLogger:
    """
    快捷获取 UnifiedLogger 实例

    Args:
        name: logger 名称
        gui_callback: GUI 回调函数（可选）

    Returns:
        UnifiedLogger: 统一日志处理器实例

    Examples:
        >>> logger = get_logger('myapp')
        >>> logger.info("快捷日志")
    """
    return UnifiedLogger(name, gui_callback=gui_callback)


# 便捷函数：直接使用模块级别的 logger
_default_logger: Optional[UnifiedLogger] = None


def set_default_logger(logger: UnifiedLogger):
    """设置默认的 logger 实例"""
    global _default_logger
    _default_logger = logger


def debug(message: str):
    """模块级别的 debug 日志"""
    if _default_logger:
        _default_logger.debug(message)


def info(message: str):
    """模块级别的 info 日志"""
    if _default_logger:
        _default_logger.info(message)


def success(message: str):
    """模块级别的 success 日志"""
    if _default_logger:
        _default_logger.success(message)


def warning(message: str):
    """模块级别的 warning 日志"""
    if _default_logger:
        _default_logger.warning(message)


def error(message: str):
    """模块级别的 error 日志"""
    if _default_logger:
        _default_logger.error(message)
