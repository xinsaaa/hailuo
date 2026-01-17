# 海螺AI自动化系统 - Linux Docker镜像
FROM ubuntu:22.04

# 设置时区和语言
ENV TZ=Asia/Shanghai
ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    nodejs \
    npm \
    git \
    curl \
    wget \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# 创建应用目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .
COPY package*.json ./frontend/ 2>/dev/null || true

# 安装Python依赖
RUN pip3 install --no-cache-dir -r requirements.txt

# 安装Playwright浏览器
RUN python3 -m playwright install-deps
RUN python3 -m playwright install chromium

# 复制前端并构建
COPY frontend ./frontend
RUN cd frontend && npm install && npm run build && cd ..

# 复制后端代码
COPY backend ./backend
COPY *.py .
COPY *.md .

# 创建必要目录
RUN mkdir -p data logs uploads user_images temp

# 设置权限
RUN chmod -R 755 data logs uploads user_images temp

# 创建非root用户
RUN useradd -m -u 1000 hailuo && chown -R hailuo:hailuo /app
USER hailuo

# 环境变量配置
ENV AUTOMATION_HEADLESS=true
ENV ENABLE_AUTO_WORKER=true
ENV PYTHONPATH=/app

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/api/config || exit 1

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["python3", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
