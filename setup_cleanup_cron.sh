#!/bin/bash

echo "⏰ 设置自动清理定时任务"
echo "========================"

# 获取当前脚本绝对路径
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLEANUP_SCRIPT="$SCRIPT_DIR/cleanup_images.sh"

# 给清理脚本执行权限
chmod +x "$CLEANUP_SCRIPT"

# 创建cron任务（每7天执行一次，周日凌晨2点）
CRON_JOB="0 2 * * 0 $CLEANUP_SCRIPT >> $SCRIPT_DIR/logs/cleanup.log 2>&1"

# 检查是否已存在相同的cron任务
if crontab -l 2>/dev/null | grep -q "$CLEANUP_SCRIPT"; then
    echo "⚠️  定时任务已存在，跳过添加"
else
    # 添加到crontab
    (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
    echo "✅ 定时任务已添加"
fi

# 创建日志目录
mkdir -p "$SCRIPT_DIR/logs"

echo ""
echo "📋 定时任务配置:"
echo "   执行时间: 每周日凌晨2点"
echo "   清理脚本: $CLEANUP_SCRIPT"
echo "   日志文件: $SCRIPT_DIR/logs/cleanup.log"
echo ""
echo "🔍 查看当前cron任务:"
crontab -l | grep cleanup || echo "   (无相关任务)"

echo ""
echo "💡 手动测试清理:"
echo "   $CLEANUP_SCRIPT"

echo ""
echo "📊 手动查看存储使用:"
echo "   python backend/cleanup.py --stats-only"
