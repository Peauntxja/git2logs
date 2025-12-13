@echo off
REM Windows 打包脚本
REM 使用 PyInstaller 将应用打包成 Windows 可执行文件

echo ==========================================
echo GitLab 提交日志生成工具 - Windows 打包
echo ==========================================

REM 检查 PyInstaller 是否安装
where pyinstaller >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo 错误: PyInstaller 未安装
    echo 请运行: pip install pyinstaller
    pause
    exit /b 1
)

REM 检查依赖
echo 检查依赖...
pip install -r requirements.txt

REM 清理之前的构建
echo 清理之前的构建...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist *.spec del /q *.spec

REM 检查图标文件
set ICON_FILE=app_icon.ico
if not exist "%ICON_FILE%" (
    echo 警告: 未找到图标文件 %ICON_FILE%
    echo 提示: 运行图标转换工具创建图标
    set ICON_PARAM=
) else (
    echo 使用图标: %ICON_FILE%
    set ICON_PARAM=--icon=%ICON_FILE%
)

REM 使用 PyInstaller 打包
echo 开始打包...
pyinstaller --name="GitLab提交日志生成工具" ^
    --windowed ^
    --onefile ^
    --add-data "git2logs.py;." ^
    --add-data "generate_report_image.py;." ^
    --hidden-import=tkinter ^
    --hidden-import=gitlab ^
    --hidden-import=tkinter.ttk ^
    --hidden-import=tkinter.scrolledtext ^
    --hidden-import=tkinter.messagebox ^
    --hidden-import=tkinter.filedialog ^
    %ICON_PARAM% ^
    git2logs_gui.py

REM 检查是否成功
if exist "dist\GitLab提交日志生成工具.exe" (
    echo.
    echo ==========================================
    echo 打包成功！
    echo 可执行文件位置: dist\GitLab提交日志生成工具.exe
    echo ==========================================
) else (
    echo.
    echo ==========================================
    echo 打包失败
    echo ==========================================
    pause
    exit /b 1
)

pause

