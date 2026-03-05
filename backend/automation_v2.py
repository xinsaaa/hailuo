"""
海螺AI自动化 V2 - 多账号版本
基于Browser Context实现多账号隔离，一个浏览器支持多个账号
核心页面交互逻辑移植自 automation.py (V1验证版本)
"""
import asyncio
import json
import os
import re
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from sqlmodel import Session, select
from backend.models import VideoOrder, SystemConfig, User, Transaction, engine

# 导入日志收集器（用于前端显示）
from backend.automation import automation_logger

def log_info(msg: str):
    """同时输出到控制台和日志收集器"""
    print(f"[AUTO-V2] {msg}")
    automation_logger.info(msg, quiet=True)

def log_success(msg: str):
    """成功日志"""
    print(f"[AUTO-V2] ✅ {msg}")
    automation_logger.success(msg)

def log_warn(msg: str):
    """警告日志"""
    print(f"[AUTO-V2] ⚠️ {msg}")
    automation_logger.warn(msg)

def log_error(msg: str):
    """错误日志"""
    print(f"[AUTO-V2] ❌ {msg}")
    automation_logger.error(msg)

# 配置缓存，避免每次都查数据库
_config_cache: Dict[str, Any] = {}
_config_cache_time: float = 0

def _get_v2_config(key, default):
    global _config_cache, _config_cache_time
    now = time.time()
    # 缓存10秒
    if now - _config_cache_time > 10:
        try:
            with Session(engine) as s:
                configs = s.exec(select(SystemConfig)).all()
                _config_cache = {c.key: c.value for c in configs}
                _config_cache_time = now
        except Exception:
            pass
    try:
        if key in _config_cache:
            return type(default)(json.loads(_config_cache[key]))
    except Exception:
        pass
    return default
from backend.multi_account_manager import MultiAccountManager, AccountConfig

HAILUO_URL = "https://hailuoai.com/create/image-to-video"
HAILUO_TEXT_URL = "https://hailuoai.com/create/text-to-video"

# ============ V1移植的工具函数 ============

def add_tracking_id(prompt: str, order_id: int) -> str:
    """在提示词末尾添加订单追踪 ID"""
    return f"{prompt} (以下内容请忽略，仅用于系统追踪：[#ORD{order_id}])"

def extract_order_id_from_text(text: str) -> Optional[int]:
    """从文本中提取订单追踪 ID"""
    match = re.search(r'\[#ORD(\d+)\]', text)
    return int(match.group(1)) if match else None

# 去重集合（限制大小防内存泄漏）
_processed_share_links: Set[str] = set()
_MAX_SHARE_LINKS = 500

# 新订单唤醒事件：延迟初始化，确保事件循环已存在
_new_order_event: Optional[asyncio.Event] = None

def _get_new_order_event() -> asyncio.Event:
    """获取或创建新订单事件（延迟初始化，确保事件循环已存在）"""
    global _new_order_event
    if _new_order_event is None:
        _new_order_event = asyncio.Event()
    return _new_order_event

def _notify_new_order():
    """通知有新订单（供外部调用）"""
    event = _get_new_order_event()
    event.set()

# 视频下载目录
VIDEOS_DIR = os.path.join(os.path.dirname(__file__), "..", "videos")
os.makedirs(VIDEOS_DIR, exist_ok=True)


class HailuoAutomationV2:
    """海螺AI自动化 V2版本 - 支持多账号"""

    def __init__(self):
        self.manager = MultiAccountManager()
        self.is_running = False
        self.task_handlers: Dict[str, asyncio.Task] = {}
        # 记录每个账号上有哪些未完成的订单ID
        self._account_orders: Dict[str, Set[int]] = {}
        # 正在处理中的订单ID，防止重复分配
        self._processing_order_ids: Set[int] = set()
        # 核心循环任务引用，用于监控和重启
        self._loop_task: Optional[asyncio.Task] = None
        self._health_task: Optional[asyncio.Task] = None
        # 系统启动时间，用于定时重启
        self._start_time: Optional[datetime] = None
        # 重启间隔（秒），默认1小时
        self._restart_interval = 3600
        # 正在被扫描的账号集合，防止健康检查/积分刷新同时操作同一个页面
        self._scanning_accounts: Set[str] = set()
        # 每个账号的提交锁：同一账号同一时间只允许一个任务执行"填写提示词+点生成"
        self._submit_locks: Dict[str, asyncio.Lock] = {}
        # 主循环心跳时间戳，用于检测卡住的任务
        self._last_heartbeat: Optional[datetime] = None
        # 心跳超时阈值（秒），超过此时间无心跳则认为主循环卡住
        self._heartbeat_timeout = 300
        
    async def start(self):
        """启动多账号自动化系统"""
        if self.is_running:
            log_info("系统已在运行中")
            return
        
        log_info("🚀 启动多账号自动化系统...")
        
        try:
            # 加载账号配置
            self.manager.load_accounts_config("accounts.json")
            log_info(f"已加载 {len(self.manager.accounts)} 个账号配置")
            
            # 检查是否有可用账号
            active_accounts = [acc for acc in self.manager.accounts.values() if acc.is_active]
            if not active_accounts:
                log_warn("没有激活的账号，系统无法启动")
                return
            
            # 设置运行状态
            self.is_running = True
            self._start_time = datetime.utcnow()
            log_success("系统状态已设置为运行中")
            
            # 并行登录所有激活的账号（先加载Cookie再登录）
            login_tasks = []
            log_info("开始初始化账号上下文...")
            
            for account_id, account in self.manager.accounts.items():
                if account.is_active:
                    try:
                        log_info(f"正在初始化账号: {account.display_name}")
                        # 创建上下文
                        await self.manager.create_account_context(account_id)
                        # 尝试加载Cookie（已在create_account_context中处理）
                        # 添加登录任务
                        login_tasks.append(self.manager.login_account(account_id))
                    except Exception as e:
                        log_error(f"初始化账号 {account.display_name} 失败: {e}")
            
            if login_tasks:
                log_info(f"开始登录 {len(login_tasks)} 个账号...")
                # 并行登录
                login_results = await asyncio.gather(*login_tasks, return_exceptions=True)
                success_count = sum(1 for result in login_results if result is True)
                log_success(f"成功登录 {success_count}/{len(login_tasks)} 个账号")
            
            # 启动任务处理循环
            log_info("启动任务处理循环...")
            self._loop_task = asyncio.create_task(self.task_processing_loop())

            # 启动账号健康检查循环
            log_info("启动账号健康检查循环...")
            self._health_task = asyncio.create_task(self.account_health_check_loop())

            # 启动监控循环，自动重启死掉的核心任务
            asyncio.create_task(self._watchdog_loop())
            
            log_success("🎉 多账号自动化系统启动成功！")
            
        except Exception as e:
            log_error(f"系统启动失败: {e}")
            self.is_running = False  # 确保启动失败时重置状态
            raise

    async def _watchdog_loop(self):
        """监控核心任务，死掉自动重启 + 每小时定时重启整个系统 + 心跳检测"""
        while self.is_running:
            try:
                await asyncio.sleep(30)
                if not self.is_running:
                    break

                # 心跳检测：检查主循环是否卡住
                if self._last_heartbeat:
                    heartbeat_elapsed = (datetime.utcnow() - self._last_heartbeat).total_seconds()
                    if heartbeat_elapsed > self._heartbeat_timeout:
                        log_warn(f"🚨 主循环心跳超时 {heartbeat_elapsed:.0f}秒，可能卡住，强制重启")
                        await self._scheduled_restart()
                        continue

                # 定时重启：检查运行时长是否超过重启间隔
                if self._start_time:
                    elapsed = (datetime.utcnow() - self._start_time).total_seconds()
                    if elapsed >= self._restart_interval:
                        active_tasks = len([t for t in self.task_handlers.values() if not t.done()])
                        # 最长再等 30 分钟，超时后强制重启（防止卡死任务导致永不重启）
                        max_delay = 1800
                        overdue = elapsed - self._restart_interval
                        if active_tasks > 0 and overdue < max_delay:
                            log_info(f"⏰ 已运行{elapsed/60:.0f}分钟，有{active_tasks}个活跃任务，延迟重启（已超期{overdue/60:.0f}分钟）...")
                        else:
                            if active_tasks > 0:
                                log_warn(f"⏰ 已运行{elapsed/60:.0f}分钟，超期{overdue/60:.0f}分钟强制重启（{active_tasks}个任务可能卡死）")
                            else:
                                log_info(f"⏰ 已运行{elapsed/60:.0f}分钟，开始定时重启...")
                            await self._scheduled_restart()
                            continue

                if self._loop_task and self._loop_task.done():
                    exc = self._loop_task.exception() if not self._loop_task.cancelled() else None
                    log_warn(f"任务处理循环已死亡{f': {exc}' if exc else ''}，正在重启...")
                    self._loop_task = asyncio.create_task(self.task_processing_loop())
                if self._health_task and self._health_task.done():
                    exc = self._health_task.exception() if not self._health_task.cancelled() else None
                    log_warn(f"健康检查循环已死亡{f': {exc}' if exc else ''}，正在重启...")
                    self._health_task = asyncio.create_task(self.account_health_check_loop())
            except Exception as e:
                log_error(f"监控循环错误: {e}")
                await asyncio.sleep(10)

    async def _scheduled_restart(self):
        """定时重启：关闭所有上下文，重新登录，重启核心循环"""
        log_info("🔄 开始定时重启...")

        # 1. 取消并等待核心循环任务结束
        for task, name in [(self._loop_task, "任务循环"), (self._health_task, "健康检查")]:
            if task and not task.done():
                task.cancel()
                try:
                    await asyncio.wait_for(asyncio.shield(task), timeout=10)
                except Exception:
                    pass
                print(f"[AUTO-V2] ✅ {name}已停止")

        # 2. 关闭所有浏览器上下文
        try:
            await self.manager.close_all()
            print("[AUTO-V2] ✅ 所有浏览器上下文已关闭")
        except Exception as e:
            print(f"[AUTO-V2] ⚠️ 关闭浏览器上下文时出错: {e}")

        # 3. 清理运行时状态
        self.task_handlers.clear()
        self._processing_order_ids.clear()
        self._account_orders.clear()

        # 4. 重新初始化并登录
        print("[AUTO-V2] 重新加载账号配置并登录...")
        try:
            self.manager.load_accounts_config("accounts.json")
            active_accounts = [aid for aid, acc in self.manager.accounts.items() if acc.is_active]

            login_tasks = []
            for account_id in active_accounts:
                try:
                    await self.manager.create_account_context(account_id)
                    login_tasks.append(self.manager.login_account(account_id))
                except Exception as e:
                    print(f"[AUTO-V2] ⚠️ 初始化账号 {account_id} 失败: {e}")

            if login_tasks:
                results = await asyncio.gather(*login_tasks, return_exceptions=True)
                success_count = sum(1 for r in results if r is True)
                print(f"[AUTO-V2] ✅ 重启后成功登录 {success_count}/{len(login_tasks)} 个账号")
        except Exception as e:
            print(f"[AUTO-V2] ❌ 重启时重新登录失败: {e}")

        # 4b. 登录完成后，将数据库中仍为 generating 的订单放回扫描队列
        # 必须在登录后执行，扫描条件要求账号在 _verified_accounts 中
        try:
            with Session(engine) as session:
                orphaned = session.exec(
                    select(VideoOrder).where(VideoOrder.status == "generating")
                ).all()
                if orphaned:
                    print(f"[AUTO-V2] 🔄 重启后发现 {len(orphaned)} 个 generating 订单，恢复扫描队列")
                    active_ids = [aid for aid in self.manager._verified_accounts
                                  if aid in self.manager.accounts and self.manager.accounts[aid].is_active]
                    if active_ids:
                        for i, order in enumerate(orphaned):
                            target = active_ids[i % len(active_ids)]
                            if target not in self._account_orders:
                                self._account_orders[target] = set()
                            self._account_orders[target].add(order.id)
                            print(f"[AUTO-V2] 📌 订单#{order.id} 分配给账号 {target}")
                    else:
                        print(f"[AUTO-V2] ⚠️ 无可用账号，generating订单暂时挂起，等待下次循环")
        except Exception as e:
            print(f"[AUTO-V2] ⚠️ 恢复 generating 订单失败: {e}")

        # 4c. 重启后立即主动扫描一次所有账号页面，加速订单恢复
        await self._initial_scan_after_restart()

        # 5. 重启核心循环
        self._loop_task = asyncio.create_task(self.task_processing_loop())
        self._health_task = asyncio.create_task(self.account_health_check_loop())

        # 6. 重置计时器
        self._start_time = datetime.utcnow()
        print("[AUTO-V2] 🎉 定时重启完成，系统已恢复运行")

    async def _initial_scan_after_restart(self):
        """重启后主动扫描所有账号页面，加速恢复generating订单"""
        print("[AUTO-V2] 🔍 重启后主动扫描所有账号页面...")
        
        all_pages = list(self.manager.pages.keys())
        verified_pages = [aid for aid in all_pages if aid in self.manager._verified_accounts]
        
        if not verified_pages:
            print("[AUTO-V2] ⚠️ 无已验证账号，跳过初始扫描")
            return
        
        scanned = 0
        for account_id in verified_pages:
            page = self.manager.pages.get(account_id)
            if not page:
                continue
            try:
                await self._scan_completed_videos(page, account_id)
                scanned += 1
            except Exception as e:
                print(f"[AUTO-V2] 初始扫描账号 {account_id} 出错: {str(e)[:80]}")
        
        print(f"[AUTO-V2] ✅ 初始扫描完成，共扫描 {scanned} 个账号")

    async def account_health_check_loop(self):
        """账号健康检查循环"""
        print("[AUTO-V2] 🔍 账号健康检查循环已启动")
        
        while self.is_running:
            try:
                await asyncio.sleep(_get_v2_config('health_check_interval', 300))
                
                if not self.is_running:
                    break
                    
                print("[AUTO-V2] 开始账号健康检查...")
                await self.manager.auto_check_and_recover_accounts(skip_accounts=self._scanning_accounts)
                
            except Exception as e:
                print(f"[AUTO-V2] 健康检查循环错误: {e}")
                await asyncio.sleep(60)
        
    async def task_processing_loop(self):
        """任务处理主循环"""
        print("[AUTO-V2] 📋 任务处理循环已启动")
        loop_count = 0

        while self.is_running:
            try:
                loop_count += 1
                self._last_heartbeat = datetime.utcnow()
                poll_interval = _get_v2_config('task_poll_interval', 5)

                print(f"[AUTO-V2] 🔁 第{loop_count}次循环 [步骤0: 开始]")

                # 统计未超时的 generating 订单
                generating_count = 0
                timeout_hours = _get_v2_config('order_timeout_hours', 2)
                timeout_threshold = datetime.utcnow() - timedelta(hours=timeout_hours)
                with Session(engine) as session:
                    generating_orders = session.exec(
                        select(VideoOrder).where(
                            VideoOrder.status == "generating",
                            VideoOrder.created_at >= timeout_threshold
                        )
                    ).all()
                    generating_count = len(generating_orders)

                print(f"[AUTO-V2] 🔁 第{loop_count}次循环 [步骤1] 活跃任务={len(self.task_handlers)} 生成中={generating_count}")

                # ========== 第1步: 异步触发扫描（不阻塞主循环）==========
                all_pages = list(self.manager.pages.keys())
                if generating_count > 0:
                    accounts_to_scan = [aid for aid in all_pages
                                        if aid in self.manager._verified_accounts
                                        and aid in self.manager.accounts
                                        and self.manager.accounts[aid].current_tasks == 0
                                        and aid not in self._scanning_accounts]
                    if accounts_to_scan:
                        print(f"[AUTO-V2] 🔍 有{generating_count}个生成中订单，异步扫描: {accounts_to_scan}")
                        for account_id in accounts_to_scan:
                            page = self.manager.pages.get(account_id)
                            if page:
                                asyncio.create_task(self._scan_completed_videos(page, account_id))
                    else:
                        print(f"[AUTO-V2] ⏳ 有{generating_count}个生成中订单，所有账号正忙/扫描中")

                print(f"[AUTO-V2] 🔁 第{loop_count}次循环 [步骤2: 扫描任务已启动]")

                # ========== 第2步: 分配 pending 订单 ==========
                pending_orders = self.get_pending_orders()
                if pending_orders:
                    print(f"[AUTO-V2] 发现 {len(pending_orders)} 个待处理订单")
                    for order in pending_orders:
                        if order['id'] in self._processing_order_ids:
                            continue
                        account_id = self.manager.get_best_account_for_task(
                            model_name=order.get('model_name', ''),
                            account_credits=getattr(self, '_account_credits', {})
                        )
                        if account_id:
                            account_has_task = any(
                                k.startswith(f"{account_id}_") for k, t in self.task_handlers.items()
                                if not t.done()
                            )
                            if account_has_task:
                                print(f"[AUTO-V2] 账号 {account_id} 已有任务运行，订单#{order['id']} 等下次循环")
                                continue
                            self._processing_order_ids.add(order['id'])
                            if account_id not in self._account_orders:
                                self._account_orders[account_id] = set()
                            self._account_orders[account_id].add(order['id'])
                            task = asyncio.create_task(self.process_order(account_id, order))
                            self.task_handlers[f"{account_id}_{order['id']}"] = task
                        else:
                            print(f"[AUTO-V2] 暂无可用账号处理订单 {order['id']}，等待下次循环")

                print(f"[AUTO-V2] 🔁 第{loop_count}次循环 [步骤3: 清理任务]")

                # ========== 第3步: 清理已完成任务 ==========
                for task_id in [k for k, t in self.task_handlers.items() if t.done()]:
                    task = self.task_handlers.pop(task_id)
                    if not task.cancelled():
                        exc = task.exception()
                        if exc:
                            log_warn(f"任务{task_id}异常: {exc}")
                    try:
                        oid = int(task_id.split('_')[-1])
                        self._processing_order_ids.discard(oid)
                    except (ValueError, IndexError):
                        pass

                print(f"[AUTO-V2] 🔁 第{loop_count}次循环 [步骤4: 超时检查]")

                # ========== 第4步: 检查超时订单 ==========
                self._check_stuck_orders()

                # ========== 兜底清理: 超过10分钟的扫描任务强制解锁 ==========
                if hasattr(self, '_scanning_start_times'):
                    now = datetime.utcnow()
                    stuck_scanning = [aid for aid, t in self._scanning_start_times.items()
                                      if (now - t).total_seconds() > 600]
                    for aid in stuck_scanning:
                        print(f"[AUTO-V2] ⚠️ 账号{aid}扫描超过10分钟，强制解锁")
                        self._scanning_accounts.discard(aid)
                        self._scanning_start_times.pop(aid, None)

                print(f"[AUTO-V2] 🔁 第{loop_count}次循环 [步骤5: 积分刷新]")

                # ========== 第5步: 空闲时异步刷新积分（绝不阻塞主循环）==========
                if generating_count == 0 and len(self.task_handlers) == 0:
                    asyncio.create_task(self._refresh_account_credits())

                print(f"[AUTO-V2] 🔁 第{loop_count}次循环 [步骤6: 等待]")

                # ========== 第6步: 等待下次循环 ==========
                has_pending = bool(self.get_pending_orders())
                if generating_count > 0 or len(self.task_handlers) > 0 or has_pending:
                    self._idle_count = 0
                    wait_interval = poll_interval
                else:
                    self._idle_count = getattr(self, '_idle_count', 0) + 1
                    wait_interval = min(poll_interval * 3 + self._idle_count * 15, 60)

                event = _get_new_order_event()
                event.clear()
                try:
                    await asyncio.wait_for(event.wait(), timeout=wait_interval)
                    log_info("⚡ 新订单唤醒，立即处理")
                except asyncio.TimeoutError:
                    pass

            except Exception as e:
                log_error(f"任务循环错误: {e}")
                await asyncio.sleep(10)

    def get_pending_orders(self) -> List[dict]:
        """获取待处理的订单（返回dict避免detached ORM对象问题）"""
        with Session(engine) as session:
            orders = session.exec(
                select(VideoOrder).where(
                    VideoOrder.status == "pending"
                ).limit(10)
            ).all()
            # 在session关闭前提取所有需要的字段
            return [
                {
                    "id": o.id,
                    "prompt": o.prompt,
                    "model_name": o.model_name,
                    "first_frame_image": getattr(o, 'first_frame_image', None),
                    "last_frame_image": getattr(o, 'last_frame_image', None),
                    "user_id": o.user_id,
                    "video_type": getattr(o, 'video_type', 'image_to_video'),
                    "resolution": getattr(o, 'resolution', '768p'),
                    "duration": getattr(o, 'duration', '6s'),
                }
                for o in orders
            ]

    async def _scan_completed_videos(self, page, account_id: str):
        """扫描页面上已完成的视频 - 需要扫描图生视频和文生视频两个页面"""
        if account_id in self._scanning_accounts:
            print(f"[AUTO-V2] ⏭️ 账号{account_id}正在扫描中，跳过重入")
            return
        self._scanning_accounts.add(account_id)
        # 记录扫描开始时间，用于主循环兜底清理
        if not hasattr(self, '_scanning_start_times'):
            self._scanning_start_times = {}
        self._scanning_start_times[account_id] = datetime.utcnow()

        try:
            # 整体超时保护：最长5分钟，超时后 finally 强制清除 _scanning_accounts
            await asyncio.wait_for(self._do_scan(page, account_id), timeout=300)
        except asyncio.TimeoutError:
            print(f"[AUTO-V2] ⚠️ 账号{account_id}扫描超时(5分钟)，强制结束")
        except Exception as e:
            print(f"[AUTO-V2] 扫描页面出错: {str(e)[:100]}")
        finally:
            self._scanning_accounts.discard(account_id)
            if hasattr(self, '_scanning_start_times'):
                self._scanning_start_times.pop(account_id, None)

    async def _do_scan(self, page, account_id: str):
        """实际扫描逻辑，由 _scan_completed_videos 包裹超时"""
        try:
            # 检查账号上有哪些类型的订单，决定扫描哪个页面
            order_types = set()
            if account_id in self._account_orders:
                with Session(engine) as session:
                    for oid in self._account_orders[account_id]:
                        order = session.get(VideoOrder, oid)
                        if order and order.status == "generating":
                            video_type = getattr(order, 'video_type', None) or 'image_to_video'
                            order_types.add(video_type)
                            print(f"[AUTO-V2] 📋 订单#{oid} video_type={video_type}")
            
            # 如果没有订单信息，默认扫描两个页面
            if not order_types:
                order_types = {'image_to_video', 'text_to_video'}
                print(f"[AUTO-V2] ⚠️ 未检测到订单类型，默认扫描两个页面")
            
            print(f"[AUTO-V2] 📋 需扫描的页面类型: {order_types}")
            
            # 扫描需要的页面
            pages_to_scan = []
            if 'image_to_video' in order_types:
                pages_to_scan.append(('图生视频', HAILUO_URL))
            if 'text_to_video' in order_types:
                pages_to_scan.append(('文生视频', HAILUO_TEXT_URL))
            
            total_completed = 0
            total_processing = 0
            
            for page_name, target_url in pages_to_scan:
                try:
                    print(f"[AUTO-V2] 🔍 账号{account_id} 扫描{page_name}页面...")
                    # 强制刷新页面，确保获取最新状态
                    current_url = page.url
                    if target_url in current_url:
                        # 已在目标页面，执行刷新
                        await asyncio.wait_for(
                            page.reload(timeout=30000, wait_until="networkidle"),
                            timeout=35
                        )
                    else:
                        # 导航到目标页面
                        await asyncio.wait_for(
                            page.goto(target_url, timeout=30000, wait_until="networkidle"),
                            timeout=35
                        )
                    await asyncio.sleep(2)
                except asyncio.TimeoutError:
                    print(f"[AUTO-V2] ⚠️ 账号{account_id} {page_name}页面操作超时(>35s)，跳过")
                    continue
                except Exception as e:
                    print(f"[AUTO-V2] {page_name}页面导航失败: {str(e)[:80]}")
                    continue
                
                completed, processing = await self._scan_current_page(page, account_id)
                total_completed += completed
                total_processing += processing
            
            if total_completed > 0 or total_processing > 0:
                print(f"[AUTO-V2] � 账号{account_id}总扫描结果: 完成{total_completed}个, 生成中{total_processing}个")
                
        except Exception as e:
            print(f"[AUTO-V2] 扫描页面出错: {str(e)[:100]}")
        finally:
            self._scanning_accounts.discard(account_id)

    async def _scan_current_page(self, page, account_id: str):
        """扫描当前页面上的视频卡片"""
        prompt_spans = await page.locator("span.prompt-plain-span").all()
        if not prompt_spans:
            print(f"[AUTO-V2] 📭 账号{account_id}当前页面无视频卡片")
            return 0, 0

        SCAN_LIMIT = 50
        if len(prompt_spans) > SCAN_LIMIT:
            prompt_spans = prompt_spans[:SCAN_LIMIT]
        print(f"[AUTO-V2] 🔍 扫描 {len(prompt_spans)} 个视频卡片（上限{SCAN_LIMIT}）")
        completed_count = 0
        processing_count = 0

        for span in prompt_spans:
            try:
                prompt_text = await span.text_content()
                if not prompt_text:
                    continue

                order_id = extract_order_id_from_text(prompt_text)
                if not order_id:
                    continue

                with Session(engine) as session:
                    order = session.get(VideoOrder, order_id)
                    if not order or order.status == "completed" or order.status == "failed":
                        continue

                print(f"[AUTO-V2] 🎯 发现订单#{order_id} (状态: {order.status if order else '?'})")

                parent = span.locator("xpath=ancestor::div[contains(@class, 'group/video-card')]").first

                still_processing = False
                processing_reason = ""

                # 检测1: 排队中
                try:
                    if await parent.locator("div:has-text('低速生成中')").is_visible():
                        still_processing = True
                        processing_reason = "排队中"
                        self._update_order_progress(order_id, -1)
                        print(f"[AUTO-V2]   检测到: 低速生成中")
                except:
                    pass

                # 检测2: 优化提示词
                if not still_processing:
                    try:
                        if await parent.locator("div:has-text('正在优化提示词')").is_visible():
                            still_processing = True
                            processing_reason = "优化提示词中"
                            print(f"[AUTO-V2]   检测到: 正在优化提示词")
                    except:
                        pass

                # 检测3: loading图
                if not still_processing:
                    try:
                        has_loading = await parent.locator("img[alt*='hailuo AI video loading']").count() > 0
                        if has_loading:
                            still_processing = True
                            processing_reason = "加载中(loading图)"
                            print(f"[AUTO-V2]   检测到: loading图")
                    except:
                        pass

                # 检测4: 取消按钮（更精确的选择器）
                if not still_processing:
                    try:
                        has_cancel = await parent.locator("button:has-text('取消')").count() > 0
                        if has_cancel:
                            still_processing = True
                            processing_reason = "生成中(有取消按钮)"
                            print(f"[AUTO-V2]   检测到: 取消按钮")
                    except:
                        pass

                # 检测5: 进度条
                if not still_processing:
                    try:
                        progress = parent.locator(".ant-progress-text")
                        if await progress.is_visible():
                            progress_text = await progress.text_content() or "0%"
                            still_processing = True
                            processing_reason = f"进度条 {progress_text}"
                            print(f"[AUTO-V2]   检测到: 进度条 {progress_text}")
                            try:
                                val = int(progress_text.replace("%", "").strip())
                                self._update_order_progress(order_id, val)
                            except:
                                pass
                    except:
                        pass

                # 检测6: 视频是否已完成（有播放按钮或下载按钮）
                if not still_processing:
                    try:
                        has_play = await parent.locator("button:has-text('播放'), video").count() > 0
                        has_download_btn = await parent.locator("button:has(path[d*='M2 9.26074']), button:has(path[d*='M8.65991'])").count() > 0
                        if has_play or has_download_btn:
                            print(f"[AUTO-V2]   检测到: 视频已完成(播放/下载按钮)")
                    except:
                        pass

                if still_processing:
                    print(f"[AUTO-V2] ⏳ 订单#{order_id} {processing_reason}")
                    processing_count += 1
                    continue

                print(f"[AUTO-V2] ✅ 订单#{order_id}生成完成，开始自动化下载")
                try:
                    dedup_key = f"order_{order_id}"
                    if dedup_key in _processed_share_links:
                        continue
                    if len(_processed_share_links) > _MAX_SHARE_LINKS:
                        _processed_share_links.clear()
                    _processed_share_links.add(dedup_key)

                    filename = f"order_{order_id}.mp4"
                    filepath = os.path.join(VIDEOS_DIR, filename)
                    download_ok = False

                    for dl_attempt in range(3):
                        try:
                            dl_trigger = None
                            for trigger_sel in [
                                "button:has(path[d*='M2 9.26074'])",
                                "button:has(path[d*='M8.65991'])",
                                "button.bg-hl_bg_10_legacy",
                            ]:
                                try:
                                    candidate = parent.locator(trigger_sel).first
                                    if await candidate.is_visible(timeout=2000):
                                        dl_trigger = candidate
                                        print(f"[AUTO-V2] 找到触发按钮: {trigger_sel}")
                                        break
                                except:
                                    pass
                            if dl_trigger is None:
                                print(f"[AUTO-V2] ⚠️ 订单#{order_id} 第{dl_attempt+1}次未找到触发按钮")
                                await asyncio.sleep(2)
                                continue

                            await dl_trigger.hover()
                            await asyncio.sleep(1.0)

                            dropdown_locator = page.locator(".ant-dropdown:not(.ant-dropdown-hidden)").first
                            try:
                                await dropdown_locator.wait_for(state="visible", timeout=3000)
                            except:
                                print(f"[AUTO-V2] ⚠️ 订单#{order_id} 浮窗未出现，重试")
                                await asyncio.sleep(1)
                                continue

                            sw_count = await dropdown_locator.locator("button[role='switch']").count()
                            for sw_idx in range(sw_count):
                                try:
                                    sw = dropdown_locator.locator("button[role='switch']").nth(sw_idx)
                                    checked = await sw.get_attribute("aria-checked", timeout=2000)
                                    if checked != "false":
                                        print(f"[AUTO-V2] 订单#{order_id} 开关[{sw_idx}]已开启，跳过")
                                        continue
                                    print(f"[AUTO-V2] 订单#{order_id} 点击水印开关[{sw_idx}]")
                                    await sw.click()
                                    await asyncio.sleep(0.8)
                                    for confirm_sel in [
                                        "button:has-text('同意')",
                                        "button:has-text('确认')",
                                        "button:has-text('确定')",
                                        ".ant-modal-footer .ant-btn-primary",
                                        ".ant-modal .ant-btn-primary",
                                    ]:
                                        try:
                                            confirm_btn = page.locator(confirm_sel).first
                                            if await confirm_btn.is_visible(timeout=1000):
                                                await confirm_btn.click()
                                                print(f"[AUTO-V2] 订单#{order_id} 开关[{sw_idx}]同意协议弹窗")
                                                await asyncio.sleep(0.5)
                                                break
                                        except:
                                            pass
                                    dropdown_visible = False
                                    try:
                                        dropdown_visible = await dropdown_locator.is_visible(timeout=800)
                                    except:
                                        pass
                                    if not dropdown_visible:
                                        print(f"[AUTO-V2] 订单#{order_id} 浮窗已关闭，重新hover")
                                        await dl_trigger.hover()
                                        await asyncio.sleep(1.0)
                                        try:
                                            await dropdown_locator.wait_for(state="visible", timeout=3000)
                                        except:
                                            print(f"[AUTO-V2] ⚠️ 订单#{order_id} 重新hover后浮窗未出现")
                                            break
                                except Exception as sw_err:
                                    print(f"[AUTO-V2] ⚠️ 订单#{order_id} 处理开关[{sw_idx}]出错: {str(sw_err)[:80]}")

                            dropdown_dl_btn = None
                            for btn_sel in [
                                "button.cl_hl_H9_M",
                                "button:has-text('下载')",
                            ]:
                                try:
                                    candidate = dropdown_locator.locator(btn_sel).first
                                    if await candidate.is_visible(timeout=1500):
                                        dropdown_dl_btn = candidate
                                        print(f"[AUTO-V2] 找到浮窗下载按钮: {btn_sel}")
                                        break
                                except:
                                    pass

                            if dropdown_dl_btn is None:
                                print(f"[AUTO-V2] ⚠️ 订单#{order_id} 未找到浮窗下载按钮，跳过")
                                await asyncio.sleep(2)
                                continue

                            async with page.expect_download(timeout=60000) as dl_info:
                                await dropdown_dl_btn.click()

                            download = await dl_info.value
                            await download.save_as(filepath)
                            size_mb = os.path.getsize(filepath) / (1024 * 1024)
                            print(f"[AUTO-V2] 📥 订单#{order_id} 下载完成 ({size_mb:.1f}MB)")
                            download_ok = True
                            break

                        except Exception as dl_err:
                            print(f"[AUTO-V2] ⚠️ 订单#{order_id} 第{dl_attempt+1}次下载异常: {str(dl_err)[:120]}")
                            await asyncio.sleep(3)

                    if download_ok:
                        self.update_order_result(order_id, f"/videos/{filename}", "completed")
                        print(f"[AUTO-V2] 🎉 订单#{order_id}完成!")
                        completed_count += 1
                    else:
                        print(f"[AUTO-V2] ❌ 订单#{order_id} 3次下载均失败，标记失败")
                        _processed_share_links.discard(dedup_key)
                        self.update_order_status(order_id, "failed")

                except Exception as e:
                    print(f"[AUTO-V2] 下载视频出错 订单#{order_id}: {str(e)[:100]}")
                    _processed_share_links.discard(f"order_{order_id}")

            except Exception:
                continue

        if completed_count > 0 or processing_count > 0:
            print(f"[AUTO-V2] 📊 扫描结果: 完成{completed_count}个, 生成中{processing_count}个")

        if account_id in self._account_orders:
            found_on_page = set()
            for span in prompt_spans:
                try:
                    text = await span.text_content()
                    if text:
                        oid = extract_order_id_from_text(text)
                        if oid:
                            found_on_page.add(oid)
                except:
                    pass
            
            missing_orders = self._account_orders[account_id] - found_on_page
            if missing_orders:
                print(f"[AUTO-V2] ⚠️ 账号{account_id}有 {len(missing_orders)} 个订单在页面上未找到: {missing_orders}")

        if account_id in self._account_orders:
            done_ids = set()
            for oid in self._account_orders[account_id]:
                with Session(engine) as session:
                    o = session.get(VideoOrder, oid)
                    if o and o.status in ("completed", "failed"):
                        done_ids.add(oid)
            if done_ids:
                self._account_orders[account_id] -= done_ids

        return completed_count, processing_count

    def _check_stuck_orders(self):
        """检查卡在generating/processing状态超久的订单 - 仅处理真正卡住的"""
        try:
            stuck_order_ids = []
            with Session(engine) as session:
                # generating 超时：用 created_at 判断，给足2小时（海螺生成时间不定）
                # 注意：不能用 updated_at，因为扫描停止时 updated_at 就不更新，会误杀正在生成的订单
                cutoff_generating = datetime.utcnow() - timedelta(hours=2)
                cutoff_processing = datetime.utcnow() - timedelta(minutes=30)

                stuck_generating = session.exec(
                    select(VideoOrder).where(
                        VideoOrder.status == "generating",
                        VideoOrder.created_at < cutoff_generating
                    )
                ).all()
                for order in stuck_generating:
                    print(f"[AUTO-V2] ⚠️ 订单#{order.id}创建超过2小时仍在generating（进度:{order.progress}），标记失败")
                    stuck_order_ids.append(order.id)

                # processing 超时：用 created_at 判断，放宽到30分钟
                stuck_processing = session.exec(
                    select(VideoOrder).where(
                        VideoOrder.status == "processing",
                        VideoOrder.created_at < cutoff_processing
                    )
                ).all()
                for order in stuck_processing:
                    print(f"[AUTO-V2] ⚠️ 订单#{order.id}创建超过30分钟仍在processing，标记失败")
                    stuck_order_ids.append(order.id)

            # 统一走update_order_status处理退款，避免双重退款
            for oid in stuck_order_ids:
                self.update_order_status(oid, "failed")
                self._processing_order_ids.discard(oid)

        except Exception as e:
            print(f"[AUTO-V2] 检查卡住订单出错: {str(e)[:80]}")

    async def _refresh_account_credits(self):
        """空闲时后台刷新账号积分缓存（每5分钟一次），不影响任务提交"""
        now = asyncio.get_event_loop().time()
        last_refresh = getattr(self, '_last_credits_refresh', 0)
        if now - last_refresh < 300:  # 5分钟间隔
            return
        self._last_credits_refresh = now

        for account_id in list(self.manager.pages.keys()):
            account = self.manager.accounts.get(account_id)
            if not account or account_id not in self.manager._verified_accounts:
                continue
            # 只在账号空闲且未被扫描时操作页面，防止与扫描循环冲突
            if account.current_tasks > 0 or account_id in self._scanning_accounts:
                continue
            page = self.manager.pages.get(account_id)
            if not page:
                continue
            try:
                # 刷新页面获取最新积分
                await page.reload(timeout=15000, wait_until="domcontentloaded")
                await asyncio.sleep(3)
                credits = await self.manager.get_account_credits(account_id)
                if not hasattr(self, '_account_credits'):
                    self._account_credits = {}
                self._account_credits[account_id] = credits
                if credits >= 0:
                    print(f"[AUTO-V2] 💰 账号 {account.display_name} 积分: {credits}")
            except Exception as e:
                print(f"[AUTO-V2] 刷新积分失败 {account_id}: {str(e)[:80]}")

    async def process_order(self, account_id: str, order: dict):
        """处理单个订单 - 基于V1验证过的选择器和流程"""
        account = self.manager.accounts.get(account_id)
        if not account:
            print(f"[AUTO-V2] ❌ 账号 {account_id} 不存在")
            self.update_order_status(order["id"], "failed")
            return

        page = self.manager.pages.get(account_id)
        if not page:
            print(f"[AUTO-V2] ❌ 账号 {account.display_name} 没有可用的页面")
            self.update_order_status(order["id"], "failed")
            return

        order_id = order["id"]

        # 先检查订单是否已经不是pending了（可能被扫描循环标记为completed）
        with Session(engine) as session:
            current_order = session.get(VideoOrder, order_id)
            if current_order and current_order.status != "pending":
                print(f"[AUTO-V2] 订单#{order_id}状态已变为{current_order.status}，跳过处理")
                return

        prompt = order["prompt"]
        model_name = order.get("model_name", "Hailuo 2.3")
        video_type = order.get("video_type", "image_to_video")
        resolution = order.get("resolution", "768p")
        duration = order.get("duration", "6s")
        first_frame_path = order.get("first_frame_image")
        last_frame_path = order.get("last_frame_image")
        is_text_mode = video_type == "text_to_video"

        print(f"[AUTO-V2] 账号 {account.display_name} 开始处理订单 {order_id} ({'文生视频' if is_text_mode else '图生视频'})")
        account.current_tasks += 1

        try:
            self.update_order_status(order_id, "processing")

            # 检查页面是否还活着
            try:
                _ = page.url
            except Exception:
                print(f"[AUTO-V2] ⚠️ 账号 {account_id} 页面已崩溃，尝试恢复...")
                try:
                    await self.manager.create_account_context(account_id)
                    page = self.manager.pages.get(account_id)
                    if not page:
                        raise Exception("页面恢复失败")
                except Exception as re_err:
                    print(f"[AUTO-V2] ❌ 页面恢复失败: {re_err}")
                    self.update_order_status(order_id, "failed")
                    return

            # 根据视频类型导航到不同页面（最多重试3次）
            target_url = HAILUO_TEXT_URL if is_text_mode else HAILUO_URL
            nav_ok = False
            for nav_attempt in range(3):
                try:
                    await page.goto(target_url, timeout=30000, wait_until="domcontentloaded")
                    await asyncio.sleep(2)
                    nav_ok = True
                    break
                except Exception as nav_err:
                    print(f"[AUTO-V2] ⚠️ 订单#{order_id}页面导航失败(第{nav_attempt+1}次): {str(nav_err)[:80]}")
                    await asyncio.sleep(3)
            if not nav_ok:
                print(f"[AUTO-V2] ❌ 订单#{order_id}页面导航3次均失败，标记失败")
                self.update_order_status(order_id, "failed")
                return

            # 关闭可能的弹窗
            await self._dismiss_popup(page)

            # 图生视频模式：上传首尾帧图片
            if not is_text_mode:
                # 步骤1: 上传首帧图片
                if first_frame_path:
                    print(f"[AUTO-V2] 📤 上传首帧图片: {first_frame_path}")
                    if not await self._upload_first_frame(page, first_frame_path):
                        print(f"[AUTO-V2] ❌ 首帧图片上传失败")
                        self.update_order_status(order_id, "failed")
                        return

                # 步骤2: 上传尾帧图片
                if last_frame_path:
                    print(f"[AUTO-V2] 📤 上传尾帧图片: {last_frame_path}")
                    await self._switch_to_last_frame_mode(page)
                    await self._upload_last_frame(page, last_frame_path)

            # ===== 关键提交段：加账号级锁，防止并发任务同时打字导致内容混乱 =====
            if account_id not in self._submit_locks:
                self._submit_locks[account_id] = asyncio.Lock()
            print(f"[AUTO-V2] 订单#{order_id} 等待提交锁...")
            async with self._submit_locks[account_id]:
                print(f"[AUTO-V2] 订单#{order_id} 获得提交锁，开始填写表单")

                # 填写提示词（最多重试3次）
                if prompt and prompt.strip():
                    prompt_with_id = add_tracking_id(prompt, order_id)
                    prompt_ok = False
                    for prompt_attempt in range(3):
                        try:
                            text_input = page.locator("#video-create-textarea")
                            if await text_input.is_visible(timeout=5000):
                                await text_input.click(force=True, timeout=5000)
                                await asyncio.sleep(0.3)
                                await page.keyboard.press("Control+A")
                                await page.keyboard.press("Delete")
                                await page.keyboard.type(prompt_with_id, delay=10)
                                print(f"[AUTO-V2] ✅ 提示词填写完成")
                                prompt_ok = True
                                break
                            else:
                                print(f"[AUTO-V2] ⚠️ 提示词输入框不可见(第{prompt_attempt+1}次)，等待重试...")
                                await asyncio.sleep(2)
                        except Exception as e:
                            print(f"[AUTO-V2] ⚠️ 填写提示词失败(第{prompt_attempt+1}次): {str(e)[:80]}")
                            await asyncio.sleep(2)
                    if not prompt_ok:
                        print(f"[AUTO-V2] ❌ 订单#{order_id}提示词填写3次均失败，标记失败")
                        self.update_order_status(order_id, "failed")
                        return

                # 步骤4: 选择模型
                await self.select_model(page, model_name)

                # 步骤4.5: 选择分辨率和秒数
                try:
                    settings_btn = page.locator("div.cursor-pointer:has(span:text('768p')), div.cursor-pointer:has(span:text('1080p'))").first
                    if await settings_btn.is_visible(timeout=3000):
                        await settings_btn.click()
                        await asyncio.sleep(0.5)

                        res_btn = page.locator(f"div.cursor-pointer:has(div:text('{resolution}'))").first
                        if await res_btn.is_visible(timeout=2000):
                            await res_btn.click()
                            await asyncio.sleep(0.2)
                            print(f"[AUTO-V2] ✅ 订单#{order_id} 选择分辨率: {resolution}")

                        dur_btn = page.locator(f"div.cursor-pointer:has(div:text('{duration}'))").first
                        if await dur_btn.is_visible(timeout=2000):
                            await dur_btn.click()
                            await asyncio.sleep(0.2)
                            print(f"[AUTO-V2] ✅ 订单#{order_id} 选择时长: {duration}")

                        await page.mouse.click(10, 10)
                        await asyncio.sleep(0.3)
                    else:
                        print(f"[AUTO-V2] ⚠️ 订单#{order_id} 未找到分辨率设置按钮，使用默认值")
                except Exception as e:
                    print(f"[AUTO-V2] ⚠️ 订单#{order_id} 设置分辨率/秒数失败: {str(e)[:60]}")

                # 步骤5: 等待popover完全关闭后再找生成按钮
                await asyncio.sleep(0.5)
                for pop_sel in [".ant-popover:not(.ant-popover-hidden)"]:
                    try:
                        pop = page.locator(pop_sel).first
                        if await pop.is_visible():
                            await page.keyboard.press("Escape")
                            await asyncio.sleep(0.5)
                    except:
                        pass

                # 点击生成按钮前检查是否暂停
                if _get_v2_config('pause_generation', False):
                    print(f"[AUTO-V2] ⏸️ 订单#{order_id}已暂停（pause_generation开启），等待恢复...")
                    while _get_v2_config('pause_generation', False):
                        await asyncio.sleep(5)
                    print(f"[AUTO-V2] ▶️ 订单#{order_id}恢复生成")

                # 点击生成按钮
                generate_btn = None
                for selector in ["button.new-color-btn-bg", "button:has-text('生成')", "button:has-text('开始生成')", "button[type='submit']"]:
                    try:
                        btn = page.locator(selector).first
                        if await btn.count() > 0:
                            generate_btn = btn
                            print(f"[AUTO-V2] ✅ 找到生成按钮: {selector}")
                            break
                    except:
                        continue

                if generate_btn:
                    submit_confirmed = False
                    for click_attempt in range(3):
                        if click_attempt > 0:
                            print(f"[AUTO-V2] 🔁 订单#{order_id}第{click_attempt+1}次尝试点击生成按钮...")
                            await asyncio.sleep(2)
                            for selector in ["button.new-color-btn-bg", "button:has-text('生成')", "button:has-text('开始生成')", "button[type='submit']"]:
                                try:
                                    btn = page.locator(selector).first
                                    if await btn.count() > 0:
                                        generate_btn = btn
                                        break
                                except Exception:
                                    continue

                        await generate_btn.click(force=True)

                        for _ in range(15):
                            await asyncio.sleep(1)
                            try:
                                queue_hint = page.locator("div:has-text('低速生成中'), div:has-text('排队'), div:has-text('生成中')")
                                if await queue_hint.count() > 0:
                                    submit_confirmed = True
                                    break
                                if await page.locator(".ant-progress-text").count() > 0:
                                    submit_confirmed = True
                                    break
                            except Exception:
                                pass
                        if submit_confirmed:
                            break

                    if submit_confirmed:
                        print(f"[AUTO-V2] ✅ 订单#{order_id}已确认提交生成")
                        self.update_order_status(order_id, "generating")
                        # 提交成功后重新加入扫描队列，让扫描循环跟踪下载
                        if account_id not in self._account_orders:
                            self._account_orders[account_id] = set()
                        self._account_orders[account_id].add(order_id)
                        print(f"[AUTO-V2] 📌 订单#{order_id} 已加入账号 {account_id} 的扫描队列，当前队列: {self._account_orders[account_id]}")
                    else:
                        print(f"[AUTO-V2] ❌ 订单#{order_id}重试3次后仍无确认信号，标记失败")
                        self.update_order_status(order_id, "failed")
                        return
                else:
                    print(f"[AUTO-V2] ❌ 未找到生成按钮")
                    self.update_order_status(order_id, "failed")
                    return
            # ===== 提交锁释放 =====

            # 提交后刷新页面重置状态，等待task_processing_loop的扫描循环来检测完成
            await asyncio.sleep(3)
            await page.goto(HAILUO_URL, timeout=30000, wait_until="domcontentloaded")
            await asyncio.sleep(3)

        except Exception as e:
            print(f"[AUTO-V2] 账号 {account.display_name} 处理订单 {order_id} 出错: {e}")
            self.update_order_status(order_id, "failed")
        finally:
            account.current_tasks = max(0, account.current_tasks - 1)
            self._processing_order_ids.discard(order_id)
    
    async def select_model(self, page: Page, model_name: str):
        """选择指定的AI模型 - 移植自V1的popover方式"""
        try:
            print(f"[AUTO-V2] 🎯 开始模型选择: {model_name}")
            await asyncio.sleep(3)

            # V1验证的选择器：data-tour="model-selection-guide"
            dropdown = page.locator("div[data-tour='model-selection-guide']")
            try:
                if not await dropdown.is_visible(timeout=5000):
                    print("[AUTO-V2] ⚠️ 未找到模型选择下拉框")
                    return
            except:
                print("[AUTO-V2] ⚠️ 未找到模型选择下拉框")
                return

            await dropdown.click(force=True, timeout=5000)
            await asyncio.sleep(2)

            # 检查popover是否出现
            popover = None
            for selector in [".ant-popover:not(.ant-popover-hidden)", ".model-selection-options:not(.ant-popover-hidden)"]:
                try:
                    el = page.locator(selector).first
                    if await el.is_visible():
                        popover = el
                        break
                except:
                    continue

            if not popover:
                print("[AUTO-V2] ❌ 模型选择菜单未出现")
                return

            # 模型名称映射
            model_mapping = {
                "hailuo 2.3": ["hailuo 2.3", "2.3"],
                "hailuo 2.3-fast": ["hailuo 2.3-fast", "2.3-fast", "fast"],
                "hailuo 2.0": ["hailuo 2.0", "2.0"],
                "beta 3.1": ["beta 3.1", "3.1"],
                "hailuo 1.0": ["hailuo 1.0", "1.0"],
                "hailuo 1.0-director": ["director"],
                "hailuo 1.0-live": ["live"]
            }
            target_lower = model_name.lower().strip()

            # 在popover中查找选项
            options = await popover.locator("div.cursor-pointer").all()
            for option in options:
                try:
                    if not await option.is_visible():
                        continue
                    text = (await option.text_content() or "").lower()
                    if len(text) < 5 or len(text) > 200 or "hailuo" not in text:
                        continue

                    is_match = target_lower in text
                    if not is_match and target_lower in model_mapping:
                        is_match = any(alias in text for alias in model_mapping[target_lower])

                    if is_match:
                        await option.click()
                        await asyncio.sleep(1)
                        print(f"[AUTO-V2] ✅ 已选择模型: {text.strip()[:50]}")
                        # 等待popover关闭，防止遮挡生成按钮
                        await asyncio.sleep(1)
                        try:
                            await page.keyboard.press("Escape")
                            await asyncio.sleep(0.5)
                        except:
                            pass
                        return
                except:
                    continue

            print(f"[AUTO-V2] ⚠️ 未匹配到模型 {model_name}，使用默认")
            # 关闭popover
            try:
                await page.keyboard.press("Escape")
                await asyncio.sleep(0.5)
            except:
                pass

        except Exception as e:
            print(f"[AUTO-V2] 模型选择失败: {str(e)[:100]}")
    
    async def wait_for_generation_complete(self, page: Page, order_id: int, timeout: int = 600) -> Optional[str]:
        """扫描页面检测订单完成并提取分享链接 - 移植自V1"""
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                prompt_spans = await page.locator("span.prompt-plain-span").all()
                for span in prompt_spans:
                    try:
                        text = await span.text_content()
                        if not text:
                            continue
                        oid = extract_order_id_from_text(text)
                        if oid != order_id:
                            continue

                        parent = span.locator("xpath=ancestor::div[contains(@class, 'group/video-card')]").first

                        # 检查排队状态
                        queue_hint = parent.locator("div:has-text('低速生成中')")
                        if await queue_hint.is_visible():
                            self._update_order_progress(order_id, -1)
                            break

                        # 检查进度条
                        progress = parent.locator(".ant-progress-text")
                        if await progress.is_visible():
                            progress_text = await progress.text_content() or "0%"
                            try:
                                val = int(progress_text.replace("%", "").strip())
                                self._update_order_progress(order_id, val)
                            except:
                                pass
                            break

                        # 没有进度条 = 生成完成，提取分享链接
                        share_btn = parent.locator("div.text-hl_text_00_legacy:has(svg path[d*='M7.84176'])").first
                        if not await share_btn.is_visible():
                            break

                        await share_btn.click()
                        await asyncio.sleep(0.5)

                        share_link = await page.evaluate("() => navigator.clipboard.readText()") or ""
                        if share_link.startswith("http") and share_link not in _processed_share_links:
                            _processed_share_links.add(share_link)
                            return share_link

                    except Exception:
                        continue

                await asyncio.sleep(_get_v2_config('task_poll_interval', 5))

            except Exception as e:
                print(f"[AUTO-V2] 扫描出错: {str(e)[:100]}")
                await asyncio.sleep(5)

        return None

    def _update_order_progress(self, order_id: int, progress: int):
        """更新订单进度"""
        with Session(engine) as session:
            order = session.get(VideoOrder, order_id)
            if order and order.progress != progress:
                order.progress = progress
                session.add(order)
                session.commit()

    async def _dismiss_popup(self, page: Page):
        """关闭弹窗 - 移植自V1"""
        try:
            close_btn = page.locator("button.ant-modal-close")
            if await close_btn.is_visible(timeout=3000):
                await close_btn.click(force=True, timeout=3000)
                await asyncio.sleep(0.5)
        except:
            pass

    async def _upload_first_frame(self, page: Page, image_path: str) -> bool:
        """上传首帧图片 - 移植自V1"""
        try:
            if not os.path.exists(image_path):
                print(f"[AUTO-V2] ❌ 图片不存在: {image_path}")
                return False

            upload_wrapper = page.locator(".upload-image-wrapper").first
            if not await upload_wrapper.is_visible():
                return False

            file_input = upload_wrapper.locator("input[type='file']")
            if not await file_input.count():
                return False

            await file_input.set_input_files(image_path)
            await asyncio.sleep(3)

            # 检查尺寸过小错误
            try:
                error_hint = page.locator(".adm-auto-center-content:has-text('图片尺寸过小')")
                if await error_hint.is_visible():
                    print("[AUTO-V2] ❌ 图片尺寸过小")
                    return False
            except:
                pass

            return True
        except Exception as e:
            print(f"[AUTO-V2] 上传首帧失败: {str(e)[:100]}")
            return False

    async def _switch_to_last_frame_mode(self, page: Page):
        """切换到尾帧模式 - 移植自V1"""
        try:
            for selector in ["button:has-text('尾帧')", "div:has-text('尾帧')", "div.text-hl_white_75:has-text('尾帧')"]:
                try:
                    btn = page.locator(selector).first
                    if await btn.is_visible():
                        await btn.click()
                        await asyncio.sleep(2)
                        return
                except:
                    continue
        except:
            pass

    async def _upload_last_frame(self, page: Page, image_path: str) -> bool:
        """上传尾帧图片 - 移植自V1"""
        try:
            if not os.path.exists(image_path):
                return False

            wrappers = await page.locator(".upload-image-wrapper").all()
            target = None
            for w in wrappers:
                text = await w.text_content() or ""
                if "尾帧" in text:
                    target = w
                    break
            if not target and len(wrappers) >= 2:
                target = wrappers[1]
            if not target:
                return False

            file_input = target.locator("input[type='file']")
            if not await file_input.count():
                return False

            await file_input.set_input_files(image_path)
            await asyncio.sleep(3)
            return True
        except Exception as e:
            print(f"[AUTO-V2] 上传尾帧失败: {str(e)[:100]}")
            return False
    
    def update_order_status(self, order_id: int, status: str):
        """更新订单状态，失败时自动退回余额（防重复退款）"""
        with Session(engine) as session:
            order = session.get(VideoOrder, order_id)
            if order:
                # 防重复退款：已经是failed的不再退
                already_failed = order.status == "failed"
                order.status = status
                order.updated_at = datetime.utcnow()
                session.add(order)

                # 失败订单自动退回余额（仅首次标记为failed时退）
                if status == "failed" and not already_failed and order.cost and order.cost > 0:
                    user = session.get(User, order.user_id)
                    if user:
                        user.balance += order.cost
                        session.add(user)
                        refund = Transaction(
                            user_id=order.user_id,
                            amount=order.cost,
                            bonus=0,
                            type="refund"
                        )
                        session.add(refund)
                        print(f"[AUTO-V2] 💰 订单#{order_id}失败，已退回 ¥{order.cost} 给用户#{order.user_id}")

                session.commit()

        # 完成或失败时从账号订单映射中移除
        if status in ("completed", "failed"):
            for aid, oids in self._account_orders.items():
                oids.discard(order_id)
            self._processing_order_ids.discard(order_id)

    def update_order_result(self, order_id: int, video_url: str, status: str):
        """更新订单结果"""
        with Session(engine) as session:
            order = session.get(VideoOrder, order_id)
            if order:
                order.video_url = video_url
                order.status = status
                order.updated_at = datetime.utcnow()
                session.add(order)
                session.commit()

        # 完成时从账号订单映射中移除
        for aid, oids in self._account_orders.items():
            oids.discard(order_id)
        self._processing_order_ids.discard(order_id)
    
    async def process_order_immediately(self, order_id: int) -> bool:
        """
        立即处理订单 - 由 API 直接调用，无需等待主循环扫描
        
        Args:
            order_id: 订单ID
            
        Returns:
            bool: True 表示已分配处理，False 表示无可用账号（订单留在 pending 状态等待主循环）
        """
        if not self.is_running:
            print(f"[AUTO-V2] ⚠️ 系统未运行，订单#{order_id}无法立即处理")
            return False
        
        if order_id in self._processing_order_ids:
            print(f"[AUTO-V2] 订单#{order_id}已在处理中")
            return True
        
        with Session(engine) as session:
            order = session.get(VideoOrder, order_id)
            if not order:
                print(f"[AUTO-V2] ❌ 订单#{order_id}不存在")
                return False
            if order.status != "pending":
                print(f"[AUTO-V2] 订单#{order_id}状态为{order.status}，跳过")
                return True
            
            order_dict = {
                "id": order.id,
                "prompt": order.prompt,
                "model_name": order.model_name,
                "first_frame_image": getattr(order, 'first_frame_image', None),
                "last_frame_image": getattr(order, 'last_frame_image', None),
                "user_id": order.user_id,
                "video_type": getattr(order, 'video_type', 'image_to_video'),
                "resolution": getattr(order, 'resolution', '768p'),
                "duration": getattr(order, 'duration', '6s'),
            }
        
        model_name = order_dict.get("model_name", "")
        account_id = self.manager.get_best_account_for_task(
            model_name=model_name,
            account_credits=getattr(self, '_account_credits', {})
        )
        
        if not account_id:
            log_info(f"📭 订单#{order_id}暂无可用账号，等待主循环处理")
            return False

        # 只检查仍在运行中的任务（过滤已完成的僵尸任务，避免误判）
        account_has_task = any(
            k.startswith(f"{account_id}_") for k, t in self.task_handlers.items()
            if not t.done()
        )
        if account_has_task:
            log_info(f"账号 {account_id} 已有任务运行，订单#{order_id}等待主循环处理")
            return False
        
        self._processing_order_ids.add(order_id)
        if account_id not in self._account_orders:
            self._account_orders[account_id] = set()
        self._account_orders[account_id].add(order_id)
        
        task = asyncio.create_task(
            self.process_order(account_id, order_dict)
        )
        self.task_handlers[f"{account_id}_{order_id}"] = task
        log_success(f"⚡ 订单#{order_id}已立即分配给账号 {account_id}")
        return True
    
    async def stop(self):
        """停止自动化系统"""
        log_info("🛑 停止多账号自动化系统...")
        self.is_running = False
        
        # 等待所有任务完成
        if self.task_handlers:
            await asyncio.gather(*self.task_handlers.values(), return_exceptions=True)
        
        # 关闭所有浏览器上下文
        await self.manager.close_all()
        
    def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        return {
            "is_running": self.is_running,
            "active_tasks": len(self.task_handlers),
            "accounts": self.manager.get_account_status(),
            "total_accounts": len(self.manager.accounts),
            "active_accounts": sum(1 for acc in self.manager.accounts.values() if acc.is_active)
        }
    
    async def force_scan_order(self, order_id: int):
        """强制扫描指定订单 - 用于卡住的订单手动触发"""
        log_info(f"🔍 强制扫描订单#{order_id}...")
        
        with Session(engine) as session:
            order = session.get(VideoOrder, order_id)
            if not order:
                log_warn(f"订单#{order_id}不存在")
                return False
            if order.status not in ("generating", "processing"):
                log_warn(f"订单#{order_id}状态为{order.status}，不需要扫描")
                return False
            
            video_type = getattr(order, 'video_type', None) or 'image_to_video'
        
        # 找一个可用的账号来扫描
        all_pages = list(self.manager.pages.keys())
        verified_pages = [aid for aid in all_pages if aid in self.manager._verified_accounts]
        
        if not verified_pages:
            log_warn(f"无已验证账号，无法扫描订单#{order_id}")
            return False
        
        # 确保订单在扫描队列中
        for account_id in verified_pages:
            if account_id not in self._account_orders:
                self._account_orders[account_id] = set()
            self._account_orders[account_id].add(order_id)
        
        # 立即触发扫描
        for account_id in verified_pages:
            page = self.manager.pages.get(account_id)
            if not page:
                continue
            try:
                log_info(f"🔍 强制扫描账号 {account_id} 页面...")
                await self._scan_completed_videos(page, account_id)
                break
            except Exception as e:
                log_error(f"扫描账号 {account_id} 出错: {str(e)[:80]}")
        
        return True


# 全局实例
automation_v2 = HailuoAutomationV2()


# ============ API集成函数 ============

async def start_automation_v2():
    """启动多账号自动化"""
    await automation_v2.start()

async def stop_automation_v2():
    """停止多账号自动化"""
    await automation_v2.stop()

def get_automation_v2_status():
    """获取多账号自动化状态"""
    return automation_v2.get_system_status()

async def process_order_immediately(order_id: int) -> bool:
    """立即处理订单 - 供 API 直接调用"""
    return await automation_v2.process_order_immediately(order_id)

async def add_account(account_config: dict):
    """添加新账号（只保存配置，不自动登录，登录由用户手动触发）"""
    account = AccountConfig(**account_config)
    automation_v2.manager.accounts[account.account_id] = account
    
    # 保存配置
    accounts_list = list(automation_v2.manager.accounts.values())
    automation_v2.manager.save_accounts_config(accounts_list)
    
    print(f"[AUTO-V2] ✅ 账号 {account.display_name} 已添加，请在管理后台手动登录")

async def toggle_account(account_id: str, is_active: bool):
    """启用/禁用账号"""
    if account_id in automation_v2.manager.accounts:
        automation_v2.manager.accounts[account_id].is_active = is_active
        
        # 保存配置
        accounts_list = list(automation_v2.manager.accounts.values())
        automation_v2.manager.save_accounts_config(accounts_list)
        
        if not is_active:
            # 关闭账号上下文
            await automation_v2.manager.close_account(account_id)
