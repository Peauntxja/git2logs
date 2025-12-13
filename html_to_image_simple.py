#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将 HTML 日报转换为图片
使用 macOS 的 screencapture 或 Python 的 weasyprint
"""
import os
import sys
import subprocess
from pathlib import Path

def html_to_image_weasyprint(html_file, output_file):
    """使用 weasyprint 将 HTML 转换为图片"""
    try:
        import weasyprint
        
        html_path = Path(html_file).absolute()
        output_path = Path(output_file).absolute()
        
        print(f"正在使用 WeasyPrint 渲染 HTML: {html_path}")
        
        # 先转换为 PDF，再转换为 PNG
        pdf_file = str(output_path).replace('.png', '.pdf')
        
        # 生成 PDF
        html_doc = weasyprint.HTML(filename=str(html_path))
        html_doc.write_pdf(pdf_file)
        
        # 使用 sips 将 PDF 转换为 PNG（macOS 自带工具）
        result = subprocess.run(
            ['sips', '-s', 'format', 'png', pdf_file, '--out', str(output_path)],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            # 删除临时 PDF
            os.remove(pdf_file)
            print(f"✓ 图片已生成: {output_path}")
            return True
        else:
            print(f"错误: {result.stderr}")
            return False
            
    except ImportError:
        print("错误: 未安装 weasyprint")
        print("请运行: pip3 install weasyprint")
        return False
    except Exception as e:
        print(f"错误: {str(e)}")
        return False

def html_to_image_selenium(html_file, output_file):
    """使用 selenium 将 HTML 转换为图片"""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        
        html_path = Path(html_file).absolute()
        
        print(f"正在使用 Selenium 渲染 HTML: {html_path}")
        
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--window-size=1600,2400')
        
        driver = webdriver.Chrome(options=chrome_options)
        
        try:
            driver.get(f"file://{html_path}")
            driver.save_screenshot(output_file)
            print(f"✓ 图片已生成: {output_file}")
            return True
        finally:
            driver.quit()
            
    except ImportError:
        print("错误: 未安装 selenium")
        print("请运行: pip3 install selenium")
        return False
    except Exception as e:
        print(f"错误: {str(e)}")
        return False

def html_to_image_browser_script(html_file, output_file):
    """使用 AppleScript 调用 Safari 截图（macOS）"""
    html_path = Path(html_file).absolute()
    
    # 创建 AppleScript
    script = f'''
    tell application "Safari"
        activate
        open file "{html_path}"
        delay 2
        tell application "System Events"
            keystroke "s" using {{command down, shift down}}
            delay 1
            keystroke "{output_file}"
            keystroke return
        end tell
    end tell
    '''
    
    try:
        result = subprocess.run(
            ['osascript', '-e', script],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print(f"✓ 图片已生成: {output_file}")
            return True
        else:
            print(f"错误: {result.stderr}")
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
    
    print("尝试使用 WeasyPrint...")
    if html_to_image_weasyprint(html_file, output_file):
        sys.exit(0)
    
    print("\n尝试使用 Selenium...")
    if html_to_image_selenium(html_file, output_file):
        sys.exit(0)
    
    print("\n所有方法都失败了，请安装以下工具之一:")
    print("1. pip3 install weasyprint")
    print("2. pip3 install selenium (需要 ChromeDriver)")
    print("3. pip3 install playwright && playwright install chromium")
    sys.exit(1)

