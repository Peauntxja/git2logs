"""正则表达式模式和关键词常量模块

预编译正则表达式以提高性能，定义常用的关键词集合。
"""

import re
from typing import Pattern, Tuple


# ====== 预编译的正则表达式 ======

# 作者信息提取
EMAIL_PATTERN: Pattern = re.compile(r'<([^>]+)>')
NAME_PATTERN: Pattern = re.compile(r'^([^<]+)')

# 日期格式匹配
DATE_PATTERN: Pattern = re.compile(r'(\d{4}年\d{1,2}月\d{1,2}日) \((\d{4}-\d{2}-\d{2})\)')
ISO_DATE_PATTERN: Pattern = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}')
SIMPLE_DATE_PATTERN: Pattern = re.compile(r'\d{4}-\d{2}-\d{2}')

# 报告解析模式（用于 generate_report_image.py）
DAILY_REPORT_DATE_PATTERN: Pattern = re.compile(r'\*\*日期\*\*: (.*?) \(')
PROJECTS_COUNT_PATTERN: Pattern = re.compile(r'\*\*涉及项目\*\*: (\d+) 个')
COMMITS_COUNT_PATTERN: Pattern = re.compile(r'\*\*总提交数\*\*: (\d+) 次')
CODE_LINES_PATTERN: Pattern = re.compile(r'\*\*代码行数\*\*: 新增 (\d+) / 删除 (\d+) / 净增 ([-\d]+)')
ACTIVE_DAYS_PATTERN: Pattern = re.compile(r'\*\*活跃天数\*\*: (\d+) 天')
SCORE_PATTERN: Pattern = re.compile(r'(\d+\.\d+)分')

# Commit 消息模式
MERGE_PATTERN: Pattern = re.compile(r'^Merge\s+(branch|pull\s+request|remote)', re.IGNORECASE)
REVERT_PATTERN: Pattern = re.compile(r'^Revert\s+', re.IGNORECASE)


# ====== 关键词常量 ======

# Bug 修复相关关键词
FIX_KEYWORDS: Tuple[str, ...] = (
    'fix', 'bug', 'bugfix', 'hotfix',
    '修复', '报错', '解决', '修正',
    'error', 'issue', 'problem',
    'patch', 'repair'
)

# 功能开发相关关键词
FEAT_KEYWORDS: Tuple[str, ...] = (
    'feat', 'feature', 'add', 'new',
    '开发', '新增', '添加', '增加',
    'implement', '实现', 'create',
    'introduce', 'support'
)

# 重构相关关键词
REFACTOR_KEYWORDS: Tuple[str, ...] = (
    'refactor', 'refactoring',
    '重构', '优化', '改进',
    'optimize', 'improve',
    'restructure', 'cleanup'
)

# 测试相关关键词
TEST_KEYWORDS: Tuple[str, ...] = (
    'test', 'testing', 'spec',
    '测试', '单元测试',
    'unit test', 'e2e',
    'coverage'
)

# 文档相关关键词
DOCS_KEYWORDS: Tuple[str, ...] = (
    'docs', 'doc', 'document',
    '文档', '注释', '说明',
    'readme', 'comment',
    'changelog'
)

# 样式相关关键词
STYLE_KEYWORDS: Tuple[str, ...] = (
    'style', 'format', 'formatting',
    '样式', '格式', '排版',
    'lint', 'prettier',
    'whitespace'
)


# ====== 辅助函数 ======

def check_commit_type(message: str) -> Tuple[bool, bool]:
    """
    检查 commit 消息类型（是否为 fix 或 feat）

    Args:
        message: commit 消息内容

    Returns:
        Tuple[bool, bool]: (是否为 fix, 是否为 feat)

    Examples:
        >>> check_commit_type("fix: 修复登录bug")
        (True, False)
        >>> check_commit_type("feat: 添加用户管理功能")
        (False, True)
        >>> check_commit_type("chore: 更新依赖")
        (False, False)
    """
    msg_lower = message.lower()

    is_fix = any(keyword in msg_lower for keyword in FIX_KEYWORDS)
    is_feat = any(keyword in msg_lower for keyword in FEAT_KEYWORDS)

    return is_fix, is_feat


def classify_commit(message: str) -> str:
    """
    分类 commit 消息类型

    Args:
        message: commit 消息内容

    Returns:
        str: commit 类型，可能的值：
            'fix' - Bug修复
            'feat' - 功能开发
            'refactor' - 代码重构
            'test' - 测试相关
            'docs' - 文档更新
            'style' - 代码样式
            'merge' - 合并提交
            'revert' - 回滚提交
            'other' - 其他类型

    Examples:
        >>> classify_commit("fix: 修复登录bug")
        'fix'
        >>> classify_commit("feat: 添加用户管理")
        'feat'
        >>> classify_commit("Merge branch 'main'")
        'merge'
    """
    msg_lower = message.lower()

    # 特殊类型优先判断
    if MERGE_PATTERN.match(message):
        return 'merge'
    if REVERT_PATTERN.match(message):
        return 'revert'

    # 按优先级判断类型
    if any(keyword in msg_lower for keyword in FIX_KEYWORDS):
        return 'fix'
    if any(keyword in msg_lower for keyword in FEAT_KEYWORDS):
        return 'feat'
    if any(keyword in msg_lower for keyword in TEST_KEYWORDS):
        return 'test'
    if any(keyword in msg_lower for keyword in REFACTOR_KEYWORDS):
        return 'refactor'
    if any(keyword in msg_lower for keyword in DOCS_KEYWORDS):
        return 'docs'
    if any(keyword in msg_lower for keyword in STYLE_KEYWORDS):
        return 'style'

    return 'other'


def is_meaningful_commit(message: str) -> bool:
    """
    判断是否为有意义的提交（排除合并、回滚等）

    Args:
        message: commit 消息内容

    Returns:
        bool: 是否为有意义的提交

    Examples:
        >>> is_meaningful_commit("fix: 修复bug")
        True
        >>> is_meaningful_commit("Merge branch 'main'")
        False
    """
    commit_type = classify_commit(message)
    return commit_type not in ('merge', 'revert')


def extract_commit_summary(message: str, max_length: int = 100) -> str:
    """
    提取 commit 消息摘要（第一行）

    Args:
        message: 完整的 commit 消息
        max_length: 最大长度，默认 100

    Returns:
        str: commit 摘要

    Examples:
        >>> extract_commit_summary("fix: 修复登录bug\\n\\n详细说明...")
        'fix: 修复登录bug'
    """
    # 获取第一行
    first_line = message.split('\n')[0].strip()

    # 限制长度
    if len(first_line) > max_length:
        return first_line[:max_length - 3] + '...'

    return first_line
