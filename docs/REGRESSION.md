# MIZUKI-TOOLBOX 回归清单

在改动报告生成、工时算法、Excel 导出、打包脚本或 GUI 业务编排后，按本清单验证。**行为须与改前一致**。

## 测试目录说明

| 路径 | 作用 | 是否提交 |
|------|------|----------|
| `tests/expected/` | 报告/HTML 解析 golden 基准 | ✅ 需提交 |
| `tests/fixtures/` | Excel 模板等固定输入 | ✅ 需提交 |
| `tests/helpers/` | 假 GitLab 数据与文本归一化 | ✅ 需提交 |
| `tests/test_regression.py` | 主回归（报告、HTML、CLI、Service） | ✅ |
| `tests/test_ai_providers.py` | AI 注册表（隔离全局状态） | ✅ |
| `tests/**/__pycache__/`、临时 xlsx/html/png | 本地运行产物 | ❌ gitignore |

**不要删除** `tests/expected/` 以“保持干净”——那是无网络的回归安全网。

## 自动化

推送至 `main` 时 GitHub Actions（`.github/workflows/test.yml`）会运行与本地相同的 unittest。

```bash
bash scripts/run_tests.sh
# 或
python3 scripts/update_golden_fixtures.py   # 仅算法/版式有意变更后
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

覆盖范围：

- 统计报告 / 开发日报 / 工时报告 / commits Markdown（固定 fixture，无 GitLab 网络）
- `calculate_work_hours` 数据结构
- Excel `merge_and_normalize_tasks` 与 `fill_excel_template` 行数
- `report_html.parse_daily_report` 结构化字段（`tests/expected/report_html_parsed.json`）

## 打包体积基线

```bash
bash build_macos.sh
bash scripts/measure_bundle.sh
python3 scripts/audit_bundle.py
```

打包脚本会在清理后自动运行 `audit_bundle.py`，禁止 grpc/numpy/PIL 等目录回潮。

结果写入 `build/metrics.json`（已 gitignore `build/`，本地对比用）。

## GUI 手工清单

1. **GitLab 配置**：填写 URL、Token、作者；可选单仓或扫描全库  
2. **日期和输出**：今天 / 自定义区间；各格式各测一次：`daily_report`、`statistics`、`work_hours`、`commits`、`all`  
3. **Excel 导出**：先生成 `work_hours`，再导出；可选加载 JSON  
4. **AI 分析**：连接测试；统计报告后会话 AI；从 `.md` 文件分析  
5. **主题**：深浅色切换，侧栏与日志区正常  

## CLI 手工清单

`scan-all` 与单仓库模式均经 `Git2LogsService` 拉取提交；单仓库 `--daily-report` 仍只改输出文件名、正文为 commits Markdown（历史行为）。

```bash
export GITLAB_TOKEN="..."
python3 git2logs.py --scan-all --gitlab-url <url> --author <name> --since 2026-01-15 --until 2026-01-15 --daily-report -o /tmp/out.md
python3 git2logs.py ... --statistics -o /tmp/stats.md
python3 git2logs.py ... --work-hours -o /tmp/wh.md
python3 git2logs.py --repo <url> --author <name> --token ... -o /tmp/commits.md
```

## macOS 打包应用

`bash build_macos.sh` 后优先使用 **`dist/MIZUKI-TOOLBOX.app`**（双击或 `open dist/MIZUKI-TOOLBOX.app`）；若无 `.app` 则使用 `dist/MIZUKI-TOOLBOX/`。重复 GUI 清单第 2–5 项。

## 更新 golden 的时机

- 有意修改报告 Markdown 版式或工时分配规则时：先改代码，再运行 `scripts/update_golden_fixtures.py`，人工 diff `tests/expected/` 后提交。
