#!/bin/bash

echo "======================================"
echo "    大帝AI - AI视频生成平台启动脚本"
echo "======================================"
echo ""

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}[1/6] 检查Python环境...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}错误：Python3未安装${NC}"
    echo "请运行: sudo apt update && sudo apt install python3 python3-pip"
    exit 1
fi
echo "✅ Python版本: $(python3 --version)"

echo -e "${GREEN}[2/6] 检查Node.js环境...${NC}"
if ! command -v node &> /dev/null; then
    echo -e "${RED}错误：Node.js未安装${NC}"
    echo "请运行: curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash - && sudo apt-get install -y nodejs"
    exit 1
fi
echo "✅ Node.js版本: $(node --version)"

echo -e "${GREEN}[3/6] 检查环境变量文件...${NC}"
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        echo -e "${YELLOW}⚠️  .env文件不存在，正在复制.env.example...${NC}"
        cp .env.example .env
        echo -e "${YELLOW}📝 请编辑.env文件设置正确的配置！${NC}"
    else
        echo -e "${RED}错误：.env.example文件不存在${NC}"
        exit 1
    fi
fi
echo "✅ 环境变量文件检查完成"

echo -e "${GREEN}[4/6] 安装Python依赖...${NC}"
cd backend
if [ ! -d venv ]; then
    echo "创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate
pip install -r requirements.txt
cd ..

echo -e "${GREEN}[5/6] 安装Node.js依赖...${NC}"
cd frontend
npm install
cd ..

echo -e "${GREEN}[6/6] 启动服务...${NC}"

# 设置环境变量
export $(grep -v '^#' .env | xargs)

# 启动后端服务（后台运行）
echo "启动后端服务 (端口8000)..."
cd backend
source venv/bin/activate
nohup python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 > ../logs/backend.log 2>&1 &
BACKEND_PID=$!
echo "后端服务PID: $BACKEND_PID"
cd ..

# 启动前端服务（后台运行）
echo "启动前端服务 (端口5173)..."
cd frontend
nohup npm run dev -- --host 0.0.0.0 > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
echo "前端服务PID: $FRONTEND_PID"
cd ..

# 保存PID到文件
mkdir -p logs
echo $BACKEND_PID > logs/backend.pid
echo $FRONTEND_PID > logs/frontend.pid

echo ""
echo -e "${GREEN}✅ 服务启动完成！${NC}"
echo -e "📱 前端访问地址: ${YELLOW}http://your-server-ip:5173${NC}"
echo -e "🔧 后端API地址: ${YELLOW}http://your-server-ip:8000${NC}"
echo -e "👨‍💼 管理后台: ${YELLOW}http://your-server-ip:5173/admin${NC}"
echo ""
echo -e "${GREEN}📊 查看日志:${NC}"
echo -e "后端日志: ${YELLOW}tail -f logs/backend.log${NC}"
echo -e "前端日志: ${YELLOW}tail -f logs/frontend.log${NC}"
echo ""
echo -e "${GREEN}🛑 停止服务:${NC}"
echo -e "运行: ${YELLOW}./stop.sh${NC}"
echo ""
