# AGENTS.md

## Cursor Cloud specific instructions

### Product Overview

MIZUKI-TOOLBOX (git2logs) is a Python desktop/CLI tool for GitLab commit log analysis and report generation. There are no backend services, databases, or Docker containers — it is a standalone tool that calls external APIs (GitLab, optionally AI providers).

### Services and Entry Points

| Entry Point | Command | Description |
|---|---|---|
| CLI Tool | `python3 git2logs.py --help` | Core logic — GitLab API, commit fetching, reports |
| GUI App | `python3 git2logs_gui_ctk.py` | CustomTkinter tabbed interface |

### Running the GUI on Headless Linux

The GUI requires a display server. On headless environments, start Xvfb first:

```bash
Xvfb :99 -screen 0 1280x1024x24 &
export DISPLAY=:99
python3 git2logs_gui_ctk.py
```

For the desktop pane (VNC display), use `DISPLAY=:1` instead.

### System Dependencies (pre-installed, not in update script)

- `python3-tk` — required for tkinter/CustomTkinter GUI
- `xvfb` — required for headless GUI testing

### Lint / Validation

No formal linter is configured in the project. Use `py_compile` for syntax checking and `pyflakes` for basic static analysis:

```bash
python3 -m py_compile git2logs.py
pyflakes git2logs.py git2logs_gui_ctk.py ai_analysis.py excel_exporter.py
```

### Testing

There are no automated tests in this project. Validation is done via:
- `py_compile` syntax checks on all `.py` files
- Module import validation (`python3 -c "import <module>"`)
- Manual GUI and CLI testing

### Important Notes

- The CLI tool requires `--author` as a mandatory argument; without a GitLab token and URL, it cannot fetch data.
- Full end-to-end testing requires a GitLab instance with a valid private access token.
- AI analysis features require API keys for OpenAI, Anthropic, or Google Gemini (all optional).
- The `google-generativeai` package emits a FutureWarning about deprecation — this is expected and does not affect functionality.
