# 日志系统安装指南

## 快速开始

### 1. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

新增的依赖：
- `loguru` - 日志库
- `hypothesis` - 属性测试库（用于未来的测试）

### 2. 配置环境变量

复制 `.env.example` 到 `.env` 并根据需要调整配置：

```bash
cp .env.example .env
```

关键配置项：

```bash
# 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_LEVEL=INFO

# 日志格式 (json, text)
LOG_FORMAT=json

# 日志目录
LOG_DIR=./logs

# 环境 (development, production)
ENVIRONMENT=development
```

### 3. 测试日志系统

运行测试脚本验证日志系统工作正常：

```bash
python -m backend.test_logging
```

预期输出：
```
============================================================
日志系统测试
============================================================

=== 测试基本日志功能 ===
✅ 基本日志测试完成

=== 测试请求上下文 ===
✅ 请求上下文测试完成 (request_id: ...)

=== 测试异常日志 ===
✅ 异常日志测试完成

=== 测试审计日志 ===
✅ 审计日志测试完成

=== 测试敏感信息脱敏 ===
✅ 敏感信息脱敏测试完成

============================================================
所有测试完成！
============================================================
```

### 4. 检查日志文件

```bash
# 查看日志目录
ls -lh logs/

# 应该看到以下文件：
# - app_2024-XX-XX.log (所有日志)
# - error_2024-XX-XX.log (错误日志)
# - audit_2024-XX-XX.log (审计日志)
```

### 5. 启动应用

```bash
# 开发模式
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# 生产模式
export ENVIRONMENT=production
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 6. 验证日志记录

访问任意 API 端点，例如：

```bash
curl http://localhost:8000/api/config
```

然后查看日志：

```bash
tail -f logs/app_$(date +%Y-%m-%d).log
```

你应该看到类似的日志条目：

```json
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "level": "INFO",
  "module": "backend.middleware.logging",
  "function": "dispatch",
  "line": 20,
  "message": "Request started",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "extra": {
    "method": "GET",
    "path": "/api/config",
    "client_ip": "127.0.0.1"
  }
}
```

## 已实现的功能

✅ **核心日志系统**
- 结构化 JSON 日志
- 彩色控制台输出（开发模式）
- 多级别日志（DEBUG, INFO, WARNING, ERROR, CRITICAL）

✅ **请求追踪**
- 自动生成唯一 request_id
- request_id 添加到响应头
- request_id 自动注入到所有日志

✅ **全局异常处理**
- 捕获所有未处理异常
- 记录完整堆栈跟踪
- 返回标准化错误响应

✅ **审计日志**
- 独立的审计日志文件
- 记录关键业务操作（注册、登录等）

✅ **日志管理**
- 自动日志轮转（100MB）
- 自动压缩（gzip）
- 自动清理（30天）

✅ **安全特性**
- 敏感信息自动脱敏
- 生产环境不暴露内部错误详情

✅ **性能优化**
- 异步日志写入
- 不阻塞请求处理

## 使用示例

### 在代码中使用日志

```python
from backend.logger import app_logger

# 基本日志
app_logger.info("User created", user_id=123, username="john")

# 错误日志（带异常）
try:
    # some code
    pass
except Exception as e:
    app_logger.error("Operation failed", exc_info=e, operation="create_user")

# 审计日志
app_logger.audit(
    "user.register",
    user_id=user.id,
    username=user.username,
    register_ip=client_ip
)
```

### 抛出自定义异常

```python
from backend.exceptions import ValidationException, NotFoundException

# 验证错误
raise ValidationException(
    "Invalid input",
    field_errors={"email": "Invalid email format"}
)

# 资源不存在
raise NotFoundException("User", user_id=123)
```

## 故障排查

### 问题：日志文件未创建

**解决方案**：
1. 检查 `LOG_DIR` 环境变量是否正确
2. 确保应用有权限创建日志目录
3. 检查磁盘空间是否充足

### 问题：日志级别不生效

**解决方案**：
1. 检查 `LOG_LEVEL` 环境变量是否正确设置
2. 重启应用使配置生效
3. 确保环境变量在应用启动前设置

### 问题：敏感信息未脱敏

**解决方案**：
1. 检查字段名是否在 `SENSITIVE_FIELDS` 列表中
2. 如需添加新的敏感字段，编辑 `backend/logger.py`

### 问题：请求 ID 未出现在日志中

**解决方案**：
1. 确保中间件顺序正确（RequestIDMiddleware 在 LoggingMiddleware 之前）
2. 检查是否在请求上下文中调用日志

## 下一步

1. **完善审计日志**：在所有关键业务操作中添加审计日志
2. **添加日志查询 API**：方便运维人员查询和分析日志
3. **集成监控系统**：将日志发送到 ELK、Loki 等日志聚合系统
4. **添加告警**：对 ERROR 和 CRITICAL 级别日志设置告警

## 文档

- [日志系统文档](./LOGGING.md) - 详细的使用文档
- [实施进度](./.kiro/specs/logging-and-error-handling/PROGRESS.md) - 当前实施进度
- [需求文档](./.kiro/specs/logging-and-error-handling/requirements.md) - 完整需求
- [设计文档](./.kiro/specs/logging-and-error-handling/design.md) - 技术设计

## 支持

如有问题，请查看：
1. 日志文件：`logs/error_*.log`
2. 应用日志：`logs/app_*.log`
3. 审计日志：`logs/audit_*.log`
