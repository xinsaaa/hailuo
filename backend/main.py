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


# 后端启动时自动启动浏览器自动化（暂时禁用，管理员端再启用）
@app.on_event("startup")
def startup_event():
    print("[MAIN] Backend started. Automation worker disabled.")
    # start_automation_worker()  # 暂时禁用


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
