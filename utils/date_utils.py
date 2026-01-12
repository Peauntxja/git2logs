"""日期处理工具模块

提供统一的日期解析和格式化功能，消除代码重复。
"""

from datetime import datetime
from typing import Union, Optional


def parse_iso_date(date_string: str) -> datetime:
    """
    解析 ISO 格式日期字符串（处理 Z 时区后缀）

    Args:
        date_string: ISO 格式日期字符串，如 "2025-01-12T10:30:00Z"

    Returns:
        datetime: 解析后的 datetime 对象

    Raises:
        ValueError: 日期格式无效

    Examples:
        >>> parse_iso_date("2025-01-12T10:30:00Z")
        datetime.datetime(2025, 1, 12, 10, 30, tzinfo=datetime.timezone.utc)
    """
    # 将 Z 时区后缀替换为 +00:00 格式
    normalized = date_string.replace('Z', '+00:00')
    return datetime.fromisoformat(normalized)


def parse_simple_date(date_string: str) -> datetime:
    """
    解析简单的 YYYY-MM-DD 格式日期字符串

    Args:
        date_string: YYYY-MM-DD 格式日期字符串

    Returns:
        datetime: 解析后的 datetime 对象

    Raises:
        ValueError: 日期格式无效

    Examples:
        >>> parse_simple_date("2025-01-12")
        datetime.datetime(2025, 1, 12, 0, 0)
    """
    return datetime.strptime(date_string, '%Y-%m-%d')


def safe_parse_commit_date(commit_date: Union[str, datetime]) -> datetime:
    """
    安全解析 commit 日期，支持多种格式

    自动检测日期格式并解析：
    - 如果已经是 datetime 对象，直接返回
    - 尝试 ISO 格式（含时区）
    - 尝试简单的 YYYY-MM-DD 格式

    Args:
        commit_date: 日期字符串或 datetime 对象

    Returns:
        datetime: 解析后的 datetime 对象

    Raises:
        ValueError: 所有格式都无法解析时抛出

    Examples:
        >>> safe_parse_commit_date("2025-01-12T10:30:00Z")
        datetime.datetime(2025, 1, 12, 10, 30, tzinfo=datetime.timezone.utc)
        >>> safe_parse_commit_date("2025-01-12")
        datetime.datetime(2025, 1, 12, 0, 0)
    """
    # 如果已经是 datetime 对象，直接返回
    if isinstance(commit_date, datetime):
        return commit_date

    # 尝试 ISO 格式
    try:
        return parse_iso_date(commit_date)
    except (ValueError, AttributeError):
        pass

    # 尝试简单格式
    try:
        return parse_simple_date(commit_date)
    except (ValueError, AttributeError):
        pass

    # 所有格式都失败
    raise ValueError(f"无法解析日期格式: {commit_date}")


def format_date_chinese(date: Union[datetime, str]) -> str:
    """
    格式化日期为中文格式（YYYY年MM月DD日）

    Args:
        date: datetime 对象或日期字符串

    Returns:
        str: 中文格式的日期字符串

    Examples:
        >>> format_date_chinese(datetime(2025, 1, 12))
        '2025年01月12日'
        >>> format_date_chinese("2025-01-12")
        '2025年01月12日'
    """
    if isinstance(date, str):
        date = safe_parse_commit_date(date)
    return date.strftime('%Y年%m月%d日')


def format_date_range(since_date: Optional[str], until_date: Optional[str]) -> str:
    """
    格式化日期范围为中文描述

    Args:
        since_date: 开始日期（YYYY-MM-DD 格式）
        until_date: 结束日期（YYYY-MM-DD 格式）

    Returns:
        str: 日期范围描述，如 "2025年01月01日 至 2025年01月31日"

    Examples:
        >>> format_date_range("2025-01-01", "2025-01-31")
        '2025年01月01日 至 2025年01月31日'
        >>> format_date_range(None, "2025-01-31")
        '至 2025年01月31日'
    """
    parts = []
    if since_date:
        parts.append(format_date_chinese(since_date))
    if until_date:
        if parts:
            parts.append('至')
        parts.append(format_date_chinese(until_date))
    return ' '.join(parts) if parts else '全部时间'


def get_date_range_days(since_date: str, until_date: str) -> int:
    """
    计算日期范围的天数（包含首尾两天）

    Args:
        since_date: 开始日期（YYYY-MM-DD 格式）
        until_date: 结束日期（YYYY-MM-DD 格式）

    Returns:
        int: 天数（包含首尾）

    Examples:
        >>> get_date_range_days("2025-01-01", "2025-01-31")
        31
    """
    start = parse_simple_date(since_date)
    end = parse_simple_date(until_date)
    return (end - start).days + 1
