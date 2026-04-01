"""
可灵账号管理后台 API — 纯HTTP扫码登录模式

流程：
  1. POST /start  → 后端请求二维码，返回 base64 图片
  2. 前端展示二维码给管理员扫
  3. GET  /status → 轮询状态（pending/scanned/done/timeout/error）
  4. done 后 cookie 自动保存
"""
import asyncio
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from backend.admin import get_admin_user
from backend.kling_api import (
    _gen_did, _gen_risk_id, _url_to_qr_base64,
    qr_start, qr_scan_result, qr_accept_result, check_login,
    request_mobile_code, mobile_code_login,
    get_kling_account, list_kling_accounts, save_kling_account, save_kling_credentials,
    delete_kling_account, update_kling_account, get_kling_credentials,
    get_user_points, init_remove_watermark,
)

router = APIRouter(prefix="/api/admin/kling-accounts", tags=["可灵账号管理"])

# 进行中的扫码会话 {account_id: session_dict}
_sessions: dict = {}


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


class KlingSmsCodeRequest(BaseModel):
    phone: str
    country_code: str = "+86"


class KlingSmsLoginRequest(BaseModel):
    phone: str
    sms_code: str
    country_code: str = "+86"


# ============ 账号 CRUD ============

@router.get("")
async def list_accounts(admin=Depends(get_admin_user)):
    return {"accounts": list_kling_accounts()}


@router.post("")
async def create_account(req: AccountCreateRequest, admin=Depends(get_admin_user)):
    acc = save_kling_account(
        account_id=req.account_id,
        display_name=req.display_name,
        priority=req.priority,
        max_concurrent=req.max_concurrent,
    )
    return {"success": True, "account": acc}


@router.patch("/{account_id}")
async def update_account(account_id: str, req: AccountUpdateRequest, admin=Depends(get_admin_user)):
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    acc = update_kling_account(account_id, **updates)
    if acc is None:
        raise HTTPException(status_code=404, detail="账号不存在")
    return {"success": True, "account": acc}


@router.delete("/{account_id}")
async def remove_account(account_id: str, admin=Depends(get_admin_user)):
    delete_kling_account(account_id)
    _sessions.pop(account_id, None)
    return {"success": True}


# ============ 扫码登录 ============

@router.post("/{account_id}/qr-login/start")
async def start_qr_login(account_id: str, admin=Depends(get_admin_user)):
    """发起二维码登录，返回二维码图片（base64）"""
    did = _gen_did()
    risk_id = _gen_risk_id()
    try:
        result = await qr_start(did, risk_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"请求可灵失败: {e}")

    if result.get("result") != 1:
        raise HTTPException(status_code=502, detail=f"可灵返回错误: {result}")

    qr_url = result["qrUrl"]
    token = result["qrLoginToken"]
    signature = result["qrLoginSignature"]
    expire_time = result["expireTime"]
    session_cookies = result.get("_session_cookies", {})

    qr_base64 = _url_to_qr_base64(qr_url)

    _sessions[account_id] = {
        "status": "pending",
        "did": did,
        "risk_id": risk_id,
        "token": token,
        "signature": signature,
        "expire_time": expire_time,
        "qr_url": qr_url,
        "qr_base64": qr_base64,
        "session_cookies": session_cookies,
    }

    # 后台开始轮询
    asyncio.create_task(_poll_login(account_id))

    return {
        "success": True,
        "qr_base64": qr_base64,
        "qr_url": qr_url,
        "expire_time": expire_time,
    }


@router.get("/{account_id}/qr-login/status")
async def get_qr_status(account_id: str, admin=Depends(get_admin_user)):
    """轮询二维码状态"""
    session = _sessions.get(account_id)
    if not session:
        # 检查是否已登录
        creds = get_kling_credentials(account_id)
        if creds:
            return {"status": "done"}
        return {"status": "none"}
    return {
        "status": session["status"],
        "qr_base64": session.get("qr_base64", ""),
    }


@router.post("/{account_id}/qr-login/cancel")
async def cancel_qr_login(account_id: str, admin=Depends(get_admin_user)):
    _sessions.pop(account_id, None)
    return {"success": True}


@router.post("/{account_id}/sms/send")
async def send_sms_code(account_id: str, req: KlingSmsCodeRequest, admin=Depends(get_admin_user)):
    """Send Kling SMS verification code and keep the login session cookies in memory."""
    if not get_kling_account(account_id):
        raise HTTPException(status_code=404, detail="账号不存在")

    did = _gen_did()
    risk_id = _gen_risk_id()
    try:
        result = await request_mobile_code(req.phone, did, risk_id, req.country_code)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"发送验证码失败: {e}")

    body = result.get("body") or {}
    if body.get("result") != 1:
        raise HTTPException(status_code=400, detail=f"可灵返回错误: {body}")

    _sessions[account_id] = {
        "status": "sms_pending",
        "did": did,
        "risk_id": risk_id,
        "phone": req.phone,
        "country_code": req.country_code,
        "session_cookies": result.get("cookies", {}),
    }
    return {"success": True, "message": "验证码已发送"}


@router.post("/{account_id}/sms/login")
async def submit_sms_login(account_id: str, req: KlingSmsLoginRequest, admin=Depends(get_admin_user)):
    """Use phone + SMS code to login to Kling and persist cookies."""
    if not get_kling_account(account_id):
        raise HTTPException(status_code=404, detail="账号不存在")

    session = _sessions.get(account_id)
    if not session or session.get("status") not in ("sms_pending", "sms_error"):
        raise HTTPException(status_code=400, detail="请先发送验证码")

    try:
        result = await mobile_code_login(
            phone=req.phone,
            sms_code=req.sms_code,
            did=session["did"],
            risk_id=session["risk_id"],
            session_cookies=session.get("session_cookies"),
            country_code=req.country_code,
        )
    except Exception as e:
        session["status"] = "sms_error"
        session["error"] = str(e)
        raise HTTPException(status_code=502, detail=f"验证码登录失败: {e}")

    body = result.get("body") or {}
    if body.get("result") != 1:
        session["status"] = "sms_error"
        session["error"] = str(body)
        raise HTTPException(status_code=400, detail=f"可灵返回错误: {body}")

    cookie = result["cookie"]
    ok = await check_login(cookie)
    if not ok:
        session["status"] = "sms_error"
        raise HTTPException(status_code=502, detail="验证码登录返回成功，但 cookie 验证失败")

    save_kling_credentials(account_id, cookie, session["did"])
    update_kling_account(
        account_id,
        is_logged_in=True,
        refresh_fail_count=0,
        refresh_paused=False,
        needs_relogin=False,
        next_refresh_retry_at=0,
        monitor_message="",
        offline_alert_sent=False,
    )
    try:
        await init_remove_watermark(cookie)
    except Exception:
        pass

    _sessions.pop(account_id, None)
    return {
        "success": True,
        "message": "验证码登录成功",
        "user_id": body.get("userId"),
        "phone": body.get("phone", req.phone),
        "is_new_user": body.get("isNewUser", False),
    }


@router.post("/{account_id}/check-login")
async def check_account_login(account_id: str, admin=Depends(get_admin_user)):
    """验证已保存 cookie 是否有效，失效时自动更新状态"""
    creds = get_kling_credentials(account_id)
    if not creds:
        update_kling_account(
            account_id,
            is_logged_in=False,
            monitor_message="请扫码重登（账号未登录）",
        )
        return {"is_logged_in": False}
    ok = await check_login(creds["cookie"])
    if ok:
        update_kling_account(
            account_id,
            is_logged_in=True,
            refresh_fail_count=0,
            refresh_paused=False,
            needs_relogin=False,
            next_refresh_retry_at=0,
            monitor_message="",
            offline_alert_sent=False,
        )
    else:
        update_kling_account(
            account_id,
            is_logged_in=False,
            monitor_message="请扫码重登（登录已失效）",
        )
    return {"is_logged_in": ok}


@router.post("/{account_id}/refresh-token")
async def refresh_account_token(account_id: str, admin=Depends(get_admin_user)):
    """手动刷新可灵账号的 token（用 passToken 换新 portal_st）"""
    creds = get_kling_credentials(account_id)
    if not creds:
        raise HTTPException(status_code=404, detail="账号未登录，无法刷新")
    from backend.kling_api import refresh_token
    new_cookie = await refresh_token(creds["cookie"])
    if new_cookie:
        save_kling_credentials(account_id, new_cookie, creds.get("did", ""))
        update_kling_account(
            account_id,
            is_logged_in=True,
            refresh_fail_count=0,
            refresh_paused=False,
            needs_relogin=False,
            next_refresh_retry_at=0,
            monitor_message="",
            offline_alert_sent=False,
        )
        return {"success": True, "message": "Token刷新成功"}
    else:
        update_kling_account(
            account_id,
            is_logged_in=False,
            monitor_message="Token刷新失败，请扫码重登",
        )
        raise HTTPException(status_code=502, detail="Token刷新失败，passToken可能已过期，需重新扫码登录")


@router.post("/{account_id}/remove-watermark")
async def remove_watermark(account_id: str, admin=Depends(get_admin_user)):
    """手动触发去水印设置（关闭品牌水印+片尾水印）"""
    creds = get_kling_credentials(account_id)
    if not creds:
        raise HTTPException(status_code=404, detail="账号未登录")
    try:
        await init_remove_watermark(creds["cookie"])
        return {"success": True, "message": "去水印设置已更新"}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"去水印设置失败: {e}")


@router.get("/{account_id}/points")
async def get_account_points(account_id: str, admin=Depends(get_admin_user)):
    """查询可灵账号积分"""
    creds = get_kling_credentials(account_id)
    if not creds:
        raise HTTPException(status_code=404, detail="账号未登录")
    try:
        points = await get_user_points(creds["cookie"])
        return {"success": True, "points": points}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"查询积分失败: {e}")


# ============ 后台轮询任务 ============

async def _poll_login(account_id: str):
    """后台轮询扫码状态，用户扫码确认后自动保存 cookie"""
    session = _sessions.get(account_id)
    if not session:
        return

    did = session["did"]
    risk_id = session["risk_id"]
    token = session["token"]
    signature = session["signature"]
    expire_ms = session["expire_time"]
    session_cookies = session.get("session_cookies", {})

    import time
    while account_id in _sessions:
        if time.time() * 1000 > expire_ms:
            _sessions[account_id]["status"] = "timeout"
            break

        try:
            data = await qr_scan_result(did, risk_id, token, signature, session_cookies)
        except Exception:
            await asyncio.sleep(3)
            continue

        result_code = data.get("result", 0)

        if result_code == 1:
            # 用户已扫码，立即调 acceptResult（服务端会等用户点确认后返回 cookie）
            _sessions[account_id]["status"] = "scanned"
            try:
                cred = await qr_accept_result(did, risk_id, token, signature, session_cookies)
                save_kling_credentials(account_id, cred["cookie"], did)
                update_kling_account(
                    account_id,
                    is_logged_in=True,
                    refresh_fail_count=0,
                    refresh_paused=False,
                    needs_relogin=False,
                    next_refresh_retry_at=0,
                    monitor_message="",
                    offline_alert_sent=False,
                )
                # 首次登录后自动初始化去水印设置
                try:
                    await init_remove_watermark(cred["cookie"])
                except Exception as wm_err:
                    logger.warning(f"[login] 账号{account_id}去水印初始化失败: {wm_err}")
                _sessions[account_id]["status"] = "done"
            except Exception as e:
                _sessions[account_id]["status"] = "error"
                _sessions[account_id]["error"] = str(e)
            break

        await asyncio.sleep(2)
