# PyInstaller hook：收集 ai_providers；打包机已安装的 AI SDK 才打入产物
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = collect_submodules("ai_providers")

for pkg in ("openai", "anthropic", "google.generativeai"):
    try:
        __import__(pkg)
    except ImportError:
        continue
    hiddenimports += collect_submodules(pkg)
