"""GitLab API 参数构建工具模块

提供统一的 API 参数构建功能，消除重复代码。
"""

import re
from typing import Dict, Any, Optional, List


class GitLabAPIParams:
    """GitLab API 参数构建器"""

    @staticmethod
    def build_commits_params(
        author: str,
        branch: Optional[str] = None,
        since_date: Optional[str] = None,
        until_date: Optional[str] = None,
        per_page: int = 100,
        page: int = 1
    ) -> Dict[str, Any]:
        """
        构建获取 commits 的 API 参数

        Args:
            author: 提交作者名称或邮箱
            branch: 分支名称（可选）
            since_date: 开始日期，格式 YYYY-MM-DD（可选）
            until_date: 结束日期，格式 YYYY-MM-DD（可选）
            per_page: 每页返回数量，默认 100
            page: 页码，默认 1

        Returns:
            Dict[str, Any]: API 查询参数字典

        Examples:
            >>> GitLabAPIParams.build_commits_params(
            ...     author="test@example.com",
            ...     branch="main",
            ...     since_date="2025-01-01",
            ...     until_date="2025-01-31"
            ... )
            {'author': 'test@example.com', 'per_page': 100, 'page': 1,
             'ref_name': 'main', 'since': '2025-01-01T00:00:00Z',
             'until': '2025-01-31T23:59:59Z'}
        """
        params = {
            'author': author,
            'per_page': per_page,
            'page': page
        }

        # 添加分支过滤
        if branch:
            params['ref_name'] = branch

        # 添加日期范围过滤
        if since_date:
            params['since'] = f"{since_date}T00:00:00Z"
        if until_date:
            params['until'] = f"{until_date}T23:59:59Z"

        return params

    @staticmethod
    def try_author_formats(author: str) -> List[str]:
        """
        提取作者的多种格式用于尝试查询

        从作者字符串中提取邮箱和名称，返回多个可能的格式用于 GitLab 查询。
        GitLab 的 author 参数可能需要不同的格式才能匹配成功。

        Args:
            author: 原始作者字符串，可能包含名称和邮箱
                   例如: "张三 <zhangsan@example.com>"

        Returns:
            List[str]: 可能的作者格式列表，按优先级排序
                      [原始字符串, 邮箱, 名称]

        Examples:
            >>> GitLabAPIParams.try_author_formats("张三 <zhangsan@example.com>")
            ['张三 <zhangsan@example.com>', 'zhangsan@example.com', '张三']

            >>> GitLabAPIParams.try_author_formats("zhangsan@example.com")
            ['zhangsan@example.com']
        """
        formats = [author]  # 首先尝试原始格式

        # 提取邮箱：查找 <xxx@yyy.zzz> 格式
        email_match = re.search(r'<([^>]+)>', author)
        if email_match:
            email = email_match.group(1)
            if email and email not in formats:
                formats.append(email)

        # 提取名称：获取 < 之前的内容
        name_match = re.match(r'^([^<]+)', author)
        if name_match:
            name = name_match.group(1).strip()
            if name and name != author and name not in formats:
                formats.append(name)

        return formats

    @staticmethod
    def build_branch_params(
        per_page: int = 100,
        page: int = 1
    ) -> Dict[str, Any]:
        """
        构建获取分支列表的 API 参数

        Args:
            per_page: 每页返回数量，默认 100
            page: 页码，默认 1

        Returns:
            Dict[str, Any]: API 查询参数字典

        Examples:
            >>> GitLabAPIParams.build_branch_params(per_page=50)
            {'per_page': 50, 'page': 1}
        """
        return {
            'per_page': per_page,
            'page': page
        }

    @staticmethod
    def build_project_params(
        search: Optional[str] = None,
        archived: bool = False,
        per_page: int = 100
    ) -> Dict[str, Any]:
        """
        构建获取项目列表的 API 参数

        Args:
            search: 搜索关键词（可选）
            archived: 是否包含已归档项目，默认 False
            per_page: 每页返回数量，默认 100

        Returns:
            Dict[str, Any]: API 查询参数字典

        Examples:
            >>> GitLabAPIParams.build_project_params(search="myproject")
            {'archived': False, 'per_page': 100, 'search': 'myproject'}
        """
        params = {
            'archived': archived,
            'per_page': per_page
        }

        if search:
            params['search'] = search

        return params


def extract_email_from_author(author: str) -> Optional[str]:
    """
    从作者字符串中提取邮箱地址

    Args:
        author: 作者字符串

    Returns:
        Optional[str]: 邮箱地址，如果未找到返回 None

    Examples:
        >>> extract_email_from_author("张三 <zhangsan@example.com>")
        'zhangsan@example.com'
        >>> extract_email_from_author("zhangsan@example.com")
        'zhangsan@example.com'
        >>> extract_email_from_author("张三")
        None
    """
    # 先尝试从 <email> 格式提取
    match = re.search(r'<([^>]+@[^>]+)>', author)
    if match:
        return match.group(1)

    # 尝试直接匹配邮箱格式
    if '@' in author and '.' in author:
        # 简单验证：包含 @ 和 .
        return author

    return None


def extract_name_from_author(author: str) -> str:
    """
    从作者字符串中提取名称

    Args:
        author: 作者字符串

    Returns:
        str: 名称部分，如果无法提取则返回原字符串

    Examples:
        >>> extract_name_from_author("张三 <zhangsan@example.com>")
        '张三'
        >>> extract_name_from_author("zhangsan@example.com")
        'zhangsan@example.com'
    """
    # 提取 < 之前的内容
    match = re.match(r'^([^<]+)', author)
    if match:
        name = match.group(1).strip()
        if name:
            return name

    return author
