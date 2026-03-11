#!/bin/bash
# 即梦服务管理脚本
# 用于在 screen 中启动、停止、重启服务

SCREEN_NAME="jimeng"
PROJECT_DIR="/home/ubuntu/hailuo"
VENV_PATH="$PROJECT_DIR/venv"
PYTHON_CMD="$VENV_PATH/bin/python"
MAIN_SCRIPT="$PROJECT_DIR/backend/main.py"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# 检查服务是否在运行
is_running() {
    screen -list | grep -q "$SCREEN_NAME"
    return $?
}

# 启动服务
start() {
    if is_running; then
        log "${YELLOW}服务已在运行中${NC}"
        return 1
    fi
    
    log "${GREEN}启动服务...${NC}"
    cd $PROJECT_DIR
    screen -dmS $SCREEN_NAME bash -c "source $VENV_PATH/bin/activate && $PYTHON_CMD $MAIN_SCRIPT"
    sleep 2
    
    if is_running; then
        log "${GREEN}服务启动成功${NC}"
        return 0
    else
        log "${RED}服务启动失败${NC}"
        return 1
    fi
}

# 停止服务
stop() {
    if ! is_running; then
        log "${YELLOW}服务未在运行${NC}"
        return 1
    fi
    
    log "${YELLOW}停止服务...${NC}"
    screen -S $SCREEN_NAME -X quit
    sleep 2
    
    if is_running; then
        log "${RED}服务停止失败${NC}"
        return 1
    else
        log "${GREEN}服务已停止${NC}"
        return 0
    fi
}

# 重启服务
restart() {
    log "${YELLOW}重启服务...${NC}"
    stop
    sleep 2
    start
}

# 查看状态
status() {
    if is_running; then
        log "${GREEN}服务运行中${NC}"
        screen -list | grep $SCREEN_NAME
    else
        log "${RED}服务未运行${NC}"
    fi
}

# 查看日志
logs() {
    if is_running; then
        screen -r $SCREEN_NAME
    else
        log "${RED}服务未运行${NC}"
    fi
}

# 健康检查（用于定时任务）
health_check() {
    # 检查服务是否在运行
    if ! is_running; then
        log "${RED}服务未运行，尝试启动...${NC}"
        start
        return
    fi
    
    # 检查 API 是否响应
    response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/health 2>/dev/null)
    if [ "$response" != "200" ]; then
        log "${RED}API 无响应 ($response)，重启服务...${NC}"
        restart
    else
        log "${GREEN}服务正常${NC}"
    fi
}

# 定时重启（用于 crontab）
scheduled_restart() {
    log "${YELLOW}执行定时重启...${NC}"
    restart
    log "${GREEN}定时重启完成${NC}"
}

# 主入口
case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    status)
        status
        ;;
    logs)
        logs
        ;;
    health)
        health_check
        ;;
    scheduled)
        scheduled_restart
        ;;
    *)
        echo "用法: $0 {start|stop|restart|status|logs|health|scheduled}"
        echo ""
        echo "命令说明:"
        echo "  start     - 启动服务"
        echo "  stop      - 停止服务"
        echo "  restart   - 重启服务"
        echo "  status    - 查看状态"
        echo "  logs      - 查看日志（进入 screen）"
        echo "  health    - 健康检查（用于定时任务）"
        echo "  scheduled - 定时重启（用于 crontab）"
        exit 1
        ;;
esac
