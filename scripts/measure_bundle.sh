#!/bin/bash
# 记录 PyInstaller onedir 产物体积，并与上次 build/metrics.json 对比。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

BUNDLE_DIR=""
if [ -d "dist/MIZUKI-TOOLBOX/_internal" ]; then
  BUNDLE_DIR="dist/MIZUKI-TOOLBOX/_internal"
elif [ -d "dist/MIZUKI-TOOLBOX.app/Contents/Resources" ]; then
  BUNDLE_DIR="dist/MIZUKI-TOOLBOX.app/Contents/Resources"
else
  echo "错误: 未找到打包产物。请先运行 build_macos.sh"
  exit 1
fi

METRICS_DIR="$ROOT/build"
METRICS_FILE="$METRICS_DIR/metrics.json"
mkdir -p "$METRICS_DIR"

TOTAL_KB=$(du -sk "$BUNDLE_DIR" | awk '{print $1}')
TOTAL_HUMAN=$(du -sh "$BUNDLE_DIR" | awk '{print $1}')
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

TOP_JSON=$(du -sk "$BUNDLE_DIR"/* 2>/dev/null | sort -nr | head -15 | awk '{printf "%s:%s\n", $2, $1}' | paste -sd, -)

python3 - "$METRICS_FILE" "$TIMESTAMP" "$TOTAL_KB" "$TOTAL_HUMAN" "$BUNDLE_DIR" "$TOP_JSON" <<'PY'
import json
import sys
from pathlib import Path

metrics_path = Path(sys.argv[1])
timestamp = sys.argv[2]
total_kb = int(sys.argv[3])
total_human = sys.argv[4]
bundle_dir = sys.argv[5]
top_pairs = sys.argv[6].split(",") if sys.argv[6] else []
top_dirs = []
for pair in top_pairs:
    if not pair.strip():
        continue
    path, kb = pair.rsplit(":", 1)
    top_dirs.append({"path": Path(path).name, "size_kb": int(kb)})

prev = None
if metrics_path.exists():
    try:
        prev = json.loads(metrics_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        prev = None

entry = {
    "timestamp": timestamp,
    "bundle_dir": bundle_dir,
    "total_kb": total_kb,
    "total_human": total_human,
    "top_dirs": top_dirs,
}
history = []
if prev and isinstance(prev.get("history"), list):
    history = prev["history"][-9:]
history.append(entry)

out = {"latest": entry, "history": history}
if prev and "latest" in prev:
    delta_kb = total_kb - int(prev["latest"].get("total_kb", total_kb))
    entry["delta_kb_vs_previous"] = delta_kb

metrics_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"体积: {total_human} ({total_kb} KB)")
if "delta_kb_vs_previous" in entry:
    sign = "+" if entry["delta_kb_vs_previous"] >= 0 else ""
    print(f"较上次: {sign}{entry['delta_kb_vs_previous']} KB")
print(f"已写入: {metrics_path}")
print("")
print("Top 目录:")
for item in top_dirs[:10]:
    print(f"  {item['size_kb']:>6} KB  {item['path']}")
PY
