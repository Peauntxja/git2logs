#!/bin/bash
# macOS 打包脚本 — 使用 MIZUKI-TOOLBOX.spec（与 Windows 模块列表一致）

set -e

echo "=========================================="
echo "MIZUKI-TOOLBOX - macOS 打包"
echo "=========================================="

if ! command -v pyinstaller &> /dev/null && ! python3 -m PyInstaller --version &> /dev/null; then
    echo "错误: PyInstaller 未安装"
    echo "请运行: pip install pyinstaller"
    exit 1
fi

if command -v pyinstaller &> /dev/null; then
    PYINSTALLER_CMD="pyinstaller"
else
    PYINSTALLER_CMD="python3 -m PyInstaller"
fi

if [ ! -f "MIZUKI-TOOLBOX.spec" ]; then
    echo "错误: 未找到 MIZUKI-TOOLBOX.spec"
    exit 1
fi

echo "检查依赖..."
pip3 install python-gitlab customtkinter openpyxl || true
pip3 install openai anthropic google-genai || echo "提示: 部分 AI 依赖未安装，打包后 AI 可能不可用"

echo "清理之前的构建..."
rm -rf build dist

echo "开始打包（onedir, arm64）..."
$PYINSTALLER_CMD --clean --noconfirm MIZUKI-TOOLBOX.spec

if [ ! -d "dist" ]; then
    echo "✗ 打包失败"
    exit 1
fi

echo "✓ 打包成功！"

APP_BUNDLE="dist/MIZUKI-TOOLBOX.app"
ONEDIR="dist/MIZUKI-TOOLBOX"
INTERNAL=""

if [ -d "$APP_BUNDLE/Contents/Resources" ]; then
    INTERNAL="$APP_BUNDLE/Contents/Resources"
elif [ -d "$ONEDIR/_internal" ]; then
    INTERNAL="$ONEDIR/_internal"
fi

if [ -n "$INTERNAL" ]; then
    bash scripts/post_pyinstaller_clean.sh "$INTERNAL"
    python3 scripts/audit_bundle.py "$INTERNAL" || exit 1
else
    echo "⚠ 未找到 Resources/_internal 目录，跳过清理与审计"
fi

# BUNDLE 模式下 PyInstaller 会同时留下 onedir，删除以免 DMG 重复打包
if [ -d "$APP_BUNDLE" ] && [ -d "$ONEDIR" ]; then
    rm -rf "$ONEDIR"
fi

if [ -d "$APP_BUNDLE" ]; then
    CLEANED_SIZE=$(du -sh "$APP_BUNDLE" 2>/dev/null | cut -f1)
    echo "✓ 产物大小: $CLEANED_SIZE"
    echo "应用包位置: $APP_BUNDLE"
elif [ -d "$ONEDIR" ]; then
    CLEANED_SIZE=$(du -sh "$ONEDIR" 2>/dev/null | cut -f1)
    echo "✓ 产物大小: $CLEANED_SIZE"
    echo "应用目录位置: $ONEDIR"
fi

if command -v hdiutil &> /dev/null; then
    echo "创建 DMG 文件..."
    APP_NAME="MIZUKI-TOOLBOX"
    TEMP_DIR=$(mktemp -d)
    if [ -d "$APP_BUNDLE" ]; then
        cp -R "$APP_BUNDLE" "$TEMP_DIR/"
    elif [ -d "dist/MIZUKI-TOOLBOX" ]; then
        cp -R "dist/MIZUKI-TOOLBOX" "$TEMP_DIR/"
    fi
    hdiutil create -volname "$APP_NAME" \
        -srcfolder "$TEMP_DIR" \
        -ov -format UDZO \
        "dist/${APP_NAME}.dmg"
    rm -rf "$TEMP_DIR"
    echo "✓ DMG 文件已创建: dist/${APP_NAME}.dmg"
fi

echo "=========================================="
echo "打包完成！"
echo "=========================================="
