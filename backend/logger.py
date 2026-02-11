"""
日志系统核心模块
使用 loguru 实现结构化日志记录
"""
import os
import sys
import json
from pathlib import Path
from typing import Any, Dict, Optional
from loguru import logger
from backend.middleware.context import get_request_id, get_user_id


# 敏感字段列表
SENSITIVE_FIELDS = {
    "password", "hashed_password", "pwd", "passwd",
    "token", "access_token", "refresh_token", "auth_token",
    "api_key", "secret_key", "secret", "key",
    "credit_card", "card_number", "cvv", "ssn",
    "private_key", "secret_access_key"
}


def mask_sensitive_data(data: Any) -> Any:
    """递归脱敏敏感信息"""
    if isinstance(data, dict):
        return {
            key: "***MASKED***" if key.lower() in SENSITIVE_FIELDS else mask_sensitive_data(value)
            for key, value in data.items()
        }
    elif isinstance(data, list):
        return [mask_sensitive_data(item) for item in data]
    elif isinstance(data, tuple):
        return tuple(mask_sensitive_data(item) for item in data)
    return data


def serialize_log_record(record: Dict) -> str:
    """序列化日志记录为 JSON 格式"""
    try:
        # 提取核心字段
        log_entry = {
            "timestamp": record["time"].isoformat(),
            "level": record["level"].name,
            "module": record["name"],
            "function": record["function"],
            "line": record["line"],
            "message": record["message"],
        }
        
        # 添加请求上下文
        request_id = get_request_id()
        if request_id:
            log_entry["request_id"] = request_id
        
        user_id = get_user_id()
        if user_id:
            log_entry["user_id"] = user_id
        
        # 添加额外字段
        if record.get("extra"):
            extra = mask_sensitive_data(record["extra"])
            # 过滤掉内部字段
            filtered_extra = {
                k: v for k, v in extra.items()
                if not k.startswith("_")
            }
            if filtered_extra:
                log_entry["extra"] = filtered_extra
        
        return json.dumps(log_entry, ensure_ascii=False) + "\n"
    except Exception as e:
        # 如果序列化失败，返回简单格式
        return json.dumps({
            "timestamp": record["time"].isoformat(),
            "level": record["level"].name,
            "message": str(record["message"]),
            "error": f"Serialization failed: {str(e)}"
        }) + "\n"


class AppLogger:
    """应用日志器单例"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._configure_logger()
            AppLogger._initialized = True
    
    def _configure_logger(self):
        """配置 loguru"""
        # 移除默认处理器
        logger.remove()
        
        # 读取环境变量
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        log_format = os.getenv("LOG_FORMAT", "json").lower()
        log_dir = os.getenv("LOG_DIR", "./logs")
        log_rotation = f"{os.getenv('LOG_ROTATION_SIZE', '100')} MB"
        log_retention = f"{os.getenv('LOG_RETENTION_DAYS', '30')} days"
        enable_audit = os.getenv("ENABLE_AUDIT_LOG", "true").lower() == "true"
        environment = os.getenv("ENVIRONMENT", "development").lower()
        
        # 创建日志目录
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        
        # 控制台处理器（开发模式使用彩色输出，生产模式使用 JSON）
        if environment == "development":
            # 开发模式：彩色、易读格式
            logger.add(
                sys.stdout,
                level=log_level,
                format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | <level>{message}</level>",
                colorize=True,
            )
        else:
            # 生产模式：JSON 格式
            logger.add(
                sys.stdout,
                level=log_level,
                format=serialize_log_record if log_format == "json" else "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
                serialize=log_format == "json",
            )
        
        # 文件处理器 - 所有日志
        logger.add(
            f"{log_dir}/app_{{time:YYYY-MM-DD}}.log",
            level=log_level,
            format=serialize_log_record if log_format == "json" else "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
            rotation=log_rotation,
            retention=log_retention,
            compression="gz",
            encoding="utf-8",
            enqueue=True,  # 异步写入
        )
        
        # 文件处理器 - 仅错误日志
        logger.add(
            f"{log_dir}/error_{{time:YYYY-MM-DD}}.log",
            level="ERROR",
            format=serialize_log_record if log_format == "json" else "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
            rotation=log_rotation,
            retention=log_retention,
            compression="gz",
            encoding="utf-8",
            enqueue=True,
        )
        
        # 审计日志处理器
        if enable_audit:
            logger.add(
                f"{log_dir}/audit_{{time:YYYY-MM-DD}}.log",
                level="INFO",
                format=serialize_log_record if log_format == "json" else "{time:YYYY-MM-DD HH:mm:ss} | {message}",
                rotation=log_rotation,
                retention=log_retention,
                compression="gz",
                encoding="utf-8",
                enqueue=True,
                filter=lambda record: record["extra"].get("audit", False),
            )
        
        logger.info("Logger initialized", log_level=log_level, log_format=log_format, environment=environment)
    
    def info(self, message: str, **kwargs):
        """记录 INFO 级别日志"""
        logger.bind(**kwargs).info(message)
    
    def debug(self, message: str, **kwargs):
        """记录 DEBUG 级别日志"""
        logger.bind(**kwargs).debug(message)
    
    def warning(self, message: str, **kwargs):
        """记录 WARNING 级别日志"""
        logger.bind(**kwargs).warning(message)
    
    def error(self, message: str, exc_info: Optional[Exception] = None, **kwargs):
        """记录 ERROR 级别日志"""
        if exc_info:
            logger.bind(**kwargs).opt(exception=exc_info).error(message)
        else:
            logger.bind(**kwargs).error(message)
    
    def critical(self, message: str, exc_info: Optional[Exception] = None, **kwargs):
        """记录 CRITICAL 级别日志"""
        if exc_info:
            logger.bind(**kwargs).opt(exception=exc_info).critical(message)
        else:
            logger.bind(**kwargs).critical(message)
    
    def audit(self, event: str, **kwargs):
        """记录审计日志"""
        # 添加审计标记
        kwargs["audit"] = True
        logger.bind(**kwargs).info(f"[AUDIT] {event}")
    
    def set_level(self, level: str):
        """动态设置日志级别"""
        level = level.upper()
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if level not in valid_levels:
            raise ValueError(f"Invalid log level: {level}. Must be one of {valid_levels}")
        
        # 重新配置 logger
        logger.remove()
        self._configure_logger()
        logger.info(f"Log level changed to {level}")


# 全局单例
app_logger = AppLogger()
