#!/bin/bash

echo "🧹 海螺AI图片清理任务"
echo "===================="

# 进入项目目录
cd "$(dirname "$0")"

# 激活虚拟环境
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    echo "✅ Python虚拟环境已激活"
else
    echo "⚠️  虚拟环境不存在，使用系统Python"
fi

# 执行清理任务
echo "🚀 开始执行图片清理任务..."
python backend/cleanup.py

# 记录执行时间
echo ""
echo "⏰ 清理任务完成时间: $(date)"
echo "===================="
