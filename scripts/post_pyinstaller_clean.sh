#!/bin/bash
# PyInstaller onedir 打包后删除未使用的大型依赖（macOS / Linux 路径）
set -euo pipefail

INTERNAL_DIR="${1:-dist/MIZUKI-TOOLBOX/_internal}"
if [ ! -d "$INTERNAL_DIR" ]; then
  echo "跳过清理: 未找到 $INTERNAL_DIR"
  exit 0
fi

echo "清理不必要的依赖文件..."
rm -rf "$INTERNAL_DIR/googleapiclient/discovery_cache/documents"
rm -rf "$INTERNAL_DIR/grpc"
rm -rf "$INTERNAL_DIR/numpy"
rm -rf "$INTERNAL_DIR"/numpy-*.dist-info
rm -rf "$INTERNAL_DIR/lxml"
rm -rf "$INTERNAL_DIR/PIL"
rm -rf "$INTERNAL_DIR/googleapiclient/discovery_cache/documents"
echo "✓ 清理完成"
