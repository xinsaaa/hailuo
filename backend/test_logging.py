"""
简单的日志系统测试脚本
运行: python -m backend.test_logging
"""
import os
import sys

# 设置测试环境变量
os.environ["LOG_LEVEL"] = "DEBUG"
os.environ["LOG_FORMAT"] = "json"
os.environ["ENVIRONMENT"] = "development"

from backend.logger import app_logger
from backend.middleware.context import set_request_id, set_user_id, generate_request_id


def test_basic_logging():
    """测试基本日志功能"""
    print("\n=== 测试基本日志功能 ===")
    
    app_logger.debug("This is a debug message", test_id=1)
    app_logger.info("This is an info message", test_id=2)
    app_logger.warning("This is a warning message", test_id=3)
    app_logger.error("This is an error message", test_id=4)
    
    print("✅ 基本日志测试完成")


def test_request_context():
    """测试请求上下文"""
    print("\n=== 测试请求上下文 ===")
    
    # 模拟请求
    request_id = generate_request_id()
    set_request_id(request_id)
    set_user_id(123)
    
    app_logger.info("Request started", method="GET", path="/api/test")
    app_logger.info("Processing request", step=1)
    app_logger.info("Request completed", status_code=200)
    
    print(f"✅ 请求上下文测试完成 (request_id: {request_id})")


def test_exception_logging():
    """测试异常日志"""
    print("\n=== 测试异常日志 ===")
    
    try:
        # 模拟异常
        result = 1 / 0
    except Exception as e:
        app_logger.error("Division by zero error", exc_info=e, operation="divide")
    
    print("✅ 异常日志测试完成")


def test_audit_logging():
    """测试审计日志"""
    print("\n=== 测试审计日志 ===")
    
    app_logger.audit(
        "user.register",
        user_id=456,
        username="test_user",
        email="test@example.com",
        register_ip="127.0.0.1"
    )
    
    app_logger.audit(
        "payment.completed",
        user_id=456,
        amount=100.0,
        payment_method="alipay",
        transaction_id="TXN123456"
    )
    
    print("✅ 审计日志测试完成")


def test_sensitive_data_masking():
    """测试敏感信息脱敏"""
    print("\n=== 测试敏感信息脱敏 ===")
    
    app_logger.info(
        "User data",
        username="john",
        password="secret123",  # 应该被脱敏
        email="john@example.com",
        token="abc123xyz",  # 应该被脱敏
        api_key="key_12345"  # 应该被脱敏
    )
    
    print("✅ 敏感信息脱敏测试完成")


def main():
    """运行所有测试"""
    print("=" * 60)
    print("日志系统测试")
    print("=" * 60)
    
    test_basic_logging()
    test_request_context()
    test_exception_logging()
    test_audit_logging()
    test_sensitive_data_masking()
    
    print("\n" + "=" * 60)
    print("所有测试完成！")
    print("=" * 60)
    print("\n请检查 logs/ 目录下的日志文件：")
    print("  - app_*.log (所有日志)")
    print("  - error_*.log (错误日志)")
    print("  - audit_*.log (审计日志)")


if __name__ == "__main__":
    main()
