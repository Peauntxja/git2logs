#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CLI 参数解析与格式映射（无网络）。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cli import build_argument_parser, cli_output_format, cli_report_type_name


class CliParserTests(unittest.TestCase):
    def test_scan_all_daily_report_format_mapping(self):
        parser = build_argument_parser()
        args = parser.parse_args([
            "--scan-all",
            "--gitlab-url",
            "http://gitlab.example.com",
            "--author",
            "MIZUKI",
            "--daily-report",
        ])
        self.assertEqual(cli_output_format(args), "daily_report")
        self.assertEqual(cli_report_type_name(args), "daily_report")

    def test_single_repo_defaults_to_commits(self):
        parser = build_argument_parser()
        args = parser.parse_args([
            "--repo",
            "group/project",
            "--author",
            "MIZUKI",
        ])
        self.assertEqual(cli_output_format(args), "commits")
        self.assertEqual(cli_report_type_name(args), "all_projects")


if __name__ == "__main__":
    unittest.main()
