"""
管理员模块：管理员认证、用户管理、订单管理、自动化控制、安全管理
"""
import os
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlmodel import Session, select, func
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta

from backend.models import User, VideoOrder, Transaction, AIModel, engine
from backend.auth import get_password_hash, verify_password, create_access_token, SECRET_KEY, ALGORITHM
from backend.security import (
    is_ip_banned, get_ban_remaining_seconds, get_fail_count,
    record_fail, record_success
)
from backend.automation import start_automation_worker, _browser, _page
from jose import JWTError, jwt

# ============ 配置（从环境变量读取）============
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")  # 生产环境请设置环境变量！
ADMIN_PASSWORD_HASH = get_password_hash(ADMIN_PASSWORD)

# 管理员登录失败限制
ADMIN_MAX_FAIL = 5  # 最大失败次数
_admin_fail_count = {}  # {ip: {"count": 0, "last": datetime}}

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
        # 30分钟后重置
        if data["last"] and (now - data["last"]).total_seconds() > 1800:
            _admin_fail_count[ip] = {"count": 0, "last": None}
            return True
        if data["count"] >= ADMIN_MAX_FAIL:
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
        
        remaining = ADMIN_MAX_FAIL - _admin_fail_count[client_ip]["count"]
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
                "created_at": u.created_at.isoformat() if u.created_at else None
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
            "created_at": user.created_at.isoformat() if user.created_at else None
        },
        "recent_orders": [
            {
                "id": o.id,
                "prompt": o.prompt[:50] + "..." if len(o.prompt) > 50 else o.prompt,
                "status": o.status,
                "created_at": o.created_at.isoformat() if o.created_at else None
            }
            for o in orders
        ],
        "recent_transactions": [
            {
                "id": t.id,
                "type": t.type,
                "amount": t.amount,
                "bonus": t.bonus,
                "created_at": t.created_at.isoformat() if t.created_at else None
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
                "created_at": o.created_at.isoformat() if o.created_at else None
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
            "created_at": order.created_at.isoformat() if order.created_at else None
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
    """获取自动化运行状态"""
    from backend.automation import _browser, _page, _is_logged_in
    
    browser_running = _browser is not None
    page_ready = _page is not None
    logged_in = _is_logged_in
    
    # 更精确的状态判断
    if browser_running and page_ready and logged_in:
        status = "running"
    elif browser_running and page_ready:
        status = "connected"  # 浏览器连接但未登录
    elif browser_running:
        status = "starting"  # 浏览器启动中
    else:
        status = "stopped"
    
    return {
        "browser_running": browser_running,
        "page_ready": page_ready,
        "logged_in": logged_in,
        "status": status
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
def start_automation(admin=Depends(get_admin_user)):
    """启动自动化"""
    if _browser is not None:
        return {"message": "自动化已在运行中"}
    
    try:
        automation_logger.info("收到启动请求，正在初始化...")
        start_automation_worker()
        return {"message": "自动化启动成功"}
    except Exception as e:
        automation_logger.error(f"启动失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"启动失败: {str(e)}")


@router.post("/automation/stop")
def stop_automation(admin=Depends(get_admin_user)):
    """停止自动化（需要实现 stop 函数）"""
    # TODO: 实现停止逻辑
    return {"message": "暂未实现停止功能，请重启后端"}


# ============ 安全管理 ============

from backend.models import IPBan, LoginFailure
from sqlmodel import select as sql_select


@router.get("/security/banned-ips")
def list_banned_ips(admin=Depends(get_admin_user), session: Session = Depends(get_session)):
    """获取被封禁的 IP 列表（从数据库）"""
    now = datetime.now()
    bans = session.exec(sql_select(IPBan).where(IPBan.expires_at > now)).all()
    
    banned_list = [
        {
            "ip": ban.ip,
            "reason": ban.reason,
            "expires_at": ban.expires_at.isoformat(),
            "remaining_seconds": max(0, int((ban.expires_at - now).total_seconds()))
        }
        for ban in bans
    ]
    
    return {"banned_ips": banned_list}


@router.delete("/security/unban")
def unban_ip(ip: str, admin=Depends(get_admin_user), session: Session = Depends(get_session)):
    """解除 IP 封禁（IP 作为 query 参数，从数据库删除）"""
    # 删除封禁记录
    ban = session.exec(sql_select(IPBan).where(IPBan.ip == ip)).first()
    if ban:
        session.delete(ban)
    
    # 重置失败计数
    failure = session.exec(sql_select(LoginFailure).where(LoginFailure.ip == ip)).first()
    if failure:
        failure.fail_count = 0
        failure.last_fail_at = None
        session.add(failure)
    
    session.commit()
    return {"message": f"已解除 {ip} 的封禁"}


@router.get("/security/fail-stats")
def get_fail_stats(admin=Depends(get_admin_user), session: Session = Depends(get_session)):
    """获取登录失败统计（从数据库）"""
    failures = session.exec(
        sql_select(LoginFailure).where(LoginFailure.fail_count > 0).order_by(LoginFailure.fail_count.desc()).limit(50)
    ).all()
    
    stats = [
        {
            "ip": f.ip,
            "fail_count": f.fail_count,
            "last_fail": f.last_fail_at.isoformat() if f.last_fail_at else None
        }
        for f in failures
    ]
    
    return {"fail_stats": stats}


# ============ 系统配置管理 ============
from backend.models import SystemConfig
import json

# 默认配置定义
DEFAULT_CONFIG = {
    "video_price": {"value": 0.99, "description": "单个视频生成价格（元）"},
    "bonus_rate": {"value": 0.2, "description": "充值赠送比例（满10元生效）"},
    "bonus_min_amount": {"value": 10, "description": "享受赠送的最低充值金额（元）"},
    "min_recharge": {"value": 0.01, "description": "最低充值金额（元）"},
    "max_recharge": {"value": 10000, "description": "最高充值金额（元）"},
}


class ConfigUpdate(BaseModel):
    key: str
    value: float


@router.get("/config")
def get_all_config(admin=Depends(get_admin_user), session: Session = Depends(get_session)):
    """获取所有配置"""
    configs = session.exec(sql_select(SystemConfig)).all()
    config_dict = {c.key: {"value": json.loads(c.value), "description": c.description} for c in configs}
    
    # 合并默认配置
    result = {}
    for key, default in DEFAULT_CONFIG.items():
        if key in config_dict:
            result[key] = config_dict[key]
        else:
            result[key] = default
    
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
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "updated_at": m.updated_at.isoformat() if m.updated_at else None
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
    
    model.updated_at = datetime.utcnow()
    session.commit()
    
    return {"message": "模型更新成功", "model_id": model_id}


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
                "created_at": m.created_at.isoformat()
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


