#!/bin/bash
# 即梦服务增强管理脚本
# 支持优雅重启、健康检查、自动恢复、定时重启

# ==================== 配置区 ====================
SCREEN_NAME="jimeng"
PROJECT_DIR="/home/ubuntu/hailuo"  # 修改为你的项目路径
VENV_PATH="$PROJECT_DIR/venv"
PYTHON_CMD="$VENV_PATH/bin/python"
UVICORN_CMD="$VENV_PATH/bin/uvicorn"
MAIN_MODULE="backend.main:app"
LOG_DIR="$PROJECT_DIR/logs"
PID_FILE="$PROJECT_DIR/jimeng.pid"
LOCK_FILE="$PROJECT_DIR/jimeng.lock"

# API 配置
API_HOST="localhost"
API_PORT="8000"
API_HEALTH_URL="http://${API_HOST}:${API_PORT}/api/config"

# 重启配置
GRACEFUL_SHUTDOWN_TIMEOUT=300  # 优雅关闭超时时间（秒）
STARTUP_WAIT_TIME=10           # 启动后等待时间（秒）
MAX_RESTART_ATTEMPTS=3         # 最大重启尝试次数

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ==================== 工具函数 ====================

log() {
    local level=$1
    shift
    local message="$@"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    case $level in
        INFO)
            echo -e "${GREEN}[INFO]${NC} [$timestamp] $message"
            ;;
        WARN)
            echo -e "${YELLOW}[WARN]${NC} [$timestamp] $message"
            ;;
        ERROR)
            echo -e "${RED}[ERROR]${NC} [$timestamp] $message"
            ;;
        DEBUG)
            echo -e "${BLUE}[DEBUG]${NC} [$timestamp] $message"
            ;;
        *)
            echo "[$timestamp] $message"
            ;;
    esac

    # 同时写入日志文件
    echo "[$level] [$timestamp] $message" >> "$LOG_DIR/service.log"
}

# 检查服务是否在运行
is_running() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if ps -p $pid > /dev/null 2>&1; then
            return 0
        else
            # PID 文件存在但进程不存在，清理 PID 文件
            rm -f "$PID_FILE"
            return 1
        fi
    fi

    # 备用检查：通过 screen 检查
    screen -list | grep -q "$SCREEN_NAME"
    return $?
}

# 获取服务 PID
get_pid() {
    if [ -f "$PID_FILE" ]; then
        cat "$PID_FILE"
    else
        echo ""
    fi
}

# 检查 API 健康状态
check_api_health() {
    local response=$(curl -s -o /dev/null -w "%{http_code}" "$API_HEALTH_URL" 2>/dev/null)
    if [ "$response" = "200" ]; then
        return 0
    else
        return 1
    fi
}

# 等待 API 就绪
wait_for_api() {
    local max_wait=$1
    local wait_time=0

    log INFO "等待 API 就绪（最多 ${max_wait} 秒）..."

    while [ $wait_time -lt $max_wait ]; do
        if check_api_health; then
            log INFO "API 已就绪"
            return 0
        fi
        sleep 2
        wait_time=$((wait_time + 2))
    done

    log ERROR "API 启动超时"
    return 1
}

# 获取文件锁
acquire_lock() {
    local timeout=${1:-10}
    local waited=0

    while [ -f "$LOCK_FILE" ]; do
        if [ $waited -ge $timeout ]; then
            log ERROR "获取锁超时"
            return 1
        fi
        log WARN "等待锁释放..."
        sleep 1
        waited=$((waited + 1))
    done

    touch "$LOCK_FILE"
    return 0
}

# 释放文件锁
release_lock() {
    rm -f "$LOCK_FILE"
}

# ==================== 核心功能 ====================

# 启动服务
start() {
    if ! acquire_lock; then
        return 1
    fi

    trap release_lock EXIT

    if is_running; then
        log WARN "服务已在运行中（PID: $(get_pid)）"
        release_lock
        return 1
    fi

    log INFO "启动服务..."

    # 确保日志目录存在
    mkdir -p "$LOG_DIR"

    # 切换到项目目录
    cd "$PROJECT_DIR" || {
        log ERROR "无法切换到项目目录: $PROJECT_DIR"
        release_lock
        return 1
    }

    # 启动服务（使用 screen）
    screen -dmS "$SCREEN_NAME" bash -c "
        source $VENV_PATH/bin/activate
        $UVICORN_CMD $MAIN_MODULE --host 0.0.0.0 --port $API_PORT --log-level info
    "

    # 等待进程启动
    sleep 2

    # 获取 PID
    local pid=$(pgrep -f "uvicorn.*$MAIN_MODULE" | head -1)
    if [ -n "$pid" ]; then
        echo $pid > "$PID_FILE"
        log INFO "服务已启动（PID: $pid）"
    else
        log ERROR "无法获取服务 PID"
        release_lock
        return 1
    fi

    # 等待 API 就绪
    if wait_for_api $STARTUP_WAIT_TIME; then
        log INFO "✓ 服务启动成功"
        release_lock
        return 0
    else
        log ERROR "✗ 服务启动失败"
        stop
        release_lock
        return 1
    fi
}

# 停止服务（强制）
stop() {
    if ! is_running; then
        log WARN "服务未在运行"
        return 1
    fi

    local pid=$(get_pid)
    log INFO "停止服务（PID: $pid）..."

    # 关闭 screen 会话
    screen -S "$SCREEN_NAME" -X quit 2>/dev/null

    # 等待进程结束
    local waited=0
    while ps -p $pid > /dev/null 2>&1; do
        if [ $waited -ge 10 ]; then
            log WARN "进程未响应，强制终止..."
            kill -9 $pid 2>/dev/null
            break
        fi
        sleep 1
        waited=$((waited + 1))
    done

    # 清理 PID 文件
    rm -f "$PID_FILE"

    log INFO "✓ 服务已停止"
    return 0
}

# 优雅停止服务
graceful_stop() {
    if ! is_running; then
        log WARN "服务未在运行"
        return 1
    fi

    local pid=$(get_pid)
    log INFO "优雅停止服务（PID: $pid）..."
    log INFO "等待正在执行的任务完成（最多 ${GRACEFUL_SHUTDOWN_TIMEOUT} 秒）..."

    # 发送 SIGTERM 信号
    kill -TERM $pid 2>/dev/null

    # 等待进程优雅退出
    local waited=0
    while ps -p $pid > /dev/null 2>&1; do
        if [ $waited -ge $GRACEFUL_SHUTDOWN_TIMEOUT ]; then
            log WARN "优雅关闭超时，强制终止..."
            kill -9 $pid 2>/dev/null
            break
        fi

        # 每 10 秒输出一次进度
        if [ $((waited % 10)) -eq 0 ]; then
            log INFO "已等待 ${waited}/${GRACEFUL_SHUTDOWN_TIMEOUT} 秒..."
        fi

        sleep 1
        waited=$((waited + 1))
    done

    # 关闭 screen 会话
    screen -S "$SCREEN_NAME" -X quit 2>/dev/null

    # 清理 PID 文件
    rm -f "$PID_FILE"

    log INFO "✓ 服务已优雅停止（等待时间: ${waited} 秒）"
    return 0
}

# 重启服务（普通）
restart() {
    log INFO "重启服务..."
    stop
    sleep 2
    start
}

# 优雅重启服务
graceful_restart() {
    if ! acquire_lock; then
        return 1
    fi

    trap release_lock EXIT

    log INFO "=========================================="
    log INFO "开始优雅重启服务"
    log INFO "=========================================="

    # 优雅停止
    graceful_stop

    # 等待一段时间
    log INFO "等待 3 秒后启动..."
    sleep 3

    # 启动服务
    if start; then
        log INFO "=========================================="
        log INFO "✓ 优雅重启完成"
        log INFO "=========================================="
        release_lock
        return 0
    else
        log ERROR "=========================================="
        log ERROR "✗ 优雅重启失败"
        log ERROR "=========================================="
        release_lock
        return 1
    fi
}

# 查看状态
status() {
    echo "=========================================="
    echo "服务状态"
    echo "=========================================="

    if is_running; then
        local pid=$(get_pid)
        echo -e "${GREEN}● 服务运行中${NC}"
        echo "  PID: $pid"

        # 显示进程信息
        echo ""
        echo "进程信息:"
        ps -p $pid -o pid,ppid,%cpu,%mem,etime,cmd --no-headers

        # 检查 API 健康状态
        echo ""
        if check_api_health; then
            echo -e "${GREEN}✓ API 健康检查通过${NC}"
        else
            echo -e "${RED}✗ API 健康检查失败${NC}"
        fi

        # 显示 screen 会话
        echo ""
        echo "Screen 会话:"
        screen -list | grep "$SCREEN_NAME" || echo "  无"

    else
        echo -e "${RED}○ 服务未运行${NC}"
    fi

    echo "=========================================="
}

# 查看日志
logs() {
    if [ "$1" = "-f" ]; then
        # 实时查看日志
        if is_running; then
            log INFO "进入 screen 会话（按 Ctrl+A 然后按 D 退出）..."
            sleep 1
            screen -r "$SCREEN_NAME"
        else
            log ERROR "服务未运行"
            return 1
        fi
    else
        # 查看日志文件
        if [ -f "$LOG_DIR/service.log" ]; then
            tail -n 50 "$LOG_DIR/service.log"
        else
            log WARN "日志文件不存在"
        fi
    fi
}

# 健康检查（用于定时任务）
health_check() {
    log INFO "执行健康检查..."

    # 检查服务是否在运行
    if ! is_running; then
        log ERROR "服务未运行，尝试启动..."
        start
        return $?
    fi

    # 检查 API 是否响应
    if ! check_api_health; then
        log ERROR "API 无响应，尝试重启..."
        graceful_restart
        return $?
    fi

    log INFO "✓ 健康检查通过"
    return 0
}

# 定时重启（用于 crontab）
scheduled_restart() {
    log INFO "=========================================="
    log INFO "执行定时重启"
    log INFO "=========================================="

    graceful_restart

    local exit_code=$?

    if [ $exit_code -eq 0 ]; then
        log INFO "✓ 定时重启成功"
    else
        log ERROR "✗ 定时重启失败"

        # 尝试强制重启
        log WARN "尝试强制重启..."
        restart
    fi

    return $exit_code
}

# 数据库备份
backup_database() {
    local backup_dir="$PROJECT_DIR/backups"
    local db_file="$PROJECT_DIR/backend/database.db"
    local timestamp=$(date '+%Y%m%d_%H%M%S')
    local backup_file="$backup_dir/database_${timestamp}.db"

    mkdir -p "$backup_dir"

    if [ -f "$db_file" ]; then
        log INFO "备份数据库..."
        cp "$db_file" "$backup_file"

        # 压缩备份
        gzip "$backup_file"

        log INFO "✓ 数据库已备份到: ${backup_file}.gz"

        # 清理旧备份（保留最近 7 天）
        find "$backup_dir" -name "database_*.db.gz" -mtime +7 -delete

        return 0
    else
        log ERROR "数据库文件不存在: $db_file"
        return 1
    fi
}

# ==================== 主入口 ====================

# 确保日志目录存在
mkdir -p "$LOG_DIR"

case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    graceful-stop)
        graceful_stop
        ;;
    restart)
        restart
        ;;
    graceful-restart)
        graceful_restart
        ;;
    status)
        status
        ;;
    logs)
        logs "$2"
        ;;
    health)
        health_check
        ;;
    scheduled)
        scheduled_restart
        ;;
    backup)
        backup_database
        ;;
    *)
        echo "用法: $0 {start|stop|graceful-stop|restart|graceful-restart|status|logs|health|scheduled|backup}"
        echo ""
        echo "命令说明:"
        echo "  start             - 启动服务"
        echo "  stop              - 停止服务（强制）"
        echo "  graceful-stop     - 优雅停止服务（等待任务完成）"
        echo "  restart           - 重启服务（强制）"
        echo "  graceful-restart  - 优雅重启服务（推荐）"
        echo "  status            - 查看服务状态"
        echo "  logs [-f]         - 查看日志（-f 实时查看）"
        echo "  health            - 健康检查（用于定时任务）"
        echo "  scheduled         - 定时重启（用于 crontab）"
        echo "  backup            - 备份数据库"
        echo ""
        echo "示例:"
        echo "  $0 start                    # 启动服务"
        echo "  $0 graceful-restart         # 优雅重启"
        echo "  $0 logs -f                  # 实时查看日志"
        echo "  $0 status                   # 查看状态"
        exit 1
        ;;
esac

exit $?
