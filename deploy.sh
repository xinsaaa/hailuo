#!/bin/bash
# ===================================================
# 大帝AI视频生成平台 - 宝塔一键部署脚本
# 使用方法: chmod +x deploy.sh && ./deploy.sh
# ===================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 配置变量 (请根据实际情况修改)
PROJECT_DIR="/www/wwwroot/hailuo"
FRONTEND_PORT="5173"
BACKEND_PORT="8000"
DOMAIN="your-domain.com"  # 替换为你的域名
GIT_REPO="https://github.com/xinsaaa/hailuo.git"

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  大帝AI视频生成平台 - 宝塔部署脚本${NC}"
echo -e "${BLUE}============================================${NC}"

# 检查是否为 root 用户
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}请使用 root 用户运行此脚本${NC}"
    exit 1
fi

# 1. 安装系统依赖
echo -e "\n${GREEN}[1/7] 安装系统依赖...${NC}"
apt-get update -qq
apt-get install -y -qq git curl wget python3 python3-pip python3-venv nodejs npm

# 检查 Node.js 版本
NODE_VERSION=$(node -v | cut -d'.' -f1 | tr -d 'v')
if [ "$NODE_VERSION" -lt 16 ]; then
    echo -e "${YELLOW}Node.js 版本过低，正在升级...${NC}"
    curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
    apt-get install -y nodejs
fi

# 2. 克隆/更新项目
echo -e "\n${GREEN}[2/7] 获取项目代码...${NC}"
if [ -d "$PROJECT_DIR" ]; then
    echo "项目目录已存在，正在更新..."
    cd "$PROJECT_DIR"
    git pull origin main
else
    echo "克隆项目..."
    git clone "$GIT_REPO" "$PROJECT_DIR"
    cd "$PROJECT_DIR"
fi

# 3. 配置 Python 虚拟环境
echo -e "\n${GREEN}[3/7] 配置 Python 后端...${NC}"
cd "$PROJECT_DIR/backend"

if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate

pip install --upgrade pip -q
pip install -r requirements.txt -q

# 安装 Playwright 浏览器 (用于自动化)
playwright install chromium --with-deps 2>/dev/null || true

deactivate

# 4. 构建前端
echo -e "\n${GREEN}[4/7] 构建前端...${NC}"
cd "$PROJECT_DIR/frontend"
npm install --silent
npm run build

# 5. 创建 Supervisor 配置 (后端进程管理)
echo -e "\n${GREEN}[5/7] 配置 Supervisor...${NC}"
cat > /etc/supervisor/conf.d/hailuo-backend.conf << EOF
[program:hailuo-backend]
directory=$PROJECT_DIR/backend
command=$PROJECT_DIR/backend/venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port $BACKEND_PORT
user=root
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/hailuo-backend.log
environment=PATH="$PROJECT_DIR/backend/venv/bin"
EOF

supervisorctl reread
supervisorctl update
supervisorctl restart hailuo-backend || supervisorctl start hailuo-backend

# 6. 创建 Nginx 配置
echo -e "\n${GREEN}[6/7] 配置 Nginx...${NC}"
cat > /www/server/panel/vhost/nginx/${DOMAIN}.conf << EOF
server {
    listen 80;
    server_name $DOMAIN;
    
    # 前端静态文件
    location / {
        root $PROJECT_DIR/frontend/dist;
        index index.html;
        try_files \$uri \$uri/ /index.html;
    }
    
    # API 反向代理
    location /api {
        proxy_pass http://127.0.0.1:$BACKEND_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # WebSocket 支持
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # 超时设置
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    # 上传文件大小限制
    client_max_body_size 50M;
    
    # 静态资源缓存
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {
        root $PROJECT_DIR/frontend/dist;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
EOF

# 重载 Nginx
nginx -t && nginx -s reload

# 7. 创建更新脚本
echo -e "\n${GREEN}[7/7] 创建更新脚本...${NC}"
cat > "$PROJECT_DIR/update.sh" << 'EOF'
#!/bin/bash
# 一键更新脚本
set -e

PROJECT_DIR="/www/wwwroot/hailuo"
cd "$PROJECT_DIR"

echo "📥 拉取最新代码..."
git pull origin main

echo "📦 更新后端依赖..."
cd backend
source venv/bin/activate
pip install -r requirements.txt -q
deactivate

echo "🔨 重新构建前端..."
cd ../frontend
npm install --silent
npm run build

echo "🔄 重启后端服务..."
supervisorctl restart hailuo-backend

echo "✅ 更新完成！"
EOF

chmod +x "$PROJECT_DIR/update.sh"

# 完成
echo -e "\n${GREEN}============================================${NC}"
echo -e "${GREEN}  部署完成！${NC}"
echo -e "${GREEN}============================================${NC}"
echo -e "前端地址: ${BLUE}http://$DOMAIN${NC}"
echo -e "后端 API: ${BLUE}http://$DOMAIN/api${NC}"
echo -e ""
echo -e "后续更新只需运行: ${YELLOW}$PROJECT_DIR/update.sh${NC}"
echo -e ""
echo -e "${YELLOW}注意事项:${NC}"
echo -e "1. 请在宝塔面板中配置 SSL 证书"
echo -e "2. 请修改 backend/.env 中的配置"
echo -e "3. 查看后端日志: tail -f /var/log/hailuo-backend.log"
