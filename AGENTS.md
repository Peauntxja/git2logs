# AGENTS.md

## Learned User Preferences

- 所有对话回复必须使用简体中文
- 优化和修改必须保持"不改变原有的功能和逻辑"——这是用户反复强调的硬性约束
- 用户偏好的工作流：审查 → 规划 → 实施 → 打包 macOS 测试 → 提交 GitHub
- 用户经常要求打包 macOS 版本来自测功能，而不是通过脚本运行
- 提交到 GitHub 时用户偏好直接推送，不需要额外确认（"直接提交到 github 仓库"）
- Git commit 信息使用 Conventional Commits 格式 + 简体中文描述
- 用户非常在意 GUI 的视觉一致性和美观度（包括 emoji 风格协调性）
- 用户会通过截图提供 UI 参考，修改时应对照截图还原期望效果
- 改动后需通过 `py_compile` 验证语法正确性

## Learned Workspace Facts

- 项目名称：MIZUKI-TOOLBOX（git2logs），GitLab 提交日志分析与报告生成工具
- 技术栈：Python 3.10 + CustomTkinter GUI + PyInstaller 打包
- macOS 打包脚本：`build_macos.sh`，产物为 `dist/MIZUKI-TOOLBOX.app` 和 `.dmg`
- 打包目标架构：arm64（Apple Silicon）
- GUI 入口文件：`git2logs_gui_ctk.py`
- 核心模块拆分：config.py、models.py、gitlab_client.py、commit_analysis.py、work_hours.py、report_generator.py、service.py、image_converter.py
- 远程仓库托管在 GitHub
- AI 分析支持 OpenAI、Anthropic、Google Gemini 三个提供商
- Excel 导出依赖 openpyxl，HTML 转图片依赖 Chrome headless 或 Playwright
- `build_windows.bat` 为 Windows 打包脚本，入口已更新为 `git2logs_gui_ctk.py`
