@echo off
echo 🚨 修复虚拟内存不足问题
echo.

echo 📊 检查系统状态...
systeminfo | findstr /C:"可用物理内存" /C:"虚拟内存"

echo.
echo 🧹 清理系统临时文件...
del /q /f "%TEMP%\playwright*" 2>nul
rd /s /q "%TEMP%\playwright_chromiumdev_profile*" 2>nul
echo ✅ 临时文件清理完成

echo.
echo 🔄 重新安装Chromium...
python -m playwright uninstall chromium
python -m playwright install chromium

echo.
echo 💾 建议增加虚拟内存:
echo    1. 右键"此电脑" → 属性 → 高级系统设置
echo    2. 性能 → 设置 → 高级 → 虚拟内存 → 更改  
echo    3. 取消"自动管理" → 自定义大小
echo    4. 初始大小: 4096MB, 最大值: 8192MB
echo    5. 确定并重启电脑

echo.
echo 🔧 或者尝试无界面模式（节省内存）:
echo    set AUTOMATION_HEADLESS=true
echo    然后重启服务器

echo.
pause
