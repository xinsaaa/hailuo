from datetime import datetime, timedelta
from typing import Optional
import bcrypt
from jose import jwt

# Secret key for JWT (Should be env var in production)
SECRET_KEY = "supersecretkeyshouldbechanged"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30 * 24 * 60 # 1 month

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

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def generate_invite_code() -> str:
    """生成唯一的邀请码（6位大写字母+数字）"""
    import random
    import string
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=6))
