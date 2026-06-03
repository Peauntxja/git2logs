# 打包说明

本文档说明如何将 GitLab 提交日志生成工具打包成可执行文件。

## 回归与体积基线

- 自动化 golden 测试与手工清单：见 [docs/REGRESSION.md](docs/REGRESSION.md)
- 打包后记录 `_internal` 体积：`bash scripts/measure_bundle.sh`（写入 `build/metrics.json`）

## 统一 PyInstaller 配置

macOS 与 Windows 共用 [`MIZUKI-TOOLBOX.spec`](MIZUKI-TOOLBOX.spec)，由 `build_macos.sh` / `build_windows.bat` 调用。打包后执行与 macOS 相同的 `_internal` 清理（删除 grpc、numpy、PIL 等未使用依赖）。

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
   - 应用目录: `dist/MIZUKI-TOOLBOX`（onedir）
   - DMG: `dist/MIZUKI-TOOLBOX.dmg`（macOS）
   - 打包后自动运行 `scripts/audit_bundle.py` 检查禁止依赖

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

请优先使用统一 spec，避免模块遗漏：

```bash
pyinstaller --clean --noconfirm MIZUKI-TOOLBOX.spec
```

macOS 会生成 `dist/MIZUKI-TOOLBOX.app`；Windows 为 `dist/MIZUKI-TOOLBOX/` 目录。

## 打包后的文件结构

- 入口：`git2logs_gui_ctk.py`（GUI）
- 业务与 CLI：`service.py`、`cli.py`、`git2logs.py` 等（见 `MIZUKI-TOOLBOX.spec` 的 `datas`）
- `gui/`、`ai_providers/`、`utils/` 作为数据目录打入 `_internal`

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

