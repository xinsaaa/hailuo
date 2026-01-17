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
import os
HAILUO_URL = "https://hailuoai.com/create/text-to-video"
PHONE_NUMBER = os.getenv("HAILUO_PHONE", "17366935232")
MAX_CONCURRENT_TASKS = 2  # 海螺 AI 允许的最大并发任务数
POLL_INTERVAL = 5  # 轮询间隔（秒）

# ============ 日志收集系统 ============
from collections import deque
from datetime import datetime

class AutomationLogger:
    """自动化服务日志收集器"""
    def __init__(self, max_logs: int = 100):
        self._logs = deque(maxlen=max_logs)
        self._lock = threading.Lock()
    
    def log(self, level: str, message: str):
        """记录日志"""
        with self._lock:
            entry = {
                "time": datetime.now().strftime("%H:%M:%S"),
                "level": level,
                "message": message
            }
            self._logs.append(entry)
            # 同时打印到控制台
            print(f"[AUTOMATION][{level}] {message}")
    
    def info(self, message: str):
        self.log("INFO", message)
    
    def warn(self, message: str):
        self.log("WARN", message)
    
    def error(self, message: str):
        self.log("ERROR", message)
    
    def success(self, message: str):
        self.log("SUCCESS", message)
    
    def get_logs(self, limit: int = 50) -> list:
        """获取最近的日志"""
        with self._lock:
            logs = list(self._logs)
            return logs[-limit:] if len(logs) > limit else logs
    
    def clear(self):
        """清空日志"""
        with self._lock:
            self._logs.clear()

# 全局日志实例
automation_logger = AutomationLogger()

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
    try:
        return page.evaluate("navigator.clipboard.readText()")
    except Exception as e:
        print(f"[AUTOMATION] 剪贴板读取失败 (可能是headless模式): {e}")
        # 在headless模式下，尝试其他方法获取分享链接
        try:
            # 尝试获取页面上最后一个分享链接
            return page.evaluate("""
                () => {
                    const shareButtons = document.querySelectorAll('[data-share-url]');
                    if (shareButtons.length > 0) {
                        return shareButtons[shareButtons.length - 1].getAttribute('data-share-url');
                    }
                    return null;
                }
            """)
        except:
            return ""


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


# ============ 登录状态管理 ============

def save_login_state(page: Page):
    """保存登录状态（cookies和localStorage）"""
    try:
        import json
        import os
        
        # 创建状态保存目录
        state_dir = "login_state"
        os.makedirs(state_dir, exist_ok=True)
        
        # 保存cookies
        cookies = page.context.cookies()
        with open(f"{state_dir}/cookies.json", "w") as f:
            json.dump(cookies, f)
        
        # 保存localStorage
        local_storage = page.evaluate("() => JSON.stringify(localStorage)")
        with open(f"{state_dir}/localStorage.json", "w") as f:
            f.write(local_storage)
            
        automation_logger.success("💾 登录状态已保存")
        
    except Exception as e:
        automation_logger.warn(f"⚠️  保存登录状态失败: {str(e)[:100]}")


def restore_login_state(page: Page) -> bool:
    """恢复登录状态"""
    try:
        import json
        import os
        
        state_dir = "login_state"
        
        # 检查状态文件是否存在
        if not (os.path.exists(f"{state_dir}/cookies.json") and 
                os.path.exists(f"{state_dir}/localStorage.json")):
            automation_logger.info("ℹ️  未找到保存的登录状态")
            return False
        
        automation_logger.info("🔄 正在恢复登录状态...")
        
        # 恢复cookies
        with open(f"{state_dir}/cookies.json", "r") as f:
            cookies = json.load(f)
        
        page.context.add_cookies(cookies)
        automation_logger.success("🍪 Cookies已恢复")
        
        # 恢复localStorage
        with open(f"{state_dir}/localStorage.json", "r") as f:
            local_storage_data = f.read()
        
        page.evaluate(f"""
            const data = {local_storage_data};
            for (const [key, value] of Object.entries(data)) {{
                localStorage.setItem(key, value);
            }}
        """)
        automation_logger.success("💾 localStorage已恢复")
        
        return True
        
    except Exception as e:
        automation_logger.warn(f"⚠️  恢复登录状态失败: {str(e)[:100]}")
        return False


def check_login_status(page: Page) -> bool:
    """检查当前页面的登录状态"""
    try:
        automation_logger.info("🔍 检查登录状态...")
        
        # 等待页面稳定
        page.wait_for_timeout(2000)
        
        # 方法1: 检查是否存在登录按钮
        try:
            login_btn = page.locator("div.border-hl_line_00:has-text('登录')").first
            login_btn.wait_for(state="visible", timeout=3000)
            automation_logger.info("❌ 发现登录按钮，未登录状态")
            return False
        except:
            # 没有找到登录按钮，可能已登录
            pass
        
        # 方法2: 检查视频创建输入框
        try:
            create_input = page.locator("#video-create-input [contenteditable='true']")
            create_input.wait_for(state="visible", timeout=5000)
            automation_logger.success("✅ 确认已登录状态")
            return True
        except:
            automation_logger.info("❓ 登录状态不明确")
            return False
            
    except Exception as e:
        automation_logger.warn(f"⚠️  检查登录状态出错: {str(e)[:100]}")
        return False


def clear_login_state():
    """清除保存的登录状态"""
    try:
        import os
        import shutil
        
        state_dir = "login_state"
        if os.path.exists(state_dir):
            shutil.rmtree(state_dir)
            automation_logger.info("🗑️  已清除登录状态")
    except Exception as e:
        automation_logger.warn(f"⚠️  清除登录状态失败: {str(e)[:100]}")


# ============ 登录流程 ============

def login_to_hailuo(page: Page) -> bool:
    """执行登录流程"""
    try:
        automation_logger.info("🔍 检查当前登录状态...")
        # 等待页面稳定
        automation_logger.info("⏳ 等待页面稳定 (2秒)...")
        page.wait_for_timeout(2000)
        
        # 检查登录按钮
        automation_logger.info("🔍 查找登录按钮...")
        login_btn = page.locator("div.border-hl_line_00:has-text('登录')").first
        
        # 增加等待时间确保元素加载
        try:
            automation_logger.info("⏳ 等待登录按钮元素加载...")
            login_btn.wait_for(state="visible", timeout=10000)
            is_login_btn_visible = login_btn.is_visible()
            automation_logger.info("✅ 登录按钮检测完成")
        except:
            automation_logger.info("ℹ️  未找到登录按钮，可能已登录")
            is_login_btn_visible = False
        
        if not is_login_btn_visible:
            automation_logger.info("🔍 验证登录状态...")
            # 检查是否真的已登录（通过检查其他元素）
            try:
                automation_logger.info("🎬 查找视频创建入口...")
                create_btn = page.locator("#video-create-input").first
                create_btn.wait_for(state="visible", timeout=5000)
                automation_logger.success("✅ 确认已登录状态")
                return True
            except:
                automation_logger.warn("⚠️  页面状态未知，继续登录流程")
                pass
        
        automation_logger.info("🔐 开始执行登录流程...")
        automation_logger.info("👆 点击登录按钮...")
        login_btn.click()
        page.wait_for_timeout(1000)
        
        # 切换到手机登录
        automation_logger.info("📱 查找手机登录选项...")
        phone_login_tab = page.locator("#rc-tabs-0-tab-phone")
        if phone_login_tab.is_visible():
            automation_logger.info("👆 切换到手机号登录...")
            phone_login_tab.click()
            page.wait_for_timeout(500)
            automation_logger.success("✅ 已切换到手机登录模式")
        else:
            automation_logger.info("ℹ️  默认为手机登录模式")
        
        # 填写手机号
        automation_logger.info(f"📝 填写手机号: {PHONE_NUMBER}")
        phone_input = page.locator("input#phone")
        phone_input.fill(PHONE_NUMBER)
        automation_logger.success("✅ 手机号填写完成")
        
        # 点击获取验证码
        automation_logger.info("📨 请求短信验证码...")
        get_code_btn = page.locator("button:has-text('获取验证码')").first
        get_code_btn.click()
        automation_logger.info("⏳ 验证码已发送，等待接收...")
        
        # 获取验证码
        automation_logger.info("🔍 从数据库查找验证码...")
        code = get_latest_verification_code_sync()
        if not code:
            automation_logger.error("❌ 验证码获取超时，请确保短信正常接收")
            return False
        automation_logger.success(f"✅ 验证码获取成功: {code}")
        
        # 填写验证码
        automation_logger.info("📝 填写验证码...")
        page.locator("input#code").fill(code)
        automation_logger.success("✅ 验证码填写完成")
        
        # 勾选协议
        automation_logger.info("☑️  勾选用户协议...")
        page.locator("button.rounded-full:has(svg)").first.click()
        automation_logger.success("✅ 用户协议已勾选")
        
        # 登录
        automation_logger.info("🚀 提交登录请求...")
        page.locator("button.login-btn").click()
        automation_logger.info("⏳ 等待登录验证...")
        page.wait_for_timeout(5000)
        
        # 验证登录
        automation_logger.info("🔍 验证登录结果...")
        try:
            page.locator("#video-create-input [contenteditable='true']").wait_for(
                state="visible", timeout=30000
            )
            automation_logger.success("🎉 登录验证成功！")
            
            # 保存登录状态
            automation_logger.info("💾 保存登录状态以便下次使用...")
            save_login_state(page)
            
            return True
        except:
            automation_logger.error("❌ 登录验证失败")
            return False
            
    except Exception as e:
        automation_logger.error(f"💥 登录流程异常: {str(e)[:200]}")
        return False


# ============ 视频生成流程 ============

def submit_video_task(page: Page, order_id: int, prompt: str) -> bool:
    """提交视频生成任务"""
    try:
        automation_logger.info(f"🎬 开始提交视频任务 (订单#{order_id})")
        
        # 添加追踪 ID
        automation_logger.info("🏷️  添加订单追踪标识...")
        prompt_with_id = add_tracking_id(prompt, order_id)
        automation_logger.info(f"📝 最终提示词: {prompt_with_id[:100]}...")
        
        # 填写提示词
        automation_logger.info("🎯 定位输入框...")
        input_area = page.locator("#video-create-input [contenteditable='true']")
        automation_logger.info("👆 点击输入框...")
        input_area.click()
        automation_logger.info("📝 填写提示词...")
        input_area.fill(prompt_with_id)
        automation_logger.info("⏳ 等待输入完成...")
        page.wait_for_timeout(500)
        automation_logger.success("✅ 提示词填写完成")
        
        # 点击生成按钮
        automation_logger.info("🔍 查找生成按钮...")
        generate_btn = page.locator("button.new-color-btn-bg").first
        if generate_btn.is_visible():
            automation_logger.info("🚀 点击生成按钮...")
            generate_btn.click()
            automation_logger.success(f"✅ 订单#{order_id}已成功提交生成")
            
            automation_logger.info("📊 更新内存状态...")
            _generating_orders.add(order_id)
            
            # 更新订单状态
            automation_logger.info("💾 更新数据库状态...")
            with Session(engine) as session:
                order = session.get(VideoOrder, order_id)
                if order:
                    order.status = "generating"
                    session.commit()
                    automation_logger.success("✅ 订单状态已更新为'generating'")
                else:
                    automation_logger.warn(f"⚠️  订单#{order_id}在数据库中不存在")
            
            automation_logger.success(f"🎉 任务提交完成! 当前生成中: {len(_generating_orders)}个")
            return True
        else:
            automation_logger.error("❌ 未找到生成按钮")
            return False
    except Exception as e:
        automation_logger.error(f"💥 提交订单#{order_id}失败: {str(e)[:200]}")
        return False


def scan_for_completed_videos(page: Page):
    """扫描页面上已完成的视频，提取分享链接"""
    try:
        automation_logger.info("🔍 开始扫描已完成的视频...")
        
        # 获取所有包含提示词的视频卡片
        automation_logger.info("📋 查找所有视频卡片...")
        prompt_spans = page.locator("span.prompt-plain-span").all()
        automation_logger.info(f"📊 找到{len(prompt_spans)}个视频卡片")
        
        completed_count = 0
        processing_count = 0
        
        for i, span in enumerate(prompt_spans):
            try:
                automation_logger.info(f"🔍 检查第{i+1}个视频卡片...")
                
                # 从提示词中提取订单 ID
                prompt_text = span.text_content()
                if not prompt_text:
                    automation_logger.info("⭐ 跳过：无提示词内容")
                    continue
                
                automation_logger.info(f"📝 提示词内容: {prompt_text[:50]}...")
                order_id = extract_order_id_from_text(prompt_text)
                if not order_id:
                    automation_logger.info("⭐ 跳过：非平台订单（无追踪ID）")
                    continue
                
                automation_logger.info(f"🎯 发现平台订单#{order_id}")
                
                # 检查订单是否已处理
                with Session(engine) as session:
                    order = session.get(VideoOrder, order_id)
                    if not order:
                        automation_logger.warn(f"⚠️  订单#{order_id}在数据库中不存在")
                        continue
                    if order.status == "completed":
                        automation_logger.info(f"✅ 订单#{order_id}已完成，跳过")
                        continue
                
                automation_logger.info(f"📹 检查订单#{order_id}生成状态...")
                
                # 找到父级视频卡片
                parent = span.locator("xpath=ancestor::div[contains(@class, 'group/video-card')]").first
                
                # 检查是否有进度条（有进度条说明还在生成中）
                progress = parent.locator(".ant-progress-text")
                if progress.is_visible():
                    progress_text = progress.text_content() or "0%"
                    automation_logger.info(f"⏳ 订单#{order_id}仍在生成中 (进度: {progress_text})")
                    processing_count += 1
                    continue
                
                automation_logger.success(f"✅ 订单#{order_id}生成完成，准备提取分享链接")
                
                # 找到分享按钮并点击
                automation_logger.info("🔍 查找分享按钮...")
                share_btn = parent.locator("div.text-hl_text_00_legacy:has(svg path[d*='M7.84176'])").first
                if not share_btn.is_visible():
                    automation_logger.warn("⚠️  未找到分享按钮")
                    continue
                
                automation_logger.info("👆 点击分享按钮...")
                share_btn.click()
                automation_logger.info("⏳ 等待分享菜单...")
                page.wait_for_timeout(500)
                
                # 获取剪贴板中的分享链接
                automation_logger.info("📋 获取剪贴板内容...")
                share_link = get_clipboard_content(page)
                
                if not share_link or not share_link.startswith("http"):
                    automation_logger.warn("⚠️  获取分享链接失败或格式异常")
                    continue
                
                automation_logger.info(f"🔗 获取到分享链接: {share_link[:50]}...")
                
                # 去重检查
                automation_logger.info("🔍 检查链接唯一性...")
                if not is_new_share_link(share_link):
                    automation_logger.warn("⚠️  链接已存在，跳过重复处理")
                    continue
                
                automation_logger.success(f"🎉 订单#{order_id}处理完成！")
                automation_logger.info(f"🔗 分享链接: {share_link}")
                
                # 更新订单
                automation_logger.info("💾 更新数据库订单状态...")
                with Session(engine) as session:
                    order = session.get(VideoOrder, order_id)
                    if order and order.status != "completed":
                        order.video_url = share_link
                        order.status = "completed"
                        session.commit()
                        automation_logger.success("✅ 数据库状态已更新为'completed'")
                        
                        automation_logger.info("📊 更新内存状态...")
                        _generating_orders.discard(order_id)
                        automation_logger.success(f"✅ 订单#{order_id}从生成列表中移除")
                        
                        completed_count += 1
                    else:
                        automation_logger.warn(f"⚠️  订单#{order_id}状态异常")
                    
            except Exception as e:
                automation_logger.error(f"💥 处理视频卡片出错: {str(e)[:150]}")
                continue
        
        if completed_count > 0:
            automation_logger.success(f"🎉 本次扫描完成 {completed_count} 个视频")
        if processing_count > 0:
            automation_logger.info(f"⏳ 仍有 {processing_count} 个视频在生成中")
        if completed_count == 0 and processing_count == 0:
            automation_logger.info("📭 暂无需要处理的视频")
                
    except Exception as e:
        automation_logger.error(f"💥 扫描视频失败: {str(e)[:200]}")


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
    
    automation_logger.info("🚀 启动自动化工作线程...")
    automation_logger.info("📋 初始化系统环境...")
    
    # Windows 兼容性修复
    import asyncio
    import sys
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        automation_logger.info("⚙️  Windows异步策略已设置")
    
    automation_logger.info("🎭 正在初始化Playwright...")
    with sync_playwright() as p:
        # 启动浏览器
        # 检测是否为无界面环境
        import os
        import sys
        
        # 环境变量控制或系统检测
        automation_logger.info("🔍 检测运行环境...")
        force_headless = os.getenv("AUTOMATION_HEADLESS", "").lower() in ["true", "1", "yes"]
        is_linux_server = sys.platform.startswith("linux") and not os.getenv("DISPLAY")
        use_headless = force_headless or is_linux_server
        
        if force_headless:
            automation_logger.info("🎛️  环境变量强制启用无界面模式")
        elif is_linux_server:
            automation_logger.info("🐧 检测到Linux无界面环境，自动启用headless模式")
        else:
            automation_logger.info("🖥️  有界面环境，启用可视化模式")
        
        automation_logger.info("⚙️  配置浏览器优化参数...")
        # 浏览器稳定性优化参数
        browser_args = [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-extensions",
            "--disable-background-timer-throttling",
            "--disable-renderer-backgrounding", 
            "--disable-backgrounding-occluded-windows",
            "--disable-features=TranslateUI,VizDisplayCompositor",
            "--disable-ipc-flooding-protection",
            "--disable-default-apps",
            "--disable-sync",
            "--disable-component-extensions-with-background-pages",
            "--disable-background-networking",
            "--memory-pressure-off",
            "--max_old_space_size=4096"
        ]
        
        if use_headless:
            browser_args.extend([
                "--virtual-time-budget=5000"
            ])
            automation_logger.info("🔧 添加无界面模式专用参数")
        
        automation_logger.info(f"📝 浏览器参数配置完成，共{len(browser_args)}个优化参数")
        
        automation_logger.info("🚀 正在启动浏览器...")
        try:
            _browser = p.chromium.launch(
                headless=use_headless,
                channel="chrome" if not use_headless else None,
                args=browser_args
            )
            automation_logger.success(f"✅ 浏览器启动成功 ({'无界面' if use_headless else '有界面'}模式)")
        except Exception as e:
            automation_logger.warn(f"⚠️  Chrome未找到，尝试使用Chromium: {str(e)[:100]}")
            try:
                _browser = p.chromium.launch(
                    headless=use_headless,
                    args=browser_args
                )
                automation_logger.success(f"✅ Chromium启动成功 ({'无界面' if use_headless else '有界面'}模式)")
            except Exception as e2:
                automation_logger.error(f"❌ 浏览器启动失败: {e2}")
                return
        
        automation_logger.info("🌐 创建浏览器上下文...")
        _context = _browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={"width": 1280, "height": 720},
            ignore_https_errors=True,
            # 预先授予权限，避免弹窗阻塞
            permissions=["clipboard-read", "clipboard-write"]
        )
        automation_logger.success("✅ 浏览器上下文创建成功")
        
        automation_logger.info("📄 创建新页面...")
        _page = _context.new_page()
        automation_logger.success("✅ 页面创建成功")
        
        try:
            # 打开海螺 AI (带重试机制)
            automation_logger.info("🌍 开始访问海螺AI网站...")
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    automation_logger.info(f"🔄 正在打开海螺 AI... (尝试 {attempt + 1}/{max_retries})")
                    automation_logger.info(f"🔗 目标URL: {HAILUO_URL}")
                    
                    _page.goto(HAILUO_URL, timeout=30000, wait_until="domcontentloaded")
                    automation_logger.info("⏳ 等待页面DOM加载完成...")
                    _page.wait_for_timeout(5000)
                    
                    automation_logger.info("🔍 验证页面加载状态...")
                    # 检查页面是否正常加载
                    page_title = _page.title()
                    automation_logger.info(f"📋 页面标题: {page_title}")
                    
                    if page_title and "海螺" in page_title:
                        automation_logger.success("✅ 页面加载成功！")
                        break
                    else:
                        automation_logger.warn(f"⚠️  页面标题异常，可能加载不完整")
                        if attempt < max_retries - 1:
                            automation_logger.info("🔄 准备重新加载页面...")
                            continue
                        
                except Exception as e:
                    automation_logger.error(f"❌ 页面加载失败 (尝试 {attempt + 1}): {str(e)[:150]}")
                    if attempt < max_retries - 1:
                        automation_logger.info("⏰ 等待3秒后重试...")
                        _page.wait_for_timeout(3000)
                        # 尝试刷新页面
                        try:
                            automation_logger.info("🔄 尝试刷新页面...")
                            _page.reload(timeout=20000)
                            automation_logger.info("⏳ 等待刷新完成...")
                            _page.wait_for_timeout(3000)
                        except Exception as reload_e:
                            automation_logger.warn(f"⚠️  页面刷新失败: {str(reload_e)[:100]}")
                        continue
                    else:
                        automation_logger.error(f"💥 页面加载最终失败，已重试 {max_retries} 次")
                        raise Exception(f"页面加载失败，已重试 {max_retries} 次")
            
            # 智能登录流程
            automation_logger.info("🔐 开始智能登录流程...")
            
            # 步骤1: 尝试恢复之前的登录状态
            automation_logger.info("🔄 尝试恢复之前的登录状态...")
            login_restored = restore_login_state(_page)
            
            if login_restored:
                # 刷新页面以应用恢复的状态
                automation_logger.info("🔄 刷新页面以应用登录状态...")
                _page.reload(timeout=20000)
                _page.wait_for_timeout(3000)
                
                # 检查恢复后的登录状态
                if check_login_status(_page):
                    automation_logger.success("✅ 登录状态恢复成功，跳过登录流程")
                    _is_logged_in = True
                else:
                    automation_logger.warn("⚠️  登录状态已过期，需要重新登录")
                    clear_login_state()  # 清除无效的状态
                    _is_logged_in = False
            else:
                automation_logger.info("ℹ️  无可用的登录状态，准备执行登录")
                _is_logged_in = False
            
            # 步骤2: 如果状态恢复失败，执行完整登录流程
            if not _is_logged_in:
                automation_logger.info("🔐 执行完整登录流程...")
                _is_logged_in = login_to_hailuo(_page)
                
            if not _is_logged_in:
                automation_logger.error("❌ 登录失败，自动化服务停止")
                return
            
            automation_logger.success("🎉 登录成功！自动化服务就绪")
            automation_logger.info("📦 初始化订单处理系统...")
            automation_logger.info(f"⚡ 最大并发任务数: {MAX_CONCURRENT_TASKS}")
            automation_logger.info(f"⏱️  轮询间隔: {POLL_INTERVAL}秒")
            automation_logger.info(f"📱 使用手机号: {PHONE_NUMBER}")
            automation_logger.success("✅ 订单处理系统初始化完成")
            
            # 主循环
            automation_logger.info("🔄 启动主处理循环...")
            consecutive_errors = 0
            max_consecutive_errors = 3
            loop_count = 0
            
            while True:
                try:
                    loop_count += 1
                    automation_logger.info(f"🔁 第{loop_count}次循环 | 队列: {_order_queue.qsize()}个订单 | 处理中: {len(_generating_orders)}个任务")
                    
                    # 检查页面是否还活着
                    automation_logger.info("🔍 检查页面存活状态...")
                    try:
                        page_title = _page.title()  # 简单的页面检查
                        automation_logger.info(f"✅ 页面正常 (标题: {page_title[:30]}...)")
                    except Exception as e:
                        automation_logger.warn(f"⚠️  页面异常，尝试重新加载: {str(e)[:100]}")
                        try:
                            automation_logger.info("🔄 正在重新加载页面...")
                            _page.reload(timeout=20000)
                            _page.wait_for_timeout(3000)
                            automation_logger.success("✅ 页面重新加载成功")
                        except Exception as reload_e:
                            automation_logger.error(f"❌ 页面重新加载失败: {str(reload_e)[:100]}")
                            raise Exception("页面无法恢复")
                    
                    # 1. 扫描已完成的视频
                    automation_logger.info("📹 开始扫描已完成的视频...")
                    try:
                        scan_result = scan_for_completed_videos(_page)
                        automation_logger.success("✅ 视频扫描完成")
                    except Exception as e:
                        automation_logger.error(f"❌ 扫描视频失败: {str(e)[:150]}")
                        consecutive_errors += 1
                        if consecutive_errors >= max_consecutive_errors:
                            automation_logger.error(f"💥 连续失败 {consecutive_errors} 次，停止工作")
                            raise Exception(f"连续失败 {consecutive_errors} 次，停止工作")
                        automation_logger.warn(f"⚠️  跳过此次扫描，错误计数: {consecutive_errors}/{max_consecutive_errors}")
                        continue
                    
                    # 2. 提交新订单（如果并发数未满）
                    available_slots = MAX_CONCURRENT_TASKS - len(_generating_orders)
                    if available_slots > 0:
                        automation_logger.info(f"📤 检查新订单提交 (可用槽位: {available_slots})")
                        submitted_count = 0
                        
                        while len(_generating_orders) < MAX_CONCURRENT_TASKS:
                            try:
                                order_id = _order_queue.get_nowait()
                                automation_logger.info(f"📝 取出订单: #{order_id}")
                                
                                # 获取订单信息
                                with Session(engine) as session:
                                    order = session.get(VideoOrder, order_id)
                                    if order:
                                        automation_logger.info(f"🎬 提交视频任务: {order.prompt[:50]}...")
                                        submit_video_task(_page, order_id, order.prompt)
                                        submitted_count += 1
                                        automation_logger.success(f"✅ 订单#{order_id}提交成功")
                                    else:
                                        automation_logger.warn(f"⚠️  订单#{order_id}不存在")
                                
                                _order_queue.task_done()
                            except queue.Empty:
                                if submitted_count == 0:
                                    automation_logger.info("📭 暂无新订单需要处理")
                                break
                            except Exception as e:
                                automation_logger.error(f"❌ 提交订单失败: {str(e)[:150]}")
                                consecutive_errors += 1
                                break
                        
                        if submitted_count > 0:
                            automation_logger.success(f"🎉 本轮提交了{submitted_count}个新任务")
                    else:
                        automation_logger.info(f"⏸️  所有任务槽位已满 ({len(_generating_orders)}/{MAX_CONCURRENT_TASKS})")
                    
                    # 如果到这里没有异常，重置错误计数
                    if consecutive_errors > 0:
                        automation_logger.success(f"🔄 错误恢复成功，重置错误计数 ({consecutive_errors} -> 0)")
                        consecutive_errors = 0
                    
                    # 3. 等待下一轮轮询
                    automation_logger.info(f"⏰ 等待{POLL_INTERVAL}秒进入下一轮循环...")
                    time.sleep(POLL_INTERVAL)
                    
                except Exception as loop_e:
                    consecutive_errors += 1
                    automation_logger.error(f"💥 主循环异常 (第{consecutive_errors}次): {str(loop_e)[:200]}")
                    if consecutive_errors >= max_consecutive_errors:
                        automation_logger.error(f"🛑 连续失败 {consecutive_errors} 次，自动化服务停止")
                        break
                    wait_time = POLL_INTERVAL * 2
                    automation_logger.warn(f"⏰ 等待{wait_time}秒后重试...")
                    time.sleep(wait_time)
                
        except Exception as e:
            automation_logger.error(f"💥 工作线程发生严重异常: {str(e)[:300]}")
            automation_logger.error("🛑 自动化服务异常停止")
        finally:
            automation_logger.info("🧹 清理资源...")
            try:
                if _browser:
                    _browser.close()
                    automation_logger.success("✅ 浏览器资源已释放")
            except:
                automation_logger.warn("⚠️  浏览器资源清理失败")
            automation_logger.info("👋 自动化工作线程已退出")


def start_automation_worker():
    """启动自动化工作线程"""
    automation_logger.info("🎬 准备启动自动化工作线程...")
    worker_thread = threading.Thread(target=automation_worker, daemon=True)
    worker_thread.start()
    automation_logger.success("🚀 自动化工作线程已启动！")
    automation_logger.info("📊 可以在管理后台查看实时日志")


def queue_order(order_id: int) -> bool:
    """将订单加入队列"""
    if _order_queue.full():
        automation_logger.warn(f"⚠️  订单队列已满，拒绝订单 #{order_id}")
        return False
    _order_queue.put(order_id)
    current_size = _order_queue.qsize()
    automation_logger.success(f"📥 订单#{order_id}已加入队列 ({current_size}/10)")
    return True


async def run_hailuo_task(order_id: int) -> bool:
    """异步接口：将订单加入队列"""
    return queue_order(order_id)
