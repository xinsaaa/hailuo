"""
GPT Image 2 文生图 API
调用 NOVART 平台的图片生成接口
"""
import asyncio
import base64
import json
import os
import time
import threading
import httpx
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.security import OAuth2PasswordBearer
from typing import Optional, List
from sqlmodel import Session, select
from pydantic import BaseModel
from jose import jwt, JWTError
from datetime import datetime

from backend.models import User, GptimageOrder, AIModel, Transaction, engine
from backend.auth import SECRET_KEY, ALGORITHM
from backend.logger import app_logger

router = APIRouter(prefix="/api/gptimage", tags=["gptimage"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# ============ NOVART 配置 ============

# 质量到分辨率映射
QUALITY_RESOLUTION_MAP = {
    "standard": "1k",
    "hd": "2k",
    "ultra": "4k",
}


def _get_novart_config() -> tuple:
    """从数据库读取 NOVART 配置，回退到环境变量"""
    from backend.models import SystemConfig
    api_key = os.getenv("NOVART_API_KEY", "")
    base_url = os.getenv("NOVART_BASE_URL", "https://www.novartspace.art")
    try:
        with Session(engine) as session:
            key_cfg = session.exec(
                select(SystemConfig).where(SystemConfig.key == "novart_api_key")
            ).first()
            if key_cfg:
                import json
                val = json.loads(key_cfg.value)
                if val:
                    api_key = val
            url_cfg = session.exec(
                select(SystemConfig).where(SystemConfig.key == "novart_base_url")
            ).first()
            if url_cfg:
                val = json.loads(url_cfg.value)
                if val:
                    base_url = val
    except Exception:
        pass
    return api_key, base_url


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


# ============ 模型列表 ============
@router.get("/models")
async def get_gptimage_models(session: Session = Depends(get_session)):
    """获取 GPT Image 2 可用模型列表"""
    all_models = session.exec(
        select(AIModel).where(AIModel.platform == "gptimage")
    ).all()

    if not all_models:
        return {
            "models": [
                {
                    "id": "gptimage_pro_flex",
                    "name": "nova-image-pro-flex",
                    "display_name": "GPT Image 2",
                    "description": "OpenAI 旗舰文生图，支持文字渲染，精准控制",
                    "price": 0.50,
                    "badge": "NEW",
                    "features": ["文字渲染", "精准控制", "2K画质"],
                    "is_default": True,
                    "is_enabled": True,
                },
                {
                    "id": "gptimage_pro",
                    "name": "nova-image-pro",
                    "display_name": "GPT Image 2 Pro",
                    "description": "更多宽高比支持，更丰富细节",
                    "price": 0.80,
                    "badge": "PRO",
                    "features": ["11种宽高比", "4K画质", "极致细节"],
                    "is_default": False,
                    "is_enabled": True,
                },
            ]
        }

    models = [m for m in all_models if m.is_enabled]
    if not models:
        return {"models": []}

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


# ============ 订单列表 ============
@router.get("/orders")
async def get_gptimage_orders(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """获取用户的 GPT Image 订单列表"""
    orders = session.exec(
        select(GptimageOrder)
        .where(GptimageOrder.user_id == current_user.id)
        .order_by(GptimageOrder.created_at.desc())
        .limit(50)
    ).all()

    return [
        {
            "id": o.id,
            "prompt": o.prompt,
            "model_name": o.model_name,
            "ratio": o.ratio,
            "quality": o.quality,
            "status": o.status,
            "progress": o.progress,
            "image_url": o.image_url,
            "cost": o.cost,
            "error_message": o.error_message,
            "created_at": o.created_at.isoformat() if o.created_at else None,
            "completed_at": o.completed_at.isoformat() if o.completed_at else None,
        }
        for o in orders
    ]


# ============ 创建订单 ============
@router.post("/orders")
async def create_gptimage_order(
    prompt: str = Form(...),
    model: str = Form("nova-image-pro-flex"),
    ratio: str = Form("1:1"),
    quality: str = Form("hd"),
    ref_image: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """创建 GPT Image 2 生成订单"""
    if not prompt.strip():
        raise HTTPException(status_code=400, detail="请输入图片描述")

    novart_api_key, _ = _get_novart_config()
    if not novart_api_key:
        raise HTTPException(status_code=503, detail="GPT Image 服务未配置 API Key，请联系管理员")

    # 查找模型获取价格
    db_model = session.exec(
        select(AIModel).where(AIModel.name == model, AIModel.platform == "gptimage")
    ).first()
    price = db_model.price if db_model else 0.50

    # 余额检查
    if current_user.balance < price:
        raise HTTPException(status_code=400, detail=f"余额不足，需要 ¥{price}，当前余额 ¥{current_user.balance:.2f}")

    # 处理参考图
    ref_image_path = None
    if ref_image and ref_image.filename:
        import tempfile
        import uuid as _uuid
        ext = ref_image.filename.split(".")[-1] if "." in ref_image.filename else "jpg"
        tmp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads", "gptimage")
        os.makedirs(tmp_dir, exist_ok=True)
        ref_image_path = os.path.join(tmp_dir, f"{_uuid.uuid4().hex[:12]}.{ext}")
        content = await ref_image.read()
        with open(ref_image_path, "wb") as f:
            f.write(content)

    # 扣费
    current_user.balance -= price
    session.add(current_user)

    # 记录交易
    transaction = Transaction(
        user_id=current_user.id,
        amount=-price,
        bonus=0,
        type="expense",
    )
    session.add(transaction)

    # 创建订单
    order = GptimageOrder(
        user_id=current_user.id,
        prompt=prompt.strip(),
        model_name=model,
        ratio=ratio,
        quality=quality,
        status="pending",
        cost=price,
        ref_image_path=ref_image_path,
    )
    session.add(order)
    session.commit()
    session.refresh(order)

    app_logger.info(
        f"[GPTImage] 新订单 #{order.id} by user {current_user.username}, model={model}, ratio={ratio}, quality={quality}"
    )

    # 后台异步执行生成任务
    threading.Thread(
        target=_run_generation_task,
        args=(order.id,),
        daemon=True,
    ).start()

    return {"message": "订单创建成功", "order_id": order.id}


# ============ NOVART API 调用 ============
def _run_generation_task(order_id: int):
    """在后台线程中执行生图任务"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_generate_image(order_id))
    except Exception as e:
        app_logger.error(f"[GPTImage] 任务线程异常 order#{order_id}: {e}")
        _update_order_status(order_id, "failed", error_message=str(e))
    finally:
        loop.close()


async def _generate_image(order_id: int):
    """调用 NOVART API 生成图片"""
    with Session(engine) as session:
        order = session.get(GptimageOrder, order_id)
        if not order:
            return

        order.status = "processing"
        order.progress = 10
        session.add(order)
        session.commit()

    app_logger.info(f"[GPTImage] 开始生成 order#{order_id}, model={order.model_name}")

    try:
        # 构建请求
        resolution = QUALITY_RESOLUTION_MAP.get(order.quality, "2k")

        parts = [{"text": order.prompt}]

        # 如果有参考图，附加 inlineData
        if order.ref_image_path and os.path.exists(order.ref_image_path):
            with open(order.ref_image_path, "rb") as f:
                img_bytes = f.read()
            img_b64 = base64.b64encode(img_bytes).decode("utf-8")
            ext = order.ref_image_path.rsplit(".", 1)[-1].lower()
            mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp", "gif": "image/gif"}
            mime_type = mime_map.get(ext, "image/png")
            parts.append({
                "inlineData": {
                    "mimeType": mime_type,
                    "data": img_b64,
                }
            })

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": parts,
                }
            ],
            "generationConfig": {
                "responseModalities": ["TEXT", "IMAGE"],
                "imageConfig": {
                    "aspectRatio": order.ratio,
                    "novartResolution": resolution,
                },
                "novart": {
                    "includeResultUrls": True,
                },
            },
        }

        novart_api_key, novart_base_url = _get_novart_config()
        if not novart_api_key:
            _update_order_status(order_id, "failed", error_message="API Key 未配置")
            _refund_order(order_id)
            return

        url = f"{novart_base_url}/v1beta/models/{order.model_name}:generateContent"
        headers = {
            "x-goog-api-key": novart_api_key,
            "Content-Type": "application/json",
        }

        with Session(engine) as session:
            order = session.get(GptimageOrder, order_id)
            order.status = "generating"
            order.progress = 30
            session.add(order)
            session.commit()

        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post(url, json=payload, headers=headers)

        if resp.status_code != 200:
            error_text = resp.text[:500]
            app_logger.error(f"[GPTImage] NOVART API 错误 {resp.status_code}: {error_text}")
            _update_order_status(order_id, "failed", error_message=f"API 错误 {resp.status_code}: {error_text[:200]}")
            _refund_order(order_id)
            return

        data = resp.json()

        # 解析响应 - 优先用 download_url，否则用 base64
        image_url = None
        novart_info = data.get("novart", {})
        results = novart_info.get("results", [])
        if results and results[0].get("download_url"):
            image_url = results[0]["download_url"]

        if not image_url:
            # 从 candidates 中提取 base64 图片，保存到本地
            candidates = data.get("candidates", [])
            if candidates:
                content_parts = candidates[0].get("content", {}).get("parts", [])
                for part in content_parts:
                    inline_data = part.get("inlineData")
                    if inline_data and inline_data.get("data"):
                        # 保存 base64 到本地文件并生成 URL
                        image_url = _save_b64_image(inline_data["data"], inline_data.get("mimeType", "image/png"), order_id)
                        break

        if not image_url:
            app_logger.error(f"[GPTImage] 响应中未找到图片 order#{order_id}")
            _update_order_status(order_id, "failed", error_message="API 响应中未找到生成的图片")
            _refund_order(order_id)
            return

        # 更新订单为完成
        with Session(engine) as session:
            order = session.get(GptimageOrder, order_id)
            order.status = "completed"
            order.progress = 100
            order.image_url = image_url
            order.task_id = str(novart_info.get("task_id", ""))
            order.completed_at = datetime.utcnow()
            session.add(order)
            session.commit()

        app_logger.info(f"[GPTImage] 生成完成 order#{order_id}, url={image_url[:80]}...")

    except httpx.TimeoutException:
        app_logger.error(f"[GPTImage] 请求超时 order#{order_id}")
        _update_order_status(order_id, "failed", error_message="生成请求超时，请重试")
        _refund_order(order_id)
    except Exception as e:
        app_logger.error(f"[GPTImage] 生成失败 order#{order_id}: {e}", exc_info=True)
        _update_order_status(order_id, "failed", error_message=str(e)[:200])
        _refund_order(order_id)


def _save_b64_image(b64_data: str, mime_type: str, order_id: int) -> str:
    """将 base64 图片保存到本地，返回访问路径"""
    ext_map = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp", "image/gif": "gif"}
    ext = ext_map.get(mime_type, "png")

    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads", "gptimage", "results")
    os.makedirs(output_dir, exist_ok=True)

    filename = f"gptimg_{order_id}_{int(time.time())}.{ext}"
    filepath = os.path.join(output_dir, filename)

    img_bytes = base64.b64decode(b64_data)
    with open(filepath, "wb") as f:
        f.write(img_bytes)

    # 返回可访问的 URL 路径
    return f"/api/gptimage/files/{filename}"


@router.get("/files/{filename}")
async def serve_gptimage_file(filename: str):
    """提供生成的图片文件"""
    from starlette.responses import FileResponse as StarletteFileResponse

    filepath = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "uploads", "gptimage", "results", filename
    )
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="文件不存在")

    # 根据扩展名设置 content-type
    ext = filename.rsplit(".", 1)[-1].lower()
    media_map = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp", "gif": "image/gif"}
    media_type = media_map.get(ext, "application/octet-stream")

    return StarletteFileResponse(filepath, media_type=media_type)


def _update_order_status(order_id: int, status: str, error_message: str = None):
    """更新订单状态"""
    with Session(engine) as session:
        order = session.get(GptimageOrder, order_id)
        if order:
            order.status = status
            if error_message:
                order.error_message = error_message
            if status == "completed":
                order.progress = 100
                order.completed_at = datetime.utcnow()
            elif status == "failed":
                order.progress = 0
            session.add(order)
            session.commit()


def _refund_order(order_id: int):
    """订单失败时退款"""
    with Session(engine) as session:
        order = session.get(GptimageOrder, order_id)
        if not order or order.cost <= 0:
            return
        user = session.get(User, order.user_id)
        if user:
            user.balance += order.cost
            session.add(user)
            # 记录退款交易
            transaction = Transaction(
                user_id=user.id,
                amount=order.cost,
                bonus=0,
                type="refund",
            )
            session.add(transaction)
            session.commit()
            app_logger.info(f"[GPTImage] 退款 ¥{order.cost} -> user#{user.id} for order#{order_id}")
