#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""日报任务产出 DeepSeek 润色。"""
import json
import logging
import re

from ai_analysis import get_ai_service
from commit_analysis import get_commit_details, is_merge_commit

logger = logging.getLogger(__name__)


def _clean_subject(message: str) -> str:
    first = (message or "").split("\n")[0].strip()
    cleaned = re.sub(
        r"^(?:feat|fix|refactor|style|perf|chore|docs|test|build|ci|revert)(?:\([^)]*\))?:\s*",
        "",
        first,
        count=1,
        flags=re.I,
    ).strip()
    return cleaned or first

_MAX_COMMITS_PER_PROJECT = 12
_MAX_FILES_PER_COMMIT = 8
_MAX_DIFF_CHARS = 240
_MAX_PROMPT_CHARS = 14000

_SYSTEM = (
    "你是资深研发写日报助手。公司会统一拉取日报核算工时，文案需体现工作饱和、任务扎实、技术深度。"
    "必须严格基于给定的 Git 提交与代码变更展开，不得编造会议、运维、文档等无关事项，不得输出仓库地址列表。"
    "task_type 简洁专业；task_summary 一句标题简述；task_output 为 3～6 句中文长段落，"
    "交代背景、改动点、联调/自测与结果，语气正式、信息密度高，足以支撑对应工时。"
    '只返回 JSON：{"projects":[{"project_path":"...","task_type":"...","task_summary":"...","task_output":"..."}]}。'
)


def _collect_project_context(all_results):
    projects = []
    for project_path, result in all_results.items():
        project = result.get("project")
        commits = []
        for commit in result.get("commits") or []:
            if is_merge_commit(getattr(commit, "message", "")):
                continue
            subject = _clean_subject(getattr(commit, "message", "") or "")
            entry = {
                "id": (getattr(commit, "id", "") or "")[:8],
                "subject": subject,
                "files": [],
                "additions": 0,
                "deletions": 0,
            }
            try:
                details = get_commit_details(project, commit)
                stats = details.get("stats") or {}
                entry["additions"] = int(stats.get("additions") or 0)
                entry["deletions"] = int(stats.get("deletions") or 0)
                for file_info in (details.get("changed_files") or [])[:_MAX_FILES_PER_COMMIT]:
                    path = file_info.get("new_path") or file_info.get("path") or file_info.get("old_path") or ""
                    if not path or path.startswith("..."):
                        continue
                    diff = (file_info.get("diff") or "")[:_MAX_DIFF_CHARS]
                    item = {"path": path}
                    if diff:
                        item["diff"] = diff
                    entry["files"].append(item)
            except Exception as exc:
                logger.debug("润色收集 commit 详情失败 %s: %s", entry["id"], exc)
            commits.append(entry)
            if len(commits) >= _MAX_COMMITS_PER_PROJECT:
                break
        if not commits:
            continue
        projects.append({
            "project_path": project_path,
            "project_name": getattr(project, "name", None) or project_path,
            "commits": commits,
        })
    return projects


def _build_prompt(projects):
    body = json.dumps(projects, ensure_ascii=False, indent=2)
    if len(body) > _MAX_PROMPT_CHARS:
        body = body[:_MAX_PROMPT_CHARS] + "\n...(已截断)"
    return (
        "请为下列每个项目生成日报字段。\n"
        "要求：\n"
        "1. task_type 用顿号连接，如「功能开发、问题修复」\n"
        "2. task_summary：一句标题简述，放入标题括号，不超过 40 字\n"
        "3. task_output：3～6 句扎实长段落，综合 commit、文件变更与行数统计，"
        "体现分析、实现、联调/验证与收尾，让阅读者感到当日工作饱满；禁止空话套话\n"
        "4. project_path 必须与输入完全一致\n"
        '5. 仅返回 JSON 对象 {"projects":[...]}\n\n'
        f"项目数据：\n{body}"
    )


def _parse_polish_list(text):
    raw = text or ""
    if "```json" in raw:
        start = raw.find("```json") + 7
        end = raw.find("```", start)
        raw = raw[start:end].strip()
    elif "```" in raw:
        start = raw.find("```") + 3
        end = raw.find("```", start)
        raw = raw[start:end].strip()
    try:
        parsed = json.loads(raw.strip())
    except json.JSONDecodeError:
        match = re.search(r"\[[\s\S]*\]", text or "")
        if not match:
            raise ValueError("无法解析润色 JSON")
        parsed = json.loads(match.group(0))
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        for key in ("projects", "items", "data", "result"):
            if isinstance(parsed.get(key), list):
                return parsed[key]
        if "project_path" in parsed:
            return [parsed]
    raise ValueError("润色结果不是 JSON 数组")


def polish_daily_projects(all_results, api_key, model=None):
    """
    返回 {project_path: {"task_type", "task_summary", "task_output"}}。
    无提交或失败时返回 {}。
    """
    projects = _collect_project_context(all_results)
    if not projects:
        return {}

    service_cls = get_ai_service("deepseek")
    service = service_cls(api_key=api_key, model=model or "deepseek-v4-pro")
    raw = service._make_api_call(_build_prompt(projects), _SYSTEM)
    items = _parse_polish_list(raw)

    result = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        path = (item.get("project_path") or "").strip()
        task_type = (item.get("task_type") or "").strip()
        summary = (item.get("task_summary") or "").strip()
        output = (item.get("task_output") or "").strip()
        if path and (summary or output):
            result[path] = {
                "task_type": task_type or "代码开发",
                "task_summary": summary or (output[:40] + "…" if len(output) > 40 else output),
                "task_output": output or summary,
            }
    return result
