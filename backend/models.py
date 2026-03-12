from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel, create_engine

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    email: Optional[str] = Field(default=None, index=True, unique=True)  # 邮箱（唯一）
    hashed_password: str
    balance: float = Field(default=3.0)  # 新用户默认送 ¥3
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = Field(default=True)
    is_superuser: bool = Field(default=False)
    # 邀请系统
    invite_code: Optional[str] = Field(default=None, index=True, unique=True)  # 用户的邀请码
    invited_by: Optional[int] = Field(default=None)  # 邀请人 ID
    # 风控字段
    device_fingerprint: Optional[str] = Field(default=None, index=True)  # 设备指纹
    register_ip: Optional[str] = Field(default=None, index=True)  # 注册时的 IP 地址

class VideoOrder(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    prompt: str
    status: str = Field(default="pending") # pending, processing, generating, completed, failed
    progress: int = Field(default=0) # 0-100 进度百分比
    video_url: Optional[str] = None
    cost: float = Field(default=0.99)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    task_id: Optional[str] = None # External task ID from automation if applicable
    # 图片转视频功能
    first_frame_image: Optional[str] = None  # 首帧图片路径
    last_frame_image: Optional[str] = None   # 尾帧图片路径
    model_name: Optional[str] = Field(default="Hailuo 2.3")  # 用户选择的生成模型
    video_type: Optional[str] = Field(default="image_to_video")  # image_to_video 或 text_to_video
    resolution: Optional[str] = Field(default="768p")  # 768p 或 1080p
    duration: Optional[str] = Field(default="6s")  # 6s 或 10s（1080p只能6s）

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


class EmailVerifyCode(SQLModel, table=True):
    """邮箱验证码"""
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True)  # 目标邮箱
    code: str  # 6位验证码
    purpose: str = Field(default="register")  # register, reset_password
    is_used: bool = Field(default=False)
    expires_at: datetime  # 过期时间
    created_at: datetime = Field(default_factory=datetime.utcnow)# ============ 安全相关模型 ============

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


class JimengOrder(SQLModel, table=True):
    """即梦视频生成订单"""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    prompt: str  # 提示词
    model_name: str = Field(default="Seedance 2.0 Fast")  # 模型名称
    task_id: Optional[str] = None  # 唯一标识，格式: jimeng_{timestamp}_{random}
    cost: float = Field(default=0.99)  # 订单金额
    duration: int = Field(default=5)  # 时长：4-12秒
    ratio: str = Field(default="16:9")  # 比例：21:9, 16:9, 4:3, 1:1, 3:4, 9:16
    resolution: str = Field(default="720P")  # 分辨率：720P, 1080P
    status: str = Field(default="pending")  # pending, processing, generating, completed, failed
    progress: int = Field(default=0)  # 进度 0-100
    video_url: Optional[str] = None  # 视频URL
    first_frame_url: Optional[str] = None  # 首帧图片URL
    last_frame_url: Optional[str] = None  # 尾帧图片URL
    error_message: Optional[str] = None  # 错误信息
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


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
    price: float = Field(default=0.99)  # 模型价格（元/次）- 海螺固定价格
    price_per_second: float = Field(default=0.0)  # 每秒单价（元/秒）- 即梦按秒计费，0表示使用固定价格
    model_type: str = Field(default="image_to_video")  # 模型类型
    platform: str = Field(default="hailuo")  # 平台：hailuo / jimeng
    features: str = Field(default="[]")  # 功能列表 JSON
    badge: Optional[str] = None  # 标签，如 NEW, 5折
    supports_last_frame: bool = Field(default=False)  # 是否支持尾帧
    is_default: bool = Field(default=False)  # 是否为默认模型
    is_enabled: bool = Field(default=True)  # 是否启用
    sort_order: int = Field(default=0)  # 排序顺序
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Ticket(SQLModel, table=True):
    """工单系统 - 客户提交问题，管理员回复"""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)  # 提交用户
    title: str  # 工单标题
    content: str  # 工单初始内容（首条消息）
    status: str = Field(default="open", index=True)  # open, replied, closed
    admin_reply: Optional[str] = None  # 兼容旧数据，新数据通过 TicketMessage 存储
    replied_at: Optional[datetime] = None  # 兼容旧数据
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class TicketMessage(SQLModel, table=True):
    """工单对话消息 - 支持多轮对话"""
    id: Optional[int] = Field(default=None, primary_key=True)
    ticket_id: int = Field(foreign_key="ticket.id", index=True)  # 关联工单
    sender_type: str  # 'user' 或 'admin'
    content: str  # 消息内容
    created_at: datetime = Field(default_factory=datetime.utcnow)

# 数据库连接（使用相对路径，支持跨环境部署）
import os
_current_dir = os.path.dirname(os.path.abspath(__file__))
sqlite_file_name = os.path.join(_current_dir, "database.db")
sqlite_url = f"sqlite:///{sqlite_file_name}"

engine = create_engine(sqlite_url)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
    # 自动迁移：给已有表添加缺失的列
    _auto_migrate()

def _auto_migrate():
    """检查并添加缺失的列（SQLite ALTER TABLE ADD COLUMN）"""
    import sqlite3
    conn = sqlite3.connect(sqlite_file_name)
    cursor = conn.cursor()

    migrations = [
        # videoorder 表
        ("videoorder", "video_type", "TEXT DEFAULT 'image_to_video'"),
        ("videoorder", "resolution", "TEXT DEFAULT '768p'"),
        ("videoorder", "duration", "TEXT DEFAULT '6s'"),
        # aimodel 表
        ("aimodel", "model_type", "TEXT DEFAULT 'image_to_video'"),
        ("aimodel", "platform", "TEXT DEFAULT 'hailuo'"),
        ("aimodel", "features", "TEXT DEFAULT '[]'"),
        ("aimodel", "badge", "TEXT"),
        ("aimodel", "supports_last_frame", "INTEGER DEFAULT 0"),
        ("aimodel", "is_default", "INTEGER DEFAULT 0"),
        ("aimodel", "is_enabled", "INTEGER DEFAULT 1"),
        ("aimodel", "sort_order", "INTEGER DEFAULT 0"),
        ("aimodel", "price_per_second", "REAL DEFAULT 0"),
        ("aimodel", "created_at", "TEXT"),
        ("aimodel", "updated_at", "TEXT"),
    ]

    # 缓存每张表的现有列
    table_cols_cache = {}
    for table, col, col_type in migrations:
        if table not in table_cols_cache:
            cursor.execute(f"PRAGMA table_info({table})")
            table_cols_cache[table] = {row[1] for row in cursor.fetchall()}
        if col not in table_cols_cache[table]:
            try:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
                table_cols_cache[table].add(col)
                print(f"[DB迁移] 添加列 {table}.{col}")
            except Exception as e:
                print(f"[DB迁移] 跳过 {table}.{col}: {e}")

    conn.commit()
    conn.close()
