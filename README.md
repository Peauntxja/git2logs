# MIZUKI-TOOLBOX（git2logs）

从 GitLab 仓库获取指定提交者的代码提交，生成 Markdown 日志、开发日报、统计/工时报告，并支持 Excel 导出与 HTML/PNG 日报。

## 功能特点

- 支持单项目或多项目自动扫描
- 开发日报、统计报告、工时分配、commits 汇总
- 支持指定分支、日期范围过滤
- 私有仓库（GitLab Token）
- **CustomTkinter GUI**（`Git2LogsService` 统一编排）
- **HTML / PNG 日报**（`report_html` + `image_converter`）
- 可选 AI 分析（OpenAI / Anthropic / Gemini / 豆包 / DeepSeek）

## 安装

```bash
pip install -r requirements.txt
```

GUI 需要 `customtkinter`（已包含在 `requirements.txt`）。

## 快速开始

### 图形界面（推荐）

```bash
python3 git2logs_gui_ctk.py
```

macOS 打包产物：`bash build_macos.sh` → `dist/MIZUKI-TOOLBOX` 或 `dist/MIZUKI-TOOLBOX.dmg`。

### 命令行

#### 单项目

```bash
export GITLAB_TOKEN="your-token"
python3 git2logs.py \
  --repo http://gitlab.example.com/group/project.git \
  --branch main \
  --author "MIZUKI" \
  --token "$GITLAB_TOKEN"
```

> 单项目下 `--daily-report` **仅改变输出文件名**，正文仍为 commits Markdown（历史 CLI 行为）。

#### 扫描所有项目

```bash
python3 git2logs.py \
  --scan-all \
  --gitlab-url http://gitlab.example.com \
  --author "MIZUKI" \
  --today \
  --token "$GITLAB_TOKEN" \
  --daily-report \
  -o /tmp/out.md
```

#### 统计 / 工时

```bash
python3 git2logs.py --scan-all --gitlab-url <url> --author <name> --statistics -o /tmp/stats.md
python3 git2logs.py --scan-all --gitlab-url <url> --author <name> --work-hours -o /tmp/wh.md
```

## 主要参数

| 参数 | 说明 |
|------|------|
| `--author` | 提交者姓名或邮箱（必需） |
| `--token` / `GITLAB_TOKEN` | 访问令牌 |
| `--repo` | 单项目仓库地址 |
| `--scan-all` | 扫描有权限的全部项目 |
| `--gitlab-url` | GitLab 实例 URL（scan-all 必需） |
| `--branch` / `--since` / `--until` / `--today` | 分支与日期 |
| `--daily-report` / `--statistics` / `--work-hours` | 报告类型（scan-all） |
| `--output` | 输出文件或目录 |

## Markdown → HTML / PNG

```bash
python3 generate_report_image.py tests/expected/daily_report.md
# 仅 HTML → PNG：
python3 image_converter.py report.html report.png
```

实现：`report_html` → `image_converter`（Chrome headless，Playwright 回退）。

## 项目结构（核心）

| 模块 | 职责 |
|------|------|
| `git2logs.py` | 公共 API 门面 |
| `cli.py` | 命令行 |
| `service.py` | `Git2LogsService` 业务编排 |
| `report_generator.py` | Markdown 报告 |
| `report_html.py` | 日报 HTML |
| `image_converter.py` | HTML → PNG |
| `gui/` | CustomTkinter 界面 |

## 开发与回归

```bash
# 语法
python3 -m py_compile git2logs.py cli.py service.py report_html.py

# 测试（无需 GitLab 网络）
python3 -m unittest discover -s tests -p 'test_*.py' -v

# 刷新 golden（算法有意变更后）
python3 scripts/update_golden_fixtures.py
```

详见 [docs/REGRESSION.md](docs/REGRESSION.md)、[PACKAGING.md](PACKAGING.md)。

## 获取访问令牌

1. GitLab → **Settings** → **Access Tokens**
2. 权限至少 `read_api`
3. 使用 `--token` 或环境变量 `GITLAB_TOKEN`

## 注意事项

- 提交者名称需与 GitLab 记录一致
- 完整仓库 URL 可自动解析 GitLab 实例地址
- PNG 生成需本机 Chrome 或 Playwright Chromium
