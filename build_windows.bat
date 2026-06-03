@echo off
REM Windows 打包脚本 — 使用 MIZUKI-TOOLBOX.spec（与 macOS 模块列表一致）

echo ==========================================
echo MIZUKI-TOOLBOX - Windows 打包
echo ==========================================

where pyinstaller >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo 错误: PyInstaller 未安装
    echo 请运行: pip install pyinstaller
    pause
    exit /b 1
)

if not exist "MIZUKI-TOOLBOX.spec" (
    echo 错误: 未找到 MIZUKI-TOOLBOX.spec
    pause
    exit /b 1
)

echo 检查依赖...
pip install -r requirements.txt

echo 清理之前的构建...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo 开始打包...
pyinstaller --clean --noconfirm MIZUKI-TOOLBOX.spec

if not exist "dist\MIZUKI-TOOLBOX" (
    echo 打包失败
    pause
    exit /b 1
)

echo 清理不必要的依赖文件...
set INTERNAL=dist\MIZUKI-TOOLBOX\_internal
if exist "%INTERNAL%\googleapiclient\discovery_cache\documents" rmdir /s /q "%INTERNAL%\googleapiclient\discovery_cache\documents"
if exist "%INTERNAL%\grpc" rmdir /s /q "%INTERNAL%\grpc"
if exist "%INTERNAL%\numpy" rmdir /s /q "%INTERNAL%\numpy"
if exist "%INTERNAL%\lxml" rmdir /s /q "%INTERNAL%\lxml"
if exist "%INTERNAL%\PIL" rmdir /s /q "%INTERNAL%\PIL"
if exist "%INTERNAL%\googleapiclient\discovery_cache\documents" rmdir /s /q "%INTERNAL%\googleapiclient\discovery_cache\documents"

echo ==========================================
echo 打包成功！输出: dist\MIZUKI-TOOLBOX
echo ==========================================
pause
