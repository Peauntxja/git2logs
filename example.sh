#!/bin/bash
# GitLab 提交日志生成工具使用示例

# ============================================
# 图形界面版本（推荐新手使用）
# ============================================

# 启动图形界面工具
# python3 git2logs_gui.py
# 或使用启动脚本
# ./start_gui.sh

# ============================================
# 命令行版本示例
# ============================================

# 示例：获取 Example User 今天的提交日志
# 仓库地址：http://gitlab.example.com/example-group/example-project.git
# 分支：master
# 提交者：Example User

# ============================================
# 基本用法：单项目模式
# ============================================

# 基本用法：只需要仓库、分支、提交者（输出文件名自动使用当天日期）
python git2logs.py \
  --repo http://gitlab.example.com/example-group/example-project.git \
  --branch master \
  --author "Example User" \
  --token YOUR_ACCESS_TOKEN

# 或者获取今天的提交
python git2logs.py \
  --repo http://gitlab.example.com/example-group/example-project.git \
  --branch master \
  --author "Example User" \
  --today \
  --token YOUR_ACCESS_TOKEN

echo "提交日志已生成（文件名格式：YYYY-MM-DD_commits_<分支名>.md）"

# ============================================
# 自动扫描所有项目
# ============================================

# 扫描所有项目，获取今天的提交
python git2logs.py \
  --scan-all \
  --gitlab-url http://gitlab.example.com \
  --author "Example User" \
  --today \
  --token YOUR_ACCESS_TOKEN

# ============================================
# 生成开发日报
# ============================================

# 生成开发日报格式（包含工作概览、详情、分类汇总、时间线等）
python git2logs.py \
  --scan-all \
  --gitlab-url http://gitlab.example.com \
  --author "Example User" \
  --today \
  --token YOUR_ACCESS_TOKEN \
  --daily-report

echo "开发日报已生成（文件名格式：YYYY-MM-DD_daily_report.md）"

# ============================================
# 生成 HTML 和 PNG 图片格式的日报
# ============================================

# 首先生成开发日报
python git2logs.py \
  --scan-all \
  --gitlab-url http://gitlab.example.com \
  --author "Example User" \
  --today \
  --token YOUR_ACCESS_TOKEN \
  --daily-report

# 然后生成 HTML 和 PNG 图片（自动从 HTML 转换）
# 需要先安装 Google Chrome
python3 generate_report_image.py 2025-12-12_daily_report.md

echo "HTML 和 PNG 图片已生成："
echo "  - HTML: 2025-12-12_daily_report.html"
echo "  - PNG:  2025-12-12_daily_report.png (与 HTML 显示完全一致)"

# ============================================
# 指定日期范围
# ============================================

# 获取指定日期范围的提交
python git2logs.py \
  --scan-all \
  --gitlab-url http://gitlab.example.com \
  --author "Example User" \
  --since 2025-12-01 \
  --until 2025-12-31 \
  --token YOUR_ACCESS_TOKEN \
  --daily-report
