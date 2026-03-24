"""
订单处理工作器 - 纯HTTP API模式
使用 hailuo_api.HailuoApiClient 提交和轮询任务
"""
import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Optional

import httpx
from sqlmodel import Session, select

from backend.models import VideoOrder, User, Transaction, engine
from backend.account_store import account_store
from backend.hailuo_api import HailuoApiClient
from backend import kling_api

logger = logging.getLogger(__name__)

# ---- model_name -> API modelID 映射 ----
# 可灵模型名 → (kling_version, mode)
KLING_MODEL_MAP: dict = {
    "Kling 3.0":       ("3.0", "std"),
    "Kling 2.6":       ("2.6", "std"),
    "Kling 2.5 Turbo": ("2.5", "pro"),
}


def _is_kling_model(model_name: Optional[str]) -> bool:
    return bool(model_name and model_name in KLING_MODEL_MAP)


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
        model_name = order.model_name

    if _is_kling_model(model_name):
        await _submit_kling_order(order_id)
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
    # 退款
    if order.cost and order.cost > 0:
        user = session.get(User, order.user_id)
        if user:
            user.balance += order.cost
            session.add(user)
            refund_tx = Transaction(
                user_id=order.user_id,
                amount=order.cost,
                bonus=0,
                type="refund"
            )
            session.add(refund_tx)
            logger.info(f"[worker] 订单#{order.id}退款 ¥{order.cost} 给用户#{order.user_id}")
    session.add(order)


async def poll_all_pending_orders():
    """扫描所有 generating/processing 状态的订单并触发轮询"""
    with Session(engine) as session:
        orders = session.exec(
            select(VideoOrder).where(
                VideoOrder.status.in_(["generating", "processing"])
            )
        ).all()
        order_data = [(o.id, o.model_name) for o in orders]

    logger.info(f"[worker] 全量扫描：找到 {len(order_data)} 个进行中订单")
    for oid, mname in order_data:
        if _is_kling_model(mname):
            asyncio.create_task(poll_kling_order(oid))
        else:
            asyncio.create_task(poll_order_status(oid))


# ============ 可灵分支 ============

def _pick_kling_account() -> Optional[tuple]:
    """从 kling_accounts.json 中选出可用账号，返回 (account_id, cookie)"""
    accounts = kling_api.list_kling_accounts()
    active = [
        a for a in accounts
        if a.get("is_active") and a.get("is_logged_in")
    ]
    if not active:
        return None
    active.sort(key=lambda x: -x.get("priority", 5))
    acc = active[0]
    acc_id = acc["account_id"]
    creds = kling_api.get_kling_credentials(acc_id)
    if not creds:
        return None
    return acc_id, creds["cookie"]


async def _submit_kling_order(order_id: int):
    """可灵订单提交：预检积分 → 上传图片（如有）→ 提交任务 → 更新状态为 generating"""
    result = _pick_kling_account()
    if not result:
        _fail_order(order_id, "无可用可灵账号")
        return

    acc_id, cookie = result

    try:
        # 预检查可灵账号积分
        try:
            pts = await kling_api.get_user_points(cookie)
            total_pts = pts.get("total", 0)
            if total_pts < 100:
                _fail_order(order_id, f"可灵账号积分不足（剩余{total_pts}），需要至少100积分，请联系管理员充值")
                return
        except Exception as e:
            logger.warning(f"[worker] 可灵积分查询失败: {e}，继续尝试提交")

        with Session(engine) as session:
            order = session.get(VideoOrder, order_id)
            if not order:
                return
            version, mode = KLING_MODEL_MAP[order.model_name]
            duration_int = int((order.duration or "5s").replace("s", ""))
            prompt = order.prompt or ""
            first_frame = order.first_frame_image
            last_frame = order.last_frame_image

        image_url = ""
        if first_frame:
            try:
                image_url = await kling_api.upload_image(cookie, first_frame)
            except Exception as e:
                logger.warning(f"[worker] 可灵上传首帧失败: {e}")

        tail_image_url = ""
        if last_frame:
            try:
                tail_image_url = await kling_api.upload_image(cookie, last_frame)
            except Exception as e:
                logger.warning(f"[worker] 可灵上传尾帧失败: {e}")

        task_id = await kling_api.submit_task(
            cookie=cookie,
            prompt=prompt,
            image_url=image_url,
            tail_image_url=tail_image_url,
            duration=duration_int,
            version=version,
            mode=mode,
        )

        with Session(engine) as session:
            order = session.get(VideoOrder, order_id)
            order.status = "generating"
            order.task_id = task_id
            order.updated_at = datetime.utcnow()
            session.add(order)
            session.commit()

        logger.info(f"[worker] 可灵订单#{order_id}已提交，task_id={task_id}，账号={acc_id}")
        asyncio.create_task(poll_kling_order(order_id, cookie=cookie))

    except Exception as e:
        logger.error(f"[worker] 可灵订单#{order_id}提交异常: {e}", exc_info=True)
        _fail_order(order_id, str(e))


VIDEOS_DIR = os.path.join(os.path.dirname(__file__), "..", "videos")


async def _download_video_to_local(url: str, order_id: int, idx: int = 0) -> str:
    """下载可灵视频到本地 /videos/ 目录，返回本地路径如 /videos/kling_order_123.mp4"""
    os.makedirs(VIDEOS_DIR, exist_ok=True)
    suffix = f"_{idx+1}" if idx > 0 else ""
    filename = f"kling_order_{order_id}{suffix}.mp4"
    filepath = os.path.join(VIDEOS_DIR, filename)
    local_url = f"/videos/{filename}"

    try:
        async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
            r = await client.get(url)
            r.raise_for_status()
            with open(filepath, "wb") as f:
                f.write(r.content)
        logger.info(f"[worker] 可灵订单#{order_id} 视频已下载到 {filepath} ({len(r.content)} bytes)")
        return local_url
    except Exception as e:
        logger.warning(f"[worker] 可灵订单#{order_id} 视频下载失败: {e}，保留原始URL")
        return url


async def poll_kling_order(order_id: int, cookie: Optional[str] = None):
    """轮询可灵任务直到完成或超时"""
    with Session(engine) as session:
        order = session.get(VideoOrder, order_id)
        if not order:
            return
        task_id = order.task_id
        model_name = order.model_name

    if not task_id:
        logger.warning(f"[worker] 可灵订单#{order_id}没有task_id，停止轮询")
        return

    # 若没有传入 cookie，尝试从账号列表中获取任意可用账号
    if not cookie:
        result = _pick_kling_account()
        if not result:
            logger.warning(f"[worker] 可灵轮询订单#{order_id}：无可用账号")
            _fail_order(order_id, "无可用可灵账号")
            return
        _, cookie = result

    try:
        result = await kling_api.poll_task(cookie, task_id, timeout=MAX_POLL_SECONDS)
        video_url = result.get("video_url", "")

        # 下载视频到本地
        if video_url:
            local_url = await _download_video_to_local(video_url, order_id)
        else:
            local_url = ""

        with Session(engine) as session:
            order = session.get(VideoOrder, order_id)
            if not order or order.status in ("completed", "failed"):
                return
            order.status = "completed"
            order.progress = 100
            order.video_url = local_url
            order.video_urls = json.dumps([local_url]) if local_url else "[]"
            order.updated_at = datetime.utcnow()
            session.add(order)
            session.commit()

        logger.info(f"[worker] 可灵订单#{order_id}完成，video_url={local_url}")

    except TimeoutError:
        logger.error(f"[worker] 可灵订单#{order_id}生成超时")
        _fail_order(order_id, "生成超时")
    except Exception as e:
        logger.error(f"[worker] 可灵订单#{order_id}轮询异常: {e}", exc_info=True)
        _fail_order(order_id, str(e))
