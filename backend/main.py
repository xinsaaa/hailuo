from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
import asyncio

# 加载环境变量（必须在其他导入之前）
load_dotenv()
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.responses import FileResponse
from starlette.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlmodel import Session, select
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid
from backend.models import User, VideoOrder, Transaction, VerificationCode, AIModel, Ticket, engine
from backend.db_utils import db_manager
from backend.error_handler import security_logger, error_handler, RateLimitError, SecurityError
import re
from backend.auth import get_password_hash, verify_password, create_access_token, SECRET_KEY, ALGORITHM, generate_invite_code
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from backend.automation import run_hailuo_task, start_automation_worker  # 单账号模式保留
from backend.security import (
    generate_captcha_challenge, verify_captcha,
    check_rate_limit, is_ip_banned, record_fail, record_success,
    get_ban_remaining_seconds, get_fail_count
)
from backend.admin import router as admin_router, get_admin_user
from backend.email_service import send_verification_code, verify_email_code
from backend.admin_multi_account import include_multi_account_routes
from backend.admin_kling_account import router as kling_account_router

# 导入日志和异常处理
from backend.logger import app_logger
from backend.middleware.request_id import RequestIDMiddleware
from backend.middleware.logging import LoggingMiddleware
from backend.middleware.exception_handler import (
    app_exception_handler,
    validation_exception_handler,
    http_exception_handler,
    global_exception_handler
)
from backend.exceptions import AppException

app = FastAPI(title="AI Video Generator API")

# 注册异常处理器
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)

# 注册管理员路由
app.include_router(admin_router)

# 注册多账号管理路由
include_multi_account_routes(app)

# 注册即梦账号管理路由
from backend.admin_jimeng_account import router as jimeng_router
app.include_router(jimeng_router)

# 注册可灵账号管理路由
app.include_router(kling_account_router)


# 注册即梦订单路由
from backend.jimeng_api import router as jimeng_api_router
app.include_router(jimeng_api_router)


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
        "http://dadiai.cn:8000",
        "http://dadiai.cn:5173",
        "http://152.32.213.113:8000",
        "http://152.32.213.113:5173",
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

# 注意：异常处理器已在上方通过 app.add_exception_handler 注册，不再重复注册

# 添加请求日志记录
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = datetime.utcnow()
    client_ip = request.client.host if request.client else "unknown"
    
    # 记录请求开始
    security_logger.info(
        f"Request started: {request.method} {request.url.path}",
        method=request.method,
        path=request.url.path,
        client_ip=client_ip,
        user_agent=request.headers.get("user-agent", "unknown")
    )
    
    try:
        response = await call_next(request)
        
        # 记录请求完成
        duration = (datetime.utcnow() - start_time).total_seconds()
        security_logger.info(
            f"Request completed: {request.method} {request.url.path} - {response.status_code}",
            method=request.method,
            path=request.url.path,
            client_ip=client_ip,
            status_code=response.status_code,
            duration_seconds=duration
        )
        
        return response
    except Exception as e:
        duration = (datetime.utcnow() - start_time).total_seconds()
        security_logger.error(
            f"Request failed: {request.method} {request.url.path}",
            exc_info=e,
            method=request.method,
            path=request.url.path,
            client_ip=client_ip,
            duration_seconds=duration
        )
        raise


# 后端启动时自动初始化数据库和启动自动化
@app.on_event("startup")
async def startup_event():
    # 确保数据库表存在
    from backend.models import create_db_and_tables
    create_db_and_tables()
    app_logger.info("Database tables initialized")

    # 初始化默认模型数据
    init_default_models()

    # 启动恢复流程（处理断电、崩溃等异常情况）
    try:
        from backend.startup_recovery import startup_recovery
        app_logger.info("Starting recovery process...")
        await startup_recovery()
        app_logger.info("Recovery process completed")
    except Exception as e:
        app_logger.error(f"Recovery process failed: {e}", exc_info=True)
    
    # 自动启动自动化工作线程（单账号模式） - 多账号系统启用时禁用
    enable_auto_worker = os.getenv("ENABLE_AUTO_WORKER", "true").lower() == "true"
    enable_multi_account = os.getenv("ENABLE_MULTI_ACCOUNT", "true").lower() == "true"
    
    if enable_auto_worker and not enable_multi_account:
        app_logger.info("Auto-starting automation worker...")
        try:
            start_automation_worker()
            app_logger.info("Automation worker started successfully")
        except Exception as e:
            app_logger.error("Failed to start automation worker", exc_info=e)
    elif enable_multi_account:
        app_logger.info("Single automation worker disabled (multi-account system enabled)")
    else:
        app_logger.info("Automation worker disabled by config")
    
    # HTTP API多账号模式无需启动浏览器
    enable_multi_account = os.getenv("ENABLE_MULTI_ACCOUNT", "true").lower() == "true"
    if enable_multi_account:
        from backend.account_store import account_store
        app_logger.info(f"HTTP API多账号模式就绪，已加载 {len(account_store.accounts)} 个账号")
    else:
        app_logger.info("Multi-account system disabled by config")

    # 配置可灵API日志输出DEBUG到终端
    import logging
    kling_logger = logging.getLogger("backend.kling_api")
    kling_logger.setLevel(logging.DEBUG)
    if not kling_logger.handlers:
        _sh = logging.StreamHandler()
        _sh.setLevel(logging.DEBUG)
        _sh.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s", datefmt="%H:%M:%S"))
        kling_logger.addHandler(_sh)

    # 启动可灵账号登录状态监测
    from backend.kling_api import start_monitor
    start_monitor()
    app_logger.info("可灵账号登录监测已启动")


def init_default_models():
    """初始化默认模型数据（只创建缺失的模型，保护已有价格设置）"""
    from backend.model_config import model_config
    with Session(engine) as session:
        
        default_models = model_config.get_default_models()
        
        # 只创建数据库中不存在的模型，保护已有的价格设置
        created_count = 0
        for model_data in default_models:
            existing_model = session.exec(
                select(AIModel).where(AIModel.model_id == model_data["model_id"])
            ).first()
            
            if not existing_model:
                # 模型不存在，创建新模型
                model = AIModel(**model_data)
                session.add(model)
                created_count += 1
                app_logger.info(f"Created new model: {model_data['model_id']} with price ¥{model_data['price']}")
            else:
                # 模型已存在，保持现有数据（特别是价格）
                # 但同步 platform 和 pricing_matrix 字段
                updated = False
                new_platform = model_data.get("platform", "hailuo")
                if existing_model.platform != new_platform:
                    existing_model.platform = new_platform
                    updated = True
                # 同步 pricing_matrix（如果数据库中为空但默认配置有值）
                new_matrix = model_data.get("pricing_matrix")
                if new_matrix and not existing_model.pricing_matrix:
                    existing_model.pricing_matrix = new_matrix
                    updated = True
                    app_logger.info(f"Synced pricing_matrix for model {existing_model.model_id}")
                # 自动迁移旧的两层pricing_matrix到三层结构
                if existing_model.pricing_matrix and existing_model.platform in ("kling", "hailuo"):
                    try:
                        old_pm = json.loads(existing_model.pricing_matrix) if isinstance(existing_model.pricing_matrix, str) else existing_model.pricing_matrix
                        if old_pm and ("480p" in old_pm or "720p" in old_pm or "768p" in old_pm or "1080p" in old_pm) and "text" not in old_pm and "single_image" not in old_pm:
                            migrated = {"text": old_pm, "single_image": old_pm, "dual_image": old_pm}
                            existing_model.pricing_matrix = json.dumps(migrated)
                            updated = True
                            app_logger.info(f"Migrated old pricing_matrix to 3-tier format for {existing_model.model_id}")
                    except Exception:
                        pass
                # 同步 price_10s（如果数据库中为0但默认配置有值）
                new_price_10s = model_data.get("price_10s", 0)
                if new_price_10s and (not existing_model.price_10s or existing_model.price_10s == 0):
                    existing_model.price_10s = new_price_10s
                    updated = True
                    app_logger.info(f"Synced price_10s={new_price_10s} for model {existing_model.model_id}")
                # 同步 features
                new_features = model_data.get("features")
                if new_features and existing_model.features != new_features:
                    existing_model.features = new_features
                    updated = True
                if updated:
                    session.add(existing_model)
        
        session.commit()
        if created_count > 0:
            app_logger.info(f"Default AI models initialized: {created_count} new models created")
        else:
            app_logger.info("All models already exist, no changes made")


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# Dependency
def get_session():
    with Session(engine) as session:
        yield session


def get_client_ip(request: Request) -> str:
    """获取客户端 IP"""
    return request.client.host if request.client else "unknown"


# 用户名验证规则
def validate_username(username: str) -> tuple[bool, str]:
    """验证用户名是否符合规范（放宽限制）"""
    
    # 长度检查
    if len(username) < 3:
        return False, "用户名至少需要3个字符"
    if len(username) > 20:
        return False, "用户名不能超过20个字符"
    
    # 字符检查 - 允许字母、数字、下划线、中文
    if not re.match(r'^[a-zA-Z0-9_\u4e00-\u9fa5]+$', username):
        return False, "用户名只能包含字母、数字、下划线或中文"
    
    # 不能全部是数字
    if username.isdigit():
        return False, "用户名不能全部是数字"
    
    # 简化的敏感词检查（只检查明显的系统词汇）
    forbidden_words = ['admin', 'administrator', 'root', 'system']
    
    username_lower = username.lower()
    for word in forbidden_words:
        if word == username_lower:  # 完全匹配才禁止
            return False, f"用户名不能使用系统保留词"
    
    # 连续字符检查
    if re.search(r'(.)\1{2,}', username):
        return False, "用户名不能包含3个以上连续相同字符"
    
    return True, "用户名格式正确"


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
    is_admin: Optional[bool] = False


class RechargeRequest(BaseModel):
    amount: float

class EmailCodeRequest(BaseModel):
    email: str
    purpose: str = "register"  # register 或 reset_password


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
        "bonus_rate": get_config_value(session, "bonus_rate", 0.2),
        "bonus_min_amount": get_config_value(session, "bonus_min_amount", 10),
        "min_recharge": get_config_value(session, "min_recharge", 0.01),
        "max_recharge": get_config_value(session, "max_recharge", 10000),
        "username_rules": {
            "min_length": 3,
            "max_length": 20,
            "pattern": "支持中文、字母、数字、下划线",
            "forbidden": "不能全是数字或使用系统保留词"
        },
        # 访问控制
        "block_mobile_users": get_config_value(session, "block_mobile_users", False),
        "block_mobile_message": get_config_value(session, "block_mobile_message", "暂不支持移动端访问，请使用电脑浏览器"),
        # 维护模式
        "maintenance_mode": get_config_value(session, "maintenance_mode", False),
        "maintenance_message": get_config_value(session, "maintenance_message", "系统维护中，请稍后再试"),
        "maintenance_password": get_config_value(session, "maintenance_password", ""),
        # 站点信息
        "site_name": get_config_value(session, "site_name", "大帝AI"),
        "site_announcement": get_config_value(session, "site_announcement", ""),
        # 用户设置
        "allow_register": get_config_value(session, "allow_register", True),
        "register_bonus": get_config_value(session, "register_bonus", 3.0),
        "invite_reward": get_config_value(session, "invite_reward", 3.0),
    }

@app.get("/api/config/public")
def get_public_config_legacy(session: Session = Depends(get_session)):
    """获取公共配置（兼容性路由）"""
    return get_public_config(session)

@app.post("/api/validate-username")
def validate_username_api(data: dict):
    """验证用户名格式"""
    username = data.get("username", "")
    is_valid, message = validate_username(username)
    return {
        "valid": is_valid,
        "message": message,
        "suggestions": [
            "以字母开头，如：john123",
            "包含字母和数字，如：user2024",
            "避免使用admin、test等敏感词"
        ] if not is_valid else []
    }


# --- 安全相关 API ---

@app.get("/api/captcha")
def get_captcha():
    """获取验证码挑战"""
    challenge = generate_captcha_challenge()
    return challenge


# ============ 邮箱验证 API ============
# send_verification_code, verify_email_code 已在文件顶部导入


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
    
    # 检查是否开放注册
    if not get_config_value(session, "allow_register", True):
        raise HTTPException(status_code=403, detail="系统暂未开放注册，请稍后再试")
    
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
    
    # 验证用户名格式
    username_valid, username_msg = validate_username(user.username)
    if not username_valid:
        record_fail(client_ip)
        raise HTTPException(status_code=400, detail=username_msg)

    # 使用优化的批量冲突检查，减少数据库查询次数
    conflicts = db_manager.check_user_conflicts(
        session, user.username, user.email,
        user.device_fingerprint or "", client_ip
    )

    if conflicts["username_exists"]:
        raise HTTPException(status_code=400, detail="用户名已存在")

    if conflicts["email_exists"]:
        raise HTTPException(status_code=400, detail="该邮箱已被注册")

    if conflicts["ip_registered"]:
        record_fail(client_ip)
        raise HTTPException(status_code=400, detail="当前网络环境已注册过账号，请勿重复注册")

    if user.device_fingerprint and conflicts["device_registered"]:
        record_fail(client_ip)
        raise HTTPException(status_code=400, detail="该设备已注册过账号，每个设备只能注册一个账号")
    
    # 处理邀请码（如果有）
    inviter = None
    if user.invite_code:
        inviter = session.exec(
            select(User).where(User.invite_code == user.invite_code)
        ).first()
        # 邀请码无效不报错，只是不给奖励
    
    # 生成新用户的邀请码（带重试限制，避免无限循环）
    new_invite_code = generate_invite_code()
    retry_count = 0
    max_retries = 10  # 最多重试10次
    while session.exec(select(User).where(User.invite_code == new_invite_code)).first():
        if retry_count >= max_retries:
            app_logger.error("Failed to generate unique invite code after 10 retries")
            raise HTTPException(status_code=500, detail="系统错误，请稍后重试")
        new_invite_code = generate_invite_code()
        retry_count += 1
    
    # 读取动态配置
    register_bonus = get_config_value(session, "register_bonus", 3.0)
    invite_reward = get_config_value(session, "invite_reward", 3.0)

    # 所有前置检查通过后，最后验证邮箱验证码（避免验证码被提前消费）
    valid, msg = verify_email_code(user.email, user.email_code, "register")
    if not valid:
        raise HTTPException(status_code=400, detail=msg)

    # 创建用户（余额使用动态配置）
    hashed_password = get_password_hash(user.password)
    new_user = User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password,
        balance=register_bonus,
        invite_code=new_invite_code,
        device_fingerprint=user.device_fingerprint,
        register_ip=client_ip,
        invited_by=inviter.id if inviter else None
    )
    session.add(new_user)
    session.commit()
    session.refresh(new_user)
    
    # 如果有邀请人，给邀请人发放奖励
    if inviter:
        inviter.balance += invite_reward
        session.add(inviter)
        session.commit()
    
    record_success(client_ip)
    
    # 记录审计日志
    app_logger.audit(
        "user.register",
        user_id=new_user.id,
        username=new_user.username,
        email=new_user.email,
        register_ip=client_ip,
        invited_by=inviter.id if inviter else None,
        device_fingerprint=user.device_fingerprint
    )
    
    access_token = create_access_token(data={"sub": new_user.username})
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/api/login", response_model=Token)
def login(data: LoginWithCaptcha, request: Request, session: Session = Depends(get_session)):
    try:
        client_ip = get_client_ip(request)
        app_logger.info("Login attempt", username=data.username, client_ip=client_ip)
        
        # 简化验证码逻辑，暂时跳过
        # fail_count = get_fail_count(client_ip)
        # if fail_count >= 3:
        #     if not data.captcha_challenge or not verify_captcha(...):
        #         record_fail(client_ip)
        #         raise HTTPException(status_code=400, detail="验证码验证失败")
        
        # 检查是否为管理员登录
        try:
            from backend.admin import ADMIN_USERNAME, ADMIN_PASSWORD_HASH
            if data.username == ADMIN_USERNAME:
                if not verify_password(data.password, ADMIN_PASSWORD_HASH):
                    app_logger.warning("Admin login failed - incorrect password", client_ip=client_ip)
                    record_fail(client_ip)
                    raise HTTPException(status_code=401, detail="用户名或密码错误")

                app_logger.audit("admin.login", username=data.username, login_ip=client_ip)
                record_success(client_ip)
                access_token = create_access_token(data={"sub": data.username, "is_admin": True})
                return {"access_token": access_token, "token_type": "bearer", "is_admin": True}
        except HTTPException:
            raise
        except Exception as e:
            app_logger.error("Admin login check error", exc_info=e)

        # 验证普通用户名密码
        user = session.exec(select(User).where(User.username == data.username)).first()
        if not user:
            app_logger.warning("Login failed - user not found", username=data.username, client_ip=client_ip)
            record_fail(client_ip)
            raise HTTPException(status_code=401, detail="用户名或密码错误")

        if not verify_password(data.password, user.hashed_password):
            app_logger.warning("Login failed - incorrect password", username=data.username, client_ip=client_ip)
            record_fail(client_ip)
            raise HTTPException(status_code=401, detail="用户名或密码错误")

        app_logger.audit("user.login", user_id=user.id, username=user.username, login_ip=client_ip)
        record_success(client_ip)
        # 安全获取管理员状态，防止数据库字段不存在
        is_admin = getattr(user, 'is_superuser', False)
        access_token = create_access_token(data={"sub": user.username, "is_admin": is_admin})
        return {"access_token": access_token, "token_type": "bearer", "is_admin": is_admin}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[LOGIN] Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"登录失败: {str(e)}")


@app.post("/api/email/send-code")
def send_email_verification_code(data: EmailCodeRequest, request: Request):
    """发送邮箱验证码"""
    client_ip = get_client_ip(request)
    
    # 简单的邮箱格式验证
    import re
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', data.email):
        raise HTTPException(status_code=400, detail="邮箱格式不正确")
    
    try:
        success, result = send_verification_code(data.email, data.purpose)
        if success:
            app_logger.info("Email verification code sent", email=data.email, purpose=data.purpose, client_ip=client_ip)
            return {"message": "验证码已发送", "expires_in_minutes": 5}
        else:
            app_logger.error("Failed to send email verification code", email=data.email, error=result)
            raise HTTPException(status_code=500, detail=result)
    except Exception as e:
        app_logger.error("Email service error", exc_info=e)
        raise HTTPException(status_code=500, detail="邮件服务异常，请稍后重试")


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
    
    # 与 /api/pay/create 保持一致的赠送逻辑：≥10元赠送20%
    if amount >= 10:
        bonus = round(amount * 0.2, 2)
        
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


class KlingLipSyncTTSRequest(BaseModel):
    text: str
    speaker_id: str
    speed: str = "1"
    emotion: str = ""


class KlingLipSyncSubmitRequest(BaseModel):
    model_name: str = "Kling Lip Sync"
    order_id: Optional[int] = None
    video_url: Optional[str] = None
    face_id_key: Optional[str] = None
    face_image_url: Optional[str] = None
    from_work_id: Optional[int] = None

    # If audio_url is empty, backend can generate TTS audio first.
    audio_url: Optional[str] = None
    tts_text: Optional[str] = None
    tts_speaker_id: Optional[str] = None
    tts_speed: str = "1"
    tts_emotion: str = ""
    tts_timbre: str = ""

    face_id: str = "0"
    face_start_time: int = 0
    face_end_time: int = 3000
    audio_start_time_in_video: int = 0
    audio_start_time: int = 0
    audio_end_time: int = 3000
    include_original_audio: bool = False
    speech_volume: float = 1.0
    original_audio_volume: float = 1.0

    wait: bool = False
    timeout: int = 600


# 可灵对口型TTS音色映射（speakerId -> 展示名）
KLING_LIP_SYNC_SPEAKERS = {
    "chat1_female_new-3": "温柔姐姐",
    "ai_shatang": "青春少女",
    "genshin_vindi2": "阳光少年",
    "chuanmeizi_speech02": "四川妹子",
    "tianjinjiejie_speech02": "天津姐姐",
    "mengwa-v1": "可爱正太",
    "chaoshandashu_speech02": "潮汕大叔",
    "diyinnansang_DB_CN_M_04-v2": "新闻播报男",
    "yizhipiannan-v1": "译制片男",
    "zhinen_xuesheng": "懂事小弟",
    "tiyuxi_xuedi": "运动少年",
    "tianmeinvsheng-v1": "活泼辣妹",
    "guanxiaofang-v2": "元气少女",
    "tianmeixuemei-v1": "撒娇小妹",
    "ai_kaiya": "阳光男友",
}


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


@app.post("/api/kling/pre-upload")
async def kling_pre_upload(
    image: UploadFile = File(...),
    frame_type: str = Form("first"),
    current_user: User = Depends(get_current_user),
):
    """用户选择图片后立即上传到可灵CDN，返回CDN URL。避免提交订单时再上传导致延迟。"""
    if not image.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="文件必须是图片")

    from backend import kling_api
    from backend.order_worker import _pick_kling_account

    result = _pick_kling_account()
    if not result:
        raise HTTPException(status_code=503, detail="无可用可灵账号")
    acc_id, cookie = result

    # 保存到临时文件
    import tempfile
    import uuid as _uuid
    ext = image.filename.split('.')[-1] if '.' in image.filename else 'jpg'
    tmp_path = os.path.join(tempfile.gettempdir(), f"kling_pre_{_uuid.uuid4().hex[:8]}.{ext}")
    try:
        content = await image.read()
        with open(tmp_path, "wb") as f:
            f.write(content)
        cdn_url = await kling_api.upload_image(cookie, tmp_path)
        return {"success": True, "cdn_url": cdn_url, "frame_type": frame_type}
    except Exception as e:
        app_logger.error(f"可灵预上传失败: {e}")
        raise HTTPException(status_code=502, detail=f"上传到可灵失败: {e}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def _pick_kling_cookie_for_lipsync(account_id: Optional[str] = None) -> tuple[str, str]:
    """Pick a logged-in Kling account cookie. Return (account_id, cookie)."""
    from backend import kling_api
    from backend.order_worker import _pick_kling_account

    if account_id:
        creds = kling_api.get_kling_credentials(account_id)
        if creds and creds.get("cookie"):
            return account_id, creds["cookie"]

    result = _pick_kling_account()
    if not result:
        raise HTTPException(status_code=503, detail="无可用可灵账号")
    return result


def _calc_lipsync_cost(model: AIModel, charge_seconds: int) -> float:
    """Lip-sync pricing priority: per-second > 10s fixed > fixed price."""
    secs = max(1, int(charge_seconds))
    if model.price_per_second and model.price_per_second > 0:
        return round(model.price_per_second * secs, 2)
    if secs == 10 and model.price_10s and model.price_10s > 0:
        return round(model.price_10s, 2)
    return round(model.price if model.price and model.price > 0 else 0.99, 2)


def _get_lipsync_model(session: Session, model_name: str) -> AIModel:
    model = session.exec(
        select(AIModel).where(
            (AIModel.name == model_name) | (AIModel.model_id == model_name),
            AIModel.is_enabled == True
        )
    ).first()
    if not model:
        raise HTTPException(status_code=400, detail=f"对口型模型不可用: {model_name}")
    if model.model_type != "lip_sync":
        raise HTTPException(status_code=400, detail=f"模型不是对口型类型: {model_name}")
    return model


async def _resolve_lipsync_source(
    req: KlingLipSyncSubmitRequest,
    current_user: User,
    session: Session,
    cookie: str,
) -> dict:
    from backend import kling_api

    if req.video_url and req.face_image_url and req.face_id_key:
        return {
            "video_url": req.video_url.strip(),
            "face_image_url": req.face_image_url.strip(),
            "face_id_key": req.face_id_key.strip(),
            "from_work_id": req.from_work_id,
            "source_duration_ms": 0,
        }

    if not req.order_id:
        raise HTTPException(status_code=400, detail="缺少对口型源视频信息")

    order = session.get(VideoOrder, req.order_id)
    if not order:
        raise HTTPException(status_code=404, detail="源视频订单不存在")
    if order.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权使用该视频进行对口型")
    if order.status != "completed":
        raise HTTPException(status_code=400, detail="请先选择一个已完成的视频")
    if not order.model_name or not (order.model_name.startswith("Kling") or order.model_name.startswith("可灵")):
        raise HTTPException(status_code=400, detail="只有可灵生成成功的视频才能对口型")
    if not order.task_id:
        raise HTTPException(status_code=400, detail="该视频缺少可灵任务信息，暂时无法对口型")

    try:
        task_status = await kling_api.get_task_status(cookie, str(order.task_id))
    except Exception as e:
        app_logger.error(f"解析对口型源视频失败 order_id={order.id}, task_id={order.task_id}: {e}")
        raise HTTPException(status_code=502, detail=f"获取可灵源视频信息失败: {e}")

    video_url = (task_status.get("video_url") or "").strip()
    face_image_url = (task_status.get("cover_url") or "").strip()
    creative_id = str(task_status.get("creative_id") or "").strip()
    from_work_id = int(creative_id) if creative_id.isdigit() else None

    if not video_url:
        raise HTTPException(status_code=400, detail="未找到可灵源视频地址，请稍后重试")
    if not face_image_url:
        raise HTTPException(status_code=400, detail="未找到可灵源视频封面，请稍后重试")

    return {
        "video_url": video_url,
        "face_image_url": face_image_url,
        "face_id_key": str(uuid.uuid4()),
        "from_work_id": from_work_id,
        "source_duration_ms": int(task_status.get("duration", 0) or 0),
    }


@app.post("/api/kling/lip-sync/tts")
async def kling_lip_sync_tts(
    req: KlingLipSyncTTSRequest,
    current_user: User = Depends(get_current_user),
):
    from backend import kling_api

    account_id, cookie = _pick_kling_cookie_for_lipsync()
    if req.speaker_id not in KLING_LIP_SYNC_SPEAKERS:
        raise HTTPException(status_code=400, detail=f"不支持的 speaker_id: {req.speaker_id}")
    try:
        tts = await kling_api.lip_sync_tts(
            cookie=cookie,
            text=req.text,
            speaker_id=req.speaker_id,
            speed=req.speed,
            emotion=req.emotion,
        )
        return {
            "success": True,
            "account_id": account_id,
            "audio_url": tts["audio_url"],
            "duration_ms": tts["duration_ms"],
            "status": tts["status"],
        }
    except Exception as e:
        app_logger.error(f"可灵对口型TTS失败: {e}")
        raise HTTPException(status_code=502, detail=f"可灵TTS失败: {e}")


@app.get("/api/kling/lip-sync/speakers")
async def kling_lip_sync_speakers(current_user: User = Depends(get_current_user)):
    return {
        "success": True,
        "speakers": [{"speaker_id": sid, "name": name} for sid, name in KLING_LIP_SYNC_SPEAKERS.items()]
    }


@app.post("/api/kling/lip-sync/submit")
async def kling_lip_sync_submit(
    req: KlingLipSyncSubmitRequest,
    account_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    from backend import kling_api

    selected_account_id, cookie = _pick_kling_cookie_for_lipsync(account_id)
    source = await _resolve_lipsync_source(req, current_user, session, cookie)

    audio_url = (req.audio_url or "").strip()
    tts_duration_ms = 0
    if not audio_url:
        if not req.tts_text or not req.tts_speaker_id:
            raise HTTPException(status_code=400, detail="audio_url 为空时，必须提供 tts_text 和 tts_speaker_id")
        try:
            tts = await kling_api.lip_sync_tts(
                cookie=cookie,
                text=req.tts_text,
                speaker_id=req.tts_speaker_id,
                speed=req.tts_speed,
                emotion=req.tts_emotion,
            )
            audio_url = tts.get("audio_url", "")
            tts_duration_ms = int(tts.get("duration_ms", 0) or 0)
            if not audio_url:
                raise RuntimeError("tts 返回空音频链接")
        except Exception as e:
            app_logger.error(f"可灵对口型自动TTS失败: {e}")
            raise HTTPException(status_code=502, detail=f"自动TTS失败: {e}")

    model = _get_lipsync_model(session, req.model_name)
    effective_audio_start_time = int(req.audio_start_time or 0)
    effective_audio_end_time = int(req.audio_end_time or 0)
    if effective_audio_end_time <= effective_audio_start_time and tts_duration_ms > 0:
        effective_audio_end_time = effective_audio_start_time + tts_duration_ms
    elif effective_audio_end_time <= effective_audio_start_time:
        effective_audio_end_time = effective_audio_start_time + 3000

    effective_face_start_time = int(req.face_start_time or 0)
    effective_face_end_time = int(req.face_end_time or 0)
    source_duration_ms = int(source.get("source_duration_ms", 0) or 0)
    if effective_face_end_time <= effective_face_start_time:
        effective_face_end_time = max(source_duration_ms, effective_audio_end_time, 3000)

    audio_window_ms = max(0, effective_audio_end_time - effective_audio_start_time)
    if audio_window_ms <= 0 and tts_duration_ms > 0:
        audio_window_ms = tts_duration_ms
    charge_seconds = max(1, int((audio_window_ms + 999) / 1000))
    total_cost = _calc_lipsync_cost(model, charge_seconds)

    # Refresh latest balance before charging.
    session.refresh(current_user)
    if current_user.balance < total_cost:
        raise HTTPException(status_code=400, detail=f"余额不足，需 {total_cost:.2f} 元")

    try:
        submit = await kling_api.submit_lip_sync_task(
            cookie=cookie,
            video_url=source["video_url"],
            audio_url=audio_url,
            face_id_key=source["face_id_key"],
            face_image_url=source["face_image_url"],
            face_id=req.face_id,
            from_work_id=source["from_work_id"],
            face_start_time=effective_face_start_time,
            face_end_time=effective_face_end_time,
            audio_start_time_in_video=req.audio_start_time_in_video,
            audio_start_time=effective_audio_start_time,
            audio_end_time=effective_audio_end_time,
            include_original_audio=req.include_original_audio,
            speech_volume=req.speech_volume,
            original_audio_volume=req.original_audio_volume,
            tts_text=req.tts_text or "",
            tts_speed=req.tts_speed,
            tts_timbre=req.tts_timbre,
            tts_emotion=req.tts_emotion,
        )

        result = {
            "success": True,
            "account_id": selected_account_id,
            "task_id": submit["task_id"],
            "status": submit["status"],
            "audio_url": audio_url,
            "model_name": model.name,
            "charged_seconds": charge_seconds,
            "cost": total_cost,
        }

        # Charge only after successful task submission.
        current_user.balance = round(current_user.balance - total_cost, 2)
        session.add(current_user)
        session.add(Transaction(
            user_id=current_user.id,
            amount=total_cost,
            bonus=0,
            type="expense",
        ))
        session.commit()
        result["balance"] = current_user.balance

        if req.wait:
            final_status = await kling_api.poll_lip_sync_task(
                cookie=cookie,
                task_id=submit["task_id"],
                timeout=max(30, int(req.timeout)),
                interval=5,
            )
            result["final"] = final_status

        return result
    except HTTPException:
        raise
    except TimeoutError as e:
        raise HTTPException(status_code=504, detail=str(e))
    except Exception as e:
        app_logger.error(f"可灵对口型提交失败: {e}")
        raise HTTPException(status_code=502, detail=f"可灵对口型提交失败: {e}")


@app.get("/api/kling/lip-sync/status/{task_id}")
async def kling_lip_sync_status(
    task_id: str,
    account_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    from backend import kling_api

    selected_account_id, cookie = _pick_kling_cookie_for_lipsync(account_id)
    try:
        status_data = await kling_api.get_lip_sync_status(cookie=cookie, task_id=task_id)
        return {
            "success": True,
            "account_id": selected_account_id,
            **status_data,
        }
    except Exception as e:
        app_logger.error(f"可灵对口型状态查询失败: {e}")
        raise HTTPException(status_code=502, detail=f"可灵对口型状态查询失败: {e}")


@app.post("/api/orders/create")
async def create_order(
    prompt: str = Form(...),
    model_name: str = Form("Hailuo 2.3"),
    video_type: str = Form("image_to_video"),
    resolution: str = Form("768p"),
    duration: str = Form("6s"),
    quantity: int = Form(1),
    first_frame_image: Optional[UploadFile] = File(None),
    last_frame_image: Optional[UploadFile] = File(None),
    aspect_ratio: Optional[str] = Form(None),
    remove_watermark: Optional[str] = Form("true"),
    first_frame_cdn_url: Optional[str] = Form(None),
    last_frame_cdn_url: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    # 校验video_type
    if video_type not in ("image_to_video", "dual_image_to_video", "text_to_video"):
        raise HTTPException(status_code=400, detail="无效的视频类型")

    # 校验分辨率和秒数
    if resolution not in ("480p", "720p", "768p", "1080p"):
        raise HTTPException(status_code=400, detail="无效的分辨率")
    duration_seconds = int(duration.replace("s", "")) if duration else 5
    if duration_seconds < 3 or duration_seconds > 15:
        raise HTTPException(status_code=400, detail="无效的时长")

    # 校验批量数量
    if quantity < 1 or quantity > 5:
        raise HTTPException(status_code=400, detail="批量数量仅支持1-5")

    # 图生视频必须上传首帧图片（或已预上传CDN URL）
    if video_type == "image_to_video" and not first_frame_image and not first_frame_cdn_url:
        raise HTTPException(status_code=400, detail="图生视频模式必须上传首帧图片")
    # 双图模式必须同时上传首帧和尾帧
    if video_type == "dual_image_to_video":
        if not first_frame_image and not first_frame_cdn_url:
            raise HTTPException(status_code=400, detail="双图模式必须上传首帧图片")
        if not last_frame_image and not last_frame_cdn_url:
            raise HTTPException(status_code=400, detail="双图模式必须上传尾帧图片")

    # 根据用户选择的模型获取价格
    model = session.exec(select(AIModel).where(AIModel.name == model_name)).first()
    if model and model.model_type == "lip_sync":
        raise HTTPException(status_code=400, detail="对口型模型请使用对口型专用接口")

    # 价格计算：优先使用 pricing_matrix 分档定价
    cost = None
    if model and model.pricing_matrix:
        try:
            matrix = json.loads(model.pricing_matrix) if isinstance(model.pricing_matrix, str) else model.pricing_matrix
            # 确定价格档位：text / single_image / dual_image
            if video_type == "text_to_video":
                tier = matrix.get("text")
            elif video_type == "dual_image_to_video":
                tier = matrix.get("dual_image")
            else:
                tier = matrix.get("single_image")

            # 兼容旧格式：如果没有 tier 层，直接用 matrix 作为分辨率层
            if not tier and ("720p" in matrix or "1080p" in matrix):
                tier = matrix

            if tier:
                # 找分辨率对应价格（720p 可灵用，768p 海螺用）
                res_key = resolution
                res_prices = tier.get(res_key)
                if not res_prices and resolution == "768p":
                    res_prices = tier.get("720p")
                if res_prices:
                    exact = res_prices.get(str(duration_seconds))
                    if exact and exact > 0:
                        cost = round(exact, 2)
                    elif res_prices.get("per_second"):
                        cost = round(res_prices["per_second"] * duration_seconds, 2)
        except Exception:
            pass

    # 回退定价逻辑
    if cost is None:
        if model and model.price_per_second and model.price_per_second > 0:
            cost = round(model.price_per_second * duration_seconds, 2)
        elif duration == "10s" and model and model.price_10s and model.price_10s > 0:
            cost = model.price_10s
        else:
            cost = model.price if model and model.price else 0.99

    total_cost = round(cost * quantity, 2)
    if current_user.balance < total_cost:
        raise HTTPException(status_code=400, detail=f"余额不足，需要 ¥{total_cost}（单价 ¥{cost} × {quantity}）")
    
    # 按用户ID分类存储上传图片
    import uuid as _uuid
    user_upload_dir = os.path.join("user_images", f"user_{current_user.id}")
    
    # 处理首帧图片：优先使用已预上传的CDN URL（可灵），否则保存本地文件
    first_frame_path = None
    if first_frame_cdn_url:
        # 已通过 /api/kling/pre-upload 预上传，直接记录CDN URL
        first_frame_path = f"CDN:{first_frame_cdn_url}"
    elif first_frame_image:
        if not first_frame_image.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="首帧文件必须是图片")
        
        os.makedirs(user_upload_dir, exist_ok=True)
        file_ext = first_frame_image.filename.split('.')[-1]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"first_{timestamp}_{_uuid.uuid4().hex[:8]}.{file_ext}"
        first_frame_path = os.path.join(user_upload_dir, filename)
        
        with open(first_frame_path, "wb") as f:
            content = await first_frame_image.read()
            f.write(content)
    
    # 处理尾帧图片：优先使用已预上传的CDN URL
    last_frame_path = None
    if last_frame_cdn_url:
        last_frame_path = f"CDN:{last_frame_cdn_url}"
    elif last_frame_image:
        if not last_frame_image.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="尾帧文件必须是图片")
        
        os.makedirs(user_upload_dir, exist_ok=True)
        file_ext = last_frame_image.filename.split('.')[-1]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"last_{timestamp}_{_uuid.uuid4().hex[:8]}.{file_ext}"
        last_frame_path = os.path.join(user_upload_dir, filename)
        
        with open(last_frame_path, "wb") as f:
            content = await last_frame_image.read()
            f.write(content)
    
    current_user.balance -= total_cost
    session.add(current_user)

    # 创建单条订单，quantity 字段记录批量数量，cost 为总价
    new_order = VideoOrder(
        user_id=current_user.id,
        prompt=prompt,
        video_url=None,
        cost=total_cost,
        model_name=model_name,
        video_type=video_type,
        resolution=resolution,
        duration=duration,
        first_frame_image=first_frame_path,
        last_frame_image=last_frame_path,
        aspect_ratio=aspect_ratio or "16:9",
        quantity=quantity,
        remove_watermark=(remove_watermark or "true").lower() in ("true", "1", "yes"),
    )
    session.add(new_order)
    session.flush()

    transaction = Transaction(
        user_id=current_user.id,
        amount=total_cost,
        bonus=0,
        type="expense"
    )
    session.add(transaction)

    session.commit()
    session.refresh(new_order)

    # 提交订单到HTTP API工作器处理
    enable_multi_account = os.getenv("ENABLE_MULTI_ACCOUNT", "true").lower() == "true"
    if enable_multi_account:
        try:
            from backend.order_worker import submit_order
            asyncio.create_task(submit_order(new_order.id))
            app_logger.info(f"订单#{new_order.id}(quantity={quantity})已提交HTTP API处理")
        except Exception as e:
            app_logger.error(f"提交订单处理失败: {e}")
    else:
        asyncio.create_task(run_hailuo_task(new_order.id))

    return new_order


@app.get("/api/orders")
def get_orders(current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    statement = select(VideoOrder).where(VideoOrder.user_id == current_user.id).order_by(VideoOrder.created_at.desc())
    results = session.exec(statement).all()
    return results


@app.post("/api/orders/{order_id}/force-scan")
async def force_scan_order(order_id: int, current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    """手动触发订单扫描 - 用于卡住的订单"""
    order = session.get(VideoOrder, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作此订单")
    if order.status not in ("generating", "processing"):
        raise HTTPException(status_code=400, detail="订单状态不允许扫描")
    
    from backend.order_worker import poll_order_status
    asyncio.create_task(poll_order_status(order_id))
    return {"message": "已触发扫描", "order_id": order_id}


@app.post("/api/admin/force-scan-all")
async def force_scan_all(admin=Depends(get_admin_user)):
    """强制扫描所有生成中的订单（管理员专用）"""
    from backend.order_worker import poll_all_pending_orders
    asyncio.create_task(poll_all_pending_orders())
    return {"message": "已触发全量扫描"}


@app.post("/api/hailuo/code")
def upload_verification_code(request: VerificationCodeRequest, session: Session = Depends(get_session)):
    match = re.search(r'【海螺AI】(\d{6})', request.text)
    if not match:
        match = re.search(r'(\d{6})', request.text)
    
    if not match:
        raise HTTPException(status_code=400, detail="Could not find verification code in text")
    
    code_str = match.group(1)
    
    # 添加到日志中显示
    app_logger.info(f"收到短信验证码: {code_str}")
    app_logger.info(f"完整短信内容: {request.text}")
    
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
    if os.getenv("ENVIRONMENT", "development").lower() == "production":
        raise HTTPException(status_code=404, detail="Not found")
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
    if os.getenv("ENVIRONMENT", "development").lower() == "production":
        raise HTTPException(status_code=404, detail="Not found")
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
            "platform": m.platform or "hailuo",
            "is_default": m.is_default,
            "features": json.loads(m.features) if m.features else [],
            "badge": m.badge,
            "supports_last_frame": m.supports_last_frame,
            "price": m.price or 0.99,
            "price_10s": m.price_10s if m.price_10s and m.price_10s > 0 else None,
            "price_per_second": m.price_per_second if m.price_per_second and m.price_per_second > 0 else None,
            "pricing_matrix": json.loads(m.pricing_matrix) if m.pricing_matrix else None
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


# ============ 交易记录 API ============

@app.get("/api/transactions")
def get_transactions(current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    """获取当前用户的交易记录"""
    from sqlmodel import desc
    records = session.exec(
        select(Transaction).where(Transaction.user_id == current_user.id).order_by(desc(Transaction.created_at)).limit(50)
    ).all()
    
    result = []
    for r in records:
        result.append({
            "id": r.id,
            "amount": r.amount,
            "bonus": r.bonus,
            "type": r.type,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    
    # 统计
    total_recharge = sum(r.amount + r.bonus for r in records if r.type == "recharge")
    total_expense = sum(r.amount for r in records if r.type == "expense")
    
    return {
        "transactions": result,
        "summary": {
            "total_recharge": round(total_recharge, 2),
            "total_expense": round(total_expense, 2),
            "balance": round(current_user.balance, 2),
        }
    }


# ============ 邀请系统 API ============

@app.get("/api/invite/stats")
def get_invite_stats(current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    """获取当前用户的邀请统计和邀请列表"""
    # 查询被该用户邀请的人
    invited_users = session.exec(
        select(User).where(User.invited_by == current_user.id).order_by(User.created_at.desc())
    ).all()
    
    invite_reward = get_config_value(session, "invite_reward", 3.0)
    
    invite_list = []
    for u in invited_users:
        invite_list.append({
            "username": u.username[:1] + "***" + u.username[-1:] if len(u.username) > 2 else u.username[:1] + "**",
            "created_at": u.created_at.isoformat() if u.created_at else None,
        })
    
    return {
        "invite_code": current_user.invite_code,
        "total_invited": len(invited_users),
        "total_earnings": len(invited_users) * invite_reward,
        "invite_reward": invite_reward,
        "invite_list": invite_list,
    }


# ============ 视频文件服务（鉴权） ============
import os
from fastapi.responses import FileResponse

# 视频文件目录
videos_dir = os.path.join(os.path.dirname(__file__), "..", "videos")
os.makedirs(videos_dir, exist_ok=True)

@app.get("/videos/{filename}")
async def serve_video(filename: str, token: Optional[str] = None, session: Session = Depends(get_session)):
    """只有下单用户和管理员能访问视频，支持query参数token鉴权"""
    if not token:
        raise HTTPException(status_code=401, detail="未登录")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        is_admin = payload.get("is_admin", False)
        if not username:
            raise HTTPException(status_code=401, detail="无效token")
    except JWTError:
        raise HTTPException(status_code=401, detail="无效token")

    # 管理员直接放行
    if is_admin:
        filepath = os.path.join(videos_dir, filename)
        if not os.path.isfile(filepath):
            raise HTTPException(status_code=404, detail="视频文件不存在")
        return FileResponse(filepath, media_type="video/mp4")

    # 普通用户：检查权限
    user = session.exec(select(User).where(User.username == username)).first()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")

    # 从文件名提取订单ID（格式: order_123.mp4）
    order_id = None
    if filename.startswith("order_") and filename.endswith(".mp4"):
        try:
            order_id = int(filename.replace("order_", "").replace(".mp4", ""))
        except ValueError:
            pass

    if order_id:
        order = session.get(VideoOrder, order_id)
        if not order:
            raise HTTPException(status_code=404, detail="订单不存在")
        if order.user_id != user.id:
            raise HTTPException(status_code=403, detail="无权访问此视频")

    filepath = os.path.join(videos_dir, filename)
    if not os.path.isfile(filepath):
        raise HTTPException(status_code=404, detail="视频文件不存在")

    return FileResponse(filepath, media_type="video/mp4")

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
