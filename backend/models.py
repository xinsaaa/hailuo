from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel, create_engine

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    hashed_password: str
    balance: float = Field(default=0.0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = Field(default=True)
    is_superuser: bool = Field(default=False)

class VideoOrder(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    prompt: str
    status: str = Field(default="pending") # pending, processing, generating, completed, failed
    progress: int = Field(default=0) # 0-100 进度百分比
    video_url: Optional[str] = None
    cost: float = Field(default=0.99)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    task_id: Optional[str] = None # External task ID from automation if applicable
    # 图片转视频功能
    first_frame_image: Optional[str] = None  # 首帧图片路径
    last_frame_image: Optional[str] = None   # 尾帧图片路径
    model_name: Optional[str] = Field(default="Hailuo 2.3")  # 用户选择的生成模型

class Transaction(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    amount: float
    bonus: float = Field(default=0.0) # Bonus amount given (e.g. charge 10 get 1, bonus=1)
    type: str = Field(default="recharge") # recharge, expense, refund
    created_at: datetime = Field(default_factory=datetime.utcnow)

class VerificationCode(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str
    source: str = Field(default="sms") # sms, manual
    is_used: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ============ 安全相关模型 ============

class IPBan(SQLModel, table=True):
    """IP 封禁记录"""
    id: Optional[int] = Field(default=None, primary_key=True)
    ip: str = Field(index=True, unique=True)
    reason: str = Field(default="登录失败次数过多")
    expires_at: datetime  # 封禁到期时间
    created_at: datetime = Field(default_factory=datetime.utcnow)


class LoginFailure(SQLModel, table=True):
    """登录失败统计"""
    id: Optional[int] = Field(default=None, primary_key=True)
    ip: str = Field(index=True, unique=True)
    fail_count: int = Field(default=0)
    last_fail_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PaymentOrder(SQLModel, table=True):
    """支付订单记录"""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    out_trade_no: str = Field(index=True, unique=True)  # 商户订单号
    amount: float  # 支付金额
    bonus: float = Field(default=0.0)  # 赠送金额
    status: str = Field(default="pending")  # pending, paid, failed
    trade_no: Optional[str] = None  # 平台交易号
    created_at: datetime = Field(default_factory=datetime.utcnow)
    paid_at: Optional[datetime] = None


class SystemConfig(SQLModel, table=True):
    """系统配置表"""
    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(index=True, unique=True)  # 配置键
    value: str  # 配置值（JSON 格式）
    description: Optional[str] = None  # 配置描述
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AIModel(SQLModel, table=True):
    """AI 生成模型配置表"""
    id: Optional[int] = Field(default=None, primary_key=True)
    model_id: str = Field(index=True, unique=True)  # 模型标识符，如 hailuo_2_3
    name: str  # 模型名称，如 Hailuo 2.3
    display_name: str  # 显示名称，如 海螺 2.3
    description: str  # 模型描述
    model_type: str = Field(default="image_to_video")  # 模型类型
    features: str = Field(default="[]")  # 功能列表 JSON
    badge: Optional[str] = None  # 标签，如 NEW, 5折
    supports_last_frame: bool = Field(default=False)  # 是否支持尾帧
    is_default: bool = Field(default=False)  # 是否为默认模型
    is_enabled: bool = Field(default=True)  # 是否启用
    sort_order: int = Field(default=0)  # 排序顺序
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

# 数据库连接（使用相对路径，支持跨环境部署）
import os
_current_dir = os.path.dirname(os.path.abspath(__file__))
sqlite_file_name = os.path.join(_current_dir, "database.db")
sqlite_url = f"sqlite:///{sqlite_file_name}"

engine = create_engine(sqlite_url)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
