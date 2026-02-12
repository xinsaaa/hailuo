#!/bin/bash

echo "======================================"
echo "    大帝AI - Ubuntu服务器部署脚本"
echo "======================================"
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 检查是否为root用户
if [[ $EUID -eq 0 ]]; then
   echo -e "${RED}此脚本不应该以root用户运行${NC}"
   echo "请使用普通用户运行，脚本会在需要时使用sudo"
   exit 1
fi

echo -e "${BLUE}[1/8] 更新系统包...${NC}"
sudo apt update
sudo apt upgrade -y

echo -e "${BLUE}[2/8] 安装基础依赖...${NC}"
sudo apt install -y curl wget git vim htop unzip software-properties-common

echo -e "${BLUE}[3/8] 安装Python 3.9+...${NC}"
sudo apt install -y python3 python3-pip python3-venv python3-dev
python3 --version

echo -e "${BLUE}[4/8] 安装Node.js 18...${NC}"
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs
node --version
npm --version

echo -e "${BLUE}[5/8] 安装Chrome浏览器...${NC}"
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list
sudo apt update
sudo apt install -y google-chrome-stable

echo -e "${BLUE}[6/8] 安装Nginx (可选)...${NC}"
sudo apt install -y nginx
sudo systemctl enable nginx
sudo systemctl start nginx

echo -e "${BLUE}[7/8] 配置防火墙...${NC}"
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw allow 8000/tcp  # Backend API
sudo ufw allow 5173/tcp  # Frontend Dev
sudo ufw --force enable

echo -e "${BLUE}[8/8] 创建项目目录...${NC}"
sudo mkdir -p /opt/hailuo-ai
sudo chown $USER:$USER /opt/hailuo-ai

echo ""
echo -e "${GREEN}✅ Ubuntu服务器环境配置完成！${NC}"
echo ""
echo -e "${YELLOW}下一步操作：${NC}"
echo "1. cd /opt/hailuo-ai"
echo "2. git clone https://github.com/xinsaaa/hailuo.git ."
echo "3. cp .env.example .env"
echo "4. nano .env  # 编辑配置文件"
echo "5. chmod +x start.sh stop.sh"
echo "6. ./start.sh"
echo ""
echo -e "${YELLOW}访问地址：${NC}"
echo "前端: http://你的服务器IP:5173"
echo "后端: http://你的服务器IP:8000"
echo "管理: http://你的服务器IP:5173/admin"
echo ""
