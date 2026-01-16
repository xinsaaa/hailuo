# Backend Setup Guide

## 1. Create and Activate Environment

```bash
# Create a new environment named 'hailuo' with Python 3.10
conda create -n hailuo python=3.10

# Activate the environment
conda activate hailuo
```

## 2. Install Dependencies

Navigate to the `backend` directory and install the required packages:

```bash
cd backend
pip install -r requirements.txt
```

## 3. Install Playwright Browsers

### Windows/有界面环境:
```bash
playwright install chromium
# 或安装 Chrome (推荐)
playwright install chrome
```

### Linux 无界面服务器:
```bash
# 安装系统依赖
sudo apt-get update
sudo apt-get install -y libnss3-dev libatk-bridge2.0-dev libx11-xcb1 libxcb-dri3-0 libxcomposite1 libxdamage1 libxrandr2 libgbm1 libgtk-3-0 libasound2

# 安装 Chromium
playwright install chromium

# 验证无界面模式
playwright install-deps
```

## 4. Environment Variables (Optional)

Create a `.env` file in the project root:

```bash
# 强制使用无界面模式 (Linux服务器会自动检测)
AUTOMATION_HEADLESS=true

# 自动化服务配置
HAILUO_PHONE=17366935232
```

## 5. Run the Server

**Important**: You must run the server from the **root directory** (the parent of `backend`):

### Windows:
```bash
cd ..
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### Linux (生产环境):
```bash
cd ..
# 使用 gunicorn 提高性能
pip install gunicorn
gunicorn backend.main:app -w 1 -k uvicorn.workers.UnicornWorker --bind 0.0.0.0:8000
```

## 6. Linux 无界面环境自动化

系统会自动检测运行环境：
- ✅ **Linux + 无DISPLAY环境变量**: 自动使用headless模式
- ✅ **Windows**: 默认使用有界面模式  
- ✅ **强制headless**: 设置环境变量 `AUTOMATION_HEADLESS=true`

### 验证自动化功能:
```bash
# 启动后端后，查看日志输出：
# [AUTOMATION] 浏览器启动成功 (无界面模式)  ✅
# [AUTOMATION] 浏览器启动成功 (有界面模式)  ✅
```
