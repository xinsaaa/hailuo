from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from sqlmodel import Session, select
from pydantic import BaseModel
from typing import Optional
from backend.models import User, VideoOrder, Transaction, VerificationCode, engine
import re
from backend.auth import get_password_hash, verify_password, create_access_token, SECRET_KEY, ALGORITHM
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



# 添加中间件（顺序很重要，Rate Limiting 需要在 CORS 之后）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)


# 后端启动时自动初始化数据库和启动自动化
@app.on_event("startup")
def startup_event():
    # 确保数据库表存在
    from backend.models import create_db_and_tables
    create_db_and_tables()
    print("[MAIN] Database tables initialized.")
    print("[MAIN] Backend started. Automation worker disabled.")


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
    password: str
    # 验证码5参数
    captcha_challenge: str
    captcha_puzzle: str
    captcha_cipher: str
    captcha_nonce: str
    captcha_proof: str
    captcha_position: float


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
    
    # 检查用户名是否存在
    db_user = session.exec(select(User).where(User.username == user.username)).first()
    if db_user:
        raise HTTPException(status_code=400, detail="用户名已存在")
    
    # 创建用户
    hashed_password = get_password_hash(user.password)
    new_user = User(username=user.username, hashed_password=hashed_password)
    session.add(new_user)
    session.commit()
    session.refresh(new_user)
    
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
    
    # 验证用户名密码
    user = session.exec(select(User).where(User.username == data.username)).first()
    if not user or not verify_password(data.password, user.hashed_password):
        is_banned = record_fail(client_ip)
        if is_banned:
            raise HTTPException(status_code=403, detail="行为异常，已被临时封禁 30 分钟")
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    
    record_success(client_ip)
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}


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
async def create_order(request: OrderRequest, background_tasks: BackgroundTasks, current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    cost = 0.99
    if current_user.balance < cost:
        raise HTTPException(status_code=400, detail="Insufficient balance")
    
    current_user.balance -= cost
    session.add(current_user)
    
    new_order = VideoOrder(
        user_id=current_user.id,
        prompt=request.prompt,
        video_url=None,
        cost=cost
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
    
    vc = VerificationCode(
        code=code_str,
        source="sms_shortcut"
    )
    session.add(vc)
    session.commit()
    session.refresh(vc)
    
    return {"message": "Code received", "code": code_str}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
