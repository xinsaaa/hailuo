"""
即梦订单 API
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from typing import Optional
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.database import get_db, SessionLocal
from backend.models import User, JimengOrder
from backend.auth import get_current_user
from backend.jimeng_automation import submit_video_task, scan_video_status

router = APIRouter(prefix="/api/jimeng", tags=["jimeng"])


class JimengOrderResponse(BaseModel):
    id: int
    prompt: str
    model_name: str
    status: str
    progress: int
    video_url: Optional[str] = None
    created_at: str
    
    class Config:
        from_attributes = True


@router.get("/models")
async def get_jimeng_models():
    """获取即梦可用模型"""
    return {
        "models": [
            {
                "id": "seedance_fast",
                "name": "Seedance 2.0 Fast",
                "display_name": "Seedance 2.0 Fast",
                "price": 0.99,
                "description": "快速生成，性价比高",
                "is_default": True,
            },
            {
                "id": "seedance",
                "name": "Seedance 2.0",
                "display_name": "Seedance 2.0",
                "price": 1.49,
                "description": "更高质量，细节更丰富",
                "is_default": False,
            },
        ]
    }


@router.get("/orders")
async def get_jimeng_orders(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取用户的即梦订单列表"""
    orders = db.query(JimengOrder).filter(
        JimengOrder.user_id == current_user.id
    ).order_by(JimengOrder.created_at.desc()).all()
    
    return [
        {
            "id": order.id,
            "prompt": order.prompt,
            "model_name": order.model_name,
            "status": order.status,
            "progress": order.progress or 0,
            "video_url": order.video_url,
            "created_at": order.created_at.isoformat() if order.created_at else None,
        }
        for order in orders
    ]


@router.post("/orders")
async def create_jimeng_order(
    prompt: str = Form(...),
    model: str = Form("Seedance 2.0 Fast"),
    first_frame: Optional[UploadFile] = File(None),
    last_frame: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建即梦视频生成订单"""
    
    # 检查余额
    model_prices = {
        "Seedance 2.0 Fast": 0.99,
        "Seedance 2.0": 1.49,
    }
    price = model_prices.get(model, 0.99)
    
    if current_user.balance < price:
        raise HTTPException(status_code=400, detail="余额不足")
    
    # 扣除余额
    current_user.balance -= price
    
    # 创建订单
    order = JimengOrder(
        user_id=current_user.id,
        prompt=prompt,
        model_name=model,
        status="pending",
        progress=0,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    
    # TODO: 处理图片上传和启动后台任务
    # 这里需要异步启动视频生成任务
    
    return {
        "success": True,
        "order_id": order.id,
        "message": "订单创建成功",
    }
