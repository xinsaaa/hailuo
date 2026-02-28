"""
管理员模块：管理员认证、用户管理、订单管理、自动化控制、安全管理
"""
import os
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlmodel import Session, select, func
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Any

import json
from backend.models import User, VideoOrder, Transaction, AIModel, SystemConfig, engine
from backend.auth import get_password_hash, verify_password, create_access_token, SECRET_KEY, ALGORITHM
from backend.security import (
    is_ip_banned, get_ban_remaining_seconds, get_fail_count,
    record_fail, record_success
)
from backend.automation_v2 import automation_v2, start_automation_v2, stop_automation_v2, get_automation_v2_status
from jose import JWTError, jwt

# 中国时区 UTC+8
CHINA_TZ = timezone(timedelta(hours=8))

def utc_to_china_time(utc_dt):
    """将UTC时间转换为中国时间"""
    if utc_dt is None:
        return None
    # 如果是naive datetime，假设它是UTC时间
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)
    # 转换为中国时间
    china_time = utc_dt.astimezone(CHINA_TZ)
    return china_time.strftime('%Y/%m/%d %H:%M:%S')

# ============ 配置（从环境变量读取）============
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")  # 生产环境请设置环境变量！
ADMIN_PASSWORD_HASH = get_password_hash(ADMIN_PASSWORD)

# 管理员登录失败限制
_admin_fail_count = {}  # {ip: {"count": 0, "last": datetime}}

def _get_admin_max_fail():
    """从DB动态读取管理员最大失败次数"""
    try:
        with Session(engine) as s:
            from sqlmodel import select as sql_select
            cfg = s.exec(sql_select(SystemConfig).where(SystemConfig.key == "admin_max_fail")).first()
            if cfg:
                return int(json.loads(cfg.value))
    except Exception:
        pass
    return 5

# 创建路由
router = APIRouter(prefix="/api/admin", tags=["admin"])


# ============ 依赖 ============
def get_session():
    with Session(engine) as session:
        yield session


def get_admin_user(request: Request):
    """验证管理员 Token"""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未授权访问")
    
    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        is_admin = payload.get("is_admin", False)
        
        if not is_admin or username != ADMIN_USERNAME:
            raise HTTPException(status_code=403, detail="需要管理员权限")
        
        return {"username": username, "is_admin": True}
    except JWTError:
        raise HTTPException(status_code=401, detail="Token 无效")


def check_admin_rate_limit(ip: str) -> bool:
    """检查管理员登录是否超限"""
    now = datetime.now()
    if ip in _admin_fail_count:
        data = _admin_fail_count[ip]
        if data["last"] and (now - data["last"]).total_seconds() > 1800:
            _admin_fail_count[ip] = {"count": 0, "last": None}
            return True
        if data["count"] >= _get_admin_max_fail():
            return False
    return True


# ============ Pydantic Schemas ============
class AdminLogin(BaseModel):
    username: str
    password: str


class UserUpdate(BaseModel):
    balance: Optional[float] = None
    is_banned: Optional[bool] = None


class OrderUpdate(BaseModel):
    status: Optional[str] = None
    video_url: Optional[str] = None


# ============ 管理员认证 ============

@router.post("/login")
def admin_login(data: AdminLogin, request: Request):
    """管理员登录"""
    client_ip = request.client.host if request.client else "unknown"
    
    # 检查管理员登录限制
    if not check_admin_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="登录尝试过多，请30分钟后再试")
    
    if data.username != ADMIN_USERNAME or not verify_password(data.password, ADMIN_PASSWORD_HASH):
        # 记录失败
        if client_ip not in _admin_fail_count:
            _admin_fail_count[client_ip] = {"count": 0, "last": None}
        _admin_fail_count[client_ip]["count"] += 1
        _admin_fail_count[client_ip]["last"] = datetime.now()
        
        remaining = _get_admin_max_fail() - _admin_fail_count[client_ip]["count"]
        raise HTTPException(status_code=401, detail=f"用户名或密码错误，剩余 {remaining} 次尝试")
    
    # 登录成功，清除失败计数
    if client_ip in _admin_fail_count:
        del _admin_fail_count[client_ip]
    
    # 生成带 is_admin 标记的 Token
    access_token = create_access_token(
        data={"sub": ADMIN_USERNAME, "is_admin": True},
        expires_delta=timedelta(hours=24)
    )
    
    return {"access_token": access_token, "token_type": "bearer"}


# ============ 修改管理员密码 ============

class ChangePasswordRequest(BaseModel):
    new_password: str

@router.post("/change-password")
def change_admin_password(data: ChangePasswordRequest, admin=Depends(get_admin_user)):
    """修改管理员密码（运行时生效，重启后需通过环境变量持久化）"""
    global ADMIN_PASSWORD, ADMIN_PASSWORD_HASH
    
    if len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail="密码长度不能少于6位")
    
    ADMIN_PASSWORD = data.new_password
    ADMIN_PASSWORD_HASH = get_password_hash(data.new_password)
    
    return {"message": "密码修改成功，重启服务后请确保环境变量 ADMIN_PASSWORD 已更新"}


# ============ 系统统计 ============

@router.get("/stats")
def get_stats(admin=Depends(get_admin_user), session: Session = Depends(get_session)):
    """获取系统统计数据"""
    # 用户统计
    total_users = session.exec(select(func.count(User.id))).one()
    
    # 订单统计
    total_orders = session.exec(select(func.count(VideoOrder.id))).one()
    completed_orders = session.exec(
        select(func.count(VideoOrder.id)).where(VideoOrder.status == "completed")
    ).one()
    pending_orders = session.exec(
        select(func.count(VideoOrder.id)).where(VideoOrder.status.in_(["pending", "processing", "generating"]))
    ).one()
    
    # 收入统计
    total_recharge = session.exec(
        select(func.sum(Transaction.amount)).where(Transaction.type == "recharge")
    ).one() or 0
    total_expense = session.exec(
        select(func.sum(Transaction.amount)).where(Transaction.type == "expense")
    ).one() or 0
    
    # 统计今日数据
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    today_orders = session.exec(
        select(func.count(VideoOrder.id)).where(VideoOrder.created_at >= today_start)
    ).one()
    
    today_recharge = session.exec(
        select(func.sum(Transaction.amount)).where(Transaction.type == "recharge").where(Transaction.created_at >= today_start)
    ).one() or 0
    
    # 邀请统计
    total_invited_users = session.exec(select(func.count(User.id)).where(User.invited_by.is_not(None))).one()
    total_invite_bonus = session.exec(
        select(func.sum(Transaction.amount)).where(Transaction.type == "invite_bonus")
    ).one() or 0
    
    return {
        "users": {
            "total": total_users,
            "invited": total_invited_users
        },
        "orders": {
            "total": total_orders,
            "completed": completed_orders,
            "pending": pending_orders,
            "today": today_orders
        },
        "revenue": {
            "total_recharge": float(total_recharge),
            "total_expense": float(total_expense),
            "today_recharge": float(today_recharge),
            "total_invite_bonus": float(total_invite_bonus)
        }
    }


# ============ 用户管理 ============

@router.get("/users")
def list_users(
    page: int = 1,
    limit: int = 20,
    admin=Depends(get_admin_user),
    session: Session = Depends(get_session)
):
    """获取用户列表"""
    offset = (page - 1) * limit
    
    users = session.exec(
        select(User).order_by(User.created_at.desc()).offset(offset).limit(limit)
    ).all()
    
    total = session.exec(select(func.count(User.id))).one()
    
    return {
        "users": [
            {
                "id": u.id,
                "username": u.username,
                "balance": u.balance,
                "invite_code": u.invite_code,
                "invited_by": u.invited_by,
                "created_at": utc_to_china_time(u.created_at)
            }
            for u in users
        ],
        "total": total,
        "page": page,
        "limit": limit
    }


@router.get("/users/{user_id}")
def get_user(user_id: int, admin=Depends(get_admin_user), session: Session = Depends(get_session)):
    """获取用户详情"""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 获取用户订单
    orders = session.exec(
        select(VideoOrder).where(VideoOrder.user_id == user_id).order_by(VideoOrder.created_at.desc()).limit(10)
    ).all()
    
    # 获取用户交易记录
    transactions = session.exec(
        select(Transaction).where(Transaction.user_id == user_id).order_by(Transaction.created_at.desc()).limit(10)
    ).all()
    
    return {
        "user": {
            "id": user.id,
            "username": user.username,
            "balance": user.balance,
            "created_at": utc_to_china_time(user.created_at)
        },
        "recent_orders": [
            {
                "id": o.id,
                "prompt": o.prompt[:50] + "..." if len(o.prompt) > 50 else o.prompt,
                "status": o.status,
                "created_at": utc_to_china_time(o.created_at)
            }
            for o in orders
        ],
        "recent_transactions": [
            {
                "id": t.id,
                "type": t.type,
                "amount": t.amount,
                "bonus": t.bonus,
                "created_at": utc_to_china_time(t.created_at)
            }
            for t in transactions
        ]
    }


@router.patch("/users/{user_id}")
def update_user(
    user_id: int,
    data: UserUpdate,
    admin=Depends(get_admin_user),
    session: Session = Depends(get_session)
):
    """更新用户信息（调整余额等）"""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    if data.balance is not None:
        old_balance = user.balance
        user.balance = data.balance
        # 记录管理员调整
        transaction = Transaction(
            user_id=user_id,
            amount=data.balance - old_balance,
            bonus=0,
            type="admin_adjust"
        )
        session.add(transaction)
    
    session.add(user)
    session.commit()
    session.refresh(user)
    
    return {"message": "更新成功", "user": {"id": user.id, "balance": user.balance}}


# ============ 订单管理 ============

@router.get("/orders")
def list_orders(
    page: int = 1,
    limit: int = 20,
    status: Optional[str] = None,
    admin=Depends(get_admin_user),
    session: Session = Depends(get_session)
):
    """获取订单列表"""
    offset = (page - 1) * limit
    
    query = select(VideoOrder)
    if status:
        query = query.where(VideoOrder.status == status)
    
    orders = session.exec(
        query.order_by(VideoOrder.created_at.desc()).offset(offset).limit(limit)
    ).all()
    
    count_query = select(func.count(VideoOrder.id))
    if status:
        count_query = count_query.where(VideoOrder.status == status)
    total = session.exec(count_query).one()
    
    return {
        "orders": [
            {
                "id": o.id,
                "user_id": o.user_id,
                "prompt": o.prompt[:100] + "..." if len(o.prompt) > 100 else o.prompt,
                "status": o.status,
                "video_url": o.video_url,
                "cost": o.cost,
                "created_at": utc_to_china_time(o.created_at)
            }
            for o in orders
        ],
        "total": total,
        "page": page,
        "limit": limit
    }


@router.get("/orders/{order_id}")
def get_order(order_id: int, admin=Depends(get_admin_user), session: Session = Depends(get_session)):
    """获取订单详情"""
    order = session.get(VideoOrder, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    
    # 获取用户信息
    user = session.get(User, order.user_id)
    
    return {
        "order": {
            "id": order.id,
            "prompt": order.prompt,
            "status": order.status,
            "video_url": order.video_url,
            "cost": order.cost,
            "created_at": utc_to_china_time(order.created_at)
        },
        "user": {
            "id": user.id if user else None,
            "username": user.username if user else "已删除"
        }
    }


@router.patch("/orders/{order_id}")
def update_order(
    order_id: int,
    data: OrderUpdate,
    admin=Depends(get_admin_user),
    session: Session = Depends(get_session)
):
    """更新订单（修改状态、视频链接）"""
    order = session.get(VideoOrder, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    
    if data.status is not None:
        order.status = data.status
    if data.video_url is not None:
        order.video_url = data.video_url
    
    session.add(order)
    session.commit()
    session.refresh(order)
    
    return {"message": "更新成功", "order": {"id": order.id, "status": order.status, "video_url": order.video_url}}


# ============ 自动化控制 ============
from backend.automation import automation_logger

@router.get("/automation/status")
def get_automation_status(admin=Depends(get_admin_user)):
    """获取自动化运行状态（V2多账号版）"""
    v2_status = get_automation_v2_status()

    is_running = v2_status.get("is_running", False)
    active_accounts = v2_status.get("active_accounts", 0)
    total_accounts = v2_status.get("total_accounts", 0)
    active_tasks = v2_status.get("active_tasks", 0)

    # 兼容前端现有的 status 字段
    if is_running and active_accounts > 0:
        status = "running"
    elif is_running:
        status = "starting"
    else:
        status = "stopped"

    return {
        "status": status,
        "is_running": is_running,
        "total_accounts": total_accounts,
        "active_accounts": active_accounts,
        "active_tasks": active_tasks,
        "accounts": v2_status.get("accounts", {})
    }


@router.get("/automation/logs")
def get_automation_logs(limit: int = 50, admin=Depends(get_admin_user)):
    """获取自动化运行日志"""
    logs = automation_logger.get_logs(limit)
    return {
        "logs": logs,
        "total": len(logs)
    }

@router.post("/automation/start")
async def start_automation(admin=Depends(get_admin_user)):
    """启动自动化（V2多账号版）"""
    if automation_v2.is_running:
        return {"message": "自动化已在运行中"}

    try:
        automation_logger.info("收到启动请求，正在初始化V2多账号系统...")
        await start_automation_v2()
        return {"message": "多账号自动化启动成功"}
    except Exception as e:
        automation_logger.error(f"启动失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"启动失败: {str(e)}")


@router.post("/automation/stop")
async def stop_automation(admin=Depends(get_admin_user)):
    """停止自动化（V2多账号版）"""
    if not automation_v2.is_running:
        return {"message": "自动化未在运行"}

    try:
        await stop_automation_v2()
        automation_logger.info("多账号自动化系统已停止")
        return {"message": "多账号自动化已停止"}
    except Exception as e:
        automation_logger.error(f"停止失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"停止失败: {str(e)}")


# ============ 安全管理 ============

from backend.models import IPBan, LoginFailure
from sqlmodel import select as sql_select


@router.get("/security/banned-ips")
def list_banned_ips(admin=Depends(get_admin_user), session: Session = Depends(get_session)):
    """获取被封禁的 IP 列表（优化版本）"""
    now = datetime.now()
    
    # 获取所有封禁记录（包括已过期的，用于显示历史记录）
    all_bans = session.exec(sql_select(IPBan).order_by(IPBan.created_at.desc()).limit(100)).all()
    
    # 清理过期的封禁记录
    expired_bans = [ban for ban in all_bans if ban.expires_at <= now]
    for expired_ban in expired_bans:
        session.delete(expired_ban)
    
    if expired_bans:
        session.commit()
        # 重新获取有效封禁记录
        valid_bans = session.exec(sql_select(IPBan).where(IPBan.expires_at > now).order_by(IPBan.created_at.desc())).all()
    else:
        valid_bans = [ban for ban in all_bans if ban.expires_at > now]
    
    banned_list = []
    for ban in valid_bans:
        remaining_seconds = max(0, int((ban.expires_at - now).total_seconds()))
        banned_list.append({
            "ip": ban.ip,
            "reason": ban.reason,
            "expires_at": utc_to_china_time(ban.expires_at),  # 使用中国时间显示
            "created_at": utc_to_china_time(ban.created_at),  # 显示封禁创建时间
            "remaining_seconds": remaining_seconds,
            "remaining_hours": round(remaining_seconds / 3600, 1)  # 显示剩余小时数
        })
    
    # 获取高风险IP（失败次数多但未封禁）
    high_risk_ips = session.exec(
        sql_select(LoginFailure).where(
            LoginFailure.fail_count >= 5,
            LoginFailure.fail_count < 10  # 未达到封禁阈值
        ).order_by(LoginFailure.fail_count.desc()).limit(20)
    ).all()
    
    risk_list = []
    for risk in high_risk_ips:
        # 检查是否已被封禁
        is_banned = session.exec(sql_select(IPBan).where(IPBan.ip == risk.ip)).first()
        if not is_banned:
            risk_list.append({
                "ip": risk.ip,
                "fail_count": risk.fail_count,
                "last_fail_at": utc_to_china_time(risk.last_fail_at) if risk.last_fail_at else None,
                "status": "高风险" if risk.fail_count >= 7 else "中风险"
            })
    
    return {
        "banned_ips": banned_list,
        "banned_count": len(banned_list),
        "high_risk_ips": risk_list,
        "risk_count": len(risk_list),
        "total_cleaned": len(expired_bans)
    }


@router.delete("/security/unban")
def unban_ip(ip: str, admin=Depends(get_admin_user), session: Session = Depends(get_session)):
    """解除 IP 封禁（IP 作为 query 参数，从数据库删除）"""
    # 删除封禁记录
    ban = session.exec(sql_select(IPBan).where(IPBan.ip == ip)).first()
    if ban:
        session.delete(ban)
        print(f"[ADMIN] 解除IP封禁: {ip}")
    
    # 重置失败计数
    failure = session.exec(sql_select(LoginFailure).where(LoginFailure.ip == ip)).first()
    if failure:
        failure.fail_count = 0
        failure.last_fail_at = None
        session.add(failure)
        print(f"[ADMIN] 重置失败计数: {ip}")
    
    session.commit()
    return {"message": f"已解除 {ip} 的封禁", "success": True}


class ManualBanRequest(BaseModel):
    ip: str
    reason: str = "管理员手动封禁"
    duration_hours: int = 24  # 封禁时长（小时）


@router.post("/security/ban-ip")
def manual_ban_ip(
    data: ManualBanRequest,
    admin=Depends(get_admin_user), 
    session: Session = Depends(get_session)
):
    """手动封禁IP"""
    # 检查IP是否已被封禁
    existing_ban = session.exec(sql_select(IPBan).where(IPBan.ip == data.ip)).first()
    if existing_ban:
        # 更新现有封禁
        existing_ban.expires_at = datetime.now() + timedelta(hours=data.duration_hours)
        existing_ban.reason = data.reason
        session.add(existing_ban)
    else:
        # 创建新封禁
        new_ban = IPBan(
            ip=data.ip,
            reason=data.reason,
            expires_at=datetime.now() + timedelta(hours=data.duration_hours)
        )
        session.add(new_ban)
    
    session.commit()
    print(f"[ADMIN] 手动封禁IP: {data.ip}, 时长: {data.duration_hours}小时, 原因: {data.reason}")
    return {
        "message": f"已封禁 IP {data.ip}",
        "duration_hours": data.duration_hours,
        "reason": data.reason,
        "success": True
    }


@router.post("/security/create-test-data")
def create_test_security_data(admin=Depends(get_admin_user), session: Session = Depends(get_session)):
    """创建测试安全数据（仅用于演示和测试）"""
    now = datetime.now()
    
    # 创建一些测试的封禁记录
    test_bans = [
        {
            "ip": "192.168.1.100",
            "reason": "暴力破解登录",
            "expires_at": now + timedelta(hours=12)
        },
        {
            "ip": "10.0.0.50",
            "reason": "恶意注册账号",
            "expires_at": now + timedelta(hours=6)
        },
        {
            "ip": "172.16.0.25",
            "reason": "频繁请求API",
            "expires_at": now + timedelta(hours=24)
        }
    ]
    
    # 创建一些测试的失败记录
    test_failures = [
        {"ip": "192.168.1.200", "fail_count": 7},
        {"ip": "10.0.0.75", "fail_count": 6},
        {"ip": "172.16.0.80", "fail_count": 8},
        {"ip": "203.0.113.15", "fail_count": 5}
    ]
    
    created_bans = 0
    created_failures = 0
    
    # 添加封禁记录
    for ban_data in test_bans:
        existing = session.exec(sql_select(IPBan).where(IPBan.ip == ban_data["ip"])).first()
        if not existing:
            ban = IPBan(**ban_data)
            session.add(ban)
            created_bans += 1
    
    # 添加失败记录
    for failure_data in test_failures:
        existing = session.exec(sql_select(LoginFailure).where(LoginFailure.ip == failure_data["ip"])).first()
        if not existing:
            failure = LoginFailure(
                ip=failure_data["ip"],
                fail_count=failure_data["fail_count"],
                last_fail_at=now - timedelta(minutes=30)
            )
            session.add(failure)
            created_failures += 1
    
    session.commit()
    
    return {
        "message": "测试数据创建完成",
        "created_bans": created_bans,
        "created_failures": created_failures,
        "success": True
    }


@router.get("/security/fail-stats")
def get_fail_stats(admin=Depends(get_admin_user), session: Session = Depends(get_session)):
    """获取登录失败统计（优化版本）"""
    failures = session.exec(
        sql_select(LoginFailure).where(LoginFailure.fail_count > 0).order_by(LoginFailure.fail_count.desc()).limit(50)
    ).all()
    
    # 一次性获取所有封禁IP，避免N+1查询
    all_bans = session.exec(sql_select(IPBan)).all()
    banned_ips = {ban.ip for ban in all_bans}
    
    stats = []
    for f in failures:
        stats.append({
            "ip": f.ip,
            "fail_count": f.fail_count,
            "last_fail": utc_to_china_time(f.last_fail_at) if f.last_fail_at else None,
            "created_at": utc_to_china_time(f.created_at),
            "is_banned": f.ip in banned_ips,
            "risk_level": "高风险" if f.fail_count >= 8 else "中风险" if f.fail_count >= 5 else "低风险"
        })
    
    # 统计信息
    total_failures = len(stats)
    high_risk_count = sum(1 for s in stats if s["fail_count"] >= 8)
    banned_count = sum(1 for s in stats if s["is_banned"])
    
    return {
        "fail_stats": stats,
        "summary": {
            "total_failures": total_failures,
            "high_risk_count": high_risk_count,
            "banned_count": banned_count,
            "active_threats": high_risk_count - banned_count
        }
    }


# ============ 系统配置管理 ============

# 默认配置定义（按分类组织）
DEFAULT_CONFIG = {
    # ---- 充值设置 ----
    "bonus_rate": {"value": 0.2, "description": "充值赠送比例（满最低金额生效）", "category": "recharge", "type": "number"},
    "bonus_min_amount": {"value": 10, "description": "享受赠送的最低充值金额（元）", "category": "recharge", "type": "number"},
    "min_recharge": {"value": 0.01, "description": "最低充值金额（元）", "category": "recharge", "type": "number"},
    "max_recharge": {"value": 10000, "description": "最高充值金额（元）", "category": "recharge", "type": "number"},
    # ---- 用户设置 ----
    "register_bonus": {"value": 3.0, "description": "新用户注册赠送金额（元）", "category": "user", "type": "number"},
    "invite_reward": {"value": 3.0, "description": "邀请奖励金额（双方各得，元）", "category": "user", "type": "number"},
    "allow_register": {"value": True, "description": "是否开放新用户注册", "category": "user", "type": "boolean"},
    # ---- 站点设置 ----
    "site_name": {"value": "大帝AI", "description": "站点名称", "category": "site", "type": "string"},
    "site_announcement": {"value": "", "description": "站点公告（为空则不显示）", "category": "site", "type": "string"},
    # ---- 自动化设置 ----
    "task_poll_interval": {"value": 5, "description": "任务轮询间隔（秒）", "category": "automation", "type": "number"},
    "health_check_interval": {"value": 300, "description": "账号健康检查间隔（秒）", "category": "automation", "type": "number"},
    "default_max_concurrent": {"value": 3, "description": "新账号默认最大并发任务数", "category": "automation", "type": "number"},
    "pause_generation": {"value": False, "description": "暂停生成（到点击生成按钮前停住）", "category": "automation", "type": "boolean"},
    # ---- 安全设置 ----
    "token_expire_hours": {"value": 24, "description": "用户Token过期时间（小时）", "category": "security", "type": "number"},
    "admin_max_fail": {"value": 5, "description": "管理员登录最大失败次数", "category": "security", "type": "number"},
    "code_expire_minutes": {"value": 5, "description": "邮箱验证码有效期（分钟）", "category": "security", "type": "number"},
    # ---- 访问控制 ----
    "block_mobile_users": {"value": False, "description": "是否拦截手机端用户访问", "category": "access", "type": "boolean"},
    "block_mobile_message": {"value": "暂不支持移动端访问，请使用电脑浏览器", "description": "手机用户拦截提示语", "category": "access", "type": "string"},
    # ---- 维护模式 ----
    "maintenance_mode": {"value": False, "description": "开启维护模式（用户访问将看到维护页面）", "category": "maintenance", "type": "boolean"},
    "maintenance_message": {"value": "系统维护中，请稍后再试", "description": "维护页面提示语", "category": "maintenance", "type": "string"},
    "maintenance_password": {"value": "", "description": "绕过维护模式的密码（留空则无法绕过）", "category": "maintenance", "type": "string"},
}


class ConfigUpdate(BaseModel):
    key: str
    value: Any


@router.get("/config")
def get_all_config(admin=Depends(get_admin_user), session: Session = Depends(get_session)):
    """获取所有配置"""
    configs = session.exec(sql_select(SystemConfig)).all()
    config_dict = {c.key: json.loads(c.value) for c in configs}
    
    # 合并默认配置，保留category和type元信息
    result = {}
    for key, default in DEFAULT_CONFIG.items():
        item = {
            "value": config_dict.get(key, default["value"]),
            "description": default["description"],
            "category": default.get("category", "other"),
            "type": default.get("type", "string"),
        }
        result[key] = item
    
    return {"configs": result}


@router.patch("/config")
def update_config(
    data: ConfigUpdate,
    admin=Depends(get_admin_user),
    session: Session = Depends(get_session)
):
    """更新单个配置"""
    if data.key not in DEFAULT_CONFIG:
        raise HTTPException(status_code=400, detail=f"不支持的配置项: {data.key}")
    
    config = session.exec(sql_select(SystemConfig).where(SystemConfig.key == data.key)).first()
    
    if config:
        config.value = json.dumps(data.value)
        config.updated_at = datetime.utcnow()
    else:
        config = SystemConfig(
            key=data.key,
            value=json.dumps(data.value),
            description=DEFAULT_CONFIG[data.key]["description"]
        )
    
    session.add(config)
    session.commit()
    
    return {"message": "配置更新成功", "key": data.key, "value": data.value}


# ============ 存储管理 ============

@router.get("/storage/stats")
def get_storage_stats(admin=Depends(get_admin_user)):
    """获取存储使用统计"""
    try:
        from backend.cleanup import get_storage_stats
        stats = get_storage_stats()
        return {
            "status": "success",
            "data": stats
        }
    except Exception as e:
        return {
            "status": "error", 
            "message": str(e)
        }

@router.post("/storage/cleanup")
def manual_cleanup(admin=Depends(get_admin_user)):
    """手动执行清理任务"""
    try:
        from backend.cleanup import cleanup_old_images, cleanup_old_orders
        
        # 执行清理
        cleanup_old_images()
        cleanup_old_orders()
        
        return {"message": "清理任务执行成功"}
    except Exception as e:
        automation_logger.error(f"手动清理失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"清理失败: {str(e)}")


# ============ 模型管理 API ============

class ModelUpdateRequest(BaseModel):
    is_enabled: Optional[bool] = None
    is_default: Optional[bool] = None
    sort_order: Optional[int] = None
    badge: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None  # 添加价格字段


class ModelOrderRequest(BaseModel):
    model_orders: List[dict]  # [{"id": 1, "sort_order": 1}, ...]


@router.get("/models")
def get_all_models(admin=Depends(get_admin_user), session: Session = Depends(get_session)):
    """获取所有模型（包括禁用的）"""
    import json
    
    models = session.exec(
        select(AIModel).order_by(AIModel.sort_order)
    ).all()
    
    result = []
    for m in models:
        result.append({
            "id": m.id,
            "model_id": m.model_id,
            "name": m.name,
            "display_name": m.display_name,
            "description": m.description,
            "model_type": m.model_type,
            "features": json.loads(m.features) if m.features else [],
            "badge": m.badge,
            "supports_last_frame": m.supports_last_frame,
            "is_default": m.is_default,
            "is_enabled": m.is_enabled,
            "sort_order": m.sort_order,
            "price": m.price or 0.99,  # 添加价格字段
            "created_at": utc_to_china_time(m.created_at),
            "updated_at": utc_to_china_time(m.updated_at)
        })
    
    return {
        "models": result,
        "total": len(result)
    }


@router.put("/models/{model_id}")
def update_model(
    model_id: int,
    data: ModelUpdateRequest,
    admin=Depends(get_admin_user),
    session: Session = Depends(get_session)
):
    """更新单个模型配置"""
    model = session.get(AIModel, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")
    
    # 如果设置为默认模型，先取消其他模型的默认状态
    if data.is_default is True:
        all_models = session.exec(select(AIModel)).all()
        for m in all_models:
            if m.id != model_id:
                m.is_default = False
        model.is_default = True
    elif data.is_default is False:
        model.is_default = False
    
    if data.is_enabled is not None:
        model.is_enabled = data.is_enabled
    
    if data.sort_order is not None:
        model.sort_order = data.sort_order
    
    if data.badge is not None:
        model.badge = data.badge if data.badge else None
    
    if data.description is not None:
        model.description = data.description
    
    # 添加价格更新逻辑
    if data.price is not None:
        if data.price < 0:
            raise HTTPException(status_code=400, detail="价格不能为负数")
        model.price = data.price
    
    model.updated_at = datetime.utcnow()
    session.commit()
    
    return {"message": "模型更新成功", "model_id": model_id, "new_price": model.price}


@router.put("/models/batch/order")
def update_models_order(
    data: ModelOrderRequest,
    admin=Depends(get_admin_user),
    session: Session = Depends(get_session)
):
    """批量更新模型排序"""
    for item in data.model_orders:
        model = session.get(AIModel, item["id"])
        if model:
            model.sort_order = item["sort_order"]
            model.updated_at = datetime.utcnow()
    
    session.commit()
    return {"message": "排序更新成功"}


# ============ 工单管理 ============
from backend.models import Ticket


class TicketReplyData(BaseModel):
    reply: str


@router.get("/tickets")
def list_admin_tickets(
    status: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    admin=Depends(get_admin_user),
    session: Session = Depends(get_session)
):
    """管理员获取所有工单列表"""
    from sqlmodel import desc
    query = select(Ticket)
    if status:
        query = query.where(Ticket.status == status)
    query = query.order_by(desc(Ticket.created_at))
    
    # 分页
    offset = (page - 1) * limit
    tickets = session.exec(query.offset(offset).limit(limit)).all()
    
    # 获取总数
    total_query = select(func.count()).select_from(Ticket)
    if status:
        total_query = total_query.where(Ticket.status == status)
    total = session.exec(total_query).one()
    
    # 附加用户名
    result = []
    for t in tickets:
        user = session.get(User, t.user_id)
        result.append({
            **t.model_dump(),
            "username": user.username if user else "未知用户"
        })
    
    return {"tickets": result, "total": total, "page": page, "limit": limit}


@router.get("/tickets/{ticket_id}")
def get_admin_ticket_detail(
    ticket_id: int,
    admin=Depends(get_admin_user),
    session: Session = Depends(get_session)
):
    """管理员获取工单详情，包含对话消息列表"""
    from backend.models import TicketMessage
    
    ticket = session.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")
    
    # 获取用户名
    user = session.get(User, ticket.user_id)
    
    # 获取对话消息
    messages = session.exec(
        select(TicketMessage).where(TicketMessage.ticket_id == ticket_id).order_by(TicketMessage.created_at)
    ).all()
    
    return {
        "ticket": {
            **ticket.model_dump(),
            "username": user.username if user else "未知用户"
        },
        "messages": [
            {
                "id": m.id,
                "sender_type": m.sender_type,
                "content": m.content,
                "created_at": utc_to_china_time(m.created_at)
            }
            for m in messages
        ]
    }


@router.post("/tickets/{ticket_id}/reply")
def reply_ticket(
    ticket_id: int,
    data: TicketReplyData,
    admin=Depends(get_admin_user),
    session: Session = Depends(get_session)
):
    """管理员回复工单（追加消息到对话）"""
    from backend.models import TicketMessage
    
    ticket = session.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")
    if ticket.status == "closed":
        raise HTTPException(status_code=400, detail="工单已关闭，无法回复")
    
    # 创建消息
    message = TicketMessage(
        ticket_id=ticket_id,
        sender_type="admin",
        content=data.reply
    )
    session.add(message)
    
    # 更新工单状态（兼容旧字段，同时更新时间戳）
    ticket.admin_reply = data.reply  # 兼容旧逻辑，保留最后一条回复
    ticket.status = "replied"
    ticket.replied_at = datetime.utcnow()
    ticket.updated_at = datetime.utcnow()
    session.add(ticket)
    session.commit()
    
    return {"message": "回复成功"}


@router.post("/tickets/{ticket_id}/close")
def close_ticket(
    ticket_id: int,
    admin=Depends(get_admin_user),
    session: Session = Depends(get_session)
):
    """管理员关闭工单"""
    ticket = session.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")
    
    ticket.status = "closed"
    ticket.updated_at = datetime.utcnow()
    session.add(ticket)
    session.commit()
    
    return {"message": "工单已关闭"}


