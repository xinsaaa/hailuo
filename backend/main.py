from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse
from starlette.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from sqlmodel import Session, select
from pydantic import BaseModel
from typing import Optional
from backend.models import User, VideoOrder, Transaction, VerificationCode, AIModel, Ticket, engine
import re
from backend.auth import get_password_hash, verify_password, create_access_token, SECRET_KEY, ALGORITHM, generate_invite_code
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from backend.automation import run_hailuo_task, start_automation_worker
from backend.security import (
    generate_captcha_challenge, verify_captcha,
    check_rate_limit, is_ip_banned, record_fail, record_success,
    get_ban_remaining_seconds, get_fail_count
)
from backend.admin import router as admin_router

app = FastAPI(title="AI Video Generator API")

# 注册管理员路由
app.include_router(admin_router)


# ============ Rate Limiting 中间件 ============
# 敏感接口（需要严格限制）
SENSITIVE_PATHS = ["/api/login", "/api/register", "/api/admin/login"]

class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 获取客户端 IP
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path
        
        # 检查 IP 是否被封禁（只对敏感接口检查）
        if any(path.startswith(p) for p in SENSITIVE_PATHS):
            if is_ip_banned(client_ip):
                remaining = get_ban_remaining_seconds(client_ip)
                return JSONResponse(
                    status_code=403,
                    content={"detail": f"行为异常，已被临时封禁，剩余 {remaining // 60} 分钟"}
                )
            
            # 敏感接口检查请求频率（严格）
            if not check_rate_limit(client_ip):
                return JSONResponse(
                    status_code=429,
                    content={"detail": "请求过于频繁，请稍后再试"}
                )
        
        response = await call_next(request)
        return response



# 添加CORS中间件（必须在其他中间件之前）
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://152.32.213.113:8000",  # 后端集成前端服务
        "http://152.32.213.113:5173",  # 开发模式备用
        "http://localhost:8000",
        "http://localhost:5173",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:5173",
        "*"
    ],
    allow_credentials=False,  # 设为False避免credentials问题
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"]
)
# 添加其他中间件
app.add_middleware(RateLimitMiddleware)


# 后端启动时自动初始化数据库和启动自动化
@app.on_event("startup")
def startup_event():
    # 确保数据库表存在
    from backend.models import create_db_and_tables
    create_db_and_tables()
    print("[MAIN] Database tables initialized.")
    
    # 初始化默认模型数据
    init_default_models()
    
    # 自动启动自动化工作线程
    import os
    enable_auto_worker = os.getenv("ENABLE_AUTO_WORKER", "true").lower() == "true"
    
    if enable_auto_worker:
        print("[MAIN] 🚀 Auto-starting automation worker...")
        try:
            start_automation_worker()
            print("[MAIN] ✅ Automation worker started successfully!")
        except Exception as e:
            print(f"[MAIN] ❌ Failed to start automation worker: {str(e)[:100]}")
    else:
        print("[MAIN] Backend started. Automation worker disabled by config.")


def init_default_models():
    """初始化默认模型数据（仅在表为空时执行）"""
    import json
    with Session(engine) as session:
        existing = session.exec(select(AIModel)).first()
        if existing:
            return  # 已有数据，跳过初始化
        
        default_models = [
            {
                "model_id": "hailuo_2_3",
                "name": "Hailuo 2.3",
                "display_name": "海螺 2.3",
                "description": "表现力全面升级，更稳定，更真实",
                "features": json.dumps(["768P-1080P", "6s-10s", "仅首帧"]),
                "badge": "NEW",
                "supports_last_frame": False,
                "is_default": True,
                "is_enabled": True,
                "sort_order": 1
            },
            {
                "model_id": "hailuo_2_3_fast",
                "name": "Hailuo 2.3-Fast",
                "display_name": "海螺 2.3-Fast",
                "description": "生成速度更快，超高性价比",
                "features": json.dumps(["768P-1080P", "6s-10s", "仅首帧"]),
                "badge": "NEW",
                "supports_last_frame": False,
                "is_default": False,
                "is_enabled": True,
                "sort_order": 2
            },
            {
                "model_id": "hailuo_2_0",
                "name": "Hailuo 2.0",
                "display_name": "海螺 2.0",
                "description": "最佳效果、超清画质、精准响应",
                "features": json.dumps(["首尾帧", "仅尾帧", "512P-1080P", "6s-10s"]),
                "badge": "NEW",
                "supports_last_frame": True,
                "is_default": False,
                "is_enabled": True,
                "sort_order": 3
            },
            {
                "model_id": "beta_3_1",
                "name": "Beta 3.1",
                "display_name": "Beta 3.1",
                "description": "音画同步，高保真，精准控制",
                "features": json.dumps(["音画同出", "首尾帧", "720P-1080P", "8s"]),
                "badge": "3.7折",
                "supports_last_frame": True,
                "is_default": False,
                "is_enabled": True,
                "sort_order": 4
            },
            {
                "model_id": "beta_3_1_fast",
                "name": "Beta 3.1 Fast",
                "display_name": "Beta 3.1 Fast",
                "description": "音画同步，更高速，更高性价比",
                "features": json.dumps(["音画同出", "首尾帧", "720P-1080P", "8s"]),
                "badge": "5折",
                "supports_last_frame": True,
                "is_default": False,
                "is_enabled": True,
                "sort_order": 5
            },
            {
                "model_id": "hailuo_1_0_director",
                "name": "Hailuo 1.0-Director",
                "display_name": "海螺 1.0-Director",
                "description": "像专业导演一样控制镜头运动",
                "features": json.dumps(["720P", "6s", "仅首帧"]),
                "badge": None,
                "supports_last_frame": False,
                "is_default": False,
                "is_enabled": True,
                "sort_order": 6
            },
            {
                "model_id": "hailuo_1_0_live",
                "name": "Hailuo 1.0-Live",
                "display_name": "海螺 1.0-Live",
                "description": "角色表现增强，稳定、流畅、生动",
                "features": json.dumps(["720P", "6s", "仅首帧"]),
                "badge": None,
                "supports_last_frame": False,
                "is_default": False,
                "is_enabled": True,
                "sort_order": 7
            },
            {
                "model_id": "hailuo_1_0",
                "name": "Hailuo 1.0",
                "display_name": "海螺 1.0",
                "description": "01系列的基础图生视频模型",
                "features": json.dumps(["720P", "6s", "仅首帧"]),
                "badge": None,
                "supports_last_frame": False,
                "is_default": False,
                "is_enabled": True,
                "sort_order": 8
            }
        ]
        
        for model_data in default_models:
            model = AIModel(**model_data)
            session.add(model)
        
        session.commit()
        print("[MAIN] ✅ Default AI models initialized.")


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# Dependency
def get_session():
    with Session(engine) as session:
        yield session


def get_client_ip(request: Request) -> str:
    """获取客户端 IP"""
    return request.client.host if request.client else "unknown"


async def get_current_user(token: str = Depends(oauth2_scheme), session: Session = Depends(get_session)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = session.exec(select(User).where(User.username == username)).first()
    if user is None:
        raise credentials_exception
    return user


# --- Pydantic Schemas ---
class UserCreate(BaseModel):
    username: str
    password: str


class UserCreateWithCaptcha(BaseModel):
    username: str
    email: str  # 邮箱（必填）
    email_code: str  # 邮箱验证码
    password: str
    # 验证码5参数
    captcha_challenge: str
    captcha_puzzle: str
    captcha_cipher: str
    captcha_nonce: str
    captcha_proof: str
    captcha_position: float
    # 设备指纹（防止同一设备多次注册）
    device_fingerprint: Optional[str] = None
    # 邀请码（可选）
    invite_code: Optional[str] = None


class LoginWithCaptcha(BaseModel):
    username: str
    password: str
    # 验证码5参数（登录失败3次后需要）
    captcha_challenge: Optional[str] = None
    captcha_puzzle: Optional[str] = None
    captcha_cipher: Optional[str] = None
    captcha_nonce: Optional[str] = None
    captcha_proof: Optional[str] = None
    captcha_position: Optional[float] = None


class Token(BaseModel):
    access_token: str
    token_type: str


class RechargeRequest(BaseModel):
    amount: float


class OrderRequest(BaseModel):
    prompt: str
    model_name: Optional[str] = "Hailuo 2.3"  # 用户选择的生成模型
    first_frame_image: Optional[str] = None   # 首帧图片路径
    last_frame_image: Optional[str] = None    # 尾帧图片路径


class VerificationCodeRequest(BaseModel):
    text: str


# ============ 系统配置 API ============
from backend.models import SystemConfig
import json

# 默认配置
DEFAULT_CONFIG = {
    "video_price": {"value": 0.99, "description": "单个视频生成价格（元）"},
    "bonus_rate": {"value": 0.2, "description": "充值赠送比例（满10元生效）"},
    "bonus_min_amount": {"value": 10, "description": "享受赠送的最低充值金额（元）"},
    "min_recharge": {"value": 0.01, "description": "最低充值金额（元）"},
    "max_recharge": {"value": 10000, "description": "最高充值金额（元）"},
}


def get_config_value(session: Session, key: str, default=None):
    """获取配置值"""
    config = session.exec(select(SystemConfig).where(SystemConfig.key == key)).first()
    if config:
        try:
            return json.loads(config.value)
        except:
            return config.value
    return default if default is not None else DEFAULT_CONFIG.get(key, {}).get("value")


def set_config_value(session: Session, key: str, value, description: str = None):
    """设置配置值"""
    config = session.exec(select(SystemConfig).where(SystemConfig.key == key)).first()
    if config:
        config.value = json.dumps(value)
        if description:
            config.description = description
        config.updated_at = datetime.utcnow()
    else:
        config = SystemConfig(
            key=key,
            value=json.dumps(value),
            description=description or DEFAULT_CONFIG.get(key, {}).get("description", "")
        )
    session.add(config)
    session.commit()
    return config


@app.get("/api/config")
def get_public_config(session: Session = Depends(get_session)):
    """获取公共配置（前端使用）"""
    return {
        "video_price": get_config_value(session, "video_price", 0.99),
        "bonus_rate": get_config_value(session, "bonus_rate", 0.2),
        "bonus_min_amount": get_config_value(session, "bonus_min_amount", 10),
        "min_recharge": get_config_value(session, "min_recharge", 0.01),
        "max_recharge": get_config_value(session, "max_recharge", 10000),
    }


# --- 安全相关 API ---

@app.get("/api/captcha")
def get_captcha():
    """获取验证码挑战"""
    challenge = generate_captcha_challenge()
    return challenge


# ============ 邮箱验证 API ============
from backend.email_service import send_verification_code, verify_email_code


class SendEmailCodeRequest(BaseModel):
    email: str
    purpose: str = "register"  # register 或 reset_password


class ForgotPasswordRequest(BaseModel):
    email: str
    email_code: str
    new_password: str


@app.post("/api/send-email-code")
def send_email_code_api(data: SendEmailCodeRequest, request: Request, session: Session = Depends(get_session)):
    """发送邮箱验证码"""
    client_ip = get_client_ip(request)
    
    # 频率限制检查
    if not check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")
    
    # 验证邮箱格式
    import re
    if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', data.email):
        raise HTTPException(status_code=400, detail="邮箱格式不正确")
    
    # 如果是注册，检查邮箱是否已被使用
    if data.purpose == "register":
        existing_email = session.exec(select(User).where(User.email == data.email)).first()
        if existing_email:
            raise HTTPException(status_code=400, detail="该邮箱已被注册")
    
    # 如果是重置密码，检查邮箱是否存在
    if data.purpose == "reset_password":
        user = session.exec(select(User).where(User.email == data.email)).first()
        if not user:
            raise HTTPException(status_code=400, detail="该邮箱未注册")
    
    # 发送验证码
    success, result = send_verification_code(data.email, data.purpose)
    if not success:
        raise HTTPException(status_code=500, detail=result)
    
    return {"message": "验证码已发送，请查收邮件"}


@app.post("/api/forgot-password")
def forgot_password_api(data: ForgotPasswordRequest, session: Session = Depends(get_session)):
    """找回密码（重置密码）"""
    # 验证邮箱验证码
    valid, msg = verify_email_code(data.email, data.email_code, "reset_password")
    if not valid:
        raise HTTPException(status_code=400, detail=msg)
    
    # 查找用户
    user = session.exec(select(User).where(User.email == data.email)).first()
    if not user:
        raise HTTPException(status_code=400, detail="用户不存在")
    
    # 更新密码
    user.hashed_password = get_password_hash(data.new_password)
    session.add(user)
    session.commit()
    
    return {"message": "密码重置成功，请使用新密码登录"}

@app.post("/api/register", response_model=Token)
def register(user: UserCreateWithCaptcha, request: Request, session: Session = Depends(get_session)):
    client_ip = get_client_ip(request)
    
    # 验证验证码（5参数验证）
    if not verify_captcha(
        user.captcha_challenge,
        user.captcha_puzzle,
        user.captcha_cipher,
        user.captcha_nonce,
        user.captcha_proof,
        user.captcha_position
    ):
        record_fail(client_ip)
        raise HTTPException(status_code=400, detail="验证码验证失败")
    
    # 验证邮箱验证码
    valid, msg = verify_email_code(user.email, user.email_code, "register")
    if not valid:
        raise HTTPException(status_code=400, detail=msg)
    
    # 检查用户名是否存在
    db_user = session.exec(select(User).where(User.username == user.username)).first()
    if db_user:
        raise HTTPException(status_code=400, detail="用户名已存在")
    
    # 检查邮箱是否已被使用
    existing_email = session.exec(select(User).where(User.email == user.email)).first()
    if existing_email:
        raise HTTPException(status_code=400, detail="该邮箱已被注册")
    
    # 风控检查：同 IP 只能注册一个账号
    existing_ip = session.exec(
        select(User).where(User.register_ip == client_ip)
    ).first()
    if existing_ip:
        record_fail(client_ip)
        raise HTTPException(status_code=400, detail="当前网络环境已注册过账号，请勿重复注册")
    
    # 风控检查：同设备只能注册一个账号
    if user.device_fingerprint:
        existing_fingerprint = session.exec(
            select(User).where(User.device_fingerprint == user.device_fingerprint)
        ).first()
        if existing_fingerprint:
            record_fail(client_ip)
            raise HTTPException(status_code=400, detail="该设备已注册过账号，每个设备只能注册一个账号")
    
    # 处理邀请码（如果有）
    inviter = None
    if user.invite_code:
        inviter = session.exec(
            select(User).where(User.invite_code == user.invite_code)
        ).first()
        # 邀请码无效不报错，只是不给奖励
    
    # 生成新用户的邀请码
    new_invite_code = generate_invite_code()
    # 确保邀请码唯一
    while session.exec(select(User).where(User.invite_code == new_invite_code)).first():
        new_invite_code = generate_invite_code()
    
    # 创建用户（默认余额 ¥3 在模型中已设置）
    hashed_password = get_password_hash(user.password)
    new_user = User(
        username=user.username,
        email=user.email,  # 存储邮箱
        hashed_password=hashed_password,
        invite_code=new_invite_code,
        device_fingerprint=user.device_fingerprint,
        register_ip=client_ip,  # 记录注册 IP
        invited_by=inviter.id if inviter else None
    )
    session.add(new_user)
    session.commit()
    session.refresh(new_user)
    
    # 如果有邀请人，给双方发放 ¥3 奖励
    if inviter:
        # 奖励邀请人
        inviter.balance += 3.0
        session.add(inviter)
        # 奖励被邀请人（额外加 ¥3，总共 ¥6）
        new_user.balance += 3.0
        session.add(new_user)
        session.commit()
    
    record_success(client_ip)
    access_token = create_access_token(data={"sub": new_user.username})
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/api/login", response_model=Token)
def login(data: LoginWithCaptcha, request: Request, session: Session = Depends(get_session)):
    client_ip = get_client_ip(request)
    
    # 检查是否需要验证码（失败 3 次后需要）
    fail_count = get_fail_count(client_ip)
    if fail_count >= 3:
        if not data.captcha_challenge or not verify_captcha(
            data.captcha_challenge,
            data.captcha_puzzle or "",
            data.captcha_cipher or "",
            data.captcha_nonce or "",
            data.captcha_proof or "",
            data.captcha_position or 0
        ):
            record_fail(client_ip)
            raise HTTPException(status_code=400, detail="验证码验证失败")
    
    # 检查是否为管理员登录
    from backend.admin import ADMIN_USERNAME, ADMIN_PASSWORD_HASH
    if data.username == ADMIN_USERNAME:
        if not verify_password(data.password, ADMIN_PASSWORD_HASH):
            is_banned = record_fail(client_ip)
            if is_banned:
                raise HTTPException(status_code=403, detail="行为异常，已被临时封禁 30 分钟")
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        
        record_success(client_ip)
        access_token = create_access_token(data={"sub": data.username, "is_admin": True})
        return {"access_token": access_token, "token_type": "bearer", "is_admin": True}
    
    # 验证普通用户名密码
    user = session.exec(select(User).where(User.username == data.username)).first()
    if not user or not verify_password(data.password, user.hashed_password):
        is_banned = record_fail(client_ip)
        if is_banned:
            raise HTTPException(status_code=403, detail="行为异常，已被临时封禁 30 分钟")
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    
    record_success(client_ip)
    access_token = create_access_token(data={"sub": user.username, "is_admin": user.is_superuser})
    return {"access_token": access_token, "token_type": "bearer", "is_admin": user.is_superuser}


@app.get("/api/security/status")
def get_security_status(request: Request):
    """获取当前 IP 的安全状态"""
    client_ip = get_client_ip(request)
    return {
        "ip": client_ip,
        "fail_count": get_fail_count(client_ip),
        "is_banned": is_ip_banned(client_ip),
        "ban_remaining": get_ban_remaining_seconds(client_ip),
        "need_captcha": get_fail_count(client_ip) >= 3
    }


@app.get("/api/risk/check")
def check_risk(request: Request, device_fingerprint: str = None, session: Session = Depends(get_session)):
    """(测试用) 检查当前环境的注册风控状态"""
    client_ip = get_client_ip(request)
    
    # 检查 IP 是否被封禁
    ip_banned = is_ip_banned(client_ip)
    fail_count = get_fail_count(client_ip)
    
    # 检查 IP 是否已注册过账号
    ip_registered = False
    ip_registered_user = None
    ip_user = session.exec(select(User).where(User.register_ip == client_ip)).first()
    if ip_user:
        ip_registered = True
        ip_registered_user = ip_user.username
    
    # 检查设备指纹是否已注册
    device_registered = False
    device_registered_user = None
    if device_fingerprint:
        device_user = session.exec(select(User).where(User.device_fingerprint == device_fingerprint)).first()
        if device_user:
            device_registered = True
            device_registered_user = device_user.username

    # 判断风险等级
    if ip_banned or ip_registered or device_registered:
        risk_level = "HIGH"
    elif fail_count > 0:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    return {
        "ip": client_ip,
        "is_ip_banned": ip_banned,
        "ip_fail_count": fail_count,
        "is_ip_registered": ip_registered,
        "ip_registered_username": ip_registered_user,
        "device_fingerprint": device_fingerprint,
        "is_device_registered": device_registered,
        "registered_username": device_registered_user,
        "risk_level": risk_level
    }



# 保留旧的 token 接口（兼容 OAuth2PasswordRequestForm）
@app.post("/api/token", response_model=Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.username == form_data.username)).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/api/users/me", response_model=User)
def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user


@app.post("/api/recharge")
def recharge(request: RechargeRequest, current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    bonus = 0.0
    amount = request.amount
    
    if amount >= 100:
        bonus = 20
    elif amount >= 50:
        bonus = 5
    elif amount >= 10:
        bonus = 1
        
    total_add = amount + bonus
    
    current_user.balance += total_add
    session.add(current_user)
    
    transaction = Transaction(
        user_id=current_user.id,
        amount=amount,
        bonus=bonus,
        type="recharge"
    )
    session.add(transaction)
    session.commit()
    session.refresh(current_user)
    
    return {"message": "Recharge successful", "new_balance": current_user.balance, "bonus_added": bonus}


# ============ Z-Pay 支付接口 ============
from backend.payment import create_payment_url, generate_order_no, verify_sign, ZPAY_KEY
from backend.models import PaymentOrder
from starlette.responses import PlainTextResponse
from datetime import datetime


class CreatePaymentRequest(BaseModel):
    amount: float  # 充值金额


@app.post("/api/pay/create")
def create_payment(
    request: CreatePaymentRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """创建支付订单，返回支付跳转 URL"""
    amount = request.amount
    
    # 校验金额
    if amount < 0.01:
        raise HTTPException(status_code=400, detail="最低充值金额为 0.01 元")
    if amount > 10000:
        raise HTTPException(status_code=400, detail="单笔最高充值 10000 元")
    
    # 计算赠送金额：大于10元送20%
    bonus = 0.0
    if amount >= 10:
        bonus = round(amount * 0.2, 2)  # 20%
    
    # 生成订单号
    out_trade_no = generate_order_no()
    
    # 创建支付订单记录
    payment_order = PaymentOrder(
        user_id=current_user.id,
        out_trade_no=out_trade_no,
        amount=amount,
        bonus=bonus,
        status="pending"
    )
    session.add(payment_order)
    session.commit()
    
    # 生成支付 URL
    pay_url = create_payment_url(
        out_trade_no=out_trade_no,
        money=amount,
        name=f"余额充值 ¥{amount}"
    )
    
    return {
        "pay_url": pay_url,
        "out_trade_no": out_trade_no,
        "amount": amount,
        "bonus": bonus
    }


@app.post("/api/pay/notify")
async def payment_notify(request: Request, session: Session = Depends(get_session)):
    """Z-Pay 支付回调通知"""
    # 获取回调参数
    form_data = await request.form()
    params = dict(form_data)
    
    # 验证签名
    sign = params.get("sign", "")
    if not verify_sign(params, ZPAY_KEY, sign):
        return PlainTextResponse("fail")
    
    # 获取订单信息
    out_trade_no = params.get("out_trade_no")
    trade_no = params.get("trade_no")
    trade_status = params.get("trade_status")
    
    # 查询支付订单
    payment_order = session.exec(
        select(PaymentOrder).where(PaymentOrder.out_trade_no == out_trade_no)
    ).first()
    
    if not payment_order:
        return PlainTextResponse("fail")
    
    # 已处理过的订单直接返回成功
    if payment_order.status == "paid":
        return PlainTextResponse("success")
    
    # 支付成功
    if trade_status == "TRADE_SUCCESS":
        payment_order.status = "paid"
        payment_order.trade_no = trade_no
        payment_order.paid_at = datetime.utcnow()
        session.add(payment_order)
        
        # 给用户加余额
        user = session.get(User, payment_order.user_id)
        if user:
            total_add = payment_order.amount + payment_order.bonus
            user.balance += total_add
            session.add(user)
            
            # 记录交易
            transaction = Transaction(
                user_id=user.id,
                amount=payment_order.amount,
                bonus=payment_order.bonus,
                type="recharge"
            )
            session.add(transaction)
        
        session.commit()
        return PlainTextResponse("success")
    
    return PlainTextResponse("fail")


@app.get("/api/pay/confirm")
def confirm_payment_by_return(
    out_trade_no: str,
    trade_no: str,
    trade_status: str,
    sign: str,
    pid: Optional[str] = None,
    type: Optional[str] = None,
    name: Optional[str] = None,
    money: Optional[str] = None,
    sign_type: Optional[str] = None,
    session: Session = Depends(get_session)
):
    """通过 return_url 参数确认支付（GET 方式）"""
    # 构建参数用于验签
    params = {
        "out_trade_no": out_trade_no,
        "trade_no": trade_no,
        "trade_status": trade_status,
    }
    if pid:
        params["pid"] = pid
    if type:
        params["type"] = type
    if name:
        params["name"] = name
    if money:
        params["money"] = money
    if sign_type:
        params["sign_type"] = sign_type
    
    # 验证签名
    if not verify_sign(params, ZPAY_KEY, sign):
        raise HTTPException(status_code=400, detail="签名验证失败")
    
    # 查询支付订单
    payment_order = session.exec(
        select(PaymentOrder).where(PaymentOrder.out_trade_no == out_trade_no)
    ).first()
    
    if not payment_order:
        raise HTTPException(status_code=404, detail="订单不存在")
    
    # 已处理过的订单直接返回成功
    if payment_order.status == "paid":
        return {"status": "already_paid", "message": "订单已处理"}
    
    # 支付成功
    if trade_status == "TRADE_SUCCESS":
        payment_order.status = "paid"
        payment_order.trade_no = trade_no
        payment_order.paid_at = datetime.utcnow()
        session.add(payment_order)
        
        # 给用户加余额
        user = session.get(User, payment_order.user_id)
        if user:
            total_add = payment_order.amount + payment_order.bonus
            user.balance += total_add
            session.add(user)
            
            # 记录交易
            transaction = Transaction(
                user_id=user.id,
                amount=payment_order.amount,
                bonus=payment_order.bonus,
                type="recharge"
            )
            session.add(transaction)
        
        session.commit()
        return {"status": "success", "message": "支付确认成功", "amount": payment_order.amount, "bonus": payment_order.bonus}
    
    raise HTTPException(status_code=400, detail="支付未成功")


@app.get("/api/pay/status/{out_trade_no}")
def get_payment_status(
    out_trade_no: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """查询支付订单状态"""
    payment_order = session.exec(
        select(PaymentOrder).where(
            PaymentOrder.out_trade_no == out_trade_no,
            PaymentOrder.user_id == current_user.id
        )
    ).first()
    
    if not payment_order:
        raise HTTPException(status_code=404, detail="订单不存在")
    
    return {
        "out_trade_no": payment_order.out_trade_no,
        "amount": payment_order.amount,
        "bonus": payment_order.bonus,
        "status": payment_order.status,
        "created_at": payment_order.created_at,
        "paid_at": payment_order.paid_at
    }


@app.post("/api/orders/create")
async def create_order(
    prompt: str = Form(...),
    model_name: str = Form("Hailuo 2.3"),
    first_frame_image: Optional[UploadFile] = File(None),
    last_frame_image: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    cost = 0.99
    if current_user.balance < cost:
        raise HTTPException(status_code=400, detail="Insufficient balance")
    
    # 处理首帧图片上传
    first_frame_path = None
    if first_frame_image:
        if not first_frame_image.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="首帧文件必须是图片")
        
        import os
        import uuid
        from datetime import datetime
        
        # 按用户ID分类存储
        user_upload_dir = os.path.join("user_images", f"user_{current_user.id}")
        os.makedirs(user_upload_dir, exist_ok=True)
        
        file_ext = first_frame_image.filename.split('.')[-1]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"first_{timestamp}_{uuid.uuid4().hex[:8]}.{file_ext}"
        first_frame_path = os.path.join(user_upload_dir, filename)
        
        with open(first_frame_path, "wb") as f:
            content = await first_frame_image.read()
            f.write(content)
    
    # 处理尾帧图片上传
    last_frame_path = None
    if last_frame_image:
        if not last_frame_image.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="尾帧文件必须是图片")
            
        # 使用相同的用户目录
        file_ext = last_frame_image.filename.split('.')[-1]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"last_{timestamp}_{uuid.uuid4().hex[:8]}.{file_ext}"
        last_frame_path = os.path.join(user_upload_dir, filename)
        
        with open(last_frame_path, "wb") as f:
            content = await last_frame_image.read()
            f.write(content)
    
    current_user.balance -= cost
    session.add(current_user)
    
    new_order = VideoOrder(
        user_id=current_user.id,
        prompt=prompt,
        video_url=None,
        cost=cost,
        model_name=model_name,
        first_frame_image=first_frame_path,
        last_frame_image=last_frame_path
    )
    session.add(new_order)
    
    transaction = Transaction(
        user_id=current_user.id,
        amount=cost,
        bonus=0,
        type="expense"
    )
    session.add(transaction)
    
    session.commit()
    session.refresh(new_order)
    
    import asyncio
    asyncio.create_task(run_hailuo_task(new_order.id))
    
    return new_order


@app.get("/api/orders")
def get_orders(current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    statement = select(VideoOrder).where(VideoOrder.user_id == current_user.id).order_by(VideoOrder.created_at.desc())
    results = session.exec(statement).all()
    return results


@app.post("/api/hailuo/code")
def upload_verification_code(request: VerificationCodeRequest, session: Session = Depends(get_session)):
    match = re.search(r'【海螺AI】(\d{6})', request.text)
    if not match:
        match = re.search(r'(\d{6})', request.text)
    
    if not match:
        raise HTTPException(status_code=400, detail="Could not find verification code in text")
    
    code_str = match.group(1)
    
    # 添加到自动化日志中显示
    from backend.automation import automation_logger
    automation_logger.success(f"📱 收到短信验证码: {code_str}")
    automation_logger.info(f"📄 完整短信内容: {request.text}")
    
    vc = VerificationCode(
        code=code_str,
        source="sms_shortcut"
    )
    session.add(vc)
    session.commit()
    session.refresh(vc)
    
    return {"message": "Code received", "code": code_str}


@app.get("/api/dev/codes")
def get_recent_codes(session: Session = Depends(get_session)):
    """开发模式：获取最近的验证码列表"""
    codes = session.exec(
        select(VerificationCode)
        .order_by(VerificationCode.created_at.desc())
        .limit(10)
    ).all()
    
    return [{
        "id": code.id,
        "code": code.code,
        "source": code.source,
        "used": code.is_used,  # 修正字段名
        "created_at": code.created_at.strftime("%H:%M:%S")
    } for code in codes]


@app.get("/api/dev/latest-code")
def get_latest_code(session: Session = Depends(get_session)):
    """开发模式：获取最新验证码"""
    code = session.exec(
        select(VerificationCode)
        .where(VerificationCode.is_used == False)  # 修正字段名
        .order_by(VerificationCode.created_at.desc())
    ).first()
    
    if not code:
        return {"code": None, "message": "暂无可用验证码"}
    
    return {
        "code": code.code,
        "created_at": code.created_at.strftime("%H:%M:%S"),
        "source": code.source
    }


@app.get("/api/models")
def get_available_models(session: Session = Depends(get_session)):
    """获取可用的生成模型列表（仅返回已启用的模型）"""
    import json
    
    # 从数据库获取已启用的模型，按 sort_order 排序
    models = session.exec(
        select(AIModel)
        .where(AIModel.is_enabled == True)
        .order_by(AIModel.sort_order)
    ).all()
    
    # 找到默认模型
    default_model = next((m for m in models if m.is_default), None)
    default_model_name = default_model.name if default_model else (models[0].name if models else "Hailuo 2.3")
    
    # 转换为前端需要的格式
    result = []
    for m in models:
        result.append({
            "id": m.model_id,
            "name": m.name,
            "display_name": m.display_name,
            "description": m.description,
            "type": m.model_type,
            "is_default": m.is_default,
            "features": json.loads(m.features) if m.features else [],
            "badge": m.badge,
            "supports_last_frame": m.supports_last_frame
        })
    
    return {
        "models": result,
        "default_model": default_model_name,
        "total": len(result)
    }


# ============ 工单系统 API ============

class TicketCreate(BaseModel):
    title: str
    content: str

class TicketReply(BaseModel):
    reply: str


@app.post("/api/tickets/create")
def create_ticket(
    ticket: TicketCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """用户创建工单"""
    new_ticket = Ticket(
        user_id=current_user.id,
        title=ticket.title,
        content=ticket.content
    )
    session.add(new_ticket)
    session.commit()
    session.refresh(new_ticket)
    return {"message": "工单已提交", "ticket_id": new_ticket.id}


@app.get("/api/tickets")
def get_user_tickets(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """获取当前用户的工单列表"""
    tickets = session.exec(
        select(Ticket).where(Ticket.user_id == current_user.id).order_by(Ticket.created_at.desc())
    ).all()
    return {"tickets": tickets}


# ============ 系统配置 API (用户端) ============

@app.get("/api/config/public")
def get_public_config(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """获取公开系统配置 (如视频价格、赠送比例)"""
    from backend.models import SystemConfig
    
    # 定义需要返回给前端的配置项 key
    public_keys = ["video_price", "bonus_rate"]
    
    configs = {}
    for key in public_keys:
        config = session.exec(select(SystemConfig).where(SystemConfig.key == key)).first()
        if config:
            configs[key] = float(config.value)
        else:
            # 默认值
            defaults = {"video_price": 5.0, "bonus_rate": 0.1}
            configs[key] = defaults.get(key, 0.0)
            
    return configs


@app.get("/api/tickets/{ticket_id}")
def get_ticket_detail(
    ticket_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """获取工单详情，包含对话消息列表"""
    from backend.models import TicketMessage
    
    ticket = session.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")
    if ticket.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权查看此工单")
    
    # 获取对话消息
    messages = session.exec(
        select(TicketMessage).where(TicketMessage.ticket_id == ticket_id).order_by(TicketMessage.created_at)
    ).all()
    
    return {
        "ticket": ticket,
        "messages": [
            {
                "id": m.id,
                "sender_type": m.sender_type,
                "content": m.content,
                "created_at": m.created_at.isoformat()
            }
            for m in messages
        ]
    }


@app.post("/api/tickets/{ticket_id}/reply")
def user_reply_ticket(
    ticket_id: int,
    data: TicketReply,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """用户回复工单（追加消息）"""
    from backend.models import TicketMessage
    from datetime import datetime
    
    ticket = session.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")
    if ticket.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作此工单")
    if ticket.status == "closed":
        raise HTTPException(status_code=400, detail="工单已关闭，无法回复")
    
    # 创建消息
    message = TicketMessage(
        ticket_id=ticket_id,
        sender_type="user",
        content=data.reply
    )
    session.add(message)
    
    # 更新工单状态和时间
    ticket.status = "open"  # 用户回复后重置为等待回复状态
    ticket.updated_at = datetime.utcnow()
    session.add(ticket)
    session.commit()
    
    return {"message": "回复成功"}


@app.post("/api/tickets/{ticket_id}/close")
def user_close_ticket(
    ticket_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """用户关闭工单"""
    from datetime import datetime
    
    ticket = session.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")
    if ticket.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作此工单")
    
    ticket.status = "closed"
    ticket.updated_at = datetime.utcnow()
    session.add(ticket)
    session.commit()
    
    return {"message": "工单已关闭"}


# ============ 静态文件服务 ============
import os

# 检查前端构建目录是否存在
frontend_dist_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.exists(frontend_dist_path):
    # 挂载静态资源文件（CSS, JS, 图片等）
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist_path, "assets")), name="assets")
    
    # SPA路由处理 - 所有非API路径都返回index.html
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # API路径直接跳过，让FastAPI处理
        if full_path.startswith("api/"):
            raise HTTPException(404, "Not found")
        
        # 检查是否为静态文件请求
        if "." in full_path.split("/")[-1]:  # 有文件扩展名的请求
            file_path = os.path.join(frontend_dist_path, full_path)
            if os.path.exists(file_path):
                return FileResponse(file_path)
            else:
                raise HTTPException(404, "File not found")
        
        # 其他所有路径都返回index.html（SPA路由）
        index_path = os.path.join(frontend_dist_path, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        else:
            raise HTTPException(404, "Frontend not built")
    
    print("✅ 前端静态文件服务已启用（SPA路由支持）")
else:
    print("⚠️  前端dist目录不存在，请先运行: cd frontend && npm run build")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
