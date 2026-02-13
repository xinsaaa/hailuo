"""
多账号管理后台API
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from backend.admin import get_admin_user
from backend.automation_v2 import automation_v2, add_account, toggle_account
from backend.multi_account_manager import AccountConfig

router = APIRouter(prefix="/api/admin/accounts", tags=["多账号管理"])


class AccountCreateRequest(BaseModel):
    account_id: str
    phone_number: str
    display_name: str
    priority: int = 5
    max_concurrent: int = 3


class AccountUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    priority: Optional[int] = None
    max_concurrent: Optional[int] = None
    is_active: Optional[bool] = None


@router.get("/list")
def list_accounts(admin=Depends(get_admin_user)):
    """获取所有账号列表"""
    accounts = []
    for account_id, account in automation_v2.manager.accounts.items():
        status = automation_v2.manager.get_account_status().get(account_id, {})
        accounts.append({
            "account_id": account_id,
            "phone_number": account.phone_number,
            "display_name": account.display_name,
            "priority": account.priority,
            "is_active": account.is_active,
            "max_concurrent": account.max_concurrent,
            "current_tasks": account.current_tasks,
            "is_logged_in": status.get("is_logged_in", False),
            "utilization": status.get("utilization", 0)
        })
    
    return {
        "accounts": accounts,
        "total": len(accounts),
        "active": sum(1 for acc in accounts if acc["is_active"]),
        "logged_in": sum(1 for acc in accounts if acc["is_logged_in"])
    }


@router.post("/create")
async def create_account(data: AccountCreateRequest, admin=Depends(get_admin_user)):
    """创建新账号"""
    # 检查账号ID是否已存在
    if data.account_id in automation_v2.manager.accounts:
        raise HTTPException(status_code=400, detail="账号ID已存在")
    
    # 创建账号
    await add_account({
        "account_id": data.account_id,
        "phone_number": data.phone_number,
        "display_name": data.display_name,
        "priority": data.priority,
        "max_concurrent": data.max_concurrent,
        "is_active": True,
        "current_tasks": 0
    })
    
    return {"message": "账号创建成功", "account_id": data.account_id}


@router.put("/{account_id}")
async def update_account(
    account_id: str,
    data: AccountUpdateRequest,
    admin=Depends(get_admin_user)
):
    """更新账号信息"""
    if account_id not in automation_v2.manager.accounts:
        raise HTTPException(status_code=404, detail="账号不存在")
    
    account = automation_v2.manager.accounts[account_id]
    
    # 更新字段
    if data.display_name is not None:
        account.display_name = data.display_name
    if data.priority is not None:
        account.priority = data.priority
    if data.max_concurrent is not None:
        account.max_concurrent = data.max_concurrent
    if data.is_active is not None:
        await toggle_account(account_id, data.is_active)
    
    return {"message": "账号更新成功"}


@router.post("/{account_id}/login")
async def login_account(account_id: str, admin=Depends(get_admin_user)):
    """尝试使用Cookie登录账号"""
    try:
        result = await automation_v2.manager.login_account(account_id)
        if result:
            return {"message": f"账号 {account_id} 登录成功", "success": True}
        else:
            # 登录失败，可能需要验证码
            return {"message": f"账号 {account_id} 需要验证码登录", "success": False, "require_code": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"登录失败: {str(e)}")


@router.post("/{account_id}/send-code")
async def send_verification_code(account_id: str, admin=Depends(get_admin_user)):
    """发送验证码到账号手机"""
    try:
        result = await automation_v2.manager.send_verification_code(account_id)
        if result:
            return {"message": "验证码已发送", "success": True}
        else:
            raise HTTPException(status_code=400, detail="发送验证码失败")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"发送验证码失败: {str(e)}")


class VerificationCodeRequest(BaseModel):
    verification_code: str

@router.post("/{account_id}/verify-code")
async def verify_and_login(account_id: str, data: VerificationCodeRequest, admin=Depends(get_admin_user)):
    """使用验证码完成登录"""
    try:
        result = await automation_v2.manager.verify_code_and_login(account_id, data.verification_code)
        if result:
            return {"message": f"账号 {account_id} 登录成功", "success": True}
        else:
            raise HTTPException(status_code=400, detail="验证码错误或登录失败")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"验证码登录失败: {str(e)}")


@router.post("/{account_id}/logout")
async def logout_account(account_id: str, admin=Depends(get_admin_user)):
    """手动登出账号"""
    if account_id not in automation_v2.manager.accounts:
        raise HTTPException(status_code=404, detail="账号不存在")
    
    await automation_v2.manager.close_account(account_id)
    return {"message": "账号已登出", "account_id": account_id}


@router.delete("/{account_id}")
async def delete_account(account_id: str, admin=Depends(get_admin_user)):
    """删除账号"""
    if account_id not in automation_v2.manager.accounts:
        raise HTTPException(status_code=404, detail="账号不存在")
    
    # 先关闭账号上下文
    await automation_v2.manager.close_account(account_id)
    
    # 从配置中删除
    del automation_v2.manager.accounts[account_id]
    
    # 保存配置
    accounts_list = list(automation_v2.manager.accounts.values())
    automation_v2.manager.save_accounts_config(accounts_list)
    
    return {"message": "账号删除成功", "account_id": account_id}


@router.get("/status")
def get_system_status(admin=Depends(get_admin_user)):
    """获取多账号系统状态"""
    try:
        status = automation_v2.get_system_status()
        # 添加额外的调试信息
        status["debug_info"] = {
            "browser_initialized": automation_v2.manager.browser is not None,
            "contexts_count": len(automation_v2.manager.contexts),
            "pages_count": len(automation_v2.manager.pages),
            "last_error": getattr(automation_v2, 'last_error', None)
        }
        return status
    except Exception as e:
        return {
            "is_running": False,
            "error": str(e),
            "debug_info": {
                "exception_type": type(e).__name__
            }
        }


@router.post("/start")
async def start_multi_account_system(admin=Depends(get_admin_user)):
    """启动多账号系统"""
    try:
        await automation_v2.start()
        return {"message": "多账号系统启动成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动失败: {str(e)}")


@router.post("/stop")
async def stop_multi_account_system(admin=Depends(get_admin_user)):
    """停止多账号系统"""
    try:
        await automation_v2.stop()
        return {"message": "多账号系统停止成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"停止失败: {str(e)}")


@router.get("/performance")
def get_performance_metrics(admin=Depends(get_admin_user)):
    """获取性能指标"""
    status = automation_v2.get_system_status()
    accounts = status["accounts"]
    
    # 计算性能指标
    total_capacity = sum(acc.max_concurrent for acc in automation_v2.manager.accounts.values() if acc.is_active)
    current_load = sum(acc.current_tasks for acc in automation_v2.manager.accounts.values())
    
    performance = {
        "total_capacity": total_capacity,
        "current_load": current_load,
        "utilization_rate": current_load / total_capacity if total_capacity > 0 else 0,
        "active_accounts": status["active_accounts"],
        "logged_in_accounts": sum(1 for acc_status in accounts.values() if acc_status["is_logged_in"]),
        "avg_utilization": sum(acc_status["utilization"] for acc_status in accounts.values()) / len(accounts) if accounts else 0
    }
    
    return performance


# 导出路由
def include_multi_account_routes(app):
    """将多账号管理路由添加到主应用"""
    app.include_router(router)
