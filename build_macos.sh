#!/bin/bash
# macOS 打包脚本
# 使用 PyInstaller 将应用打包成 macOS 应用和 DMG

set -e

echo "=========================================="
echo "MIZUKI-TOOLBOX - macOS 打包"
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
echo "安装核心依赖..."
pip3 install python-gitlab || echo "警告: python-gitlab 安装失败，但继续打包..."

echo "尝试安装AI依赖（可选，如果失败不影响打包）..."
pip3 install openai || echo "提示: openai 未安装，AI功能将不可用"
pip3 install anthropic || echo "提示: anthropic 未安装，AI功能将不可用"
pip3 install google-generativeai || echo "提示: google-generativeai 未安装，AI功能将不可用"

echo "安装 CustomTkinter（现代化UI）..."
pip3 install customtkinter || echo "警告: customtkinter 安装失败，将使用标准 tkinter 界面"

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

# 使用 PyInstaller 打包（使用 onedir 模式以提升启动速度）
echo "开始打包（使用 onedir 模式以提升启动速度）..."
$PYINSTALLER_CMD --name="MIZUKI-TOOLBOX" \
    --windowed \
    --onedir \
    --add-data "git2logs.py:." \
    --add-data "ai_analysis.py:." \
    --add-data "generate_report_image.py:." \
    --add-data "git2logs_gui_ctk.py:." \
    --hidden-import=tkinter \
    --hidden-import=gitlab \
    --hidden-import=tkinter.ttk \
    --hidden-import=tkinter.scrolledtext \
    --hidden-import=tkinter.messagebox \
    --hidden-import=tkinter.filedialog \
    --hidden-import=statistics \
    --hidden-import=openai \
    --hidden-import=anthropic \
    --hidden-import=google.generativeai \
    --hidden-import=ai_analysis \
    --hidden-import=customtkinter \
    --hidden-import=PIL \
    --hidden-import=PIL.Image \
    --hidden-import=PIL.ImageTk \
    $ICON_PARAM \
    git2logs_gui_ctk.py

# 检查是否成功
if [ -d "dist" ]; then
    echo "✓ 打包成功！"
    
    # onedir 模式下，应用在 dist/MIZUKI-TOOLBOX.app 目录中
    APP_DIR="dist/MIZUKI-TOOLBOX"
    APP_BUNDLE="${APP_DIR}.app"
    
    if [ -d "$APP_BUNDLE" ]; then
        echo "应用包位置: $APP_BUNDLE"
        echo "提示: onedir 模式启动速度更快，因为不需要解压临时文件"
    elif [ -d "$APP_DIR" ]; then
        echo "应用目录位置: $APP_DIR"
        echo "提示: 需要手动创建 .app 包，或直接运行 dist/MIZUKI-TOOLBOX/MIZUKI-TOOLBOX"
    else
        echo "警告: 未找到预期的应用目录"
    fi
    
    # 创建 DMG（需要 hdiutil）
    if command -v hdiutil &> /dev/null; then
        echo "创建 DMG 文件..."
        APP_NAME="MIZUKI-TOOLBOX"
        DMG_NAME="${APP_NAME}.dmg"
        
        # 创建临时目录
        TEMP_DIR=$(mktemp -d)
        
        # onedir 模式下，复制 .app 包或目录
        if [ -d "$APP_BUNDLE" ]; then
            cp -R "$APP_BUNDLE" "$TEMP_DIR/"
        elif [ -d "$APP_DIR" ]; then
            cp -R "$APP_DIR" "$TEMP_DIR/"
        else
            echo "错误: 未找到应用文件"
            rm -rf "$TEMP_DIR"
            exit 1
        fi
        
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

