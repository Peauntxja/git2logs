# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

MIZUKI-TOOLBOX (git2logs) is a Python-based GitLab commit log analysis tool. See `CLAUDE.md` for full architecture details and `README.md` for usage instructions.

### Running the application

- **CLI**: `python3 git2logs.py --help` (see README.md for full CLI usage)
- **GUI**: Requires a display. On headless environments, start Xvfb first:
  ```
  Xvfb :99 -screen 0 1280x1024x24 &
  export DISPLAY=:99
  python3 git2logs_gui_ctk.py
  ```

### System dependency: tkinter

The `python3-tk` system package is required for CustomTkinter GUI. It is installed as part of the VM snapshot but if missing, install via `sudo apt-get install -y python3-tk`.

### Validation commands

- **Syntax check**: `python3 -m py_compile <file.py>` for any modified file
- **Module imports**: All modules can be verified with `python3 -c "import <module>"`
- **No formal test suite exists** — validation is done via `py_compile` and manual testing

### Key caveats

- The tool requires a GitLab instance and access token for actual data fetching. Without these, core data-fetching functionality returns 401/connection errors (expected).
- AI analysis features (OpenAI, Anthropic, Gemini) require respective API keys — these are optional and the tool works without them.
- The `google-generativeai` package emits a FutureWarning about deprecation — this is a known upstream issue and does not affect functionality.
- PNG report generation requires Chrome/Chromium installed for headless screenshot conversion.
