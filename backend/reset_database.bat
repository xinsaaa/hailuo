@echo off
REM 数据库重置脚本 (Windows)
REM 用法: reset_database.bat

echo 🔄 开始重置数据库...
echo.

REM 检查是否在backend目录
if not exist "main.py" (
    echo ❌ 错误：请在backend目录中运行此脚本
    exit /b 1
)

REM 检查数据库文件是否存在
if exist "database.db" (
    echo 📁 找到数据库文件: database.db
    
    REM 备份旧数据库
    for /f "tokens=2-4 delims=/ " %%a in ('date /t') do (set mydate=%%c%%a%%b)
    for /f "tokens=1-2 delims=/:" %%a in ('time /t') do (set mytime=%%a%%b)
    set BACKUP_NAME=database.db.backup.%mydate%_%mytime%
    
    echo 💾 备份旧数据库到: %BACKUP_NAME%
    copy database.db "%BACKUP_NAME%"
    
    REM 删除数据库
    echo 🗑️  删除旧数据库...
    del database.db
    echo ✅ 数据库已删除
) else (
    echo ℹ️  数据库文件不存在，将创建新数据库
)

echo.
echo 🔄 运行重置脚本...
python reset_models.py

if %errorlevel% equ 0 (
    echo.
    echo ✅ 数据库重置成功！
    echo.
    echo 📝 下一步：
    echo    1. 重启后端服务
    echo    2. 验证API: curl http://localhost:8000/api/models
    echo    3. 检查返回的模型数量应该是10个
) else (
    echo.
    echo ❌ 重置失败！请检查错误信息
    exit /b 1
)

pause
