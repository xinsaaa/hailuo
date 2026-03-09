"""
即梦账号管理后台API
"""
import json
import os
import asyncio
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from backend.admin import get_admin_user

router = APIRouter(prefix="/api/admin/jimeng-accounts", tags=["即梦账号管理"])

JIMENG_ACCOUNTS_FILE = os.path.join(os.path.dirname(__file__), "jimeng_accounts.json")


def _load_jimeng_accounts() -> dict:
    if not os.path.exists(JIMENG_ACCOUNTS_FILE):
        default = {"accounts": [], "settings": {"browser_headless": True, "max_total_concurrent": 5}}
        _save_jimeng_accounts(default)
        return default
    with open(JIMENG_ACCOUNTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_jimeng_accounts(data: dict):
    with open(JIMENG_ACCOUNTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class JimengAccountCreate(BaseModel):
    account_id: str
    display_name: str
    cookie: Optional[str] = None
    priority: int = 5
    max_concurrent: int = 3


class JimengAccountUpdate(BaseModel):
    display_name: Optional[str] = None
    cookie: Optional[str] = None
    priority: Optional[int] = None
    max_concurrent: Optional[int] = None
    is_active: Optional[bool] = None


class JimengCookieLogin(BaseModel):
    cookie: str


@router.get("/list")
def list_jimeng_accounts(admin=Depends(get_admin_user)):
    data = _load_jimeng_accounts()
    accounts = data.get("accounts", [])
    return {
        "accounts": accounts,
        "total": len(accounts),
        "active": sum(1 for a in accounts if a.get("is_active", False)),
        "logged_in": sum(1 for a in accounts if a.get("is_logged_in", False)),
    }


@router.post("/create")
def create_jimeng_account(body: JimengAccountCreate, admin=Depends(get_admin_user)):
    data = _load_jimeng_accounts()
    accounts = data.get("accounts", [])
    if any(a["account_id"] == body.account_id for a in accounts):
        raise HTTPException(status_code=400, detail="账号ID已存在")
    accounts.append({
        "account_id": body.account_id,
        "display_name": body.display_name,
        "cookie": body.cookie or "",
        "priority": body.priority,
        "max_concurrent": body.max_concurrent,
        "is_active": True,
        "is_logged_in": bool(body.cookie),
        "current_tasks": 0,
    })
    data["accounts"] = accounts
    _save_jimeng_accounts(data)
    return {"message": "账号创建成功", "account_id": body.account_id}


@router.put("/{account_id}")
def update_jimeng_account(account_id: str, body: JimengAccountUpdate, admin=Depends(get_admin_user)):
    data = _load_jimeng_accounts()
    accounts = data.get("accounts", [])
    account = next((a for a in accounts if a["account_id"] == account_id), None)
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")
    if body.display_name is not None:
        account["display_name"] = body.display_name
    if body.cookie is not None:
        account["cookie"] = body.cookie
        account["is_logged_in"] = bool(body.cookie)
    if body.priority is not None:
        account["priority"] = body.priority
    if body.max_concurrent is not None:
        account["max_concurrent"] = body.max_concurrent
    if body.is_active is not None:
        account["is_active"] = body.is_active
    _save_jimeng_accounts(data)
    return {"message": "账号更新成功"}


@router.post("/{account_id}/cookie-login")
def cookie_login(account_id: str, body: JimengCookieLogin, admin=Depends(get_admin_user)):
    """粘贴Cookie完成登录"""
    data = _load_jimeng_accounts()
    accounts = data.get("accounts", [])
    account = next((a for a in accounts if a["account_id"] == account_id), None)
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")
    if not body.cookie.strip():
        raise HTTPException(status_code=400, detail="Cookie不能为空")
    account["cookie"] = body.cookie.strip()
    account["is_logged_in"] = True
    _save_jimeng_accounts(data)
    return {"message": "Cookie保存成功，账号已标记为已登录", "success": True}


@router.post("/{account_id}/logout")
def logout_jimeng_account(account_id: str, admin=Depends(get_admin_user)):
    data = _load_jimeng_accounts()
    accounts = data.get("accounts", [])
    account = next((a for a in accounts if a["account_id"] == account_id), None)
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")
    account["cookie"] = ""
    account["is_logged_in"] = False
    _save_jimeng_accounts(data)
    return {"message": "已登出", "success": True}


@router.delete("/{account_id}")
def delete_jimeng_account(account_id: str, admin=Depends(get_admin_user)):
    data = _load_jimeng_accounts()
    accounts = data.get("accounts", [])
    before = len(accounts)
    data["accounts"] = [a for a in accounts if a["account_id"] != account_id]
    if len(data["accounts"]) == before:
        raise HTTPException(status_code=404, detail="账号不存在")
    _save_jimeng_accounts(data)
    return {"message": "账号已删除"}


# ===== 二维码登录 API =====

@router.post("/{account_id}/qr-login/start")
async def start_qr_login(account_id: str, admin=Depends(get_admin_user)):
    """启动抖音二维码登录流程，返回二维码 base64"""
    from backend.jimeng_automation import get_or_create_session, get_session

    data = _load_jimeng_accounts()
    accounts = data.get("accounts", [])
    account = next((a for a in accounts if a["account_id"] == account_id), None)
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")

    session = get_or_create_session(account_id)
    if session.status not in ("pending", "scanning"):
        # 旧会话已结束，重建
        from backend.jimeng_automation import remove_session
        remove_session(account_id)
        session = get_or_create_session(account_id)

    if session.status == "pending":
        session.start()

    # 等待二维码就绪（最多 30 秒）
    for _ in range(60):
        if session.qr_base64 or session.status in ("success", "failed", "timeout"):
            break
        await asyncio.sleep(0.5)

    if session.status == "failed":
        raise HTTPException(status_code=500, detail=session.error or "启动登录失败")
    if session.status == "timeout":
        raise HTTPException(status_code=408, detail="获取二维码超时")
    if not session.qr_base64:
        raise HTTPException(status_code=500, detail="未能获取二维码，请重试")

    return {"success": True, "qr_base64": session.qr_base64, "status": session.status}


@router.get("/{account_id}/qr-login/status")
async def check_qr_login_status(account_id: str, admin=Depends(get_admin_user)):
    """轮询二维码登录状态"""
    from backend.jimeng_automation import get_session, remove_session

    session = get_session(account_id)
    if not session:
        return {"status": "not_started"}

    if session.status == "success" and session.cookie:
        # 保存 Cookie 到文件
        data = _load_jimeng_accounts()
        accounts = data.get("accounts", [])
        account = next((a for a in accounts if a["account_id"] == account_id), None)
        if account:
            account["cookie"] = session.cookie
            account["is_logged_in"] = True
            _save_jimeng_accounts(data)
        remove_session(account_id)
        return {"status": "success", "message": "登录成功，Cookie已保存"}

    if session.status == "failed":
        error = session.error
        remove_session(account_id)
        return {"status": "failed", "message": error or "登录失败"}

    if session.status == "timeout":
        remove_session(account_id)
        return {"status": "timeout", "message": "二维码已过期"}

    return {"status": session.status, "qr_base64": session.qr_base64}


@router.post("/{account_id}/qr-login/cancel")
async def cancel_qr_login(account_id: str, admin=Depends(get_admin_user)):
    """取消二维码登录"""
    from backend.jimeng_automation import remove_session
    remove_session(account_id)
    return {"success": True, "message": "已取消"}
