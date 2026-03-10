"""
即梦订单 API
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.security import OAuth2PasswordBearer
from typing import Optional, List
from sqlmodel import Session, select
from pydantic import BaseModel
from jose import jwt, JWTError
import json

from backend.models import User, JimengOrder, AIModel, engine
from backend.auth import SECRET_KEY, ALGORITHM
from backend.jimeng_automation import submit_video_task, scan_video_status

router = APIRouter(prefix="/api/jimeng", tags=["jimeng"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def get_session():
    with Session(engine) as session:
        yield session


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


class JimengModelResponse(BaseModel):
    id: str
    name: str
    display_name: str
    description: str
    price: float
    badge: Optional[str] = None
    features: List[str] = []
    is_default: bool = False
    is_enabled: bool = True

    class Config:
        from_attributes = True


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
async def get_jimeng_models(
    session: Session = Depends(get_session),
):
    """获取即梦可用模型列表"""
    models = session.exec(
        select(AIModel).where(
            AIModel.platform == "jimeng",
            AIModel.is_enabled == True
        )
    ).all()

    # 如果数据库中没有即梦模型，返回默认列表
    if not models:
        return {
            "models": [
                {
                    "id": "seedance_fast",
                    "name": "Seedance 2.0 Fast",
                    "display_name": "Seedance 2.0 Fast",
                    "description": "快速生成，性价比高",
                    "price": 0.99,
                    "badge": None,
                    "features": ["快速生成", "高性价比"],
                    "is_default": True,
                    "is_enabled": True,
                },
                {
                    "id": "seedance",
                    "name": "Seedance 2.0",
                    "display_name": "Seedance 2.0",
                    "description": "更高质量，细节更丰富",
                    "price": 1.49,
                    "badge": None,
                    "features": ["高质量", "细节丰富"],
                    "is_default": False,
                    "is_enabled": True,
                },
            ]
        }

    return {
        "models": [
            {
                "id": m.model_id,
                "name": m.name,
                "display_name": m.display_name,
                "description": m.description,
                "price": m.price,
                "badge": m.badge,
                "features": json.loads(m.features) if m.features else [],
                "is_default": m.is_default,
                "is_enabled": m.is_enabled,
            }
            for m in models
        ]
    }


@router.get("/status")
async def get_jimeng_status(
    session: Session = Depends(get_session),
):
    """获取即梦服务状态（是否有启用的模型）"""
    models = session.exec(
        select(AIModel).where(
            AIModel.platform == "jimeng",
            AIModel.is_enabled == True
        )
    ).all()
    enabled_count = len(models)

    return {
        "enabled": enabled_count > 0,
        "model_count": enabled_count,
    }


@router.get("/orders")
async def get_jimeng_orders(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """获取用户的即梦订单列表"""
    orders = session.exec(
        select(JimengOrder).where(
            JimengOrder.user_id == current_user.id
        ).order_by(JimengOrder.created_at.desc())
    ).all()

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
    session: Session = Depends(get_session),
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
    session.add(order)
    session.commit()
    session.refresh(order)

    # TODO: 处理图片上传和启动后台任务
    # 这里需要异步启动视频生成任务

    return {
        "success": True,
        "order_id": order.id,
        "message": "订单创建成功",
    }
