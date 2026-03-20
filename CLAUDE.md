# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MIZUKI-TOOLBOX (git2logs) is a GitLab commit log analysis tool that generates daily reports, work hour allocation reports, and exports to Excel. Built with Python and CustomTkinter for GUI, with PyInstaller packaging for macOS (.app + .dmg).

## Architecture Overview

### Core Components

**Main Application Files:**
- `git2logs.py` - Core logic: GitLab API integration, commit fetching, daily/hourly report generation
- `git2logs_gui_ctk.py` - CustomTkinter GUI main file with tabbed interface
- `ai_analysis.py` - AI analysis module supporting OpenAI, Anthropic, and Google Gemini
- `excel_exporter.py` - Excel work hour template filling and export
- `generate_report_image.py` - HTML and PNG report generation with Chrome headless

**Utility Modules (`utils/`):**
- `api_utils.py` - GitLab API wrapper and HTTP request handling
- `date_utils.py` - Date manipulation and formatting utilities
- `logger.py` - Logging configuration and output formatting
- `patterns.py` - Code pattern recognition for commit classification

**Build & Packaging:**
- `build_macos.sh` - macOS PyInstaller build script with dependency management
- `MIZUKI-TOOLBOX.spec` - PyInstaller configuration file
- `requirements.txt` - Python dependencies including AI libraries

### Key Workflows

1. **GitLab Integration**: API authentication → Project discovery → Commit fetching → Data processing
2. **Report Generation**: Commit analysis → Pattern classification → Statistics calculation → Format output
3. **GUI Operation**: Tab-based interface → Parameter input → Background processing → Real-time logging
4. **Export Pipeline**: Data transformation → Excel template filling → HTML/PNG generation

## Development Commands

### Environment Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Install optional AI dependencies
pip install openai anthropic google-generativeai customtkinter openpyxl
```

### Code Validation
```bash
# Syntax checking for modified files
python3 -m py_compile git2logs.py
python3 -m py_compile git2logs_gui_ctk.py

# Run GUI application
python3 git2logs_gui_ctk.py

# Command-line usage examples
python git2logs.py --scan-all --gitlab-url http://gitlab.example.com --author "User" --today --token TOKEN
python git2logs.py --repo http://gitlab.example.com/project.git --author "User" --daily-report

# Generate Excel reports
python git2logs.py --scan-all --gitlab-url http://gitlab.example.com --author "User" --today --token TOKEN --excel-export
```

### Testing & Debugging
```bash
# Generate HTML/PNG reports from existing markdown
python3 generate_report_image.py 2025-12-12_daily_report.md

# Validate Excel export functionality
python3 -c "import excel_exporter; print('Excel module loaded successfully')"

# Test AI analysis integration
python3 -c "import ai_analysis; print('AI analysis module loaded successfully')"

# Quick syntax check for all Python files
python3 -m py_compile *.py && echo "All files compile successfully"
```

### Build & Packaging
```bash
# macOS application packaging
bash build_macos.sh

# Verify build output
ls -la dist/

# Clean build artifacts
rm -rf build dist *.spec
```

## Code Organization Guidelines

### File Modification Strategy

**High-Impact Files (Require Careful Review):**
- `git2logs.py` - Core business logic (lines 2214+ contain daily report generation)
- `git2logs_gui_ctk.py` - GUI state management and event handling (UIStyles class for theming)
- `ai_analysis.py` - Multi-provider AI integration with strategy pattern

**Utility Files (Safe for Updates):**
- `utils/` directory - Independent helper functions
- `excel_exporter.py` - Template-based Excel generation with openpyxl
- `generate_report_image.py` - HTML/CSS styling and Chrome automation for PNG conversion

### GUI Architecture

The CustomTkinter GUI uses a tabbed interface with these key sections:
- **Tab 1**: GitLab configuration (URL, token, author)
- **Tab 2**: Project/branch selection and scanning
- **Tab 3**: Date range and output format selection
- **Tab 4**: Excel export and advanced options
- **Tab 5**: AI analysis configuration
- **Tab 6**: Execution logs and status

### Data Flow

```
GitLab API → Raw Commits → Pattern Analysis → Statistics → Report Generation → Export Formats
                              ↓
                         AI Analysis → Enhanced Insights
```

## Common Development Tasks

### Adding New Features
1. **GUI Integration**: Add controls to appropriate tab in `git2logs_gui_ctk.py`
2. **Core Logic**: Implement functionality in `git2logs.py` or new utility module
3. **Export Support**: Update `excel_exporter.py` and `generate_report_image.py` if needed
4. **Testing**: Validate with `py_compile` and manual testing

### Bug Fixes
1. **Reproduction**: Use GUI or command-line to reproduce issue
2. **Isolation**: Identify whether issue is in core logic, GUI, or export modules
3. **Fix**: Apply minimal change with proper error handling
4. **Validation**: Test with `py_compile` and build verification

### Report Customization
- **Daily Report Format**: Modify `generate_daily_report()` function in `git2logs.py` (line ~2214)
- **HTML Styling**: Update CSS in `generate_report_image.py`
- **Excel Templates**: Modify `excel_exporter.py` template handling

## Build and Deployment

### macOS Packaging Requirements
- PyInstaller with onedir mode for faster startup
- Chrome browser for HTML-to-PNG conversion
- ARM64 target architecture support
- Custom app icon (app_icon.icns)

### Distribution Structure
```
dist/
├── MIZUKI-TOOLBOX.app      # macOS application bundle
├── MIZUKI-TOOLBOX.dmg      # macOS disk image
└── MIZUKI-TOOLBOX/         # onedir mode executable directory
```

## Git Workflow

### Branch Strategy
- `main` branch for production-ready code
- Feature branches for development
- Commit format: `<type>(<scope>): <description>` (Chinese descriptions)

### Pre-commit Checklist
1. Syntax validation with `py_compile`
2. Verify GUI functionality
3. Test build process
4. Update documentation if needed

## Troubleshooting

### Common Issues
- **GUI fails to start**: Check CustomTkinter installation, fallback to tkinter
- **GitLab API errors**: Verify token permissions and URL format
- **Excel export fails**: Ensure openpyxl is installed and template format is correct
- **PNG generation fails**: Verify Chrome browser installation and headless mode

### Debug Mode
Enable verbose logging by modifying logger configuration in `utils/logger.py` for detailed execution traces.
