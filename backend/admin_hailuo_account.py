"""
海螺AI 账号管理后台 API

登录方式：
  1. 短信验证码登录（POST send-sms → POST verify-sms）
  2. Cookie 手动登录（POST cookie-login）
"""
import asyncio
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from backend.admin import get_admin_user
from backend.hailuo_api import (
    list_hailuo_accounts, save_hailuo_account, save_hailuo_credentials,
    delete_hailuo_account, update_hailuo_account, get_hailuo_credentials,
    build_client, send_sms_code, login_with_sms, HailuoApiClient,
)
import uuid as _uuid
import random

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/hailuo-accounts", tags=["海螺账号管理"])

# 短信登录会话 {account_id: {phone, uuid, device_id, status}}
_sms_sessions: dict = {}


class AccountCreateRequest(BaseModel):
    account_id: str
    display_name: str
    priority: int = 5
    max_concurrent: int = 3


class AccountUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    priority: Optional[int] = None
    max_concurrent: Optional[int] = None
    is_active: Optional[bool] = None


class CookieLoginRequest(BaseModel):
    cookie: str
    uuid: Optional[str] = None
    device_id: Optional[str] = None


class SmsSendRequest(BaseModel):
    phone: str


class SmsVerifyRequest(BaseModel):
    code: str


# ============ 账号 CRUD ============

@router.get("")
async def list_accounts(admin=Depends(get_admin_user)):
    return {"accounts": list_hailuo_accounts()}


@router.post("")
async def create_account(req: AccountCreateRequest, admin=Depends(get_admin_user)):
    acc = save_hailuo_account(
        account_id=req.account_id,
        display_name=req.display_name,
        priority=req.priority,
        max_concurrent=req.max_concurrent,
    )
    return {"success": True, "account": acc}


@router.patch("/{account_id}")
async def update_account(account_id: str, req: AccountUpdateRequest, admin=Depends(get_admin_user)):
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    acc = update_hailuo_account(account_id, **updates)
    if acc is None:
        raise HTTPException(status_code=404, detail="账号不存在")
    return {"success": True, "account": acc}


@router.delete("/{account_id}")
async def remove_account(account_id: str, admin=Depends(get_admin_user)):
    delete_hailuo_account(account_id)
    _sms_sessions.pop(account_id, None)
    return {"success": True}


# ============ Cookie 登录 ============

@router.post("/{account_id}/cookie-login")
async def cookie_login(account_id: str, req: CookieLoginRequest, admin=Depends(get_admin_user)):
    """手动填入 Cookie 登录"""
    uuid_val = req.uuid or str(_uuid.uuid4())
    device_id = req.device_id or str(random.randint(10**17, 10**18 - 1))

    # 验证 cookie 是否有效
    client = HailuoApiClient(cookie=req.cookie, uuid=uuid_val, device_id=device_id)
    try:
        ok = await client.check_login()
    finally:
        await client.close()

    if not ok:
        raise HTTPException(status_code=400, detail="Cookie 无效或已过期")

    save_hailuo_credentials(account_id, req.cookie, uuid_val, device_id)
    update_hailuo_account(account_id, is_logged_in=True)
    return {"success": True, "message": "Cookie 登录成功"}


# ============ 短信验证码登录 ============

@router.post("/{account_id}/sms/send")
async def sms_send(account_id: str, req: SmsSendRequest, admin=Depends(get_admin_user)):
    """发送短信验证码"""
    uuid_val = str(_uuid.uuid4())
    device_id = str(random.randint(10**17, 10**18 - 1))

    try:
        resp = await send_sms_code(req.phone, uuid_val, device_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"发送验证码失败: {e}")

    code = (resp.get("statusInfo") or {}).get("code", -1)
    if code != 0:
        msg = (resp.get("statusInfo") or {}).get("message", "未知错误")
        raise HTTPException(status_code=400, detail=f"发送失败: {msg}")

    _sms_sessions[account_id] = {
        "phone": req.phone,
        "uuid": uuid_val,
        "device_id": device_id,
        "status": "sent",
    }
    return {"success": True, "message": f"验证码已发送到 {req.phone}"}


@router.post("/{account_id}/sms/verify")
async def sms_verify(account_id: str, req: SmsVerifyRequest, admin=Depends(get_admin_user)):
    """验证短信验证码并登录"""
    session = _sms_sessions.get(account_id)
    if not session or session["status"] != "sent":
        raise HTTPException(status_code=400, detail="请先发送验证码")

    try:
        result = await login_with_sms(
            session["phone"], req.code,
            session["uuid"], session["device_id"],
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"登录失败: {e}")

    resp_json = result["json"]
    code = (resp_json.get("statusInfo") or {}).get("code", -1)
    if code != 0:
        msg = (resp_json.get("statusInfo") or {}).get("message", "验证码错误")
        raise HTTPException(status_code=400, detail=f"登录失败: {msg}")

    data = resp_json.get("data") or {}
    token = data.get("token", "")
    new_device_id = data.get("deviceID", session["device_id"])

    # 构建完整 cookie
    set_cookies = result.get("cookies", "")
    if set_cookies:
        cookie = f"{set_cookies}; _token={token}"
    else:
        cookie = f"_token={token}"

    save_hailuo_credentials(account_id, cookie, session["uuid"], new_device_id)
    update_hailuo_account(account_id, is_logged_in=True)
    _sms_sessions.pop(account_id, None)

    return {
        "success": True,
        "message": "登录成功",
        "username": data.get("webName") or data.get("username", ""),
        "user_id": data.get("realUserID", ""),
    }


# ============ 验证 & 积分 ============

@router.post("/{account_id}/check-login")
async def check_account_login(account_id: str, admin=Depends(get_admin_user)):
    """验证 cookie 是否有效，失效时自动更新状态"""
    creds = get_hailuo_credentials(account_id)
    if not creds:
        update_hailuo_account(account_id, is_logged_in=False)
        return {"is_logged_in": False}
    client = HailuoApiClient(
        cookie=creds["cookie"], uuid=creds["uuid"], device_id=creds["device_id"],
    )
    try:
        ok = await client.check_login()
    finally:
        await client.close()
    update_hailuo_account(account_id, is_logged_in=ok)
    return {"is_logged_in": ok}


@router.get("/{account_id}/points")
async def get_account_points(account_id: str, admin=Depends(get_admin_user)):
    """查询海螺账号贝壳积分"""
    creds = get_hailuo_credentials(account_id)
    if not creds:
        raise HTTPException(status_code=404, detail="账号未登录")
    client = HailuoApiClient(
        cookie=creds["cookie"], uuid=creds["uuid"], device_id=creds["device_id"],
    )
    try:
        credits = await client.get_credits()
    finally:
        await client.close()
    if credits is None:
        raise HTTPException(status_code=502, detail="查询积分失败")
    return {"success": True, "points": {"total": credits}}
