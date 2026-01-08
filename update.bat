@echo off
chcp 65001 > nul
title AI视频生成平台 - 更新并重启

:: 设置项目路径
set PROJECT_PATH=C:\Users\Administrator\Desktop\src\hailuo

:: 检查路径
if not exist "%PROJECT_PATH%" (
    echo [错误] 项目路径不存在: %PROJECT_PATH%
    pause
    exit /b 1
)

echo ========================================
echo    AI 视频生成平台 - 更新并重启
echo ========================================
echo.

:: 关闭旧进程
echo [1/5] 关闭旧进程...
taskkill /f /im node.exe 2>nul
taskkill /f /im python.exe 2>nul
timeout /t 2 /nobreak > nul

:: 更新代码
echo [2/5] 拉取最新代码...
cd /d %PROJECT_PATH%
git fetch origin
git reset --hard origin/main
echo.

:: 安装依赖（如有更新）
echo [3/5] 检查前端依赖...
cd /d %PROJECT_PATH%\frontend
npm install --silent
echo.

:: 启动后端
echo [4/5] 启动后端服务 (端口: 8000)...
start "后端服务" cmd /k "cd /d %PROJECT_PATH% && uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"
timeout /t 3 /nobreak > nul

:: 启动前端
echo [5/5] 启动前端服务 (端口: 5173)...
start "前端服务" cmd /k "cd /d %PROJECT_PATH%\frontend && npm run dev -- --host 0.0.0.0"

echo.
echo ========================================
echo    更新并重启完成！
echo    前端: http://152.32.213.113:5173
echo    后端: http://152.32.213.113:8000
echo ========================================
echo.
echo 按任意键关闭此窗口...
pause > nul
