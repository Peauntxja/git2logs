#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Golden 回归：核心报告/工时/Excel 规则在固定 fixture 下输出稳定。"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.helpers.fake_gitlab import build_sample_all_results, build_grouped_commits
from tests.helpers.normalize import normalize_report_text
from report_generator import (
    generate_statistics_report,
    generate_work_hours_report,
    generate_daily_report,
    generate_markdown_log,
)
from work_hours import calculate_work_hours
from excel_exporter import merge_and_normalize_tasks, fill_excel_template

EXPECTED = Path(__file__).parent / "expected"
FIXTURES = Path(__file__).parent / "fixtures"

AUTHOR = "MIZUKI"
SINCE = "2026-01-15"
UNTIL = "2026-01-15"


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
        self.assertEqual(
            normalize_report_text(actual),
            _load_expected("statistics.md"),
        )

    def test_daily_report_matches_golden(self):
        with mock.patch("report_generator.get_commit_details", side_effect=_fake_commit_details):
            actual = generate_daily_report(
                build_sample_all_results(), AUTHOR,
                since_date=SINCE, until_date=UNTIL, branch="main",
            )
        self.assertEqual(
            normalize_report_text(actual),
            _load_expected("daily_report.md"),
        )

    def test_work_hours_report_matches_golden(self):
        actual = generate_work_hours_report(
            build_sample_all_results(), AUTHOR,
            since_date=SINCE, until_date=UNTIL, branch="main",
        )
        self.assertEqual(
            normalize_report_text(actual),
            _load_expected("work_hours.md"),
        )

    def test_commits_markdown_matches_golden(self):
        actual = generate_markdown_log(
            build_grouped_commits(), AUTHOR,
            repo_name="demo/project-a", project=None,
        )
        self.assertEqual(
            normalize_report_text(actual),
            _load_expected("commits.md"),
        )

    def test_work_hours_data_matches_golden(self):
        actual = calculate_work_hours(
            build_sample_all_results(),
            since_date=SINCE, until_date=UNTIL, branch="main",
        )
        expected = json.loads(_load_expected("work_hours_data.json"))
        self.assertEqual(actual, expected)

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
        actual = merge_and_normalize_tasks(tasks)
        expected = json.loads(_load_expected("excel_merged_tasks.json"))
        self.assertEqual(actual, expected)

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


if __name__ == "__main__":
    unittest.main()
