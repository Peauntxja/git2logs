#!/bin/bash
# 图标转换脚本
# 将图片转换为 macOS (.icns) 和 Windows (.ico) 格式

set -e

echo "=========================================="
echo "图标转换工具"
echo "=========================================="

# 检查输入文件
if [ -z "$1" ]; then
    echo "用法: $0 <图片文件路径>"
    echo "示例: $0 icon.png"
    echo ""
    echo "支持的图片格式: PNG, JPG, JPEG"
    exit 1
fi

ICON_SOURCE="$1"

if [ ! -f "$ICON_SOURCE" ]; then
    echo "错误: 文件不存在: $ICON_SOURCE"
    exit 1
fi

echo "源文件: $ICON_SOURCE"

# 检查 ImageMagick 或 sips (macOS 自带)
if command -v convert &> /dev/null; then
    CONVERT_CMD="convert"
elif command -v sips &> /dev/null; then
    CONVERT_CMD="sips"
else
    echo "错误: 未找到图片转换工具"
    echo "请安装 ImageMagick: brew install imagemagick"
    echo "或使用 macOS 自带的 sips 工具"
    exit 1
fi

# 创建临时目录
TEMP_DIR=$(mktemp -d)
echo "临时目录: $TEMP_DIR"

# macOS .icns 创建
echo ""
echo "创建 macOS 图标 (.icns)..."
ICONSET_DIR="$TEMP_DIR/appicon.iconset"
mkdir -p "$ICONSET_DIR"

# 生成不同尺寸的图标
if [ "$CONVERT_CMD" = "convert" ]; then
    # 使用 ImageMagick
    convert "$ICON_SOURCE" -resize 16x16 "$ICONSET_DIR/icon_16x16.png"
    convert "$ICON_SOURCE" -resize 32x32 "$ICONSET_DIR/icon_16x16@2x.png"
    convert "$ICON_SOURCE" -resize 32x32 "$ICONSET_DIR/icon_32x32.png"
    convert "$ICON_SOURCE" -resize 64x64 "$ICONSET_DIR/icon_32x32@2x.png"
    convert "$ICON_SOURCE" -resize 128x128 "$ICONSET_DIR/icon_128x128.png"
    convert "$ICON_SOURCE" -resize 256x256 "$ICONSET_DIR/icon_128x128@2x.png"
    convert "$ICON_SOURCE" -resize 256x256 "$ICONSET_DIR/icon_256x256.png"
    convert "$ICON_SOURCE" -resize 512x512 "$ICONSET_DIR/icon_256x256@2x.png"
    convert "$ICON_SOURCE" -resize 512x512 "$ICONSET_DIR/icon_512x512.png"
    convert "$ICON_SOURCE" -resize 1024x1024 "$ICONSET_DIR/icon_512x512@2x.png"
else
    # 使用 sips
    sips -z 16 16 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_16x16.png"
    sips -z 32 32 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_16x16@2x.png"
    sips -z 32 32 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_32x32.png"
    sips -z 64 64 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_32x32@2x.png"
    sips -z 128 128 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_128x128.png"
    sips -z 256 256 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_128x128@2x.png"
    sips -z 256 256 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_256x256.png"
    sips -z 512 512 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_256x256@2x.png"
    sips -z 512 512 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_512x512.png"
    sips -z 1024 1024 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_512x512@2x.png"
fi

# 转换为 .icns
iconutil -c icns "$ICONSET_DIR" -o "app_icon.icns"
echo "✓ macOS 图标已创建: app_icon.icns"

# Windows .ico 创建
echo ""
echo "创建 Windows 图标 (.ico)..."
if [ "$CONVERT_CMD" = "convert" ]; then
    # ImageMagick 可以直接创建 .ico
    convert "$ICON_SOURCE" -define icon:auto-resize=256,128,64,48,32,16 "app_icon.ico"
    echo "✓ Windows 图标已创建: app_icon.ico"
else
    # 使用 sips 创建不同尺寸，然后使用在线工具或手动转换
    echo "提示: sips 不支持直接创建 .ico"
    echo "请使用以下方法之一："
    echo "1. 安装 ImageMagick: brew install imagemagick"
    echo "2. 使用在线工具转换: https://convertio.co/png-ico/"
    echo "3. 使用在线工具转换: https://icoconvert.com/"
    echo ""
    echo "已创建 PNG 文件，可以手动转换为 .ico:"
    sips -z 256 256 "$ICON_SOURCE" --out "app_icon_256.png"
    echo "  - app_icon_256.png (256x256)"
fi

# 清理临时文件
rm -rf "$TEMP_DIR"

echo ""
echo "=========================================="
echo "图标转换完成！"
echo "=========================================="
echo ""
echo "生成的文件:"
echo "  - app_icon.icns (macOS)"
if [ -f "app_icon.ico" ]; then
    echo "  - app_icon.ico (Windows)"
fi
echo ""
echo "现在可以运行打包脚本，图标会自动使用。"

