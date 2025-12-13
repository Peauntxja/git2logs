# 图标设置说明

## 快速开始

### 步骤 1: 准备图标图片

1. 准备一张图片文件（PNG、JPG 等格式）
2. 建议尺寸：至少 512x512 像素，最好是 1024x1024 像素
3. 图片应该是正方形（1:1 比例）

### 步骤 2: 转换为图标格式

#### macOS

```bash
# 运行图标转换脚本
chmod +x create_icons.sh
./create_icons.sh your_icon.png

# 这会生成:
# - app_icon.icns (macOS 图标)
# - app_icon.ico (Windows 图标，如果支持)
```

#### Windows

Windows 用户需要：
1. 使用在线工具将 PNG 转换为 .ico
   - https://convertio.co/png-ico/
   - https://icoconvert.com/
2. 将转换后的文件保存为 `app_icon.ico`

或者安装 ImageMagick 后使用命令行：
```cmd
convert your_icon.png -define icon:auto-resize=256,128,64,48,32,16 app_icon.ico
```

### 步骤 3: 打包应用

图标文件准备好后，运行打包脚本即可：

**macOS:**
```bash
./build_macos.sh
```

**Windows:**
```cmd
build_windows.bat
```

打包脚本会自动检测并使用图标文件。

## 图标要求

### macOS (.icns)
- 格式：.icns
- 包含多种尺寸：16x16, 32x32, 64x64, 128x128, 256x256, 512x512, 1024x1024
- 文件名：`app_icon.icns`

### Windows (.ico)
- 格式：.ico
- 包含多种尺寸：16x16, 32x32, 48x48, 64x64, 128x128, 256x256
- 文件名：`app_icon.ico`

## 工具说明

### create_icons.sh

macOS 图标转换脚本，功能：
- 自动生成多种尺寸的图标
- 转换为 .icns 格式（macOS）
- 尝试转换为 .ico 格式（Windows）

**依赖：**
- ImageMagick（推荐）：`brew install imagemagick`
- 或 macOS 自带的 `sips` 工具

**使用方法：**
```bash
./create_icons.sh your_image.png
```

## 手动创建图标

### macOS (.icns)

1. 创建图标集目录：
```bash
mkdir appicon.iconset
```

2. 生成不同尺寸的图标：
```bash
sips -z 16 16 icon.png --out appicon.iconset/icon_16x16.png
sips -z 32 32 icon.png --out appicon.iconset/icon_16x16@2x.png
sips -z 32 32 icon.png --out appicon.iconset/icon_32x32.png
sips -z 64 64 icon.png --out appicon.iconset/icon_32x32@2x.png
sips -z 128 128 icon.png --out appicon.iconset/icon_128x128.png
sips -z 256 256 icon.png --out appicon.iconset/icon_128x128@2x.png
sips -z 256 256 icon.png --out appicon.iconset/icon_256x256.png
sips -z 512 512 icon.png --out appicon.iconset/icon_256x256@2x.png
sips -z 512 512 icon.png --out appicon.iconset/icon_512x512.png
sips -z 1024 1024 icon.png --out appicon.iconset/icon_512x512@2x.png
```

3. 转换为 .icns：
```bash
iconutil -c icns appicon.iconset -o app_icon.icns
```

### Windows (.ico)

使用在线工具或 ImageMagick：
```bash
convert icon.png -define icon:auto-resize=256,128,64,48,32,16 app_icon.ico
```

## 验证图标

打包完成后，检查：
- macOS: 在 Finder 中查看应用图标
- Windows: 在文件资源管理器中查看 .exe 文件图标

如果图标没有显示，可能需要：
1. 清除系统图标缓存
2. 重新打包应用
3. 检查图标文件格式是否正确

