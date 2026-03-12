#!/bin/bash
# 即梦服务一键安装脚本

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}即梦服务一键安装脚本${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 检查是否为 root 用户
if [ "$EUID" -eq 0 ]; then
    echo -e "${YELLOW}警告: 不建议使用 root 用户运行此脚本${NC}"
    read -p "是否继续? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 获取项目路径
CURRENT_DIR=$(pwd)
echo -e "${GREEN}当前目录: $CURRENT_DIR${NC}"
read -p "项目路径 (默认: $CURRENT_DIR): " PROJECT_DIR
PROJECT_DIR=${PROJECT_DIR:-$CURRENT_DIR}

echo ""
echo -e "${BLUE}项目路径: $PROJECT_DIR${NC}"
echo ""

# 检查项目目录
if [ ! -d "$PROJECT_DIR/backend" ]; then
    echo -e "${RED}错误: 未找到 backend 目录，请确认项目路径正确${NC}"
    exit 1
fi

# 1. 安装系统依赖
echo -e "${GREEN}[1/7] 检查系统依赖...${NC}"

if ! command -v python3 &> /dev/null; then
    echo -e "${YELLOW}安装 Python 3...${NC}"
    sudo apt-get update
    sudo apt-get install -y python3 python3-pip python3-venv
fi

if ! command -v screen &> /dev/null; then
    echo -e "${YELLOW}安装 screen...${NC}"
    sudo apt-get install -y screen
fi

if ! command -v curl &> /dev/null; then
    echo -e "${YELLOW}安装 curl...${NC}"
    sudo apt-get install -y curl
fi

echo -e "${GREEN}✓ 系统依赖检查完成${NC}"
echo ""

# 2. 创建虚拟环境
echo -e "${GREEN}[2/7] 创建 Python 虚拟环境...${NC}"

cd "$PROJECT_DIR"

if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}✓ 虚拟环境创建完成${NC}"
else
    echo -e "${YELLOW}虚拟环境已存在，跳过${NC}"
fi

echo ""

# 3. 安装 Python 依赖
echo -e "${GREEN}[3/7] 安装 Python 依赖...${NC}"

source venv/bin/activate

if [ -f "backend/requirements.txt" ]; then
    pip install --upgrade pip
    pip install -r backend/requirements.txt
    echo -e "${GREEN}✓ Python 依赖安装完成${NC}"
else
    echo -e "${RED}错误: 未找到 requirements.txt${NC}"
    exit 1
fi

echo ""

# 4. 安装 Playwright 浏览器
echo -e "${GREEN}[4/7] 安装 Playwright 浏览器...${NC}"

playwright install chromium
playwright install-deps chromium

echo -e "${GREEN}✓ Playwright 浏览器安装完成${NC}"
echo ""

# 5. 创建必要的目录
echo -e "${GREEN}[5/7] 创建必要的目录...${NC}"

mkdir -p logs
mkdir -p data
mkdir -p uploads
mkdir -p user_images
mkdir -p login_state
mkdir -p backups

echo -e "${GREEN}✓ 目录创建完成${NC}"
echo ""

# 6. 配置服务脚本
echo -e "${GREEN}[6/7] 配置服务脚本...${NC}"

# 修改脚本中的项目路径
sed -i "s|PROJECT_DIR=\"/home/ubuntu/hailuo\"|PROJECT_DIR=\"$PROJECT_DIR\"|g" scripts/jimeng_service_enhanced.sh

# 添加执行权限
chmod +x scripts/jimeng_service_enhanced.sh

echo -e "${GREEN}✓ 服务脚本配置完成${NC}"
echo ""

# 7. 配置 crontab
echo -e "${GREEN}[7/7] 配置定时任务...${NC}"

read -p "是否配置定时任务? (y/n) " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    # 修改 crontab 配置中的项目路径
    sed -i "s|PROJECT_DIR=/home/ubuntu/hailuo|PROJECT_DIR=$PROJECT_DIR|g" scripts/crontab_config.txt

    echo ""
    echo -e "${YELLOW}请手动执行以下命令配置 crontab:${NC}"
    echo -e "${BLUE}crontab -e${NC}"
    echo ""
    echo -e "${YELLOW}然后将以下内容添加到 crontab 中:${NC}"
    echo ""
    cat scripts/crontab_config.txt | grep -v "^#" | grep -v "^$"
    echo ""
else
    echo -e "${YELLOW}跳过定时任务配置${NC}"
fi

echo ""

# 安装完成
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ 安装完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

echo -e "${BLUE}使用方法:${NC}"
echo ""
echo -e "  启动服务:         ${GREEN}./scripts/jimeng_service_enhanced.sh start${NC}"
echo -e "  停止服务:         ${GREEN}./scripts/jimeng_service_enhanced.sh stop${NC}"
echo -e "  优雅重启:         ${GREEN}./scripts/jimeng_service_enhanced.sh graceful-restart${NC}"
echo -e "  查看状态:         ${GREEN}./scripts/jimeng_service_enhanced.sh status${NC}"
echo -e "  查看日志:         ${GREEN}./scripts/jimeng_service_enhanced.sh logs -f${NC}"
echo -e "  健康检查:         ${GREEN}./scripts/jimeng_service_enhanced.sh health${NC}"
echo -e "  备份数据库:       ${GREEN}./scripts/jimeng_service_enhanced.sh backup${NC}"
echo ""

echo -e "${YELLOW}建议:${NC}"
echo -e "  1. 配置定时任务实现自动重启和健康检查"
echo -e "  2. 定期备份数据库（已包含在 crontab 配置中）"
echo -e "  3. 监控日志文件: ${BLUE}tail -f logs/service.log${NC}"
echo ""

# 询问是否立即启动服务
read -p "是否立即启动服务? (y/n) " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    ./scripts/jimeng_service_enhanced.sh start
fi

echo ""
echo -e "${GREEN}安装脚本执行完成！${NC}"
