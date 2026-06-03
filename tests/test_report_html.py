#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""report_html.parse_daily_report golden 回归。"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from report_html import parse_daily_report

EXPECTED = Path(__file__).parent / "expected"


class ReportHtmlGoldenTests(unittest.TestCase):
    def test_parse_daily_report_matches_golden(self):
        golden_path = EXPECTED / "report_html_parsed.json"
        if not golden_path.exists():
            self.skipTest("缺少 tests/expected/report_html_parsed.json")

        md_path = EXPECTED / "daily_report.md"
        actual = parse_daily_report(str(md_path))
        expected = json.loads(golden_path.read_text(encoding="utf-8"))
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
