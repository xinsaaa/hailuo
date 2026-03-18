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
HAILUO_API_KEYWORD = "feed/creation/my/batch"

# ============ 海螺 SSR 数据解析 ============

async def fetch_hailuo_videos_via_api(page) -> list:
    """
    刷新页面并从 SSR __next_f.push 数据中提取视频列表。
    每个视频: {desc, status, downloadURL, videoURL, batchID, createTime}
    status: 2=完成, 其他=生成中/失败
    """
    try:
        await page.reload(timeout=30000, wait_until="networkidle")
        await asyncio.sleep(2)
    except Exception as e:
        print(f"[API-DEBUG] reload异常: {str(e)[:80]}")

    # 从页面 JS 中提取 batchFeeds 数据
    captured = await page.evaluate("""() => {
        const results = [];
        const debug = [];
        try {
            // 方案1：从 __NEXT_DATA__ 获取
            try {
                const nextData = window.__NEXT_DATA__;
                if (nextData) {
                    debug.push('__NEXT_DATA__ exists, keys: ' + Object.keys(nextData).join(','));
                    const props = nextData.props?.pageProps;
                    if (props) {
                        debug.push('pageProps keys: ' + Object.keys(props).join(','));
                        if (props.inintBatchFeedsData?.batchFeeds) {
                            const rawData = props.inintBatchFeedsData.batchFeeds;
                            debug.push('batchFeeds found: ' + rawData.length + ' batches');
                            for (const batch of rawData) {
                                const feeds = batch.feeds || [];
                                for (const feed of feeds) {
                                    const common = feed.commonInfo || {};
                                    const param = feed.modelParameter?.videoParameter || {};
                                    const meta = feed.metaInfo?.videoMetaInfo?.mediaInfo || {};
                                    const dl = meta.downloadURL || {};
                                    results.push({
                                        desc: param.desc || '',
                                        status: common.status,
                                        downloadURL: dl.withoutWatermarkURL || '',
                                        videoURL: meta.url || '',
                                        batchID: batch.batchID || '',
                                        createTime: common.createTime || 0,
                                    });
                                }
                            }
                        }
                    }
                } else {
                    debug.push('__NEXT_DATA__ not found');
                }
            } catch(e) {
                debug.push('__NEXT_DATA__ error: ' + e.message);
            }

            // 方案2：从页面 HTML 中搜索 batchFeeds
            if (results.length === 0) {
                const html = document.documentElement.innerHTML;
                const idx = html.indexOf('inintBatchFeedsData');
                if (idx >= 0) {
                    debug.push('found inintBatchFeedsData at ' + idx);
                    // 打印附近200字符看实际格式
                    debug.push('context: ' + html.substring(idx, idx + 300).replace(/</g, '&lt;'));

                    // 尝试多种格式匹配 batchFeeds
                    let bfIdx = html.indexOf('"batchFeeds":[', idx);
                    if (bfIdx < 0) bfIdx = html.indexOf('\\"batchFeeds\\":[', idx);
                    if (bfIdx < 0) bfIdx = html.indexOf('\\u0022batchFeeds\\u0022:[', idx);
                    if (bfIdx < 0) bfIdx = html.indexOf('batchFeeds', idx + 19); // skip the first one

                    if (bfIdx >= 0) {
                        debug.push('found batchFeeds variant at ' + bfIdx);
                        debug.push('bf context: ' + html.substring(bfIdx, bfIdx + 200));
                    } else {
                        debug.push('batchFeeds not found in any format');
                    }
                        // 从 batchFeeds 开始，找到匹配的 ]
                        const start = bfIdx + '"batchFeeds":'.length;
                        let depth = 0;
                        let end = start;
                        for (let i = start; i < html.length && i < start + 500000; i++) {
                            if (html[i] === '[') depth++;
                            else if (html[i] === ']') {
                                depth--;
                                if (depth === 0) { end = i + 1; break; }
                            }
                        }
                        if (end > start) {
                            try {
                                const raw = html.substring(start, end);
                                // 处理转义的 JSON（SSR 数据可能是双重转义的）
                                let parsed;
                                try {
                                    parsed = JSON.parse(raw);
                                } catch(e) {
                                    // 尝试反转义
                                    const unescaped = raw.replace(/\\\\"/g, '"').replace(/\\\\\\\\/g, '\\\\');
                                    parsed = JSON.parse(unescaped);
                                }
                                debug.push('parsed batchFeeds: ' + parsed.length + ' batches');
                                for (const batch of parsed) {
                                    const feeds = batch.feeds || [];
                                    for (const feed of feeds) {
                                        const common = feed.commonInfo || {};
                                        const param = feed.modelParameter?.videoParameter || {};
                                        const meta = feed.metaInfo?.videoMetaInfo?.mediaInfo || {};
                                        const dl = meta.downloadURL || {};
                                        results.push({
                                            desc: param.desc || '',
                                            status: common.status,
                                            downloadURL: dl.withoutWatermarkURL || '',
                                            videoURL: meta.url || '',
                                            batchID: batch.batchID || '',
                                            createTime: common.createTime || 0,
                                        });
                                    }
                                }
                            } catch(e) {
                                debug.push('parse error: ' + e.message);
                                // 打印前200字符帮助调试
                                debug.push('raw start: ' + html.substring(start, start + 200));
                            }
                        }
                    } else {
                        debug.push('batchFeeds array not found after inintBatchFeedsData');
                    }
                } else {
                    debug.push('inintBatchFeedsData not found in HTML');
                }
            }
        } catch(e) {
            debug.push('outer error: ' + e.message);
        }
        return {results, debug};
    }""")

    debug_info = captured.get("debug", []) if isinstance(captured, dict) else []
    video_list = captured.get("results", []) if isinstance(captured, dict) else captured

    for d in debug_info:
        print(f"[API-DEBUG] {d}")

    if not video_list:
        print(f"[API-DEBUG] 未从SSR数据中提取到视频")
    else:
        print(f"[API-DEBUG] 从SSR数据提取到 {len(video_list)} 个视频")

    return video_list

    return captured


async def check_order_in_api(page, order_id: int) -> dict | None:
    """
    刷新页面，通过 API 监听检查指定订单是否存在。
    返回匹配的视频信息 dict 或 None。
    """
    videos = await fetch_hailuo_videos_via_api(page)
    tag = f"[#ORD{order_id}]"
    for v in videos:
        if tag in v.get("desc", ""):
            return v
    return None

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
        self._scan_task: Optional[asyncio.Task] = None
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
        # 每个账号上次提交完成的时间，用于冷却控制
        self._account_last_submit: Dict[str, datetime] = {}
        # 提交冷却时间（秒）：同一账号两次提交之间的最小间隔
        self._submit_cooldown = 10
        
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

            # ===== 重启恢复：把上次中断的 processing 订单重置回 pending =====
            # processing 说明已经开始提交但还没确认，重启后页面丢失，必须重新处理
            # generating 不重置：它可能在海螺那边还在生成，扫描循环会继续跟踪
            try:
                with Session(engine) as session:
                    orphaned = session.exec(
                        select(VideoOrder).where(VideoOrder.status == "processing")
                    ).all()
                    if orphaned:
                        log_warn(f"发现 {len(orphaned)} 个遗留 processing 订单，重置为 pending 重新处理")
                        for o in orphaned:
                            o.status = "pending"
                        session.commit()
            except Exception as e:
                log_error(f"重置遗留订单失败: {e}")
            
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

            # 启动独立扫描循环（完全独立，不受主循环影响）
            self._scan_task = asyncio.create_task(self._scan_loop())

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
                        try:
                            await asyncio.wait_for(self._scheduled_restart(), timeout=300)
                        except asyncio.TimeoutError:
                            log_error("🚨 心跳重启超时(5分钟)，强制重置计时器")
                            self._start_time = datetime.utcnow()
                            self._last_heartbeat = datetime.utcnow()
                        except Exception as e:
                            log_error(f"🚨 心跳重启异常: {e}，强制重置")
                            self._start_time = datetime.utcnow()
                            self._last_heartbeat = datetime.utcnow()
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
                            try:
                                await asyncio.wait_for(self._scheduled_restart(), timeout=300)
                            except asyncio.TimeoutError:
                                log_error("🚨 定时重启超时(5分钟)，强制重置计时器")
                                self._start_time = datetime.utcnow()
                            except Exception as e:
                                log_error(f"🚨 定时重启异常: {e}，强制重置计时器")
                                self._start_time = datetime.utcnow()
                            continue

                if self._loop_task and self._loop_task.done():
                    exc = self._loop_task.exception() if not self._loop_task.cancelled() else None
                    log_warn(f"任务处理循环已死亡{f': {exc}' if exc else ''}，正在重启...")
                    self._loop_task = asyncio.create_task(self.task_processing_loop())
                if self._health_task and self._health_task.done():
                    exc = self._health_task.exception() if not self._health_task.cancelled() else None
                    log_warn(f"健康检查循环已死亡{f': {exc}' if exc else ''}，正在重启...")
                    self._health_task = asyncio.create_task(self.account_health_check_loop())
                if self._scan_task and self._scan_task.done():
                    exc = self._scan_task.exception() if not self._scan_task.cancelled() else None
                    log_warn(f"扫描循环已死亡{f': {exc}' if exc else ''}，正在重启...")
                    self._scan_task = asyncio.create_task(self._scan_loop())
            except Exception as e:
                log_error(f"监控循环错误: {e}")
                await asyncio.sleep(10)

    async def _scheduled_restart(self):
        """定时重启：关闭所有上下文，重新登录，重启核心循环"""
        log_info("🔄 开始定时重启...")

        # 1. 取消并等待核心循环任务结束
        for task, name in [(self._loop_task, "任务循环"), (self._health_task, "健康检查"), (self._scan_task, "扫描循环")]:
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
        self._scanning_accounts.clear()
        if hasattr(self, '_scanning_start_times'):
            self._scanning_start_times.clear()
        self._submit_locks.clear()  # 重置所有提交锁，防止 cancel 后锁永远持有

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
        self._scan_task = asyncio.create_task(self._scan_loop())

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
        
    async def _scan_loop(self):
        """独立扫描循环：只要有 generating 订单就持续扫描，和主循环完全分离"""
        print("[AUTO-V2] 🔍 独立扫描循环已启动")
        while self.is_running:
            try:
                # 查数据库有没有 generating 订单
                with Session(engine) as session:
                    generating_count = session.exec(
                        select(VideoOrder).where(VideoOrder.status == "generating")
                    ).all()
                    generating_count = len(generating_count)

                if generating_count > 0:
                    print(f"[SCAN-LOOP] 发现{generating_count}个生成中订单，触发扫描")
                    for account_id, page in list(self.manager.pages.items()):
                        if account_id not in self.manager._verified_accounts:
                            continue
                        if account_id in self._scanning_accounts:
                            print(f"[SCAN-LOOP] 账号{account_id}已在扫描中，跳过")
                            continue
                        asyncio.create_task(self._scan_completed_videos(page, account_id))

                await asyncio.sleep(15)  # 每15秒扫一次

            except Exception as e:
                print(f"[SCAN-LOOP] 错误: {e}")
                await asyncio.sleep(15)

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

                # ========== 第2步: 分配 pending 订单（严格排队：每个账号同一时间只处理一个）==========
                pending_orders = self.get_pending_orders()
                if pending_orders:
                    print(f"[AUTO-V2] 发现 {len(pending_orders)} 个待处理订单")
                    # 收集当前哪些账号正忙（有未完成的task_handler）
                    busy_accounts = set()
                    for k, t in self.task_handlers.items():
                        if not t.done():
                            aid = k.rsplit("_", 1)[0]
                            busy_accounts.add(aid)

                    for order in pending_orders:
                        if order['id'] in self._processing_order_ids:
                            continue
                        account_id = self.manager.get_best_account_for_task(
                            model_name=order.get('model_name', ''),
                            account_credits=getattr(self, '_account_credits', {})
                        )
                        if account_id:
                            # 检查1：账号是否有正在运行的任务
                            if account_id in busy_accounts:
                                print(f"[AUTO-V2] 账号 {account_id} 已有任务运行，订单#{order['id']} 排队等待")
                                continue
                            # 检查2：账号冷却时间（上次提交后需冷却一段时间）
                            last_submit = self._account_last_submit.get(account_id)
                            if last_submit:
                                elapsed = (datetime.utcnow() - last_submit).total_seconds()
                                if elapsed < self._submit_cooldown:
                                    print(f"[AUTO-V2] 账号 {account_id} 冷却中（{elapsed:.0f}/{self._submit_cooldown}秒），订单#{order['id']} 稍后处理")
                                    continue

                            self._processing_order_ids.add(order['id'])
                            if account_id not in self._account_orders:
                                self._account_orders[account_id] = set()
                            self._account_orders[account_id].add(order['id'])
                            task = asyncio.create_task(self.process_order(account_id, order))
                            self.task_handlers[f"{account_id}_{order['id']}"] = task
                            # 标记该账号为忙碌，本轮不再分配
                            busy_accounts.add(account_id)
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
                    "quantity": getattr(o, 'quantity', 1),
                }
                for o in orders
            ]

    async def _scan_completed_videos(self, page, account_id: str):
        """扫描页面上已完成的视频 - 需要扫描图生视频和文生视频两个页面"""
        if account_id in self._scanning_accounts:
            print(f"[AUTO-V2] ⏭️ 账号{account_id}正在扫描中，跳过重入")
            return
        # 如果该账号正在提交表单，跳过本次扫描，避免 goto/reload 打断提交
        submit_lock = self._submit_locks.get(account_id)
        if submit_lock and submit_lock.locked():
            print(f"[AUTO-V2] ⏭️ 账号{account_id}正在提交订单，跳过本次扫描")
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
        """通过监听海螺 batchCursor API 响应来扫描视频状态"""
        try:
            # 获取该账号需要扫描的订单
            pending_orders = {}
            if account_id in self._account_orders:
                with Session(engine) as session:
                    for oid in self._account_orders[account_id]:
                        order = session.get(VideoOrder, oid)
                        if order and order.status == "generating":
                            pending_orders[oid] = order.status
                            print(f"[AUTO-V2] 📋 待扫描订单#{oid}")

            if not pending_orders:
                print(f"[AUTO-V2] 📭 账号{account_id}无待扫描订单")
                return

            # 监听 API 响应并刷新页面
            print(f"[AUTO-V2] 🔍 账号{account_id} 通过API扫描 {len(pending_orders)} 个订单...")
            videos = await fetch_hailuo_videos_via_api(page)
            print(f"[AUTO-V2] 📡 API返回 {len(videos)} 个视频记录")

            total_completed = 0
            total_processing = 0

            # 按 batchID 分组视频
            batch_groups = {}
            for v in videos:
                bid = v.get("batchID", "")
                if bid:
                    if bid not in batch_groups:
                        batch_groups[bid] = []
                    batch_groups[bid].append(v)

            for oid in list(pending_orders.keys()):
                tag = f"[#ORD{oid}]"
                matched = None
                matched_batch_id = None
                for v in videos:
                    if tag in v.get("desc", ""):
                        matched = v
                        matched_batch_id = v.get("batchID", "")
                        break

                if not matched:
                    print(f"[AUTO-V2] ⏳ 订单#{oid} API中未找到，可能还在排队")
                    total_processing += 1
                    continue

                # 读取订单的批量数量
                with Session(engine) as session:
                    order_obj = session.get(VideoOrder, oid)
                    order_quantity = getattr(order_obj, 'quantity', 1) if order_obj else 1

                if order_quantity <= 1:
                    # 单个视频
                    api_status = matched.get("status")
                    download_url = matched.get("downloadURL", "")

                    if api_status == 2 and download_url:
                        print(f"[AUTO-V2] ✅ 订单#{oid} API检测到已完成，downloadURL: {download_url[:80]}...")
                        total_completed += 1

                        dedup_key = f"order_{oid}"
                        if dedup_key in _processed_share_links:
                            continue
                        if len(_processed_share_links) > _MAX_SHARE_LINKS:
                            _processed_share_links.clear()
                        _processed_share_links.add(dedup_key)

                        await self._complete_order(oid, download_url)
                        if account_id in self._account_orders:
                            self._account_orders[account_id].discard(oid)
                    else:
                        print(f"[AUTO-V2] ⏳ 订单#{oid} 状态={api_status}，生成中...")
                        total_processing += 1
                else:
                    # 批量：收集同 batchID 的所有视频
                    batch_videos = batch_groups.get(matched_batch_id, [matched])

                    ready_urls = []
                    all_ready = True
                    for idx in range(order_quantity):
                        if idx >= len(batch_videos):
                            all_ready = False
                            break
                        v = batch_videos[idx]
                        if v.get("status") == 2 and v.get("downloadURL"):
                            ready_urls.append(v["downloadURL"])
                        else:
                            all_ready = False
                            break

                    if all_ready and len(ready_urls) == order_quantity:
                        dedup_key = f"order_{oid}"
                        if dedup_key in _processed_share_links:
                            continue
                        if len(_processed_share_links) > _MAX_SHARE_LINKS:
                            _processed_share_links.clear()
                        _processed_share_links.add(dedup_key)

                        await self._complete_batch_order(oid, ready_urls)
                        if account_id in self._account_orders:
                            self._account_orders[account_id].discard(oid)
                        total_completed += 1
                    else:
                        print(f"[AUTO-V2] ⏳ 订单#{oid} 批量视频尚未全部生成（{len(ready_urls)}/{order_quantity}）")
                        total_processing += 1

            if total_completed > 0 or total_processing > 0:
                print(f"[AUTO-V2] 📊 账号{account_id} API扫描结果: 完成{total_completed}个, 生成中{total_processing}个")

        except Exception as e:
            print(f"[AUTO-V2] API扫描出错: {str(e)[:100]}")
        finally:
            self._scanning_accounts.discard(account_id)



    def _check_stuck_orders(self):
        """检查卡在generating/processing状态超久的订单 - 仅处理真正卡住的"""
        try:
            stuck_order_ids = []
            with Session(engine) as session:
                # generating 超时：用 created_at 判断，给足2小时（海螺生成时间不定）
                # 不能用 updated_at：扫描停止时 updated_at 不更新，会误杀仍在生成的订单
                cutoff_generating = datetime.utcnow() - timedelta(hours=2)

                # processing 超时：用 updated_at 判断（状态变为processing的时间）
                # 不能用 created_at：旧订单重启后重新变为processing，created_at仍是老时间，会立刻被误杀
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

                # processing 用 updated_at，超时后重置回 pending 而非直接 failed，给一次重试机会
                stuck_processing = session.exec(
                    select(VideoOrder).where(
                        VideoOrder.status == "processing",
                        VideoOrder.updated_at < cutoff_processing
                    )
                ).all()
                for order in stuck_processing:
                    print(f"[AUTO-V2] ⚠️ 订单#{order.id}进入processing超过30分钟无进展，重置为pending重试")
                    order.status = "pending"
                    order.updated_at = datetime.utcnow()
                    session.add(order)
                session.commit()

            # generating 超时才真正标记失败（退款）
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

        # 直接从订单字典读取批量数量
        batch_quantity = order.get("quantity", 1)
        if batch_quantity > 1:
            print(f"[AUTO-V2] 订单#{order_id} 批量数量: {batch_quantity}")

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
                    # 触发器：包含768p/1080p和时长文字的border按钮（sm:flex，桌面端可见）
                    settings_btn = page.locator("div.border-hl_line_01.cursor-pointer").first
                    if not await settings_btn.is_visible(timeout=3000):
                        # 备选：通过文字内容匹配
                        settings_btn = page.locator("div.cursor-pointer:has(span:text-is('768p')), div.cursor-pointer:has(span:text-is('1080p'))").first

                    if await settings_btn.is_visible(timeout=5000):
                        await settings_btn.scroll_into_view_if_needed()
                        await asyncio.sleep(0.3)
                        await settings_btn.click(force=True)
                        await asyncio.sleep(1)

                        # 弹出面板：bg-hl_bg_05 容器，包含分辨率和时长选项
                        popover = page.locator("div.bg-hl_bg_05:has(div.font-medium)").last
                        if await popover.is_visible(timeout=3000):
                            # 选择分辨率：text-is 精确匹配
                            res_option = popover.locator(f"div:has(> div.font-medium:text-is('{resolution}'))").first
                            if await res_option.is_visible(timeout=2000):
                                await res_option.click()
                                await asyncio.sleep(0.3)
                                print(f"[AUTO-V2] ✅ 订单#{order_id} 选择分辨率: {resolution}")

                            # 选择时长
                            dur_option = popover.locator(f"div:has(> div.font-medium:text-is('{duration}'))").first
                            if await dur_option.is_visible(timeout=2000):
                                await dur_option.click()
                                await asyncio.sleep(0.3)
                                print(f"[AUTO-V2] ✅ 订单#{order_id} 选择时长: {duration}")

                            # 关闭 popover
                            await page.mouse.click(10, 10)
                            await asyncio.sleep(0.3)
                        else:
                            print(f"[AUTO-V2] ⚠️ 订单#{order_id} 分辨率弹窗未出现")
                    else:
                        print(f"[AUTO-V2] ⚠️ 订单#{order_id} 未找到分辨率设置按钮，使用默认值")
                except Exception as e:
                    print(f"[AUTO-V2] ⚠️ 订单#{order_id} 设置分辨率/秒数失败: {str(e)[:60]}")

                # 步骤4.6: 设置批量数量（如果 > 1）
                if batch_quantity > 1:
                    try:
                        # 点击批量按钮：包含层叠svg图标和数字span的div
                        batch_btn = page.locator("div.cursor-pointer:has(svg):has(span.ml-1)").first
                        if await batch_btn.is_visible(timeout=3000):
                            await batch_btn.click()
                            await asyncio.sleep(1)

                            # 在弹出的 quantity-popover 中选择数量
                            qty_popover = page.locator("div.quantity-popover").first
                            if await qty_popover.is_visible(timeout=3000):
                                qty_btn = qty_popover.locator(f"button:has(div > div:text-is('{batch_quantity}'))").first
                                if await qty_btn.is_visible(timeout=2000):
                                    await qty_btn.click()
                                    await asyncio.sleep(0.5)
                                    print(f"[AUTO-V2] ✅ 订单#{order_id} 设置批量数量: {batch_quantity}")
                                else:
                                    print(f"[AUTO-V2] ⚠️ 订单#{order_id} 未找到数量{batch_quantity}的按钮")
                            else:
                                print(f"[AUTO-V2] ⚠️ 订单#{order_id} 批量选择弹窗未出现")
                        else:
                            print(f"[AUTO-V2] ⚠️ 订单#{order_id} 未找到批量按钮")
                    except Exception as e:
                        print(f"[AUTO-V2] ⚠️ 订单#{order_id} 设置批量数量失败: {str(e)[:60]}")

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

                        # 滚动到生成按钮位置，确保可见
                        try:
                            await generate_btn.scroll_into_view_if_needed()
                            await asyncio.sleep(0.5)
                        except:
                            pass
                        await generate_btn.click(force=True)
                        print(f"[AUTO-V2] 🖱️ 已点击生成按钮（第{click_attempt+1}次）")

                        # 确认信号：等待后刷新页面，通过 API 监听检测订单是否提交成功
                        await asyncio.sleep(8)
                        result = await check_order_in_api(page, order_id)
                        if result:
                            submit_confirmed = True
                            print(f"[AUTO-V2] ✅ API确认订单#{order_id}已提交，status={result.get('status')}")
                            break

                    if submit_confirmed:
                        print(f"[AUTO-V2] ✅ 订单#{order_id}已确认提交生成")
                        self.update_order_status(order_id, "generating")
                        # 记录提交完成时间，用于冷却控制
                        self._account_last_submit[account_id] = datetime.utcnow()
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
        """选择指定的AI模型"""
        try:
            print(f"[AUTO-V2] 🎯 开始模型选择: {model_name}")
            await asyncio.sleep(3)

            # 点击模型选择触发器
            dropdown = page.locator("div[data-tour='model-selection-guide']")
            try:
                if not await dropdown.is_visible(timeout=10000):
                    print("[AUTO-V2] ⚠️ 未找到模型选择下拉框")
                    return
            except:
                print("[AUTO-V2] ⚠️ 未找到模型选择下拉框")
                return

            await dropdown.scroll_into_view_if_needed()
            await asyncio.sleep(0.5)
            await dropdown.click(force=True, timeout=5000)
            await asyncio.sleep(3)

            # 新版 popover：bg-hl_bg_03 面板，包含"模型"标题
            popover = None
            for selector in [
                "div.bg-hl_bg_03:has(span:text('当前选择'))",
                "div.bg-hl_bg_03:has(span:text('模型'))",
                ".ant-popover:not(.ant-popover-hidden)",
            ]:
                try:
                    el = page.locator(selector).first
                    if await el.is_visible(timeout=3000):
                        popover = el
                        print(f"[AUTO-V2] ✅ 模型菜单已出现 (selector: {selector})")
                        break
                except:
                    continue

            if not popover:
                print("[AUTO-V2] ❌ 模型选择菜单未出现")
                return

            # 模型名称映射
            model_mapping = {
                "hailuo 2.3": ["hailuo 2.3"],
                "hailuo 2.3-fast": ["hailuo 2.3-fast"],
                "hailuo 2.0": ["hailuo 2.0"],
                "beta 3.1": ["beta 3.1"],
                "beta 3.1 fast": ["beta 3.1 fast"],
                "hailuo 1.0": ["hailuo 1.0"],
                "hailuo 1.0-director": ["hailuo 1.0-director"],
                "hailuo 1.0-live": ["hailuo 1.0-live"]
            }
            target_lower = model_name.lower().strip()

            # 新版结构：每个选项是 div.cursor-pointer，模型名在 div.font-500 里
            options = await popover.locator("div.cursor-pointer").all()
            for option in options:
                try:
                    if not await option.is_visible():
                        continue
                    # 从 font-500 元素取模型名
                    name_el = option.locator("div.font-500").first
                    if await name_el.count() == 0:
                        continue
                    name_text = (await name_el.text_content() or "").strip().lower()
                    if not name_text:
                        continue

                    is_match = target_lower == name_text
                    if not is_match and target_lower in model_mapping:
                        is_match = any(alias == name_text for alias in model_mapping[target_lower])
                    if not is_match:
                        # 模糊匹配：target 包含在 name 中或反过来
                        is_match = target_lower in name_text or name_text in target_lower

                    if is_match:
                        await option.click()
                        await asyncio.sleep(1)
                        print(f"[AUTO-V2] ✅ 已选择模型: {name_text}")
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
    
    async def _complete_order(self, order_id: int, download_url: str):
        """通过 API 获取的 downloadURL 下载视频到本地，然后完成订单"""
        import httpx

        filename = f"order_{order_id}.mp4"
        filepath = os.path.join(VIDEOS_DIR, filename)
        local_url = f"/videos/{filename}"

        # 下载视频到本地
        try:
            print(f"[AUTO-V2] 📥 订单#{order_id} 开始下载视频...")
            async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
                resp = await client.get(download_url)
                if resp.status_code == 200:
                    with open(filepath, "wb") as f:
                        f.write(resp.content)
                    size_mb = os.path.getsize(filepath) / (1024 * 1024)
                    print(f"[AUTO-V2] 📥 订单#{order_id} 下载完成 ({size_mb:.1f}MB)")
                else:
                    print(f"[AUTO-V2] ❌ 订单#{order_id} 下载失败 HTTP {resp.status_code}，使用远程URL")
                    local_url = download_url
        except Exception as e:
            print(f"[AUTO-V2] ❌ 订单#{order_id} 下载异常: {str(e)[:100]}，使用远程URL")
            local_url = download_url

        with Session(engine) as session:
            order = session.get(VideoOrder, order_id)
            if not order or order.status == "completed":
                return
            order.video_url = local_url
            order.status = "completed"
            order.progress = 100
            order.updated_at = datetime.utcnow()
            session.add(order)
            session.commit()
        print(f"[AUTO-V2] ✅ 订单#{order_id} 已完成，视频: {local_url}")
        self._processing_order_ids.discard(order_id)

    async def _complete_batch_order(self, order_id: int, download_urls: list):
        """下载批量视频并存储到 video_urls（JSON数组）"""
        import httpx
        import json

        local_urls = []
        for idx, download_url in enumerate(download_urls):
            filename = f"order_{order_id}_{idx+1}.mp4"
            filepath = os.path.join(VIDEOS_DIR, filename)
            local_url = f"/videos/{filename}"

            try:
                print(f"[AUTO-V2] 📥 订单#{order_id} 下载视频 {idx+1}/{len(download_urls)}...")
                async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
                    resp = await client.get(download_url)
                    if resp.status_code == 200:
                        with open(filepath, "wb") as f:
                            f.write(resp.content)
                        size_mb = os.path.getsize(filepath) / (1024 * 1024)
                        print(f"[AUTO-V2] 📥 订单#{order_id} 视频{idx+1} 下载完成 ({size_mb:.1f}MB)")
                    else:
                        local_url = download_url
            except Exception as e:
                print(f"[AUTO-V2] ❌ 订单#{order_id} 视频{idx+1} 下载异常: {str(e)[:80]}")
                local_url = download_url

            local_urls.append(local_url)

        with Session(engine) as session:
            order = session.get(VideoOrder, order_id)
            if not order or order.status == "completed":
                return
            order.video_url = local_urls[0]
            order.video_urls = json.dumps(local_urls)
            order.status = "completed"
            order.progress = 100
            order.updated_at = datetime.utcnow()
            session.add(order)
            session.commit()
        print(f"[AUTO-V2] ✅ 订单#{order_id} 批量完成，{len(local_urls)}个视频")
        self._processing_order_ids.discard(order_id)

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
