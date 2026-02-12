#!/bin/bash

echo "======================================"
echo "    大帝AI - 停止所有服务"
echo "======================================"
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${GREEN}正在停止服务...${NC}"

# 停止后端服务
if [ -f logs/backend.pid ]; then
    BACKEND_PID=$(cat logs/backend.pid)
    if ps -p $BACKEND_PID > /dev/null 2>&1; then
        echo "停止后端服务 (PID: $BACKEND_PID)"
        kill $BACKEND_PID
        rm logs/backend.pid
    else
        echo "后端服务未运行"
        rm -f logs/backend.pid
    fi
fi

# 停止前端服务
if [ -f logs/frontend.pid ]; then
    FRONTEND_PID=$(cat logs/frontend.pid)
    if ps -p $FRONTEND_PID > /dev/null 2>&1; then
        echo "停止前端服务 (PID: $FRONTEND_PID)"
        kill $FRONTEND_PID
        rm logs/frontend.pid
    else
        echo "前端服务未运行"
        rm -f logs/frontend.pid
    fi
fi

# 强制杀死相关进程
echo "检查并清理相关进程..."
pkill -f "uvicorn.*main:app" 2>/dev/null || true
pkill -f "vite.*dev" 2>/dev/null || true
pkill -f "node.*vite" 2>/dev/null || true

echo ""
echo -e "${GREEN}✅ 所有服务已停止${NC}"
echo ""
