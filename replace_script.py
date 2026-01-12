#!/usr/bin/env python3
"""
批量替换 git2logs.py 中的重复代码
使用新创建的工具模块替换重复的日期解析、API参数构建等代码
"""

import re
from pathlib import Path


def replace_date_parsing(content: str) -> str:
    """替换日期解析逻辑"""

    # 模式 1: datetime.fromisoformat(...replace('Z', '+00:00'))
    # 替换为: parse_iso_date(...)
    pattern1 = r'datetime\.fromisoformat\(([^)]+?)\.replace\([\'"]Z[\'"]\s*,\s*[\'"]\+00:00[\'"]\)\)'
    content = re.sub(pattern1, r'parse_iso_date(\1)', content)

    # 模式 2: datetime.strptime(..., '%Y-%m-%d')
    # 替换为: parse_simple_date(...)
    pattern2 = r'datetime\.strptime\(([^,]+?),\s*[\'"]%Y-%m-%d[\'"]'
    content = re.sub(pattern2, r'parse_simple_date(\1', content)

    # 模式 3: 条件判断日期解析
    # if isinstance(commit_date, str):
    #     date_obj = datetime.fromisoformat(commit_date.replace('Z', '+00:00'))
    # else:
    #     date_obj = commit_date
    # 替换为: date_obj = safe_parse_commit_date(commit_date)
    pattern3 = r'if isinstance\((\w+),\s*str\):\s+(\w+)\s*=\s*datetime\.fromisoformat\(\1\.replace\([\'"]Z[\'"]\s*,\s*[\'"]\+00:00[\'"]\)\)\s+else:\s+\2\s*=\s*\1'
    content = re.sub(pattern3, r'\2 = safe_parse_commit_date(\1)', content)

    return content


def replace_api_params(content: str) -> str:
    """替换 API 参数构建逻辑"""

    # 查找并替换 API 参数构建的代码块
    # 这个比较复杂，需要手动处理关键位置

    return content


def replace_keywords(content: str) -> str:
    """替换关键词列表定义"""

    # 替换 fix_keywords 定义
    pattern1 = r"fix_keywords\s*=\s*\[[^\]]+\]"
    if re.search(pattern1, content):
        content = re.sub(pattern1, "fix_keywords = FIX_KEYWORDS  # 从 utils.patterns 导入", content)

    # 替换 feat_keywords 定义
    pattern2 = r"feat_keywords\s*=\s*\[[^\]]+\]"
    if re.search(pattern2, content):
        content = re.sub(pattern2, "feat_keywords = FEAT_KEYWORDS  # 从 utils.patterns 导入", content)

    # 替换关键词检查逻辑
    # 模式: any(kw in message.lower() for kw in [...]
    # 替换为: check_commit_type(message)

    return content


def main():
    # 读取文件
    file_path = Path('/Users/kusuri_mizuki/myProject/git2logs/git2logs.py')
    print(f"正在读取文件: {file_path}")

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    original_length = len(content)
    print(f"原始文件长度: {original_length} 字符")

    # 备份原文件
    backup_path = file_path.with_suffix('.py.backup')
    with open(backup_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"已备份到: {backup_path}")

    # 执行替换
    print("\n开始替换...")
    print("1. 替换日期解析逻辑...")
    content = replace_date_parsing(content)

    print("2. 替换关键词定义...")
    content = replace_keywords(content)

    new_length = len(content)
    print(f"\n新文件长度: {new_length} 字符")
    print(f"减少了: {original_length - new_length} 字符")

    # 写回文件
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"\n✓ 替换完成！文件已更新: {file_path}")
    print(f"  如需恢复，请使用备份文件: {backup_path}")


if __name__ == '__main__':
    main()
