"""
安全模块：多层加密验证码、Rate Limiting、IP 封禁
加密设计：3层混淆、5个参数组合、3个加密过程
"""
import time
import secrets
import hashlib
import hmac
import base64
import json
from typing import Dict, Optional
from datetime import datetime, timedelta
from collections import defaultdict
from threading import Lock

# ============ 配置 ============
# 多层密钥（不同层使用不同密钥）
SECRET_LAYER_1 = "dadi_ai_L1_x7k9m2p5"
SECRET_LAYER_2 = "cipher_L2_q3w8e1r6"
SECRET_LAYER_3 = "verify_L3_t4y0u9i2"
CAPTCHA_EXPIRE_SECONDS = 300
RATE_LIMIT_REQUESTS = 100  # 每分钟最大请求数（调高避免正常使用被限制）
RATE_LIMIT_WINDOW = 60
BAN_THRESHOLD = 10
BAN_DURATION_MINUTES = 30


# ============ 内存存储 ============
_lock = Lock()
_captcha_store: Dict[str, dict] = {}
_rate_limit_store: Dict[str, list] = defaultdict(list)
_fail_count_store: Dict[str, dict] = defaultdict(lambda: {"count": 0, "last_fail": None})
_banned_ips: Dict[str, datetime] = {}


# ============ 加密工具函数 ============

def _xor_encode(data: str, key: str) -> str:
    """XOR 混淆编码"""
    result = []
    for i, char in enumerate(data):
        result.append(chr(ord(char) ^ ord(key[i % len(key)])))
    return base64.b64encode(''.join(result).encode('latin-1')).decode()


def _xor_decode(encoded: str, key: str) -> str:
    """XOR 混淆解码"""
    try:
        data = base64.b64decode(encoded).decode('latin-1')
        result = []
        for i, char in enumerate(data):
            result.append(chr(ord(char) ^ ord(key[i % len(key)])))
        return ''.join(result)
    except:
        return ""


def _hmac_sign(data: str, key: str) -> str:
    """HMAC-SHA256 签名"""
    return hmac.new(key.encode(), data.encode(), hashlib.sha256).hexdigest()


def _hash_combine(*args) -> str:
    """多参数哈希组合"""
    combined = "|".join(str(a) for a in args)
    return hashlib.sha512(combined.encode()).hexdigest()


def _obfuscate_number(num: int, salt: str) -> str:
    """数字混淆（多层变换）"""
    # 第1步：添加偏移
    offset = sum(ord(c) for c in salt) % 100
    shifted = num + offset
    
    # 第2步：乘以质数并取模
    prime = 7919
    transformed = (shifted * prime) % 10000
    
    # 第3步：转换为混淆字符串
    chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    result = ""
    temp = transformed + int(salt[:8], 16) % 1000
    for _ in range(6):
        result += chars[temp % len(chars)]
        temp //= len(chars)
    
    return result


def _deobfuscate_number(obfuscated: str, salt: str, original_range: tuple = (0, 100)) -> int:
    """数字反混淆（暴力匹配，因为不可逆）"""
    for num in range(original_range[0], original_range[1] + 1):
        if _obfuscate_number(num, salt) == obfuscated:
            return num
    return -1


# ============ 验证码生成与验证（增强版）============

def generate_captcha_challenge() -> dict:
    """
    生成验证码挑战（多层加密）
    返回5个参数：challenge, puzzle, cipher, nonce, proof
    """
    # 生成基础数据（target 范围 40-85，避免缺口出现在左边看不见的位置）
    target = secrets.randbelow(46) + 40  # 40-85
    token = secrets.token_urlsafe(24)
    timestamp = int(time.time())
    nonce = secrets.token_hex(8)
    
    # ===== 第1层加密：生成 challenge（包含加密的 token）=====
    token_data = json.dumps({"t": token, "ts": timestamp})
    challenge = _xor_encode(token_data, SECRET_LAYER_1)
    
    # ===== 第2层加密：生成 puzzle（包含混淆的 target）=====
    salt = hashlib.md5(f"{token}{nonce}".encode()).hexdigest()
    obfuscated_target = _obfuscate_number(target, salt)
    puzzle_data = json.dumps({"p": obfuscated_target, "n": nonce[:4]})
    puzzle = _xor_encode(puzzle_data, SECRET_LAYER_2)
    
    # ===== 第3层加密：生成 cipher（组合签名）=====
    sig_data = f"{token}:{target}:{timestamp}:{nonce}"
    cipher = _hmac_sign(sig_data, SECRET_LAYER_3)
    
    # ===== 生成 proof（验证链）=====
    proof = _hash_combine(challenge, puzzle, cipher, nonce, timestamp)[:32]
    
    # 存储用于验证
    expires = datetime.now() + timedelta(seconds=CAPTCHA_EXPIRE_SECONDS)
    with _lock:
        _captcha_store[token] = {
            "target": target,
            "timestamp": timestamp,
            "nonce": nonce,
            "expires": expires,
            "proof": proof
        }
        _cleanup_expired_captchas()
    
    return {
        "challenge": challenge,
        "puzzle": puzzle,
        "cipher": cipher,
        "nonce": nonce,
        "proof": proof,
        # 加密的 target（前端需要解密）
        # 简化加密：target ^ 0x5A，直接 Base64
        "hint": base64.b64encode(bytes([target ^ 0x5A])).decode()
    }


def verify_captcha(challenge: str, puzzle: str, cipher: str, nonce: str, 
                   proof: str, position: float) -> bool:
    """
    验证滑块验证码（多层验证）
    验证顺序：proof → challenge → puzzle → cipher → position
    """
    try:
        # ===== 第1步：解密 challenge，提取 token =====
        token_json = _xor_decode(challenge, SECRET_LAYER_1)
        if not token_json:
            print(f"[CAPTCHA] 验证失败：XOR 解密失败")
            return False
        token_data = json.loads(token_json)
        token = token_data.get("t")
        timestamp = token_data.get("ts")
        
        if not token or not timestamp:
            print(f"[CAPTCHA] 验证失败：token 或 timestamp 为空")
            return False
        
        with _lock:
            # 检查 token 是否存在
            if token not in _captcha_store:
                print(f"[CAPTCHA] 验证失败：token 不存在（可能已被使用或过期）")
                return False
            
            stored = _captcha_store[token]
            
            # 检查是否过期
            if datetime.now() > stored["expires"]:
                del _captcha_store[token]
                print(f"[CAPTCHA] 验证失败：token 已过期")
                return False
            
            # ===== 第2步：验证 proof =====
            expected_proof = _hash_combine(challenge, puzzle, cipher, nonce, timestamp)[:32]
            if proof != expected_proof:
                print(f"[CAPTCHA] 验证失败：proof 不匹配")
                return False
            
            # ===== 第3步：验证 nonce =====
            if nonce != stored["nonce"]:
                print(f"[CAPTCHA] 验证失败：nonce 不匹配")
                return False
            
            # ===== 第4步：验证 cipher 签名 =====
            sig_data = f"{token}:{stored['target']}:{timestamp}:{nonce}"
            expected_cipher = _hmac_sign(sig_data, SECRET_LAYER_3)
            if cipher != expected_cipher:
                print(f"[CAPTCHA] 验证失败：cipher 签名不匹配")
                return False
            
            # ===== 第5步：验证位置 =====
            if abs(position - stored["target"]) > 8:
                print(f"[CAPTCHA] 验证失败：位置不匹配 (position={position}, target={stored['target']})")
                return False
            
            # 验证成功，删除 token
            del _captcha_store[token]
            print(f"[CAPTCHA] 验证成功！")
            return True
            
    except Exception as e:
        print(f"[CAPTCHA] 验证异常: {e}")
        return False


def _cleanup_expired_captchas():
    """清理过期的验证码"""
    now = datetime.now()
    expired = [k for k, v in _captcha_store.items() if now > v["expires"]]
    for k in expired:
        del _captcha_store[k]


# ============ Rate Limiting （仍使用内存，短期数据）============

def check_rate_limit(ip: str) -> bool:
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW
    
    with _lock:
        _rate_limit_store[ip] = [t for t in _rate_limit_store[ip] if t > window_start]
        if len(_rate_limit_store[ip]) >= RATE_LIMIT_REQUESTS:
            return False
        _rate_limit_store[ip].append(now)
        return True


def get_rate_limit_remaining(ip: str) -> int:
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW
    with _lock:
        valid_requests = [t for t in _rate_limit_store[ip] if t > window_start]
        return max(0, RATE_LIMIT_REQUESTS - len(valid_requests))


# ============ IP 封禁（数据库持久化）============

from sqlmodel import Session, select
from backend.models import engine, IPBan, LoginFailure


def is_ip_banned(ip: str) -> bool:
    """检查 IP 是否被封禁"""
    with Session(engine) as session:
        ban = session.exec(select(IPBan).where(IPBan.ip == ip)).first()
        if ban:
            if datetime.now() < ban.expires_at:
                return True
            else:
                # 封禁已过期，删除记录并重置失败计数
                session.delete(ban)
                failure = session.exec(select(LoginFailure).where(LoginFailure.ip == ip)).first()
                if failure:
                    failure.fail_count = 0
                    failure.last_fail_at = None
                    session.add(failure)
                session.commit()
        return False


def record_fail(ip: str) -> bool:
    """记录登录失败，返回是否达到封禁阈值"""
    with Session(engine) as session:
        failure = session.exec(select(LoginFailure).where(LoginFailure.ip == ip)).first()
        
        if not failure:
            failure = LoginFailure(ip=ip, fail_count=1, last_fail_at=datetime.now())
            session.add(failure)
        else:
            failure.fail_count += 1
            failure.last_fail_at = datetime.now()
            session.add(failure)
        
        # 检查是否达到封禁阈值
        if failure.fail_count >= BAN_THRESHOLD:
            # 创建封禁记录
            existing_ban = session.exec(select(IPBan).where(IPBan.ip == ip)).first()
            if not existing_ban:
                ban = IPBan(
                    ip=ip,
                    expires_at=datetime.now() + timedelta(minutes=BAN_DURATION_MINUTES)
                )
                session.add(ban)
            session.commit()
            return True
        
        session.commit()
        return False


def record_success(ip: str):
    """登录成功，清除失败计数"""
    with Session(engine) as session:
        failure = session.exec(select(LoginFailure).where(LoginFailure.ip == ip)).first()
        if failure:
            failure.fail_count = 0
            failure.last_fail_at = None
            session.add(failure)
            session.commit()


def get_fail_count(ip: str) -> int:
    """获取登录失败次数"""
    with Session(engine) as session:
        failure = session.exec(select(LoginFailure).where(LoginFailure.ip == ip)).first()
        return failure.fail_count if failure else 0


def get_ban_remaining_seconds(ip: str) -> int:
    """获取封禁剩余时间（秒）"""
    with Session(engine) as session:
        ban = session.exec(select(IPBan).where(IPBan.ip == ip)).first()
        if ban:
            remaining = (ban.expires_at - datetime.now()).total_seconds()
            return max(0, int(remaining))
        return 0

