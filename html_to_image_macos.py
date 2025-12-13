#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将 HTML 日报转换为图片
使用 macOS 系统工具（Safari + AppleScript）
"""
import os
import sys
import subprocess
import time
from pathlib import Path

def html_to_image_safari(html_file, output_file):
    """使用 Safari 和 AppleScript 将 HTML 转换为图片"""
    html_path = Path(html_file).absolute()
    output_path = Path(output_file).absolute()
    
    if not html_path.exists():
        print(f"错误: HTML 文件不存在: {html_file}")
        return False
    
    print(f"正在使用 Safari 渲染 HTML: {html_path}")
    
    # 创建 AppleScript 来打开 Safari 并截图
    script = f'''
    tell application "Safari"
        activate
        if (count of windows) = 0 then
            make new document
        end if
        set URL of current tab of front window to "file://{html_path}"
        delay 3
    end tell
    
    tell application "System Events"
        tell process "Safari"
            -- 等待页面加载
            delay 2
            -- 全屏截图
            keystroke "s" using {{command down, shift down, control down}}
        end tell
    end tell
    '''
    
    try:
        # 先尝试使用 Safari 打开
        subprocess.run(['open', '-a', 'Safari', str(html_path)], check=True)
        time.sleep(3)
        
        # 使用 screencapture 截图（需要手动或自动化）
        # 或者使用更简单的方法：直接调用 Safari 的打印功能
        
        print("Safari 已打开 HTML 文件")
        print(f"请手动截图并保存为: {output_path}")
        print("或者按 Command+Shift+4 进行区域截图")
        
        return True
        
    except Exception as e:
        print(f"错误: {str(e)}")
        return False

def html_to_image_chrome_headless(html_file, output_file):
    """使用 Chrome 无头模式截图（如果可用）"""
    html_path = Path(html_file).absolute()
    output_path = Path(output_file).absolute()
    
    # 检查 Chrome 是否在常见位置
    chrome_paths = [
        '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '/Applications/Chromium.app/Contents/MacOS/Chromium',
    ]
    
    chrome_path = None
    for path in chrome_paths:
        if os.path.exists(path):
            chrome_path = path
            break
    
    if not chrome_path:
        return False
    
    print(f"正在使用 Chrome 渲染 HTML: {html_path}")
    
    try:
        # 使用 Chrome 的 headless 模式截图
        cmd = [
            chrome_path,
            '--headless',
            '--disable-gpu',
            '--window-size=1600,2400',
            '--screenshot=' + str(output_path),
            f'file://{html_path}'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0 and output_path.exists():
            print(f"✓ 图片已生成: {output_path}")
            return True
        else:
            print(f"错误: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("错误: Chrome 截图超时")
        return False
    except Exception as e:
        print(f"错误: {str(e)}")
        return False

def html_to_image_webkit2png(html_file, output_file):
    """使用 webkit2png（如果已安装）"""
    html_path = Path(html_file).absolute()
    output_path = Path(output_file).absolute()
    
    try:
        result = subprocess.run(
            ['which', 'webkit2png'],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            return False
        
        print(f"正在使用 webkit2png 渲染 HTML: {html_path}")
        
        cmd = [
            'webkit2png',
            '-W', '1600',
            '-H', '2400',
            '-F',  # 全页面
            '-o', str(output_path).replace('.png', ''),
            f'file://{html_path}'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            # webkit2png 可能添加了后缀，需要重命名
            generated_files = list(output_path.parent.glob(output_path.stem + '*.png'))
            if generated_files:
                os.rename(generated_files[0], output_path)
            print(f"✓ 图片已生成: {output_path}")
            return True
        else:
            print(f"错误: {result.stderr}")
            return False
            
    except Exception as e:
        return False

def html_to_image_python_imgkit(html_file, output_file):
    """使用 imgkit（需要 wkhtmltoimage）"""
    try:
        import imgkit
        
        html_path = Path(html_file).absolute()
        output_path = Path(output_file).absolute()
        
        print(f"正在使用 imgkit 渲染 HTML: {html_path}")
        
        options = {
            'width': 1600,
            'disable-smart-shrinking': '',
            'format': 'png',
        }
        
        imgkit.from_file(str(html_path), str(output_path), options=options)
        
        if output_path.exists():
            print(f"✓ 图片已生成: {output_path}")
            return True
        else:
            print("错误: 图片生成失败")
            return False
            
    except ImportError:
        return False
    except Exception as e:
        print(f"错误: {str(e)}")
        return False

if __name__ == '__main__':
    html_file = '2025-12-12_daily_report.html'
    output_file = '2025-12-12_daily_report.png'
    
    if len(sys.argv) > 1:
        html_file = sys.argv[1]
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    
    # 按优先级尝试不同方法
    print("=" * 60)
    print("HTML 转图片工具")
    print("=" * 60)
    
    # 方法1: Chrome headless（最快最可靠）
    print("\n[方法1] 尝试使用 Chrome headless...")
    if html_to_image_chrome_headless(html_file, output_file):
        sys.exit(0)
    
    # 方法2: webkit2png
    print("\n[方法2] 尝试使用 webkit2png...")
    if html_to_image_webkit2png(html_file, output_file):
        sys.exit(0)
    
    # 方法3: imgkit
    print("\n[方法3] 尝试使用 imgkit...")
    if html_to_image_python_imgkit(html_file, output_file):
        sys.exit(0)
    
    # 方法4: Safari（需要手动操作）
    print("\n[方法4] 使用 Safari（需要手动截图）...")
    if html_to_image_safari(html_file, output_file):
        print("\n提示: 已打开 Safari，请手动截图")
        sys.exit(0)
    
    # 所有方法都失败
    print("\n" + "=" * 60)
    print("所有自动方法都不可用，请选择以下方案之一：")
    print("=" * 60)
    print("\n方案1: 安装 Chrome 并使用 headless 模式")
    print("  - 下载安装 Google Chrome")
    print("  - 然后运行此脚本")
    print("\n方案2: 安装 webkit2png")
    print("  - brew install webkit2png")
    print("  - 然后运行此脚本")
    print("\n方案3: 手动截图")
    print("  - 在浏览器中打开 HTML 文件")
    print("  - 按 Command+Shift+4 进行区域截图")
    print("  - 或使用浏览器的开发者工具截图功能")
    print("\n方案4: 使用在线工具")
    print("  - 上传 HTML 到在线 HTML 转图片服务")
    
    sys.exit(1)

