"""
多账号管理后台API — 纯HTTP模式（无浏览器）
"""
import random
import uuid as uuid_module
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from backend.admin import get_admin_user
from backend.account_store import account_store, AccountConfig
from backend.hailuo_api import send_sms_code, login_with_sms

router = APIRouter(prefix="/api/admin/accounts", tags=["多账号管理"])

# 临时存储待验证的短信会话 {phone_number: {uuid, device_id}}
_pending_sms: dict = {}


class AccountCreateRequest(BaseModel):
    account_id: str
    phone_number: str
    display_name: str
    priority: int = 5
    max_concurrent: int = 3
    series: str = "2.3"


class SmsSendRequest(BaseModel):
    phone_number: str


class SmsCreateRequest(BaseModel):
    account_id: str
    phone_number: str
    display_name: str
    code: str
    priority: int = 5
    max_concurrent: int = 3
    series: str = "2.3"


class AccountUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    priority: Optional[int] = None
    max_concurrent: Optional[int] = None
    series: Optional[str] = None


class VerificationCodeRequest(BaseModel):
    verification_code: str


# ============ 固定路径路由（必须全部在 /{account_id} 之前） ============

@router.get("")
def list_accounts(admin=Depends(get_admin_user)):
    """获取所有账号列表"""
    status = account_store.get_status()
    return list(status["accounts"].values())


@router.get("/list")
def list_accounts_alias(admin=Depends(get_admin_user)):
    """/list 别名，兼容旧前端"""
    status = account_store.get_status()
    return {"accounts": list(status["accounts"].values())}


@router.get("/status")
def get_status(admin=Depends(get_admin_user)):
    """系统运行状态"""
    status_data = account_store.get_status()
    accounts = status_data.get("accounts", {})
    active_accounts = sum(1 for a in accounts.values() if a.get("is_active") and a.get("is_logged_in"))
    return {
        "status": "running" if active_accounts > 0 else "stopped",
        "is_running": active_accounts > 0,
        "total_accounts": len(accounts),
        "active_accounts": active_accounts,
        "active_tasks": sum(a.get("current_tasks", 0) for a in accounts.values()),
        "accounts": accounts,
    }


@router.get("/performance")
def get_performance_metrics(admin=Depends(get_admin_user)):
    """获取性能指标"""
    accounts = account_store.accounts
    creds = account_store._creds

    total_accounts = len(accounts)
    active_accounts = sum(1 for a in accounts.values() if a.is_active)
    logged_in_accounts = sum(1 for aid in accounts if aid in creds)
    total_capacity = sum(a.max_concurrent for a in accounts.values() if a.is_active)
    current_load = sum(a.current_tasks for a in accounts.values())
    utilization = current_load / total_capacity if total_capacity > 0 else 0

    if utilization < 0.3:
        performance_level = "优秀"
    elif utilization < 0.6:
        performance_level = "良好"
    elif utilization < 0.8:
        performance_level = "一般"
    else:
        performance_level = "繁忙"

    return {
        "total_accounts": total_accounts,
        "active_accounts": active_accounts,
        "logged_in_accounts": logged_in_accounts,
        "total_capacity": total_capacity,
        "current_load": current_load,
        "utilization": utilization,
        "performance_level": performance_level,
        "available_slots": total_capacity - current_load,
        "efficiency_score": (logged_in_accounts / active_accounts * 100) if active_accounts > 0 else 0,
    }


@router.post("/start")
async def start_system(admin=Depends(get_admin_user)):
    return {"ok": True, "message": "HTTP API模式已就绪"}


@router.post("/stop")
async def stop_system(admin=Depends(get_admin_user)):
    return {"ok": True, "message": "HTTP API模式无需停止"}


# ============ 短信登录流程 ============

@router.post("/sms/send")
async def send_sms(data: SmsSendRequest, admin=Depends(get_admin_user)):
    """Step1: 向手机号发送登录验证码"""
    u = str(uuid_module.uuid4())
    dev = str(random.randint(10**18, 10**19 - 1))
    _pending_sms[data.phone_number] = {"uuid": u, "device_id": dev}
    resp = await send_sms_code(data.phone_number, u, dev)
    code = resp.get("statusInfo", {}).get("code", -1)
    if code != 0:
        msg = resp.get("statusInfo", {}).get("message", "未知错误")
        raise HTTPException(status_code=400, detail=f"发送验证码失败: {msg}")
    return {"ok": True}


@router.post("/sms/login")
async def sms_login(data: SmsCreateRequest, admin=Depends(get_admin_user)):
    """Step2: 用验证码完成登录并创建账号"""
    session = _pending_sms.get(data.phone_number)
    if not session:
        raise HTTPException(status_code=400, detail="请先发送验证码")

    resp = await login_with_sms(data.phone_number, data.code, session["uuid"], session["device_id"])
    code = resp.get("statusInfo", {}).get("code", -1)
    if code != 0:
        msg = resp.get("statusInfo", {}).get("message", "未知错误")
        raise HTTPException(status_code=400, detail=f"登录失败: {msg}")

    token = (resp.get("data") or {}).get("token", "")
    if not token:
        raise HTTPException(status_code=400, detail="登录成功但未获取到token")

    cfg = AccountConfig(
        account_id=data.account_id,
        phone_number=data.phone_number,
        display_name=data.display_name,
        priority=data.priority,
        max_concurrent=data.max_concurrent,
        is_active=True,
        series=data.series,
    )
    account_store.add_account(cfg)
    account_store.set_credentials(data.account_id, {
        "cookie": f"_token={token}",
        "uuid": session["uuid"],
        "device_id": session["device_id"],
    })
    _pending_sms.pop(data.phone_number, None)
    return {"ok": True, "account_id": data.account_id}


@router.post("/create")
async def create_account(data: AccountCreateRequest, admin=Depends(get_admin_user)):
    """创建新账号（无凭证，后续通过短信登录获取cookie）"""
    if data.account_id in account_store.accounts:
        raise HTTPException(status_code=400, detail="账号ID已存在")
    cfg = AccountConfig(
        account_id=data.account_id,
        phone_number=data.phone_number,
        display_name=data.display_name,
        priority=data.priority,
        max_concurrent=data.max_concurrent,
        is_active=True,
        series=data.series,
    )
    account_store.add_account(cfg)
    return {"ok": True, "message": "账号已创建，请通过短信登录获取凭证"}


# ============ 单账号操作（/{account_id} 系列，必须放在所有固定路径之后） ============

@router.get("/{account_id}/credits")
async def get_account_credits(account_id: str, admin=Depends(get_admin_user)):
    """查询账号贝壳积分"""
    if account_id not in account_store.accounts:
        raise HTTPException(status_code=404, detail="账号不存在")
    creds = account_store.get_credentials(account_id)
    if not creds:
        return {"success": False, "credits": -1, "message": "未登录"}
    from backend.hailuo_api import HailuoApiClient
    client = HailuoApiClient(cookie=creds["cookie"], uuid=creds["uuid"], device_id=creds["device_id"])
    try:
        credits = await client.get_credits()
        return {"success": True, "credits": credits}
    except Exception as e:
        return {"success": False, "credits": -1, "message": str(e)}
    finally:
        await client.close()


@router.post("/{account_id}/login")
async def login_account_alias(account_id: str, admin=Depends(get_admin_user)):
    """兼容旧前端：返回 success=False 让前端弹出验证码窗口"""
    return {"success": False, "message": "请使用验证码登录"}


@router.post("/{account_id}/send-code")
async def send_code_for_account(account_id: str, admin=Depends(get_admin_user)):
    """为已有账号重新发送登录验证码"""
    if account_id not in account_store.accounts:
        raise HTTPException(status_code=404, detail="账号不存在")
    acc = account_store.accounts[account_id]
    u = str(uuid_module.uuid4())
    dev = str(random.randint(10**18, 10**19 - 1))
    _pending_sms[acc.phone_number] = {"uuid": u, "device_id": dev, "account_id": account_id}
    resp = await send_sms_code(acc.phone_number, u, dev)
    code = resp.get("statusInfo", {}).get("code", -1)
    if code != 0:
        msg = resp.get("statusInfo", {}).get("message", "未知错误")
        raise HTTPException(status_code=400, detail=f"发送验证码失败: {msg}")
    return {"ok": True, "phone_number": acc.phone_number}


@router.post("/{account_id}/verify-code")
async def verify_code_for_account(account_id: str, data: VerificationCodeRequest, admin=Depends(get_admin_user)):
    """用验证码完成账号登录"""
    if account_id not in account_store.accounts:
        raise HTTPException(status_code=404, detail="账号不存在")
    acc = account_store.accounts[account_id]
    session = _pending_sms.get(acc.phone_number)
    if not session:
        raise HTTPException(status_code=400, detail="请先发送验证码")
    resp = await login_with_sms(acc.phone_number, data.verification_code, session["uuid"], session["device_id"])
    code = resp.get("statusInfo", {}).get("code", -1)
    if code != 0:
        msg = resp.get("statusInfo", {}).get("message", "未知错误")
        raise HTTPException(status_code=400, detail=f"登录失败: {msg}")
    token = (resp.get("data") or {}).get("token", "")
    if not token:
        raise HTTPException(status_code=400, detail="登录成功但未获取到token")
    account_store.set_credentials(account_id, {
        "cookie": f"_token={token}",
        "uuid": session["uuid"],
        "device_id": session["device_id"],
    })
    _pending_sms.pop(acc.phone_number, None)
    return {"ok": True, "account_id": account_id}


@router.get("/{account_id}")
def get_account(account_id: str, admin=Depends(get_admin_user)):
    if account_id not in account_store.accounts:
        raise HTTPException(status_code=404, detail="账号不存在")
    status = account_store.get_status()
    return status["accounts"][account_id]


@router.put("/{account_id}")
def update_account(account_id: str, data: AccountUpdateRequest, admin=Depends(get_admin_user)):
    if account_id not in account_store.accounts:
        raise HTTPException(status_code=404, detail="账号不存在")
    acc = account_store.accounts[account_id]
    if data.display_name is not None:
        acc.display_name = data.display_name
    if data.priority is not None:
        acc.priority = data.priority
    if data.max_concurrent is not None:
        acc.max_concurrent = data.max_concurrent
    if data.series is not None:
        acc.series = data.series
    account_store.save()
    return {"ok": True}


@router.post("/{account_id}/toggle")
def toggle_account(account_id: str, admin=Depends(get_admin_user)):
    if account_id not in account_store.accounts:
        raise HTTPException(status_code=404, detail="账号不存在")
    acc = account_store.accounts[account_id]
    acc.is_active = not acc.is_active
    account_store.save()
    return {"ok": True, "is_active": acc.is_active}


@router.delete("/{account_id}")
def delete_account(account_id: str, admin=Depends(get_admin_user)):
    if account_id not in account_store.accounts:
        raise HTTPException(status_code=404, detail="账号不存在")
    account_store.remove_account(account_id)
    return {"message": "账号删除成功", "account_id": account_id}


# 导出路由
def include_multi_account_routes(app):
    """将多账号管理路由添加到主应用"""
    app.include_router(router)
