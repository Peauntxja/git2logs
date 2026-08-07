"""日期处理工具模块

提供统一的日期解析和格式化功能，消除代码重复。

业务日历日固定为 Asia/Shanghai（东八区），避免「早上 7 点提交」
因 UTC 日界被算到前一天而漏扫。
"""

from datetime import datetime, timezone
from typing import Union, Optional
import re
from zoneinfo import ZoneInfo

REPORT_TZ = ZoneInfo("Asia/Shanghai")


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

    if isinstance(commit_date, str):
        commit_date = commit_date.strip()
        if not commit_date:
            raise ValueError(f"无法解析日期格式: {commit_date}")

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
    格式化日期为中文格式（YYYY年MM月DD日）。

    不用 strftime 的中文格式符，避免部分运行环境（如打包 App）下输出为空。
    """
    if isinstance(date, datetime):
        return f"{date.year}年{date.month:02d}月{date.day:02d}日"

    s = (date or "").strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        y, mo, d = m.groups()
        return f"{y}年{mo}月{d}日"

    try:
        parsed = safe_parse_commit_date(s)
        return f"{parsed.year}年{parsed.month:02d}月{parsed.day:02d}日"
    except Exception:
        return s or "未知日期"


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


def ensure_aware_utc(dt: Union[datetime, str]) -> datetime:
    """将提交时间规范为带时区的 UTC datetime。"""
    if isinstance(dt, str):
        dt = parse_iso_date(dt)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def to_local_datetime(dt: Union[datetime, str]) -> datetime:
    """提交时间 → Asia/Shanghai 本地时间。"""
    return ensure_aware_utc(dt).astimezone(REPORT_TZ)


def to_local_date_str(dt: Union[datetime, str]) -> str:
    """提交时间 → Asia/Shanghai 日历日 YYYY-MM-DD。"""
    return to_local_datetime(dt).strftime('%Y-%m-%d')


def to_gitlab_datetime(date_str: str, end_of_day: bool = False) -> str:
    """
    将业务日历日（Asia/Shanghai）转为 GitLab API 所需的 UTC ISO 8601。

    例：查询 2026-08-06（上海）→
      since = 2026-08-05T16:00:00Z
      until = 2026-08-06T15:59:59Z
    从而覆盖上海时间当天 00:00–23:59（含早上 7 点提交）。
    """
    date_str = (date_str or "").strip()
    if end_of_day:
        local_dt = datetime.strptime(date_str, '%Y-%m-%d').replace(
            hour=23, minute=59, second=59, tzinfo=REPORT_TZ,
        )
    else:
        local_dt = datetime.strptime(date_str, '%Y-%m-%d').replace(
            hour=0, minute=0, second=0, tzinfo=REPORT_TZ,
        )
    return local_dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
