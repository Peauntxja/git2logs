#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Git2LogsService.fetch_commits 行为测试（无网络）。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models import GitLabConnectionError, ReportParams
from service import Git2LogsService


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

        self.assertEqual(len(result), 1)
        entry = next(iter(result.values()))
        self.assertIs(entry["project"], project)
        self.assertEqual(entry["commits"], [commit])

    @mock.patch("service.create_gitlab_client")
    def test_fetch_commits_strict_raises_on_project_error(self, mock_create_client):
        mock_gl = mock.Mock()
        mock_gl.projects.get.side_effect = RuntimeError("404 Project Not Found")
        mock_create_client.return_value = mock_gl

        with self.assertRaises(GitLabConnectionError):
            Git2LogsService().fetch_commits(
                self._params(),
                strict_single_project=True,
            )


if __name__ == "__main__":
    unittest.main()
