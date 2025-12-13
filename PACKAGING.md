# 打包说明

本文档说明如何将 GitLab 提交日志生成工具打包成可执行文件。

## 前置要求

### macOS
- Python 3.7+
- PyInstaller: `pip install pyinstaller`

### Windows
- Python 3.7+
- PyInstaller: `pip install pyinstaller`

## 打包步骤

### macOS

1. **安装依赖**
   ```bash
   pip install -r requirements.txt
   pip install pyinstaller
   ```

2. **运行打包脚本**
   ```bash
   chmod +x build_macos.sh
   ./build_macos.sh
   ```

3. **结果**
   - 可执行文件: `dist/GitLab提交日志生成工具`
   - DMG 文件: `dist/GitLab提交日志生成工具.dmg`（如果系统支持）

### Windows

1. **安装依赖**
   ```cmd
   pip install -r requirements.txt
   pip install pyinstaller
   ```

2. **运行打包脚本**
   ```cmd
   build_windows.bat
   ```

3. **结果**
   - 可执行文件: `dist\GitLab提交日志生成工具.exe`

## 手动打包（高级）

如果自动脚本不工作，可以手动使用 PyInstaller：

### macOS
```bash
pyinstaller --name="GitLab提交日志生成工具" \
    --windowed \
    --onefile \
    --add-data "git2logs.py:." \
    --add-data "generate_report_image.py:." \
    --hidden-import=tkinter \
    --hidden-import=gitlab \
    git2logs_gui.py
```

### Windows
```cmd
pyinstaller --name="GitLab提交日志生成工具" ^
    --windowed ^
    --onefile ^
    --add-data "git2logs.py;." ^
    --add-data "generate_report_image.py;." ^
    --hidden-import=tkinter ^
    --hidden-import=gitlab ^
    git2logs_gui.py
```

## 打包后的文件结构

打包后的可执行文件包含：
- `git2logs_gui.py` - 图形界面主程序
- `git2logs.py` - 命令行工具
- `generate_report_image.py` - 图片生成工具
- 所有 Python 依赖库

## 注意事项

1. **Chrome 依赖**: 生成 PNG 图片需要系统安装 Google Chrome。如果用户没有安装 Chrome，HTML 转图片功能将不可用，但其他功能正常。

2. **文件大小**: 打包后的文件可能较大（50-100MB），因为包含了 Python 解释器和所有依赖。

3. **首次运行**: 首次运行可能需要几秒钟来解压和初始化。

4. **权限**: macOS 可能需要授予运行权限（系统设置 > 安全性与隐私）。

## 分发

### macOS
- 可以直接分发 `.dmg` 文件
- 或者分发 `.app` 应用包

### Windows
- 可以直接分发 `.exe` 文件
- 建议使用代码签名（可选）

## 测试

打包完成后，建议在干净的系统中测试：
1. 不安装 Python
2. 不安装任何依赖
3. 直接运行打包后的可执行文件

确保所有功能正常工作。

