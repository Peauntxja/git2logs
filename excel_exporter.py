#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Excel 工时模板填充模块

读取 Excel 模板，将工时分配数据填入对应字段。
支持的模板字段：任务名称、预计工时、计划开始日期、计划结束日期、任务描述

合并规则：
- 工时 >= 1h 的任务：保留，每条最高截断至 8h
- 工时 < 1h 的任务（同一天）：合并为「综合开发」条目
  - 合并后总工时不足 1h：补齐至 1h
  - 合并后总工时超过 8h：拆分为多条（每条 ≤ 8h）
"""
from __future__ import annotations

import logging
from copy import copy
from pathlib import Path

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

logger = logging.getLogger(__name__)

# 需要识别并填充的表头关键字 -> 内部字段名
HEADER_FIELD_MAP: dict[str, str] = {
    "任务名称": "task_name",
    "预计工时": "hours",
    "计划开始日期": "start_date",
    "计划结束日期": "end_date",
    "任务描述": "description",
}


def _check_openpyxl() -> None:
    if not OPENPYXL_AVAILABLE:
        raise ImportError("未安装 openpyxl，请运行: pip install openpyxl")


def _find_header_row(ws) -> int | None:
    """扫描工作表，返回包含表头关键字的行号（1-indexed）。"""
    for row_idx, row in enumerate(ws.iter_rows(), start=1):
        for cell in row:
            if cell.value and str(cell.value).strip() in HEADER_FIELD_MAP:
                return row_idx
    return None


def _find_column_map(ws, header_row: int) -> dict[str, int]:
    """返回 {字段名: 列号} 映射。"""
    col_map: dict[str, int] = {}
    for cell in ws[header_row]:
        if cell.value:
            key = str(cell.value).strip()
            if key in HEADER_FIELD_MAP:
                col_map[HEADER_FIELD_MAP[key]] = cell.column
    return col_map


def _copy_cell_style(src_cell, dst_cell) -> None:
    """将源单元格的样式复制到目标单元格。"""
    if src_cell.has_style:
        dst_cell.font = copy(src_cell.font)
        dst_cell.fill = copy(src_cell.fill)
        dst_cell.alignment = copy(src_cell.alignment)
        dst_cell.border = copy(src_cell.border)
        dst_cell.number_format = src_cell.number_format


def merge_and_normalize_tasks(tasks: list[dict]) -> list[dict]:
    """
    对任务列表进行合并与规范化（针对同一天的任务）。

    规则：
    - 工时 >= 1h：保留，单条上限截断至 8h
    - 工时 < 1h：合并为「综合开发」条目
        - 合并后不足 1h → 补齐至 1h
        - 合并后超过 8h → 拆分为多条（每条 ≤ 8h）
    """
    large = [t for t in tasks if t["hours"] >= 1.0]
    small = [t for t in tasks if t["hours"] < 1.0]

    result: list[dict] = []

    # 大任务：单条截断至 8h
    for t in large:
        merged = t.copy()
        merged["hours"] = min(round(t["hours"], 2), 8.0)
        result.append(merged)

    if not small:
        return result

    # 合并小任务
    total = sum(t["hours"] for t in small)
    total = max(total, 1.0)          # 最低 1h

    names = [t["task_name"] for t in small]
    preview = names[:4]
    merged_name = "综合开发: " + "、".join(preview)
    if len(names) > 4:
        merged_name += f" 等{len(names)}项"
    description = "合并小任务 (<1h): " + "; ".join(names)
    base = small[0]

    remaining = total
    while remaining > 0.009:          # 浮点安全阈值
        chunk = min(remaining, 8.0)
        result.append({
            "task_name": merged_name,
            "hours": round(chunk, 2),
            "start_date": base.get("start_date", ""),
            "end_date": base.get("end_date", ""),
            "description": description,
            "project_name": base.get("project_name", ""),
            "task_type": "综合",
        })
        remaining -= chunk

    return result


def collect_tasks(
    work_hours_data: dict,
    project_filters: list[str] | None = None,
) -> list[dict]:
    """
    从工时数据中收集任务列表，可按项目名称过滤，并按日期做合并规范化。

    Args:
        work_hours_data: calculate_work_hours() 返回的字典
        project_filters: 项目名称列表（精确匹配，为 None 或空则收集全部）

    Returns:
        list of task dicts, 已做合并规范化（每条 hours ∈ [1, 8]）
    """
    tasks_by_date: dict[str, list[dict]] = {}

    for date_str, date_data in sorted(work_hours_data.items()):
        for project_path, project_data in date_data.get("projects", {}).items():
            project_name = project_data.get("project_name", project_path)

            # 项目过滤（精确匹配项目名）
            if project_filters:
                if project_name not in project_filters:
                    continue

            for task in project_data.get("tasks", []):
                commit_id = task.get("commit_id", "")
                desc_parts = [task["task_name"]]
                if task.get("task_type"):
                    desc_parts.append(f"[{task['task_type']}]")
                if commit_id:
                    desc_parts.append(f"(commit: {commit_id})")

                tasks_by_date.setdefault(date_str, []).append({
                    "task_name": task["task_name"],
                    "hours": task["hours"],
                    "start_date": date_str,
                    "end_date": date_str,
                    "description": " ".join(desc_parts),
                    "project_name": project_name,
                    "task_type": task.get("task_type", ""),
                })

    # 按日期排序，每天内做合并规范化
    result: list[dict] = []
    for date_str in sorted(tasks_by_date.keys()):
        result.extend(merge_and_normalize_tasks(tasks_by_date[date_str]))

    return result


def fill_excel_template(
    template_path: str | Path,
    work_hours_data: dict,
    output_path: str | Path,
    project_filters: list[str] | None = None,
) -> int:
    """
    将工时数据填入 Excel 模板并保存。

    模板约定：
    - 存在一行表头，包含"任务名称"、"预计工时"等关键字
    - 表头下方有一行示例数据（提供样式和其他列的默认值）
    - 函数会删除示例行，插入实际任务行

    Args:
        template_path: Excel 模板文件路径
        work_hours_data: calculate_work_hours() 返回的工时数据
        output_path: 输出 Excel 文件路径
        project_filters: 要导出的项目名称列表（精确匹配；None 则导出全部）

    Returns:
        写入的任务行数

    Raises:
        ImportError: openpyxl 未安装
        ValueError: 模板格式不符合预期 / 无可用数据
        FileNotFoundError: 模板文件不存在
    """
    _check_openpyxl()

    template_path = Path(template_path)
    if not template_path.exists():
        raise FileNotFoundError(f"模板文件不存在: {template_path}")

    tasks = collect_tasks(work_hours_data, project_filters)
    if not tasks:
        filter_hint = f"（已选项目：{', '.join(project_filters)}）" if project_filters else ""
        raise ValueError(f"未找到任何任务数据{filter_hint}，请先生成工时报告")

    wb = openpyxl.load_workbook(template_path)
    ws = wb.active

    # 1. 定位表头行
    header_row = _find_header_row(ws)
    if header_row is None:
        raise ValueError(
            "找不到表头行。请确认 Excel 模板包含以下列之一：\n"
            + "、".join(HEADER_FIELD_MAP.keys())
        )

    # 2. 获取列映射
    col_map = _find_column_map(ws, header_row)
    missing = [k for k, v in HEADER_FIELD_MAP.items() if v not in col_map]
    if missing:
        logger.warning("模板中未找到以下列（将跳过）: %s", "、".join(missing))

    if not col_map:
        raise ValueError("模板中没有可识别的目标列，请检查表头名称")

    # 3. 读取示例行（表头下一行）并记录整行样式
    example_row_idx = header_row + 1
    max_col = ws.max_column

    example_row_data: list[tuple] = []
    for col_idx in range(1, max_col + 1):
        cell = ws.cell(row=example_row_idx, column=col_idx)
        example_row_data.append((cell.value, cell if cell.has_style else None))

    # 4. 删除示例行
    ws.delete_rows(example_row_idx)

    # 5. 逐任务插入行
    insert_at = example_row_idx
    for i, task in enumerate(tasks):
        current_row = insert_at + i
        ws.insert_rows(current_row)

        # 先用示例行填充默认值和样式
        for col_idx, (default_val, src_cell) in enumerate(example_row_data, start=1):
            dst = ws.cell(row=current_row, column=col_idx)
            dst.value = default_val
            if src_cell is not None:
                _copy_cell_style(src_cell, dst)

        # 覆盖需要填充的字段
        field_values = {
            "task_name": task["task_name"],
            "hours": task["hours"],
            "start_date": task["start_date"],
            "end_date": task["end_date"],
            "description": task["description"],
        }
        for field, col_idx in col_map.items():
            if field in field_values:
                ws.cell(row=current_row, column=col_idx).value = field_values[field]

    wb.save(output_path)
    logger.info("Excel 导出完成：%s（共 %d 行）", output_path, len(tasks))
    return len(tasks)


def list_projects(work_hours_data: dict) -> list[str]:
    """返回工时数据中所有项目名称的去重排序列表。"""
    projects: set[str] = set()
    for date_data in work_hours_data.values():
        for project_data in date_data.get("projects", {}).values():
            projects.add(project_data.get("project_name", ""))
    return sorted(p for p in projects if p)


def parse_work_hours_md(content: str) -> dict:
    """
    将工时分配报告（Markdown 格式）解析回 work_hours_data 字典。

    支持单日和多日报告格式。返回的字典与 calculate_work_hours() 输出兼容。

    Args:
        content: Markdown 文件内容

    Returns:
        work_hours_data dict

    Raises:
        ValueError: 未找到有效的工时数据
    """
    import re

    result: dict = {}

    date_pattern = re.compile(r"\*\*统计日期\*\*[：:]\s*(\d{4}-\d{2}-\d{2})")
    total_hours_pattern = re.compile(r"\*\*标准工时\*\*[：:]\s*([\d.]+)")

    date_matches = list(date_pattern.finditer(content))
    if not date_matches:
        raise ValueError(
            "未找到工时数据。\n"
            "请确认所选文件是「工时分配报告」（包含「**统计日期**」字段）。"
        )

    for i, date_match in enumerate(date_matches):
        date_str = date_match.group(1)
        start = date_match.start()
        end = date_matches[i + 1].start() if i + 1 < len(date_matches) else len(content)
        section = content[start:end]

        th_match = total_hours_pattern.search(section)
        total_hours = float(th_match.group(1)) if th_match else 8.0

        # 解析 Markdown 表格行
        # 格式: | **项目名** (4.5h) | 任务名 | 任务类型 | 2.50 | commitid | branch | url |
        # 续行: |                   | 任务名 | 任务类型 | 2.00 | commitid | branch | url |
        table_row_pat = re.compile(r"^\|(.+)\|$", re.MULTILINE)
        projects: dict = {}
        current_project: str | None = None

        for row_str in table_row_pat.findall(section):
            cells = [c.strip() for c in row_str.split("|")]
            # 需要至少 4 列：项目/空、任务名、任务类型、工时
            if len(cells) < 4:
                continue
            # 跳过表头和分隔行
            if "项目名称" in cells[0] or "------" in cells[0]:
                continue

            project_cell = cells[0]
            task_name = cells[1] if len(cells) > 1 else ""
            task_type = cells[2] if len(cells) > 2 else ""
            hours_str = cells[3] if len(cells) > 3 else "0"
            commit_id = (cells[4] if len(cells) > 4 else "").strip()
            branch = (cells[5] if len(cells) > 5 else "").strip()

            # 判断是否有新项目名
            if project_cell:
                proj_match = re.match(r"\*\*(.+?)\*\*\s*\(([\d.]+)h\)", project_cell)
                if proj_match:
                    current_project = proj_match.group(1)
                    project_total = float(proj_match.group(2))
                    if current_project not in projects:
                        projects[current_project] = {
                            "project_name": current_project,
                            "total_hours": project_total,
                            "tasks": [],
                        }

            if not current_project or not task_name:
                continue

            try:
                hours = float(hours_str)
            except ValueError:
                hours = 0.0

            projects[current_project]["tasks"].append({
                "task_name": task_name,
                "task_type": task_type,
                "hours": hours,
                "commit_id": commit_id,
                "branch": branch,
                "commit_url": "",
                "gitlab_url": "",
                "commits": 1,
                "additions": 0,
                "deletions": 0,
            })

        if projects:
            result[date_str] = {
                "date": date_str,
                "total_hours": total_hours,
                "projects": projects,
            }

    if not result:
        raise ValueError("文件中未解析到有效的项目/任务数据，请检查报告格式。")

    return result


def load_work_hours_file(path: str) -> dict:
    """
    自动识别文件类型（.json / .md），加载并返回 work_hours_data 字典。

    Args:
        path: 文件路径（.json 或 .md）

    Returns:
        work_hours_data dict

    Raises:
        ValueError: 格式不支持或解析失败
        FileNotFoundError: 文件不存在
    """
    import json
    from pathlib import Path as _Path

    p = _Path(path)
    if not p.exists():
        raise FileNotFoundError(f"文件不存在: {path}")

    suffix = p.suffix.lower()
    content = p.read_text(encoding="utf-8")

    if suffix == ".json":
        data = json.loads(content)
        if not isinstance(data, dict) or not data:
            raise ValueError("JSON 文件格式不正确，应为工时数据字典")
        return data
    elif suffix in (".md", ".markdown"):
        return parse_work_hours_md(content)
    else:
        # 尝试 JSON 优先，再尝试 MD
        try:
            data = json.loads(content)
            if isinstance(data, dict) and data:
                return data
        except Exception:
            pass
        return parse_work_hours_md(content)
