#!/bin/bash

# 数据库重置脚本
# 用法: bash reset_database.sh

echo "🔄 开始重置数据库..."
echo ""

# 检查是否在backend目录
if [ ! -f "main.py" ]; then
    echo "❌ 错误：请在backend目录中运行此脚本"
    exit 1
fi

# 检查数据库文件是否存在
if [ -f "database.db" ]; then
    echo "📁 找到数据库文件: database.db"
    
    # 备份旧数据库
    BACKUP_NAME="database.db.backup.$(date +%Y%m%d_%H%M%S)"
    echo "💾 备份旧数据库到: $BACKUP_NAME"
    cp database.db "$BACKUP_NAME"
    
    # 删除数据库
    echo "🗑️  删除旧数据库..."
    rm database.db
    echo "✅ 数据库已删除"
else
    echo "ℹ️  数据库文件不存在，将创建新数据库"
fi

echo ""
echo "🔄 运行重置脚本..."
python reset_models.py

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ 数据库重置成功！"
    echo ""
    echo "📝 下一步："
    echo "   1. 重启后端服务: pm2 restart backend"
    echo "   2. 验证API: curl http://localhost:8000/api/models"
    echo "   3. 检查返回的模型数量应该是10个"
else
    echo ""
    echo "❌ 重置失败！请检查错误信息"
    exit 1
fi
