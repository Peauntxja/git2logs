#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试公共路径与常量。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TESTS_DIR = Path(__file__).resolve().parent
EXPECTED = TESTS_DIR / "expected"
FIXTURES = TESTS_DIR / "fixtures"

AUTHOR = "MIZUKI"
SINCE = "2026-01-15"
UNTIL = "2026-01-15"
