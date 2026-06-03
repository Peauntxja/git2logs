#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查 PyInstaller onedir 产物是否混入应删除的大型依赖目录。

用法:
  python3 scripts/audit_bundle.py
  python3 scripts/audit_bundle.py dist/MIZUKI-TOOLBOX/_internal
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_DIR_NAMES = (
    "grpc",
    "numpy",
    "lxml",
    "PIL",
    "pandas",
    "matplotlib",
    "scipy",
    "torch",
    "tensorflow",
)

FORBIDDEN_SUBPATHS = (
    "googleapiclient/discovery_cache/documents",
)


def find_bundle_internal() -> Path | None:
    candidates = [
        ROOT / "dist" / "MIZUKI-TOOLBOX" / "_internal",
        ROOT / "dist" / "MIZUKI-TOOLBOX.app" / "Contents" / "Resources",
    ]
    for path in candidates:
        if path.is_dir():
            return path
    return None


def audit(internal_dir: Path) -> list[str]:
    issues: list[str] = []
    for name in FORBIDDEN_DIR_NAMES:
        if (internal_dir / name).exists():
            issues.append(f"禁止目录仍存在: {name}/")

    for sub in FORBIDDEN_SUBPATHS:
        if (internal_dir / sub).exists():
            issues.append(f"禁止路径仍存在: {sub}")

    return issues


def main() -> int:
    if len(sys.argv) > 1:
        internal = Path(sys.argv[1])
    else:
        internal = find_bundle_internal()

    if internal is None or not internal.is_dir():
        print("错误: 未找到打包 _internal 目录，请先 build_macos.sh", file=sys.stderr)
        return 1

    print(f"审计目录: {internal}")
    issues = audit(internal)
    if issues:
        print("审计失败:")
        for item in issues:
            print(f"  - {item}")
        return 1

    print("审计通过: 未发现禁止的大型依赖目录")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
