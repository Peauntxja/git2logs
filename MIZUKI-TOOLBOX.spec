# -*- mode: python ; coding: utf-8 -*-
# MIZUKI-TOOLBOX PyInstaller 规范（macOS / Windows 共用）
# 由 build_macos.sh / build_windows.bat 调用

import sys

block_cipher = None
_target_arch = "arm64" if sys.platform == "darwin" else None

_project_modules = [
    'git2logs.py',
    'config.py',
    'models.py',
    'gitlab_client.py',
    'commit_analysis.py',
    'work_hours.py',
    'report_generator.py',
    'service.py',
    'image_converter.py',
    'ai_analysis.py',
    'generate_report_image.py',
    'excel_exporter.py',
    'git2logs_gui_ctk.py',
]

datas = [(name, '.') for name in _project_modules]
datas.append(('utils', 'utils'))
datas.append(('ai_providers', 'ai_providers'))
datas.append(('gui', 'gui'))

hiddenimports = [
    'tkinter',
    'tkinter.ttk',
    'tkinter.scrolledtext',
    'tkinter.messagebox',
    'tkinter.filedialog',
    'statistics',
    'concurrent.futures',
    'gitlab',
    'customtkinter',
    'openpyxl',
    'openpyxl.styles',
    'et_xmlfile',
    'ai_analysis',
    'config',
    'models',
    'gitlab_client',
    'commit_analysis',
    'work_hours',
    'report_generator',
    'service',
    'image_converter',
    'gui',
    'gui.styles',
    'gui.service_bridge',
    'gui.app',
    'gui.entry',
    'gui.layout_mixin',
    'gui.handlers_mixin',
    'gui.tabs.gitlab_tab',
    'gui.tabs.date_output_tab',
    'gui.tabs.ai_tab',
    'gui.tabs.excel_tab',
    'gui.tabs.actions_tab',
    'utils.date_utils',
]

excludes = [
    'pandas',
    'IPython',
    'matplotlib',
    'scipy',
    'pytest',
    'numpy',
    'lxml',
    'grpc',
    'google.cloud',
    'googleapiclient.discovery_cache',
    'PIL',
    'torch',
    'tensorflow',
]

a = Analysis(
    ['git2logs_gui_ctk.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=['hooks'],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MIZUKI-TOOLBOX',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=_target_arch,
    codesign_identity=None,
    entitlements_file=None,
    icon=['app_icon.icns'] if __import__('pathlib').Path('app_icon.icns').exists() else (
        ['app_icon.ico'] if __import__('pathlib').Path('app_icon.ico').exists() else None
    ),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='MIZUKI-TOOLBOX',
)
