"""
海螺 AI 自动化视频生成模块

功能：
1. 后端启动时自动打开浏览器并登录海螺 AI
2. 并行提交多个视频生成任务（带订单追踪 ID）
3. 监控生成进度，完成后提取分享链接
4. 三层去重：内存集合 + 订单状态 + 追踪 ID 匹配
"""

import time
import re
import threading
import queue
import requests
from typing import Optional, Set, Dict
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext
from sqlmodel import Session, select
from backend.models import VerificationCode, VideoOrder, engine

# ============ 常量配置 ============
HAILUO_URL = "https://hailuoai.com/create/text-to-video"
PHONE_NUMBER = "15781806380"
MAX_CONCURRENT_TASKS = 2  # 海螺 AI 允许的最大并发任务数
POLL_INTERVAL = 5  # 轮询间隔（秒）

# ============ 全局状态 ============
_browser: Optional[Browser] = None
_page: Optional[Page] = None
_context: Optional[BrowserContext] = None
_order_queue: queue.Queue = queue.Queue(maxsize=10)
_is_logged_in = False

# 去重集合：已处理的分享链接
_processed_share_links: Set[str] = set()

# 正在生成中的订单 ID
_generating_orders: Set[int] = set()


# ============ 工具函数 ============

def add_tracking_id(prompt: str, order_id: int) -> str:
    """在提示词末尾添加订单追踪 ID，并提示 AI 忽略"""
    return f"{prompt} (以下内容请忽略，仅用于系统追踪：[#ORD{order_id}])"


def extract_order_id_from_text(text: str) -> Optional[int]:
    """从文本中提取订单追踪 ID"""
    match = re.search(r'\[#ORD(\d+)\]', text)
    return int(match.group(1)) if match else None


def get_clipboard_content(page: Page) -> str:
    """获取剪贴板内容"""
    return page.evaluate("navigator.clipboard.readText()")


def fetch_video_metadata(share_link: str) -> Optional[str]:
    """访问分享链接，提取 meta description 中的提示词"""
    try:
        resp = requests.get(share_link, timeout=10)
        if resp.status_code == 200:
            match = re.search(r'<meta name="description" content="([^"]+)"', resp.text)
            if match:
                return match.group(1)
    except Exception as e:
        print(f"[AUTOMATION] 获取视频元数据失败: {e}")
    return None


def is_new_share_link(link: str) -> bool:
    """检查链接是否是新的（未处理过）"""
    if link in _processed_share_links:
        return False
    _processed_share_links.add(link)
    return True


def get_latest_verification_code_sync() -> Optional[str]:
    """从数据库获取最新未使用的验证码"""
    with Session(engine) as session:
        for _ in range(60):
            statement = select(VerificationCode).where(
                VerificationCode.is_used == False
            ).order_by(VerificationCode.created_at.desc())
            results = session.exec(statement).first()
            if results:
                results.is_used = True
                session.add(results)
                session.commit()
                return results.code
            time.sleep(1)
    return None


# ============ 登录流程 ============

def login_to_hailuo(page: Page) -> bool:
    """执行登录流程"""
    print("[AUTOMATION] 检查登录状态...")
    login_btn = page.locator("div.border-hl_line_00:has-text('登录')").first
    
    if not login_btn.is_visible():
        print("[AUTOMATION] 已登录")
        return True
    
    print("[AUTOMATION] 开始登录流程...")
    login_btn.click()
    page.wait_for_timeout(1000)
    
    # 切换到手机登录
    phone_login_tab = page.locator("#rc-tabs-0-tab-phone")
    if phone_login_tab.is_visible():
        phone_login_tab.click()
        page.wait_for_timeout(500)
        print("[AUTOMATION] 已切换到手机登录")
    
    # 填写手机号
    phone_input = page.locator("input#phone")
    phone_input.fill(PHONE_NUMBER)
    
    # 点击获取验证码
    get_code_btn = page.locator("button:has-text('获取验证码')").first
    get_code_btn.click()
    print("[AUTOMATION] 等待短信验证码...")
    
    # 获取验证码
    code = get_latest_verification_code_sync()
    if not code:
        print("[AUTOMATION] 验证码获取超时")
        return False
    print(f"[AUTOMATION] 收到验证码: {code}")
    
    # 填写验证码
    page.locator("input#code").fill(code)
    
    # 勾选协议
    page.locator("button.rounded-full:has(svg)").first.click()
    
    # 登录
    page.locator("button.login-btn").click()
    print("[AUTOMATION] 登录中...")
    page.wait_for_timeout(5000)
    
    # 验证登录
    try:
        page.locator("#video-create-input [contenteditable='true']").wait_for(
            state="visible", timeout=30000
        )
        print("[AUTOMATION] 登录成功！")
        return True
    except:
        print("[AUTOMATION] 登录失败")
        return False


# ============ 视频生成流程 ============

def submit_video_task(page: Page, order_id: int, prompt: str) -> bool:
    """提交视频生成任务"""
    try:
        # 添加追踪 ID
        prompt_with_id = add_tracking_id(prompt, order_id)
        
        # 填写提示词
        input_area = page.locator("#video-create-input [contenteditable='true']")
        input_area.click()
        input_area.fill(prompt_with_id)
        page.wait_for_timeout(500)
        
        # 点击生成按钮
        generate_btn = page.locator("button.new-color-btn-bg").first
        if generate_btn.is_visible():
            generate_btn.click()
            print(f"[AUTOMATION] 订单 {order_id} 已提交生成")
            _generating_orders.add(order_id)
            
            # 更新订单状态
            with Session(engine) as session:
                order = session.get(VideoOrder, order_id)
                if order:
                    order.status = "generating"
                    session.commit()
            
            return True
    except Exception as e:
        print(f"[AUTOMATION] 提交订单 {order_id} 失败: {e}")
    return False


def scan_for_completed_videos(page: Page):
    """扫描页面上已完成的视频，提取分享链接"""
    try:
        # 获取所有包含提示词的视频卡片
        prompt_spans = page.locator("span.prompt-plain-span").all()
        
        for span in prompt_spans:
            try:
                # 从提示词中提取订单 ID
                prompt_text = span.text_content()
                if not prompt_text:
                    continue
                    
                order_id = extract_order_id_from_text(prompt_text)
                if not order_id:
                    # 不是我们的订单（没有追踪 ID）
                    continue
                
                # 检查订单是否已处理
                with Session(engine) as session:
                    order = session.get(VideoOrder, order_id)
                    if not order or order.status == "completed":
                        continue
                
                # 找到父级视频卡片
                parent = span.locator("xpath=ancestor::div[contains(@class, 'group/video-card')]").first
                
                # 检查是否有进度条（有进度条说明还在生成中）
                progress = parent.locator(".ant-progress-text")
                if progress.is_visible():
                    continue
                
                # 找到分享按钮并点击
                share_btn = parent.locator("div.text-hl_text_00_legacy:has(svg path[d*='M7.84176'])").first
                if not share_btn.is_visible():
                    continue
                    
                share_btn.click()
                page.wait_for_timeout(500)
                
                # 获取剪贴板中的分享链接
                share_link = get_clipboard_content(page)
                
                if not share_link or not share_link.startswith("http"):
                    continue
                
                # 去重检查
                if not is_new_share_link(share_link):
                    continue
                
                print(f"[AUTOMATION] 订单 {order_id} 已完成！链接: {share_link}")
                
                # 更新订单
                with Session(engine) as session:
                    order = session.get(VideoOrder, order_id)
                    if order and order.status != "completed":
                        order.video_url = share_link
                        order.status = "completed"
                        session.commit()
                        _generating_orders.discard(order_id)
                    
            except Exception as e:
                print(f"[AUTOMATION] 处理视频卡片出错: {e}")
                continue
                
    except Exception as e:
        print(f"[AUTOMATION] 扫描视频出错: {e}")


def check_progress(page: Page) -> Dict[int, int]:
    """检查所有生成中任务的进度，返回 {order_id: progress%}"""
    progress_map = {}
    try:
        progress_elements = page.locator(".ant-progress-text").all()
        for elem in progress_elements:
            text = elem.text_content()
            if text and "%" in text:
                progress = int(text.replace("%", ""))
                # 这里无法直接获取订单 ID，只能返回进度列表
                # 后续可以通过父元素找到对应的提示词来匹配
    except:
        pass
    return progress_map


# ============ 主工作循环 ============

def automation_worker():
    """主工作线程"""
    global _browser, _page, _context, _is_logged_in
    
    print("[AUTOMATION] 启动自动化工作线程...")
    
    with sync_playwright() as p:
        # 启动浏览器
        try:
            _browser = p.chromium.launch(headless=False, channel="chrome")
            print("[AUTOMATION] Chrome 启动成功")
        except Exception as e:
            print(f"[AUTOMATION] Chrome 未找到，使用 Chromium: {e}")
            _browser = p.chromium.launch(headless=False)
        
        _context = _browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={"width": 1280, "height": 720},
            ignore_https_errors=True,
            # 预先授予权限，避免弹窗阻塞
            permissions=["clipboard-read", "clipboard-write"]
        )
        _page = _context.new_page()
        
        try:
            # 打开海螺 AI
            print("[AUTOMATION] 正在打开海螺 AI...")
            _page.goto(HAILUO_URL, timeout=60000, wait_until="domcontentloaded")
            _page.wait_for_timeout(3000)
            
            # 登录
            _is_logged_in = login_to_hailuo(_page)
            if not _is_logged_in:
                print("[AUTOMATION] 登录失败，停止工作")
                return
            
            print("[AUTOMATION] 开始处理订单...")
            
            # 主循环
            while True:
                print(f"[DEBUG] 循环开始，队列大小: {_order_queue.qsize()}, 生成中: {len(_generating_orders)}")
                
                # 1. 扫描已完成的视频
                print("[DEBUG] 开始扫描视频...")
                scan_for_completed_videos(_page)
                print("[DEBUG] 扫描完成")
                
                # 2. 提交新订单（如果并发数未满）
                while len(_generating_orders) < MAX_CONCURRENT_TASKS:
                    try:
                        order_id = _order_queue.get_nowait()
                        print(f"[DEBUG] 取出订单: {order_id}")
                        
                        # 获取订单信息
                        with Session(engine) as session:
                            order = session.get(VideoOrder, order_id)
                            if order:
                                submit_video_task(_page, order_id, order.prompt)
                        
                        _order_queue.task_done()
                    except queue.Empty:
                        break
                
                # 3. 等待下一轮轮询
                print(f"[DEBUG] 等待 {POLL_INTERVAL} 秒...")
                time.sleep(POLL_INTERVAL)
                
        except Exception as e:
            print(f"[AUTOMATION] 工作线程异常: {e}")
        finally:
            _browser.close()


def start_automation_worker():
    """启动自动化工作线程"""
    worker_thread = threading.Thread(target=automation_worker, daemon=True)
    worker_thread.start()
    print("[AUTOMATION] 工作线程已启动")


def queue_order(order_id: int) -> bool:
    """将订单加入队列"""
    if _order_queue.full():
        print(f"[AUTOMATION] 队列已满，拒绝订单 {order_id}")
        return False
    _order_queue.put(order_id)
    print(f"[AUTOMATION] 订单 {order_id} 已加入队列 ({_order_queue.qsize()}/10)")
    return True


async def run_hailuo_task(order_id: int) -> bool:
    """异步接口：将订单加入队列"""
    return queue_order(order_id)
