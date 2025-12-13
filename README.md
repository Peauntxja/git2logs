# GitLab 提交日志生成工具

从 GitLab 仓库获取指定提交者每天的代码提交，生成 Markdown 格式日志或开发日报。

## 功能特点

- 支持单项目或多项目自动扫描
- 自动生成提交日志或开发日报
- 支持指定分支、日期范围过滤
- 支持私有仓库（需要访问令牌）
- **支持生成 HTML 和 PNG 图片格式的日报**（与 HTML 显示完全一致）

## 安装

```bash
pip install -r requirements.txt
```

## 快速开始

### 图形界面版本（推荐）

使用图形界面工具，无需记忆命令行参数：

```bash
python3 git2logs_gui.py
```

**功能特点：**
- 可视化参数输入（GitLab URL、仓库地址、令牌等）
- 日期选择（今天或指定日期范围）
- 输出格式选择（Markdown/开发日报/HTML/PNG）
- 实时执行日志显示
- 一键生成所有格式

### 命令行版本

#### 单项目模式

```bash
python git2logs.py \
  --repo http://gitlab.example.com/group/project.git \
  --branch master \
  --author "Example User" \
  --token YOUR_TOKEN
```

### 自动扫描所有项目

```bash
python git2logs.py \
  --scan-all \
  --gitlab-url http://gitlab.example.com \
  --author "Example User" \
  --today \
  --token YOUR_TOKEN
```

### 生成开发日报

```bash
python git2logs.py \
  --scan-all \
  --gitlab-url http://gitlab.example.com \
  --author "Example User" \
  --today \
  --token YOUR_TOKEN \
  --daily-report
```

## 主要参数

| 参数 | 说明 | 必需 |
|------|------|------|
| `--author` | 提交者姓名或邮箱 | ✅ |
| `--token` | GitLab 访问令牌 | 私有仓库必需 |
| `--repo` | 仓库地址（单项目模式） | 单项目模式必需 |
| `--scan-all` | 自动扫描所有项目 | 多项目模式必需 |
| `--gitlab-url` | GitLab 实例 URL | 多项目模式必需 |
| `--branch` | 指定分支名称 | ❌ |
| `--today` | 仅获取今天的提交 | ❌ |
| `--since` | 起始日期 (YYYY-MM-DD) | ❌ |
| `--until` | 结束日期 (YYYY-MM-DD) | ❌ |
| `--daily-report` | 生成开发日报格式 | ❌ |
| `--output` | 输出文件路径 | ❌ |

## 输出文件

- **单项目模式**：`YYYY-MM-DD_commits_<分支名>.md`
- **多项目模式**：`YYYY-MM-DD_all_projects_<分支名>.md`
- **开发日报**：`YYYY-MM-DD_daily_report_<分支名>.md`
- **HTML 格式**：`YYYY-MM-DD_daily_report.html`（使用 `generate_report_image.py` 生成）
- **PNG 图片**：`YYYY-MM-DD_daily_report.png`（自动从 HTML 转换，与 HTML 显示完全一致）

## 使用示例

### 获取今天的提交

```bash
python git2logs.py \
  --scan-all \
  --gitlab-url http://gitlab.example.com \
  --author "Example User" \
  --today \
  --branch test \
  --token YOUR_TOKEN
```

### 生成开发日报

```bash
python git2logs.py \
  --scan-all \
  --gitlab-url http://gitlab.example.com \
  --author "Example User" \
  --today \
  --branch test \
  --token YOUR_TOKEN \
  --daily-report
```

### 指定日期范围

```bash
python git2logs.py \
  --scan-all \
  --gitlab-url http://gitlab.example.com \
  --author "Example User" \
  --since 2025-12-01 \
  --until 2025-12-31 \
  --token YOUR_TOKEN
```

## 获取访问令牌

1. 登录 GitLab
2. 进入 **Settings** > **Access Tokens**
3. 创建令牌，至少需要 `read_api` 权限
4. 复制并保存令牌

## 开发日报内容

开发日报包含：
- 📊 工作概览（项目数、提交数、工作时间、类型分布）
- 📦 工作详情（按项目分组的提交记录）
- 📋 工作分类汇总（按类型分组）
- ⏰ 工作时间线（按时间排序）
- 📝 工作总结

## 生成图片格式的日报

生成开发日报后，可以使用 `generate_report_image.py` 将 Markdown 日报转换为 HTML 和 PNG 图片：

```bash
# 生成 HTML 和 PNG 图片（自动从 HTML 转换）
python3 generate_report_image.py 2025-12-12_daily_report.md
```

**功能特点：**
- 自动生成美观的 HTML 格式日报
- 使用 Chrome headless 模式将 HTML 转换为 PNG 图片
- 图片与 HTML 显示完全一致（包括样式、emoji、布局等）
- 图片尺寸：1600x2400 像素，适合打印和分享

**要求：**
- 需要安装 Google Chrome（用于 HTML 转图片）
- macOS 系统会自动检测 Chrome 路径

## 使用方式

### 方式一：图形界面（推荐新手）

运行图形界面工具：
```bash
python3 git2logs_gui.py
```

在界面中填写参数并选择输出格式，点击"生成日志"即可。

### 方式二：命令行（适合自动化）

使用命令行工具，适合脚本和自动化场景。

## 注意事项

- 私有仓库需要提供访问令牌
- 提交者姓名必须与 GitLab 中的提交记录完全匹配
- 如果提供完整的仓库 URL，工具会自动提取 GitLab URL
- 生成图片功能需要系统已安装 Google Chrome
- 图形界面需要 Python 3.x 和 tkinter（通常 Python 自带）
