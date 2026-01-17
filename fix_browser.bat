@echo off
echo 🔧 修复浏览器问题 - 安装Playwright浏览器
echo.

echo 📋 当前状态检查...
python -c "import playwright; print('✅ Playwright已安装')" 2>nul || (echo ❌ Playwright未安装 && exit /b 1)

echo.
echo 🚀 开始安装Chromium浏览器...
python -m playwright install chromium

echo.
echo 🔧 安装所有浏览器依赖...
python -m playwright install-deps

echo.
echo ✅ 浏览器修复完成！
echo 💡 现在重启服务器即可正常使用Chrome/Chromium
echo.
pause
