"""
请求上下文管理模块
使用 contextvars 存储请求级别的上下文信息
"""
from contextvars import ContextVar
from typing import Optional
import uuid


# 上下文变量
request_id_var: ContextVar[Optional[str]] = ContextVar('request_id', default=None)
user_id_var: ContextVar[Optional[int]] = ContextVar('user_id', default=None)


def get_request_id() -> Optional[str]:
    """获取当前请求 ID"""
    return request_id_var.get()


def set_request_id(request_id: str):
    """设置请求 ID"""
    request_id_var.set(request_id)


def get_user_id() -> Optional[int]:
    """获取当前用户 ID"""
    return user_id_var.get()


def set_user_id(user_id: int):
    """设置用户 ID"""
    user_id_var.set(user_id)


def generate_request_id() -> str:
    """生成唯一请求 ID"""
    return str(uuid.uuid4())


def clear_context():
    """清理上下文（请求结束时调用）"""
    request_id_var.set(None)
    user_id_var.set(None)
