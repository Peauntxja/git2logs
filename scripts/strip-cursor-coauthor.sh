#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! git rev-parse --git-dir >/dev/null 2>&1; then
  echo "错误: 当前目录不是 git 仓库" >&2
  exit 1
fi

echo "正在重写提交信息，移除 Co-authored-by: Cursor …"
FILTER_BRANCH_SQUELCH_WARNING=1 git filter-branch -f --msg-filter \
  "grep -v '^Co-authored-by: Cursor <cursoragent@cursor.com>\$'" \
  -- --all

echo "完成。请执行: git push --force-with-lease origin main"
