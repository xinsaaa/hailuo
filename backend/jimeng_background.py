"""
即梦订单后台处理任务
"""
import asyncio
import os
from datetime import datetime
from sqlmodel import Session, select

from backend.models import JimengOrder, User, Transaction, engine
from backend.jimeng_automation import submit_video_task, scan_video_status
from backend.admin_jimeng_account import _load_jimeng_accounts


async def process_jimeng_order(order_id: int):
    """
    处理即梦视频生成订单
    
    流程：
    1. 获取订单信息
    2. 选择一个可用的账号
    3. 提交视频生成任务
    4. 轮询任务状态
    5. 更新订单状态
    """
    print(f"[JIMENG-BG] 开始处理订单 #{order_id}")
    
    # 在 session 内获取订单数据
    order_data = None
    with Session(engine) as session:
        order = session.get(JimengOrder, order_id)
        if not order:
            print(f"[JIMENG-BG] 订单 #{order_id} 不存在")
            return
        
        if order.status != "pending":
            print(f"[JIMENG-BG] 订单 #{order_id} 状态不是 pending，跳过")
            return
        
        # 更新状态为处理中
        order.status = "processing"
        session.add(order)
        session.commit()
        
        # 提取订单数据（在 session 关闭前）
        order_data = {
            "prompt": order.prompt,
            "model_name": order.model_name,
            "duration": order.duration,
            "ratio": order.ratio,
            "first_frame_url": order.first_frame_url,
            "last_frame_url": order.last_frame_url,
        }
    
    try:
        # 获取可用账号
        account = get_available_jimeng_account()
        if not account:
            update_order_failed(order_id, "没有可用的即梦账号")
            return
        
        print(f"[JIMENG-BG] 订单 #{order_id} 使用账号: {account.get('display_name', account.get('account_id'))}")
        
        # 提交视频生成任务
        result = await submit_video_task(
            account=account,
            prompt=order_data["prompt"],
            model=order_data["model_name"],
            duration=order_data["duration"],
            ratio=order_data["ratio"],
            first_frame_url=order_data["first_frame_url"],
            last_frame_url=order_data["last_frame_url"],
        )
        
        if not result.get("success"):
            update_order_failed(order_id, result.get("error", "提交任务失败"))
            return
        
        task_id = result.get("task_id")
        print(f"[JIMENG-BG] 订单 #{order_id} 任务已提交，task_id: {task_id}")
        
        # 更新订单状态为生成中
        with Session(engine) as session:
            order = session.get(JimengOrder, order_id)
            order.status = "generating"
            session.add(order)
            session.commit()
        
        # 轮询任务状态
        max_wait_time = 600  # 最长等待10分钟
        start_time = asyncio.get_event_loop().time()
        
        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > max_wait_time:
                update_order_failed(order_id, "任务超时")
                return
            
            # 扫描视频状态
            scan_result = await scan_video_status(account, order_data["prompt"])
            
            if scan_result.get("success"):
                videos = scan_result.get("videos", [])
                for video in videos:
                    if video.get("status") == "completed" and video.get("video_url"):
                        # 找到完成的视频
                        update_order_completed(order_id, video.get("video_url"))
                        return
                    elif video.get("status") == "generating":
                        # 更新进度
                        progress = video.get("progress", 0)
                        update_order_progress(order_id, progress)
            
            await asyncio.sleep(5)  # 每5秒检查一次
            
    except Exception as e:
        print(f"[JIMENG-BG] 订单 #{order_id} 处理异常: {e}")
        update_order_failed(order_id, str(e))


def get_available_jimeng_account() -> dict:
    """获取一个可用的即梦账号"""
    data = _load_jimeng_accounts()
    accounts = data.get("accounts", [])
    
    # 筛选已登录且激活的账号
    available = [a for a in accounts if a.get("is_logged_in") and a.get("is_active", True)]
    
    if not available:
        return None
    
    # 简单轮询：返回第一个可用账号
    # TODO: 可以实现更复杂的负载均衡策略
    return available[0]


def update_order_failed(order_id: int, error: str):
    """更新订单为失败状态，并退还余额"""
    with Session(engine) as session:
        order = session.get(JimengOrder, order_id)
        if order:
            # 检查是否已经退款（防止重复退款）
            already_failed = order.status == "failed"
            
            order.status = "failed"
            order.error_message = error
            session.add(order)
            
            # 失败订单自动退回余额（仅首次标记为failed时退）
            if not already_failed and order.cost and order.cost > 0:
                user = session.get(User, order.user_id)
                if user:
                    user.balance += order.cost
                    session.add(user)
                    
                    # 记录退款交易
                    refund = Transaction(
                        user_id=order.user_id,
                        amount=order.cost,
                        bonus=0,
                        type="refund"
                    )
                    session.add(refund)
                    print(f"[JIMENG-BG] 订单 #{order_id} 已退款 {order.cost} 元")
            
            session.commit()
    print(f"[JIMENG-BG] 订单 #{order_id} 失败: {error}")


def update_order_completed(order_id: int, video_url: str):
    """更新订单为完成状态"""
    with Session(engine) as session:
        order = session.get(JimengOrder, order_id)
        if order:
            order.status = "completed"
            order.video_url = video_url
            order.progress = 100
            order.completed_at = datetime.utcnow()
            session.add(order)
            session.commit()
    print(f"[JIMENG-BG] 订单 #{order_id} 完成: {video_url}")


def update_order_progress(order_id: int, progress: int):
    """更新订单进度"""
    with Session(engine) as session:
        order = session.get(JimengOrder, order_id)
        if order and order.progress != progress:
            order.progress = progress
            session.add(order)
            session.commit()
    print(f"[JIMENG-BG] 订单 #{order_id} 进度: {progress}%")
