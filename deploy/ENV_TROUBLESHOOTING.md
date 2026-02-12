# 🔧 Ubuntu服务器环境变量不生效问题排查指南

## 🚨 常见问题和解决方案

### 1. .env文件不存在或路径错误
```bash
# 检查.env文件是否存在
ls -la /opt/hailuo-ai/.env

# 如果不存在，复制模板
cp /opt/hailuo-ai/.env.example /opt/hailuo-ai/.env
```

### 2. .env文件权限问题
```bash
# 设置正确的文件权限
chmod 600 /opt/hailuo-ai/.env
chown $USER:$USER /opt/hailuo-ai/.env
```

### 3. 环境变量格式错误
```bash
# 检查.env文件格式，确保没有空格
cat /opt/hailuo-ai/.env | grep -E "^[A-Z]"

# 正确格式示例：
SECRET_KEY=your_secret_key
# 错误格式：
# SECRET_KEY = your_secret_key  (有空格)
```

### 4. Python进程未加载.env文件
```bash
# 方法1: 手动加载环境变量
export $(grep -v '^#' /opt/hailuo-ai/.env | xargs)

# 方法2: 使用python-dotenv (推荐)
cd /opt/hailuo-ai/backend
source venv/bin/activate
pip install python-dotenv
```

### 5. 系统服务未正确配置
```bash
# 如果使用systemd服务
sudo systemctl edit hailuo-ai.service

# 添加环境变量文件路径
[Service]
EnvironmentFile=/opt/hailuo-ai/.env
```

### 6. Docker环境变量问题
```bash
# 检查docker-compose.yml中的环境变量配置
# 确保env_file正确指向.env文件

services:
  hailuo-ai:
    env_file:
      - .env
```

## 🔍 调试方法

### 检查环境变量是否加载
```python
# 在backend/main.py开头添加调试代码
import os
print("=== 环境变量调试 ===")
print(f"SECRET_KEY: {os.getenv('SECRET_KEY', 'NOT_FOUND')}")
print(f"ADMIN_PASSWORD: {os.getenv('ADMIN_PASSWORD', 'NOT_FOUND')}")
print(f"SMTP_USER: {os.getenv('SMTP_USER', 'NOT_FOUND')}")
print("==================")
```

### 检查服务状态
```bash
# 检查服务运行状态
ps aux | grep uvicorn
ps aux | grep node

# 查看服务日志
tail -f /opt/hailuo-ai/logs/backend.log
tail -f /opt/hailuo-ai/logs/frontend.log
```

## ✅ 正确的启动流程

### 手动启动（推荐用于调试）
```bash
cd /opt/hailuo-ai

# 1. 确保.env文件存在
cp .env.example .env
nano .env  # 编辑配置

# 2. 加载环境变量
export $(grep -v '^#' .env | xargs)

# 3. 启动后端
cd backend
source venv/bin/activate
python -m uvicorn main:app --host 0.0.0.0 --port 8000

# 4. 新终端启动前端
cd /opt/hailuo-ai/frontend
npm run dev -- --host 0.0.0.0
```

### 使用启动脚本
```bash
cd /opt/hailuo-ai
chmod +x start.sh stop.sh
./start.sh
```

### 使用systemd服务
```bash
# 复制服务文件
sudo cp deploy/hailuo-ai.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable hailuo-ai
sudo systemctl start hailuo-ai
```

## 🛠️ 快速修复命令

```bash
# 一键修复环境变量问题
cd /opt/hailuo-ai
cp .env.example .env
chmod 600 .env
export $(grep -v '^#' .env | xargs)
./stop.sh
./start.sh
```
