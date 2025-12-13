#!/bin/bash
# macOS 打包脚本
# 使用 PyInstaller 将应用打包成 macOS 应用和 DMG

set -e

echo "=========================================="
echo "GitLab 提交日志生成工具 - macOS 打包"
echo "=========================================="

# 检查 PyInstaller 是否安装
if ! command -v pyinstaller &> /dev/null && ! python3 -m PyInstaller --version &> /dev/null; then
    echo "错误: PyInstaller 未安装"
    echo "请运行: pip install pyinstaller"
    exit 1
fi

# 确定 PyInstaller 命令
if command -v pyinstaller &> /dev/null; then
    PYINSTALLER_CMD="pyinstaller"
else
    PYINSTALLER_CMD="python3 -m PyInstaller"
fi

# 检查依赖
echo "检查依赖..."
pip3 install -r requirements.txt

# 清理之前的构建
echo "清理之前的构建..."
rm -rf build dist *.spec

# 检查图标文件
ICON_FILE="app_icon.icns"
if [ ! -f "$ICON_FILE" ]; then
    echo "警告: 未找到图标文件 $ICON_FILE"
    echo "提示: 运行 ./create_icons.sh <图片文件> 创建图标"
    ICON_PARAM=""
else
    echo "使用图标: $ICON_FILE"
    ICON_PARAM="--icon=$ICON_FILE"
fi

# 使用 PyInstaller 打包
echo "开始打包..."
$PYINSTALLER_CMD --name="GitLab提交日志生成工具" \
    --windowed \
    --onefile \
    --add-data "git2logs.py:." \
    --add-data "generate_report_image.py:." \
    --hidden-import=tkinter \
    --hidden-import=gitlab \
    --hidden-import=tkinter.ttk \
    --hidden-import=tkinter.scrolledtext \
    --hidden-import=tkinter.messagebox \
    --hidden-import=tkinter.filedialog \
    $ICON_PARAM \
    git2logs_gui.py

# 检查是否成功
if [ -d "dist" ]; then
    echo "✓ 打包成功！"
    echo "可执行文件位置: dist/GitLab提交日志生成工具"
    
    # 创建 DMG（需要 hdiutil）
    if command -v hdiutil &> /dev/null; then
        echo "创建 DMG 文件..."
        APP_NAME="GitLab提交日志生成工具"
        DMG_NAME="${APP_NAME}.dmg"
        
        # 创建临时目录
        TEMP_DIR=$(mktemp -d)
        cp -R "dist/${APP_NAME}" "$TEMP_DIR/"
        
        # 创建 DMG
        hdiutil create -volname "$APP_NAME" \
            -srcfolder "$TEMP_DIR" \
            -ov -format UDZO \
            "dist/${DMG_NAME}"
        
        rm -rf "$TEMP_DIR"
        echo "✓ DMG 文件已创建: dist/${DMG_NAME}"
    else
        echo "提示: 未找到 hdiutil，跳过 DMG 创建"
    fi
else
    echo "✗ 打包失败"
    exit 1
fi

echo "=========================================="
echo "打包完成！"
echo "=========================================="

