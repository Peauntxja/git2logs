#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
离线回归测试（无 GitLab 网络）。

覆盖：报告 golden、HTML 解析、CLI 映射、fetch_commits mock。
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests._common import AUTHOR, EXPECTED, FIXTURES, SINCE, UNTIL
from tests.helpers.fake_gitlab import build_grouped_commits, build_sample_all_results
from tests.helpers.normalize import normalize_report_text

from cli import build_argument_parser, cli_output_format, cli_report_type_name
from excel_exporter import fill_excel_template, merge_and_normalize_tasks
from models import GitLabConnectionError, ReportParams
from report_generator import (
    generate_daily_report,
    generate_markdown_log,
    generate_statistics_report,
    generate_work_hours_report,
)
from report_html import generate_html_report, parse_daily_report
from service import Git2LogsService
from work_hours import calculate_work_hours


def _load_expected(name: str) -> str:
    return (EXPECTED / name).read_text(encoding="utf-8")


def _fake_commit_details(_project, commit):
    msg = (commit.message or "").split("\n")[0]
    return {
        "short_message": msg,
        "full_message": commit.message or "",
        "stats": None,
        "changed_files": [],
    }


class GoldenReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (EXPECTED / "statistics.md").exists():
            raise unittest.SkipTest(
                "缺少 tests/expected，请先运行: python3 scripts/update_golden_fixtures.py"
            )

    def test_statistics_report_matches_golden(self):
        actual = generate_statistics_report(
            build_sample_all_results(), AUTHOR,
            since_date=SINCE, until_date=UNTIL,
        )
        self.assertEqual(normalize_report_text(actual), _load_expected("statistics.md"))

    def test_daily_report_matches_golden(self):
        with mock.patch("report_generator.get_commit_details", side_effect=_fake_commit_details):
            actual = generate_daily_report(
                build_sample_all_results(), AUTHOR,
                since_date=SINCE, until_date=UNTIL, branch="main",
            )
        self.assertEqual(normalize_report_text(actual), _load_expected("daily_report.md"))

    def test_work_hours_report_matches_golden(self):
        actual = generate_work_hours_report(
            build_sample_all_results(), AUTHOR,
            since_date=SINCE, until_date=UNTIL, branch="main",
        )
        self.assertEqual(normalize_report_text(actual), _load_expected("work_hours.md"))

    def test_commits_markdown_matches_golden(self):
        actual = generate_markdown_log(
            build_grouped_commits(), AUTHOR,
            repo_name="demo/project-a", project=None,
        )
        self.assertEqual(normalize_report_text(actual), _load_expected("commits.md"))

    def test_work_hours_data_matches_golden(self):
        actual = calculate_work_hours(
            build_sample_all_results(),
            since_date=SINCE, until_date=UNTIL, branch="main",
        )
        self.assertEqual(actual, json.loads(_load_expected("work_hours_data.json")))

    def test_excel_merge_rules_match_golden(self):
        wh_data = json.loads(_load_expected("work_hours_data.json"))
        tasks = []
        for date_str, date_data in wh_data.items():
            for _proj, pdata in date_data.get("projects", {}).items():
                for task in pdata.get("tasks", []):
                    tasks.append({
                        "task_name": task["task_name"],
                        "hours": task["hours"],
                        "start_date": date_str,
                        "end_date": date_str,
                        "description": task["task_name"],
                        "task_type": task.get("task_type", ""),
                    })
        self.assertEqual(
            merge_and_normalize_tasks(tasks),
            json.loads(_load_expected("excel_merged_tasks.json")),
        )

    def test_fill_excel_template_row_count(self):
        try:
            import openpyxl  # noqa: F401
        except ImportError:
            self.skipTest("openpyxl 未安装")

        template = FIXTURES / "work_hours_template.xlsx"
        if not template.exists():
            self.skipTest("缺少 tests/fixtures/work_hours_template.xlsx")

        wh_data = json.loads(_load_expected("work_hours_data.json"))
        meta = json.loads(_load_expected("meta.json"))
        out = FIXTURES / "_test_export_output.xlsx"
        if out.exists():
            out.unlink()

        count = fill_excel_template(
            template_path=template,
            work_hours_data=wh_data,
            output_path=out,
        )
        self.assertEqual(count, meta["excel_expected_row_count"])
        self.assertTrue(out.exists())
        out.unlink()


class ReportHtmlTests(unittest.TestCase):
    def test_parse_daily_report_matches_golden(self):
        golden_path = EXPECTED / "report_html_parsed.json"
        if not golden_path.exists():
            self.skipTest("缺少 report_html_parsed.json")

        actual = parse_daily_report(str(EXPECTED / "daily_report.md"))
        expected = json.loads(golden_path.read_text(encoding="utf-8"))
        self.assertEqual(actual, expected)

    def test_generate_html_report_includes_sorted_timeline(self):
        golden_path = EXPECTED / "report_html_parsed.json"
        if not golden_path.exists():
            self.skipTest("缺少 report_html_parsed.json")

        data = json.loads(golden_path.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "daily.html"
            generate_html_report(data, str(out))
            html = out.read_text(encoding="utf-8")
        self.assertIn("10:30", html)
        self.assertIn("16:45", html)
        self.assertLess(html.index("10:30"), html.index("16:45"))


class CliParserTests(unittest.TestCase):
    def test_scan_all_daily_report_format_mapping(self):
        args = build_argument_parser().parse_args([
            "--scan-all", "--gitlab-url", "http://gitlab.example.com",
            "--author", "MIZUKI", "--daily-report",
        ])
        self.assertEqual(cli_output_format(args), "daily_report")
        self.assertEqual(cli_report_type_name(args), "daily_report")

    def test_single_repo_defaults_to_commits(self):
        args = build_argument_parser().parse_args([
            "--repo", "group/project", "--author", "MIZUKI",
        ])
        self.assertEqual(cli_output_format(args), "commits")
        self.assertEqual(cli_report_type_name(args), "all_projects")


class FetchCommitsTests(unittest.TestCase):
    def _params(self, **kwargs) -> ReportParams:
        base = dict(
            gitlab_url="http://gitlab.example.com",
            token="token",
            author="MIZUKI",
            scan_all=False,
            repo_url="http://gitlab.example.com/group/project.git",
        )
        base.update(kwargs)
        return ReportParams(**base)

    @mock.patch("service.create_gitlab_client")
    @mock.patch("service.get_commits_by_author")
    def test_fetch_commits_single_project_returns_results(
        self, mock_get_commits, mock_create_client,
    ):
        project = mock.Mock(name="Demo")
        commit = mock.Mock(message="feat: test")
        mock_gl = mock.Mock()
        mock_gl.projects.get.return_value = project
        mock_get_commits.return_value = [commit]
        mock_create_client.return_value = mock_gl

        result = Git2LogsService().fetch_commits(self._params())
        entry = next(iter(result.values()))
        self.assertEqual(entry["commits"], [commit])

    @mock.patch("service.create_gitlab_client")
    def test_fetch_commits_strict_raises_on_project_error(self, mock_create_client):
        mock_gl = mock.Mock()
        mock_gl.projects.get.side_effect = RuntimeError("404 Project Not Found")
        mock_create_client.return_value = mock_gl

        with self.assertRaises(GitLabConnectionError):
            Git2LogsService().fetch_commits(
                self._params(), strict_single_project=True,
            )


class CommitAnalysisTests(unittest.TestCase):
    def test_is_merge_commit(self):
        from commit_analysis import is_merge_commit

        self.assertTrue(is_merge_commit("Merge branch 'test' of http://gitlab.example.com/a into test"))
        self.assertTrue(is_merge_commit("merge pull request !123 from feature/foo"))
        self.assertFalse(is_merge_commit("feat(auth): 增加登录校验"))

    def test_analyze_commit_type_perf(self):
        from commit_analysis import analyze_commit_type

        self.assertEqual(analyze_commit_type("perf(views): 优化委员会组织树加载体验"), ("性能优化", "⚡"))

    def test_feat_with_fix_keyword_is_bugfix(self):
        from commit_analysis import analyze_commit_type

        self.assertEqual(analyze_commit_type("feat:修复新增时 id 传参"), ("Bug修复", "🐛"))
        self.assertEqual(analyze_commit_type("feat(auth): 增加登录校验"), ("功能开发", "✨"))

    def test_format_date_chinese_strips_whitespace(self):
        from utils.date_utils import format_date_chinese

        self.assertEqual(format_date_chinese(" 2026-06-08 "), "2026年06月08日")
        self.assertEqual(format_date_chinese("2026-08-06"), "2026年08月06日")


class BranchSkipTests(unittest.TestCase):
    def _branch(self, committed_date: str):
        commit = mock.Mock()
        commit.committed_date = committed_date
        branch = mock.Mock()
        branch.commit = commit
        branch.name = "main"
        return branch

    def test_tip_after_until_must_not_skip(self):
        """查昨天时 tip 已到今天，仍应查询（旧逻辑会误跳过）。"""
        from gitlab_client import _should_skip_branch

        branch = self._branch("2026-08-07T10:00:00Z")
        self.assertFalse(
            _should_skip_branch(branch, since_date="2026-08-06", until_date="2026-08-06")
        )

    def test_tip_before_since_skips(self):
        from gitlab_client import _should_skip_branch

        branch = self._branch("2026-08-01T10:00:00Z")
        self.assertTrue(
            _should_skip_branch(branch, since_date="2026-08-06", until_date="2026-08-06")
        )

    def test_morning_shanghai_tip_not_skipped(self):
        """上海早上 7:30 提交（UTC 前一天 23:30），查当天不应跳过。"""
        from gitlab_client import _should_skip_branch

        branch = self._branch("2026-08-05T23:30:00Z")
        self.assertFalse(
            _should_skip_branch(branch, since_date="2026-08-06", until_date="2026-08-06")
        )


class TimezoneTests(unittest.TestCase):
    def test_to_gitlab_datetime_shanghai_day(self):
        from utils.date_utils import to_gitlab_datetime

        self.assertEqual(to_gitlab_datetime("2026-08-06"), "2026-08-05T16:00:00Z")
        self.assertEqual(
            to_gitlab_datetime("2026-08-06", end_of_day=True),
            "2026-08-06T15:59:59Z",
        )

    def test_morning_commit_maps_to_shanghai_day(self):
        from utils.date_utils import to_local_date_str

        self.assertEqual(to_local_date_str("2026-08-05T23:30:00Z"), "2026-08-06")


if __name__ == "__main__":
    unittest.main()
