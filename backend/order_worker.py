"""
订单处理工作器 - 纯HTTP API模式
使用 hailuo_api.HailuoApiClient 提交和轮询任务
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Optional

from sqlmodel import Session, select

from backend.models import VideoOrder, engine
from backend.account_store import account_store
from backend.hailuo_api import HailuoApiClient

logger = logging.getLogger(__name__)

# ---- model_name -> API modelID 映射 ----
MODEL_ID_MAP: dict = {
    "Hailuo 2.3":          "23217",
    "Hailuo 2.3-Fast":     "23218",
    "Hailuo 2.0":          "23210",
    "Hailuo 1.0":          "23000",
    "Hailuo 1.0 Director": "23010",
    "Hailuo 1.0 Live":     "23011",
    # 3.x 系列 ID 待确认后补充
    "Hailuo 3.1":          "23217",
    "Hailuo 3.1-Pro":      "23217",
    "Beta 3.1":            "23217",
    "Beta 3.1 Fast":       "23218",
}

POLL_INTERVAL = 5       # 秒
MAX_POLL_SECONDS = 600  # 10 分钟超时


def _get_api_model_id(model_name: Optional[str]) -> str:
    if not model_name:
        return "23204"
    return MODEL_ID_MAP.get(model_name, "23204")


def _pick_account() -> Optional[tuple]:
    """选出优先级最高且有余量的账号，返回 (account_id, client)"""
    candidates = [
        (acc_id, acc)
        for acc_id, acc in account_store.accounts.items()
        if acc.is_active and acc.current_tasks < acc.max_concurrent
        and account_store.has_credentials(acc_id)
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda x: (-x[1].priority, x[1].current_tasks))
    acc_id, _ = candidates[0]
    creds = account_store.get_credentials(acc_id)
    client = HailuoApiClient(
        cookie=creds["cookie"],
        uuid=creds["uuid"],
        device_id=creds["device_id"],
    )
    return acc_id, client


async def submit_order(order_id: int):
    """选账号、调API提交生成任务，更新订单状态为 generating"""
    with Session(engine) as session:
        order = session.get(VideoOrder, order_id)
        if not order:
            logger.error(f"[worker] 订单#{order_id}不存在")
            return
        if order.status != "pending":
            logger.warning(f"[worker] 订单#{order_id}状态={order.status}，跳过提交")
            return

    result = _pick_account()
    if not result:
        logger.error(f"[worker] 无可用账号，订单#{order_id}等待重试")
        await asyncio.sleep(5)
        result = _pick_account()
        if not result:
            _fail_order(order_id, "无可用账号")
            return

    acc_id, client = result
    account_store.inc_tasks(acc_id)

    try:
        with Session(engine) as session:
            order = session.get(VideoOrder, order_id)

            model_id = _get_api_model_id(order.model_name)
            duration_int = int((order.duration or "6s").replace("s", ""))
            resolution_str = (order.resolution or "768p").replace("p", "")
            quantity = order.quantity or 1

            file_list = []
            if order.first_frame_image:
                try:
                    r = await client.upload_image(order.first_frame_image)
                    if r:
                        file_list.append({"id": r["id"], "url": r["url"], "type": r["type"], "frameType": 0})
                except Exception as e:
                    logger.warning(f"[worker] 上传首帧失败: {e}")
            if order.last_frame_image:
                try:
                    r = await client.upload_image(order.last_frame_image)
                    if r:
                        file_list.append({"id": r["id"], "url": r["url"], "type": r["type"], "frameType": 1})
                except Exception as e:
                    logger.warning(f"[worker] 上传尾帧失败: {e}")

            resp = await client.generate_video(
                desc=order.prompt,
                model_id=model_id,
                duration=duration_int,
                resolution=resolution_str,
                file_list=file_list,
                quantity=quantity,
            )

        status_code = resp.get("statusInfo", {}).get("code", -1)
        if status_code != 0:
            msg = resp.get("statusInfo", {}).get("message", "未知错误")
            logger.error(f"[worker] 订单#{order_id}提交失败: {msg}")
            _fail_order(order_id, msg)
            return

        tasks = resp.get("data", {}).get("tasks", [])
        task_ids = [t["taskID"] for t in tasks if "taskID" in t]
        if not task_ids:
            _fail_order(order_id, "API未返回taskID")
            return

        with Session(engine) as session:
            order = session.get(VideoOrder, order_id)
            order.status = "generating"
            order.task_id = json.dumps(task_ids)
            order.updated_at = datetime.utcnow()
            session.add(order)
            session.commit()

        logger.info(f"[worker] 订单#{order_id}已提交，task_ids={task_ids}，账号={acc_id}")
        asyncio.create_task(poll_order_status(order_id, acc_id=acc_id))

    except Exception as e:
        logger.error(f"[worker] 订单#{order_id}提交异常: {e}", exc_info=True)
        _fail_order(order_id, str(e))
    finally:
        account_store.dec_tasks(acc_id)


async def poll_order_status(order_id: int, acc_id: Optional[str] = None):
    """轮询任务状态直到完成或超时"""
    elapsed = 0

    while elapsed < MAX_POLL_SECONDS:
        await asyncio.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL

        with Session(engine) as session:
            order = session.get(VideoOrder, order_id)
            if not order:
                return
            if order.status in ("completed", "failed"):
                return
            task_ids_raw = order.task_id

        if not task_ids_raw:
            logger.warning(f"[worker] 订单#{order_id}没有task_id，停止轮询")
            return

        try:
            task_ids = json.loads(task_ids_raw)
        except Exception:
            task_ids = [task_ids_raw]

        client = _make_client(acc_id)
        if not client:
            logger.warning(f"[worker] 轮询订单#{order_id}找不到可用客户端")
            continue

        try:
            resp = await client.get_tasks_by_ids(task_ids)
        except Exception as e:
            logger.warning(f"[worker] 查询任务状态失败: {e}")
            continue

        tasks = resp.get("data", {}).get("tasks", [])
        if not tasks:
            continue

        _update_order_from_tasks(order_id, tasks)

        with Session(engine) as session:
            order = session.get(VideoOrder, order_id)
            if order and order.status in ("completed", "failed"):
                return

    logger.error(f"[worker] 订单#{order_id}轮询超时")
    _fail_order(order_id, "生成超时")


def _make_client(acc_id: Optional[str]) -> Optional[HailuoApiClient]:
    """从账号store构建客户端，acc_id为None时自动选择"""
    if acc_id and account_store.has_credentials(acc_id):
        creds = account_store.get_credentials(acc_id)
    else:
        creds = None
        for aid, acc in account_store.accounts.items():
            if acc.is_active and account_store.has_credentials(aid):
                creds = account_store.get_credentials(aid)
                break
        if not creds:
            return None
    return HailuoApiClient(
        cookie=creds["cookie"],
        uuid=creds["uuid"],
        device_id=creds["device_id"],
    )


def _update_order_from_tasks(order_id: int, tasks: list):
    """根据API返回的tasks列表更新订单状态
    API task status: 50=生成中, 60=完成, 70/80=失败
    """
    all_done = True
    any_failed = False
    video_urls = []

    for task in tasks:
        task_status = task.get("status", 0)
        video = task.get("video") or {}
        url = video.get("url") or video.get("videoURL") or ""

        if task_status == 60:
            if url:
                video_urls.append(url)
        elif task_status in (70, 80, -1):
            any_failed = True
        else:
            all_done = False

    with Session(engine) as session:
        order = session.get(VideoOrder, order_id)
        if not order or order.status in ("completed", "failed"):
            return

        if not all_done and not any_failed:
            done_count = len(video_urls)
            total = order.quantity or 1
            order.progress = int(done_count / total * 80)
            order.updated_at = datetime.utcnow()
        elif video_urls:
            order.status = "completed"
            order.progress = 100
            order.video_url = video_urls[0]
            order.video_urls = json.dumps(video_urls)
            order.updated_at = datetime.utcnow()
            logger.info(f"[worker] 订单#{order_id}完成，视频数={len(video_urls)}")
        elif any_failed and all_done:
            _fail_order_in_session(session, order)

        session.add(order)
        session.commit()


def _fail_order(order_id: int, reason: str = ""):
    with Session(engine) as session:
        order = session.get(VideoOrder, order_id)
        if order:
            _fail_order_in_session(session, order, reason)
            session.commit()


def _fail_order_in_session(session, order, reason: str = ""):
    order.status = "failed"
    order.progress = 0
    order.updated_at = datetime.utcnow()
    if reason:
        logger.error(f"[worker] 订单#{order.id}失败: {reason}")
    session.add(order)


async def poll_all_pending_orders():
    """扫描所有 generating/processing 状态的订单并触发轮询"""
    with Session(engine) as session:
        orders = session.exec(
            select(VideoOrder).where(
                VideoOrder.status.in_(["generating", "processing"])
            )
        ).all()
        order_ids = [o.id for o in orders]

    logger.info(f"[worker] 全量扫描：找到 {len(order_ids)} 个进行中订单")
    for oid in order_ids:
        asyncio.create_task(poll_order_status(oid))
