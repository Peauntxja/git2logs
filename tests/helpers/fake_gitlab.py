#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GitLab API 对象的轻量替身，供 golden 测试使用（无网络）。"""


class FakeProject:
    def __init__(self, name: str, web_url: str, project_id: int = 1):
        self.name = name
        self.web_url = web_url
        self.id = project_id


class FakeCommit:
    def __init__(
        self,
        commit_id: str,
        message: str,
        committed_date: str,
        web_url: str = "",
    ):
        self.id = commit_id
        self.message = message
        self.committed_date = committed_date
        self.web_url = web_url or f"https://gitlab.example.com/demo/-/commit/{commit_id}"


def build_sample_all_results():
    """固定样本：单日、单项目、两条提交。"""
    project = FakeProject(
        name="Demo Project",
        web_url="https://gitlab.example.com/demo/project-a",
    )
    commits = [
        FakeCommit(
            "a1b2c3d4e5f6789012345678901234567890ab",
            "feat(auth): 增加登录校验",
            # 上海 10:30 / 16:45 → UTC 02:30 / 08:45
            "2026-01-15T02:30:00Z",
        ),
        FakeCommit(
            "b2c3d4e5f6789012345678901234567890abcd",
            "fix(ui): 修复按钮样式",
            "2026-01-15T08:45:00Z",
        ),
    ]
    return {
        "demo/project-a": {
            "project": project,
            "commits": commits,
        }
    }


def build_grouped_commits():
    """按日期分组的提交（用于 commits Markdown）。"""
    results = build_sample_all_results()
    return {"2026-01-15": results["demo/project-a"]["commits"]}
