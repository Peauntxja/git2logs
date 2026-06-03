#!/usr/bin/env bash
# 本地回归：语法检查 + unittest（与 CI 一致）
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> py_compile (core)"
python3 -m py_compile \
  git2logs.py cli.py service.py report_html.py \
  git2logs_gui_ctk.py gui/entry.py gui/app.py

echo "==> unittest"
python3 -m unittest discover -s tests -p 'test_*.py' -v

echo "==> OK"
