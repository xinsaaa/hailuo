#!/bin/bash
# ===================================================
# 大帝AI视频生成平台 - 一键更新脚本
# 使用方法: chmod +x update.sh && ./update.sh
# ===================================================

set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 配置变量
PROJECT_DIR="/www/wwwroot/hailuo"

echo -e "${GREEN}🚀 开始更新...${NC}"

cd "$PROJECT_DIR"

# 1. 拉取最新代码
echo -e "\n${GREEN}📥 拉取最新代码...${NC}"
git pull origin main

# 2. 更新后端依赖
echo -e "\n${GREEN}📦 更新后端依赖...${NC}"
cd backend
source venv/bin/activate
pip install -r requirements.txt -q
deactivate

# 3. 重新构建前端
echo -e "\n${GREEN}🔨 重新构建前端...${NC}"
cd ../frontend
npm install --silent
npm run build

# 4. 重启后端服务
echo -e "\n${GREEN}🔄 重启后端服务...${NC}"
supervisorctl restart hailuo-backend

echo -e "\n${GREEN}✅ 更新完成！${NC}"
echo -e "${YELLOW}提示: 请刷新浏览器查看更新效果${NC}"
