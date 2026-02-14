from datetime import datetime, timedelta
from typing import Optional
import bcrypt
from jose import jwt
import os
import secrets

# 从环境变量读取JWT配置，使用强随机默认值
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_urlsafe(64))
ALGORITHM = "HS256"
# 缩短Token过期时间至24小时，提高安全性
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("TOKEN_EXPIRE_HOURS", "24")) * 60

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码是否正确"""
    # bcrypt 只支持最多 72 字节
    truncated = plain_password[:72] if len(plain_password) > 72 else plain_password
    return bcrypt.checkpw(truncated.encode('utf-8'), hashed_password.encode('utf-8'))

def get_password_hash(password: str) -> str:
    """生成密码哈希"""
    # bcrypt 只支持最多 72 字节
    truncated = password[:72] if len(password) > 72 else password
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(truncated.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def _get_token_expire_hours():
    """从DB动态读取Token过期时间"""
    try:
        import json
        from sqlmodel import Session, select
        from backend.models import SystemConfig, engine
        with Session(engine) as s:
            cfg = s.exec(select(SystemConfig).where(SystemConfig.key == "token_expire_hours")).first()
            if cfg:
                return int(json.loads(cfg.value))
    except Exception:
        pass
    return 24

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        hours = _get_token_expire_hours()
        expire = datetime.utcnow() + timedelta(hours=hours)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def generate_invite_code() -> str:
    """生成唯一的邀请码（6位大写字母+数字）"""
    import random
    import string
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=6))
