"""
即梦 (Seedance) Playwright 自动化
登录：扫码登录，二维码截图返回给前端展示
定位原则：语义定位优先，不依赖动态 class
"""
import asyncio
import base64
import os
import json
import time
import re
from typing import Optional
from playwright.async_api import async_playwright, Page, BrowserContext

JIMENG_URL = "https://jimeng.jianying.com/ai-tool/home"
JIMENG_VIDEO_URL = "https://jimeng.jianying.com/ai-tool/generate?type=video"
DEBUG_DIR = os.path.join(os.path.dirname(__file__), "jimeng_debug")

os.makedirs(DEBUG_DIR, exist_ok=True)

# 即梦订单追踪标识（与海螺 automation.py 保持一致的机制）
JIMENG_ORDER_TAG_PREFIX = "#JMORD"

def add_jimeng_tracking_id(prompt: str, order_id: int) -> str:
    """在提示词末尾添加即梦订单追踪ID"""
    return f"{prompt} (以下内容请忽略，仅用于系统追踪：[{JIMENG_ORDER_TAG_PREFIX}{order_id}])"

def extract_jimeng_order_id(text: str) -> Optional[int]:
    """从文本中提取即梦订单追踪ID"""
    match = re.search(r'\[' + JIMENG_ORDER_TAG_PREFIX + r'(\d+)\]', text)
    return int(match.group(1)) if match else None


def _debug_path(name: str) -> str:
    ts = int(time.time())
    return os.path.join(DEBUG_DIR, f"{ts}_{name}.png")


class JimengLoginSession:
    """单次扫码登录会话，供 API 轮询使用"""

    def __init__(self, account_id: str):
        self.account_id = account_id
        self.qr_base64: Optional[str] = None       # 二维码图片 base64
        self.status: str = "pending"               # pending / scanning / success / failed / timeout
        self.cookie: Optional[str] = None          # 登录成功后的 cookie
        self.error: Optional[str] = None
        self._task: Optional[asyncio.Task] = None

    def start(self):
        self._task = asyncio.create_task(self._run())

    def cancel(self):
        if self._task and not self._task.done():
            self._task.cancel()

    async def _run(self):
        try:
            await self._do_login()
        except asyncio.CancelledError:
            self.status = "failed"
            self.error = "已取消"
        except Exception as e:
            self.status = "failed"
            self.error = str(e)
            print(f"[JIMENG-LOGIN] 登录会话异常: {e}")

    async def _do_login(self):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            try:
                # ===== 步骤 1：打开首页 =====
                print(f"[JIMENG-LOGIN] [{self.account_id}] 步骤1: 打开首页")
                await page.goto(JIMENG_URL, wait_until="domcontentloaded")
                await page.screenshot(path=_debug_path("01_homepage"))

                # ===== 步骤 2：点击登录按钮 =====
                print(f"[JIMENG-LOGIN] [{self.account_id}] 步骤2: 点击登录按钮")
                await page.get_by_text("登录", exact=True).click()
                await page.wait_for_timeout(500)
                await page.screenshot(path=_debug_path("02_after_login_click"))

                # ===== 步骤 3：点击同意按钮（用户协议弹窗）=====
                print(f"[JIMENG-LOGIN] [{self.account_id}] 步骤3: 点击同意按钮")
                agree_btn = page.get_by_role("button", name="同意", exact=True)
                await agree_btn.wait_for(state="visible", timeout=10000)
                await page.screenshot(path=_debug_path("03_agree_dialog"))

                # ===== 步骤 4：监听弹出窗口，再点击同意 =====
                print(f"[JIMENG-LOGIN] [{self.account_id}] 步骤4: 监听popup，点击同意")
                popup_promise = page.wait_for_event("popup")
                await agree_btn.click()
                auth_page: Page = await asyncio.wait_for(popup_promise, timeout=15)
                await auth_page.wait_for_load_state("networkidle")
                await asyncio.sleep(1)
                await auth_page.screenshot(path=_debug_path("04_auth_popup"))

                # ===== 步骤 5：截取二维码图片 =====
                print(f"[JIMENG-LOGIN] [{self.account_id}] 步骤5: 截取二维码")
                # 等待二维码图片加载（最多等待 30 秒）
                qr_img = auth_page.locator("img.semi-image-img").first
                try:
                    await qr_img.wait_for(state="visible", timeout=30000)
                except Exception:
                    await auth_page.screenshot(path=_debug_path("05_qr_not_found"))
                    self.status = "failed"
                    self.error = "未找到二维码图片"
                    return
                await auth_page.screenshot(path=_debug_path("05_qr_page"))

                qr_bytes = await qr_img.screenshot()
                self.qr_base64 = base64.b64encode(qr_bytes).decode()
                self.status = "pending"  # 二维码已就绪，等待用户扫码
                print(f"[JIMENG-LOGIN] [{self.account_id}] 二维码已就绪，等待用户扫码")

                # ===== 步骤 6：等待 popup 关闭（扫码成功）=====
                # 最多等 3 分钟
                try:
                    await asyncio.wait_for(auth_page.wait_for_event("close"), timeout=180)
                except asyncio.TimeoutError:
                    self.status = "timeout"
                    self.error = "二维码已过期，请重新发起登录"
                    await auth_page.screenshot(path=_debug_path("06_qr_timeout"))
                    return

                print(f"[JIMENG-LOGIN] [{self.account_id}] 步骤6: popup已关闭，等待主页登录态")
                await page.wait_for_timeout(500)
                await page.screenshot(path=_debug_path("06_popup_closed"))

                # ===== 步骤 7：等待头像出现，判定登录成功 =====
                print(f"[JIMENG-LOGIN] [{self.account_id}] 步骤7: 检测头像登录态")
                avatar = page.locator("img.dreamina-component-avatar")
                try:
                    await avatar.wait_for(state="visible", timeout=15000)
                except Exception:
                    await page.screenshot(path=_debug_path("07_avatar_not_found"))
                    self.status = "failed"
                    self.error = "登录后未检测到用户头像，可能登录失败"
                    return

                await page.screenshot(path=_debug_path("07_logged_in"))

                # ===== 步骤 8：关闭可能的"绑定剪映账号"弹窗 =====
                print(f"[JIMENG-LOGIN] [{self.account_id}] 步骤8: 检查并关闭弹窗")
                try:
                    # 检测"绑定剪映账号"弹窗（class 前缀: bind-capcut-account-first-screen-modal-content）
                    bind_modal = page.locator("[class*='bind-capcut-account-first-screen-modal-content']")
                    if await bind_modal.count() > 0:
                        print(f"[JIMENG-LOGIN] [{self.account_id}] 检测到绑定剪映弹窗，尝试关闭")
                        # 点击弹窗内的关闭按钮
                        close_btn = bind_modal.locator("[class*='close-icon']").first
                        if await close_btn.is_visible(timeout=2000):
                            await close_btn.click()
                            await asyncio.sleep(1)
                            print(f"[JIMENG-LOGIN] [{self.account_id}] 已关闭绑定剪映弹窗")
                except Exception as e:
                    print(f"[JIMENG-LOGIN] [{self.account_id}] 关闭弹窗异常（继续）: {e}")

                # ===== 步骤 9：提取 Cookie =====
                print(f"[JIMENG-LOGIN] [{self.account_id}] 步骤9: 提取Cookie")
                cookies = await context.cookies()
                cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in cookies)
                self.cookie = cookie_str
                self.status = "success"
                print(f"[JIMENG-LOGIN] [{self.account_id}] 登录成功，Cookie长度={len(cookie_str)}")

            finally:
                await browser.close()


# ===== 全局会话管理 =====
_sessions: dict[str, JimengLoginSession] = {}


def get_or_create_session(account_id: str) -> JimengLoginSession:
    """创建新会话或获取已存在的会话"""
    existing = _sessions.get(account_id)
    if existing and existing.status in ("pending", "scanning"):
        return existing
    session = JimengLoginSession(account_id)
    _sessions[account_id] = session
    return session


def get_session(account_id: str) -> Optional[JimengLoginSession]:
    return _sessions.get(account_id)


def remove_session(account_id: str):
    session = _sessions.pop(account_id, None)
    if session:
        session.cancel()


# ===== 视频生成（文生视频/图生视频）=====
JIMENG_VIDEO_URL = "https://jimeng.jianying.com/ai-tool/generate?type=video"


async def submit_video_task(
    account: dict,
    prompt: str,
    model: str = "Seedance 2.0 Fast",
    duration: int = 5,
    ratio: str = "16:9",
    first_frame_url: Optional[str] = None,
    last_frame_url: Optional[str] = None,
    task_id: Optional[str] = None,
    order_id: Optional[int] = None,
    skip_generate: bool = False,
) -> dict:
    """
    提交即梦视频生成任务

    参数:
        account: 账号信息，包含 cookie
        prompt: 提示词
        model: 模型名称，支持 "Seedance 2.0 Fast" 和 "Seedance 2.0"
        duration: 时长，4-12秒
        ratio: 比例，21:9, 16:9, 4:3, 1:1, 3:4, 9:16
        first_frame_url: 首帧图片URL（可选，用于图生视频）
        last_frame_url: 尾帧图片URL（可选，用于图生视频）
        skip_generate: 是否跳过点击生成按钮（测试用）
    
    返回: {"success": bool, "task_id": str, "error": str}
    """
    cookie = account.get("cookie", "")
    if not cookie:
        return {"success": False, "error": "账号未登录（无Cookie）"}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)  # 服务器必须使用无头模式
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        # 注入 Cookie
        parsed = []
        for part in cookie.split(";"):
            part = part.strip()
            if "=" in part:
                name, _, value = part.partition("=")
                parsed.append({"name": name.strip(), "value": value.strip(), "domain": ".jianying.com", "path": "/"})
        if parsed:
            await context.add_cookies(parsed)

        page = await context.new_page()
        account_id = account.get("account_id", "unknown")

        try:
            # 步骤1：进入视频生成页
            print(f"[JIMENG-SUBMIT] [{account_id}] 进入视频生成页")
            await page.goto(JIMENG_VIDEO_URL, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(2000)

            # 步骤2：关闭可能的弹窗
            try:
                bind_modal = page.locator("[class*='bind-capcut-account']")
                if await bind_modal.count() > 0:
                    print(f"[JIMENG-SUBMIT] [{account_id}] 检测到弹窗，关闭中...")
                    close_btn = bind_modal.first.locator("[class*='close-icon'], [class*='close-btn'], button[aria-label*='关闭']").first
                    if await close_btn.count() > 0:
                        await close_btn.click()
                    else:
                        await page.keyboard.press("Escape")
                    await page.wait_for_timeout(500)
            except Exception as e:
                print(f"[JIMENG-SUBMIT] [{account_id}] 弹窗处理异常（继续）: {str(e)[:50]}")

            await page.screenshot(path=_debug_path("submit_01_gen_page"))

            # 步骤3：选择模型、比例、时长
            print(f"[JIMENG-SUBMIT] [{account_id}] 配置参数: 模型={model}, 比例={ratio}, 时长={duration}s")
            await _select_video_model(page, model, account_id)
            await _select_resolution_ratio(page, ratio, account_id)
            await _select_duration(page, duration, account_id)

            # 步骤4：上传参考图片（如果有）
            if first_frame_url or last_frame_url:
                print(f"[JIMENG-SUBMIT] [{account_id}] 上传参考图片")
                await _upload_reference_images(page, first_frame_url, last_frame_url, account_id)

            # 步骤5：输入提示词（带订单追踪ID）
            actual_prompt = prompt
            if order_id is not None:
                actual_prompt = add_jimeng_tracking_id(prompt, order_id)
                print(f"[JIMENG-SUBMIT] [{account_id}] 输入提示词（含追踪ID: #JMORD{order_id}）")
            else:
                print(f"[JIMENG-SUBMIT] [{account_id}] 输入提示词")
            prompt_input = page.locator("textarea[class*='prompt-textarea']").first
            if await prompt_input.count() == 0:
                prompt_input = page.get_by_placeholder("输入文字，描述你想创作的画面内容")
            if await prompt_input.count() == 0:
                prompt_input = page.locator(".lv-textarea.prompt-textarea, textarea.lv-textarea").first
            await prompt_input.click()
            await prompt_input.fill(actual_prompt)
            await page.wait_for_timeout(500)
            await page.screenshot(path=_debug_path("submit_02_prompt_filled"))

            # 步骤6：点击生成按钮
            if skip_generate:
                print(f"[JIMENG-SUBMIT] [{account_id}] 跳过点击生成按钮（测试模式）")
                await page.screenshot(path=_debug_path("submit_03_before_generate"))
            else:
                print(f"[JIMENG-SUBMIT] [{account_id}] 点击生成按钮")

                # 滚动到底部确保按钮可见
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(500)

                submit_btns = page.locator("button[class*='submit-button']")
                btn_count = await submit_btns.count()
                clicked = False

                if btn_count > 0:
                    for i in range(btn_count):
                        btn = submit_btns.nth(i)
                        if await btn.is_visible():
                            await btn.scroll_into_view_if_needed()
                            await btn.click()
                            print(f"[JIMENG-SUBMIT] [{account_id}] 已点击生成按钮")
                            clicked = True
                            break

                if not clicked:
                    # 备用方案
                    print(f"[JIMENG-SUBMIT] [{account_id}] 主按钮未找到，尝试备用定位")
                    generate_btn = page.get_by_role("button", name="生成")
                    if await generate_btn.count() > 0:
                        await generate_btn.scroll_into_view_if_needed()
                        await generate_btn.click()
                    else:
                        generate_btn = page.locator(".lv-btn-primary").first
                        await generate_btn.scroll_into_view_if_needed()
                        await generate_btn.click()

                await page.wait_for_timeout(1000)

                # 步骤7：处理确认弹窗（如果有）
                try:
                    confirm_btn = page.get_by_role("button", name="确认")
                    if await confirm_btn.count() > 0 and await confirm_btn.is_visible():
                        print(f"[JIMENG-SUBMIT] [{account_id}] 点击确认弹窗")
                        await confirm_btn.click()
                        await page.wait_for_timeout(1000)
                except Exception as e:
                    print(f"[JIMENG-SUBMIT] [{account_id}] 确认弹窗处理: {str(e)[:50]}")

                await page.screenshot(path=_debug_path("submit_03_after_generate"))

                # 步骤8：验证是否真正开始生成
                print(f"[JIMENG-SUBMIT] [{account_id}] 验证生成是否启动...")
                await page.wait_for_timeout(2000)

                # 检查是否出现错误提示（积分不足、频率限制等）
                error_toast = page.locator("[class*='lv-message--error'], [class*='toast-error'], [class*='error-message']").first
                if await error_toast.count() > 0:
                    error_text = (await error_toast.text_content(timeout=3000) or "").strip()
                    if error_text:
                        print(f"[JIMENG-SUBMIT] [{account_id}] 生成失败，页面报错: {error_text}")
                        await page.screenshot(path=_debug_path("submit_04_error_toast"))
                        return {"success": False, "error": f"页面报错: {error_text}"}

                # 检查是否出现进度条/排队状态（说明真正开始了）
                generation_started = False
                for _ in range(3):
                    progress = page.locator("[class*='progress-badge'], [class*='generating'], [class*='queuing']").first
                    if await progress.count() > 0:
                        badge_text = (await progress.text_content(timeout=3000) or "").strip()
                        print(f"[JIMENG-SUBMIT] [{account_id}] 生成已启动: {badge_text}")
                        generation_started = True
                        break
                    await page.wait_for_timeout(1500)

                if not generation_started:
                    # 再检查一下提示词输入框是否被清空（清空说明提交成功了）
                    try:
                        prompt_input_check = page.locator("textarea[class*='prompt-textarea']").first
                        if await prompt_input_check.count() > 0:
                            remaining_text = (await prompt_input_check.input_value(timeout=3000) or "").strip()
                            if remaining_text == prompt.strip():
                                print(f"[JIMENG-SUBMIT] [{account_id}] 提示词未清空，生成可能未成功")
                                await page.screenshot(path=_debug_path("submit_04_not_started"))
                                return {"success": False, "error": "生成按钮点击后未检测到生成状态，可能未成功提交"}
                    except:
                        pass
                    print(f"[JIMENG-SUBMIT] [{account_id}] 未检测到明确的生成状态，但继续（可能页面结构变化）")

                await page.screenshot(path=_debug_path("submit_04_verified"))

            # 使用传入的 task_id，如果没有则生成新的
            if not task_id:
                task_id = f"jimeng_{int(time.time())}_{account.get('account_id', 'unknown')}"

            return {"success": True, "task_id": task_id}

        except Exception as e:
            await page.screenshot(path=_debug_path("submit_error"))
            print(f"[JIMENG-SUBMIT] [{account_id}] 提交失败: {e}")
            return {"success": False, "error": str(e)}
        finally:
            await browser.close()


async def verify_cookie(cookie: str) -> tuple[bool, str]:
    """
    验证 Cookie 是否有效
    
    返回: (is_valid: bool, username_or_error: str)
    """
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            
            # 设置 Cookie - 修复变量引用错误
            cookie_pairs = [c.strip().split("=", 1) for c in cookie.split(";") if "=" in c.strip()]
            cookies = [{"name": name, "value": value, "domain": ".jianying.com"} for name, value in cookie_pairs]
            await context.add_cookies(cookies)
            
            # 访问即梦首页
            page = await context.new_page()
            await page.goto(JIMENG_URL, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(2000)
            
            # 检查是否登录成功（查找头像元素）
            avatar = page.locator("img.dreamina-component-avatar")
            if await avatar.count() > 0:
                # 获取用户名
                username = await avatar.first.get_attribute("alt") or ""
                if not username:
                    username_el = page.locator("[class*='user-name'], [class*='username']")
                    if await username_el.count() > 0:
                        username = await username_el.first.text_content() or ""
                
                await browser.close()
                return True, username or "用户"
            
            # 检查是否有登录按钮（未登录状态）
            login_btn = page.locator("button:has-text('登录')")
            if await login_btn.count() > 0:
                await browser.close()
                return False, "未检测到登录状态，请先登录"
            
            await browser.close()
            return False, "Cookie无效或已过期"
            
    except Exception as e:
        try:
            await browser.close()
        except:
            pass
        return False, f"验证失败: {str(e)}"


async def _select_video_model(page: Page, target_model: str, account_id: str):
    """
    选择视频模型（第二个下拉框）
    
    下拉框顺序：
    1. 第一个：选择模式（忽略）
    2. 第二个：选择模型
    
    支持的模型：
    - Seedance 2.0 Fast
    - Seedance 2.0
    - 视频3.0 (测试模型)
    """
    supported_models = ["Seedance 2.0 Fast", "Seedance 2.0", "视频3.0"]
    if target_model not in supported_models:
        print(f"[JIMENG-SUBMIT] [{account_id}] 不支持的模型: {target_model}，使用默认模型")
        target_model = "Seedance 2.0 Fast"
    
    try:
        await page.wait_for_timeout(500)
        
        # 获取所有下拉框
        all_selects = page.locator(".lv-select-view")
        select_count = await all_selects.count()
        print(f"[JIMENG-SUBMIT] [{account_id}] 页面上找到 {select_count} 个下拉框")
        
        # 第二个下拉框是模型选择器（索引1）
        if select_count >= 2:
            model_select = all_selects.nth(1)  # 索引1 = 第二个
            print(f"[JIMENG-SUBMIT] [{account_id}] 使用第二个下拉框作为模型选择器")
            
            # 点击打开下拉框
            selector_btn = model_select.locator(".lv-select-view-selector")
            if await selector_btn.count() > 0:
                await selector_btn.click()
            else:
                await model_select.click()
            await page.wait_for_timeout(800)
            
            # 截图查看下拉框内容
            await page.screenshot(path=_debug_path("model_dropdown_open"))
            
            # 方法1：尝试包含文本的选项
            # 使用 locator 配合 has_text
            options = page.locator("[class*='select-option'], [class*='lv-select-option'], .lv-select-dropdown-item")
            option_count = await options.count()
            print(f"[JIMENG-SUBMIT] [{account_id}] 找到 {option_count} 个下拉选项")
            
            found = False
            for i in range(option_count):
                try:
                    opt = options.nth(i)
                    opt_text = await opt.text_content() or ""
                    print(f"[JIMENG-SUBMIT] [{account_id}] 选项 {i+1}: '{opt_text.strip()}'")
                    
                    # 检查是否包含目标模型名称的关键词
                    if "Fast" in target_model and "Fast" in opt_text:
                        await opt.click()
                        print(f"[JIMENG-SUBMIT] [{account_id}] 模型已切换为 {target_model}")
                        found = True
                        break
                    elif "Seedance" in target_model and "Fast" not in target_model and "Seedance" in opt_text and "Fast" not in opt_text:
                        await opt.click()
                        print(f"[JIMENG-SUBMIT] [{account_id}] 模型已切换为 {target_model}")
                        found = True
                        break
                    elif "视频3.0" in target_model and ("视频3.0" in opt_text or "3.0" in opt_text):
                        await opt.click()
                        print(f"[JIMENG-SUBMIT] [{account_id}] 模型已切换为 {target_model}")
                        found = True
                        break
                except Exception as e:
                    print(f"[JIMENG-SUBMIT] [{account_id}] 检查选项 {i+1} 失败: {str(e)[:30]}")
            
            if not found:
                # 方法2：直接用 get_by_role 点击
                print(f"[JIMENG-SUBMIT] [{account_id}] 方法1未找到，尝试方法2...")
                
                # 尝试点击包含目标模型关键词的选项
                seedance_options = page.get_by_role("option")
                opt_count = await seedance_options.count()
                print(f"[JIMENG-SUBMIT] [{account_id}] 找到 {opt_count} 个 role=option")
                
                for i in range(opt_count):
                    opt = seedance_options.nth(i)
                    opt_text = await opt.text_content() or ""
                    
                    # 匹配 Seedance 模型
                    if "Seedance" in opt_text:
                        if ("Fast" in target_model and "Fast" in opt_text) or ("Fast" not in target_model and "Fast" not in opt_text):
                            await opt.click()
                            print(f"[JIMENG-SUBMIT] [{account_id}] 模型已切换为 {target_model}（方法2）")
                            found = True
                            break
                    # 匹配 视频3.0 模型
                    elif "视频3.0" in target_model and ("视频3.0" in opt_text or "3.0" in opt_text):
                        await opt.click()
                        print(f"[JIMENG-SUBMIT] [{account_id}] 模型已切换为 {target_model}（方法2）")
                        found = True
                        break
            
            if not found:
                await page.keyboard.press("Escape")
                print(f"[JIMENG-SUBMIT] [{account_id}] 未找到模型选项: {target_model}")
        else:
            print(f"[JIMENG-SUBMIT] [{account_id}] 下拉框数量不足，跳过模型选择")
        
        await page.wait_for_timeout(300)
        
    except Exception as e:
        print(f"[JIMENG-SUBMIT] [{account_id}] 模型选择失败（继续）: {str(e)[:100]}")
        await page.screenshot(path=_debug_path("model_error"))


async def _select_duration(page: Page, duration: int, account_id: str):
    """
    选择视频时长（第四个下拉框）
    
    下拉框顺序：
    1. 第一个：选择模式（忽略）
    2. 第二个：选择模型
    3. 第三个：忽略
    4. 第四个：选择时长
    """
    if duration not in [4, 5, 6, 7, 8, 9, 10, 11, 12]:
        duration = 5
    
    try:
        await page.wait_for_timeout(500)
        
        # 获取所有下拉框
        all_selects = page.locator(".lv-select-view")
        select_count = await all_selects.count()
        print(f"[JIMENG-SUBMIT] [{account_id}] 页面上找到 {select_count} 个下拉框")
        
        # 第四个下拉框是时长选择器（索引3）
        if select_count >= 4:
            duration_select = all_selects.nth(3)  # 索引3 = 第四个
            print(f"[JIMENG-SUBMIT] [{account_id}] 使用第四个下拉框作为时长选择器")
            
            # 检查当前选中的值
            value_el = duration_select.locator(".lv-select-view-value")
            if await value_el.count() > 0:
                current_value = await value_el.text_content() or ""
                print(f"[JIMENG-SUBMIT] [{account_id}] 当前时长值: {current_value}")
                
                # 如果已经是目标时长，跳过
                if f"{duration}s" in current_value:
                    print(f"[JIMENG-SUBMIT] [{account_id}] 时长已是 {duration}s，无需切换")
                    return
            
            # 点击打开下拉框
            selector_btn = duration_select.locator(".lv-select-view-selector")
            if await selector_btn.count() > 0:
                await selector_btn.click()
            else:
                await duration_select.click()
            await page.wait_for_timeout(500)
            
            # 点击目标时长
            target_option = page.get_by_text(f"{duration}s", exact=True)
            if await target_option.count() > 0:
                await target_option.first.click()
                await page.wait_for_timeout(300)
                print(f"[JIMENG-SUBMIT] [{account_id}] 时长已切换为 {duration}s")
            else:
                await page.keyboard.press("Escape")
                print(f"[JIMENG-SUBMIT] [{account_id}] 未找到时长选项: {duration}s")
        else:
            print(f"[JIMENG-SUBMIT] [{account_id}] 下拉框数量不足，跳过时长选择")
        
    except Exception as e:
        print(f"[JIMENG-SUBMIT] [{account_id}] 时长选择失败（继续）: {str(e)[:100]}")


async def _select_resolution_ratio(page: Page, ratio: str, account_id: str):
    """
    选择比例（按钮形式）
    
    比例按钮：class 包含 toolbar-button，文本如 "9:16"
    比例选项：div.radio-content 包含比例文本
    """
    if ratio not in ["21:9", "16:9", "4:3", "1:1", "3:4", "9:16"]:
        ratio = "16:9"
    
    try:
        await page.wait_for_timeout(500)
        
        # 查找比例按钮
        toolbar_buttons = page.locator("button[class*='toolbar-button']")
        btn_count = await toolbar_buttons.count()
        print(f"[JIMENG-SUBMIT] [{account_id}] 找到 {btn_count} 个 toolbar-button 按钮")
        
        for i in range(btn_count):
            btn = toolbar_buttons.nth(i)
            try:
                btn_text = await btn.text_content() or ""
                print(f"[JIMENG-SUBMIT] [{account_id}] toolbar-button {i+1}: '{btn_text[:40]}'")
                
                # 检查是否是比例按钮
                if any(r in btn_text for r in ["21:9", "16:9", "4:3", "1:1", "3:4", "9:16"]):
                    print(f"[JIMENG-SUBMIT] [{account_id}] 找到比例按钮，点击打开下拉菜单")
                    
                    await btn.click()
                    await page.wait_for_timeout(800)
                    
                    await page.screenshot(path=_debug_path("ratio_dropdown_open"))
                    
                    # 选择比例
                    print(f"[JIMENG-SUBMIT] [{account_id}] 尝试选择比例: {ratio}")
                    
                    # 方法1：使用 radio-content class 定位
                    radio_items = page.locator("div[class*='radio-content']")
                    radio_count = await radio_items.count()
                    print(f"[JIMENG-SUBMIT] [{account_id}] 找到 {radio_count} 个 radio-content 元素")
                    
                    ratio_selected = False
                    for j in range(radio_count):
                        try:
                            radio = radio_items.nth(j)
                            radio_text = await radio.text_content() or ""
                            radio_text_clean = radio_text.strip()
                            
                            if j < 10:
                                print(f"[JIMENG-SUBMIT] [{account_id}] radio {j+1}: '{radio_text_clean}'")
                            
                            # 精确匹配
                            if radio_text_clean == ratio:
                                print(f"[JIMENG-SUBMIT] [{account_id}] 精确匹配比例: '{radio_text_clean}'")
                                await radio.click()
                                await page.wait_for_timeout(300)
                                print(f"[JIMENG-SUBMIT] [{account_id}] 已选择比例: {ratio}")
                                ratio_selected = True
                                break
                        except Exception as e:
                            pass
                    
                    if not ratio_selected:
                        # 方法2：遍历所有 span，查找比例文本
                        print(f"[JIMENG-SUBMIT] [{account_id}] 方法1未找到，尝试遍历 span...")
                        all_spans = page.locator("span")
                        span_count = await all_spans.count()
                        
                        for j in range(span_count):
                            try:
                                span = all_spans.nth(j)
                                span_text = await span.text_content() or ""
                                span_text_clean = span_text.strip()
                                
                                if len(span_text_clean) < 20 and j < 30:
                                    print(f"[JIMENG-SUBMIT] [{account_id}] span {j+1}: '{span_text_clean}'")
                                
                                if span_text_clean == ratio:
                                    print(f"[JIMENG-SUBMIT] [{account_id}] 找到比例 span: '{span_text_clean}'")
                                    parent = span.locator("xpath=..")
                                    await parent.click()
                                    await page.wait_for_timeout(300)
                                    print(f"[JIMENG-SUBMIT] [{account_id}] 已选择比例: {ratio}")
                                    ratio_selected = True
                                    break
                            except Exception as e:
                                pass
                    
                    if not ratio_selected:
                        print(f"[JIMENG-SUBMIT] [{account_id}] 未找到比例选项: {ratio}")
                        await page.keyboard.press("Escape")
                    
                    break
                    
            except Exception as e:
                print(f"[JIMENG-SUBMIT] [{account_id}] toolbar-button {i+1} 检查失败: {str(e)[:50]}")
        
    except Exception as e:
        print(f"[JIMENG-SUBMIT] [{account_id}] 比例选择失败（继续）: {str(e)[:100]}")


async def _upload_reference_images(
    page: Page, 
    first_frame_url: Optional[str], 
    last_frame_url: Optional[str],
    account_id: str
):
    """
    上传首帧和尾帧参考图片
    
    定位方式：
    - 首帧：包含"首帧"文字的容器内的 file input
    - 尾帧：包含"尾帧"文字的容器内的 file input
    """
    import httpx
    import tempfile
    
    async def download_and_upload(url: str, label: str, input_locator):
        """下载图片并上传（支持本地路径和HTTP URL）"""
        try:
            # 判断是本地文件还是远程URL
            if url.startswith("http://") or url.startswith("https://"):
                # 远程URL：下载到临时文件
                async with httpx.AsyncClient(timeout=30) as client:
                    response = await client.get(url)
                    response.raise_for_status()

                content_type = response.headers.get("content-type", "image/png")
                ext = content_type.split("/")[-1] if "/" in content_type else "png"
                if ext not in ["jpg", "jpeg", "png", "webp", "bmp"]:
                    ext = "png"

                with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
                    tmp.write(response.content)
                    file_path = tmp.name

                print(f"[JIMENG-SUBMIT] [{account_id}] 上传{label}(远程): {url[:50]}...")
                await input_locator.set_input_files(file_path)
                await page.wait_for_timeout(1000)
                os.unlink(file_path)
            else:
                # 本地文件路径：直接上传
                local_path = os.path.abspath(url)
                if not os.path.exists(local_path):
                    print(f"[JIMENG-SUBMIT] [{account_id}] {label}文件不存在: {local_path}")
                    return

                print(f"[JIMENG-SUBMIT] [{account_id}] 上传{label}(本地): {local_path}")
                await input_locator.set_input_files(local_path)
                await page.wait_for_timeout(1000)

            print(f"[JIMENG-SUBMIT] [{account_id}] {label}上传成功")

        except Exception as e:
            print(f"[JIMENG-SUBMIT] [{account_id}] {label}上传失败: {str(e)[:100]}")
    
    try:
        await page.screenshot(path=_debug_path("upload_00_before"))
        
        # 上传首帧
        if first_frame_url:
            # 定位首帧上传区域：包含"首帧"文字的容器
            first_frame_container = page.locator("[class*='reference-upload']").filter(
                has_text="首帧"
            ).first
            if await first_frame_container.count() > 0:
                first_frame_input = first_frame_container.locator("input[type='file']")
                if await first_frame_input.count() > 0:
                    await download_and_upload(first_frame_url, "首帧", first_frame_input)
            else:
                print(f"[JIMENG-SUBMIT] [{account_id}] 未找到首帧上传区域")
        
        # 上传尾帧
        if last_frame_url:
            # 定位尾帧上传区域：包含"尾帧"文字的容器
            last_frame_container = page.locator("[class*='reference-upload']").filter(
                has_text="尾帧"
            ).first
            if await last_frame_container.count() > 0:
                last_frame_input = last_frame_container.locator("input[type='file']")
                if await last_frame_input.count() > 0:
                    await download_and_upload(last_frame_url, "尾帧", last_frame_input)
            else:
                print(f"[JIMENG-SUBMIT] [{account_id}] 未找到尾帧上传区域")
        
        await page.screenshot(path=_debug_path("upload_01_after"))
        
    except Exception as e:
        print(f"[JIMENG-SUBMIT] [{account_id}] 参考图片上传失败（继续）: {str(e)[:100]}")
        await page.screenshot(path=_debug_path("upload_error"))


# ===== 视频状态扫描 =====

# 视频状态枚举
JIMENG_STATUS_QUEUING = "queuing"      # 排队中
JIMENG_STATUS_GENERATING = "generating"  # 生成中
JIMENG_STATUS_COMPLETED = "completed"    # 已完成
JIMENG_STATUS_FAILED = "failed"          # 失败（审核不通过等）
JIMENG_STATUS_UNKNOWN = "unknown"        # 未知


async def scan_video_status(
    account: dict,
    prompt: Optional[str] = None,
    order_id: Optional[int] = None,
) -> dict:
    """
    扫描即梦视频生成状态

    参数:
        account: 账号信息，包含 cookie
        prompt: 提示词（可选，已废弃，优先使用 order_id）
        order_id: 订单ID（可选，用于通过追踪标识精确匹配）
    
    返回: {
        "success": bool,
        "videos": [
            {
                "prompt": str,
                "model": str,
                "status": str,  # queuing/generating/completed
                "progress": int,  # 0-100，排队中为-1
                "video_url": str,  # 仅 completed 状态有
            }
        ]
    }
    """
    cookie = account.get("cookie", "")
    if not cookie:
        return {"success": False, "error": "账号未登录（无Cookie）"}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        # 注入 Cookie
        parsed = []
        for part in cookie.split(";"):
            part = part.strip()
            if "=" in part:
                name, _, value = part.partition("=")
                parsed.append({"name": name.strip(), "value": value.strip(), "domain": ".jianying.com", "path": "/"})
        if parsed:
            await context.add_cookies(parsed)

        page = await context.new_page()
        account_id = account.get("account_id", "unknown")

        try:
            # 进入视频生成页面（包含历史记录）
            print(f"[JIMENG-SCAN] [{account_id}] 扫描视频状态...")
            await page.goto(JIMENG_VIDEO_URL, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(3000)

            # 关闭可能的弹窗
            try:
                bind_modal = page.locator("[class*='bind-capcut-account-first-screen-modal-content']")
                if await bind_modal.count() > 0:
                    close_btn = bind_modal.locator("[class*='close-icon']").first
                    if await close_btn.is_visible(timeout=2000):
                        await close_btn.click()
                        await page.wait_for_timeout(1000)
            except:
                pass

            # 滚动加载视频卡片，目标约20个
            TARGET_VIDEO_COUNT = 20
            MAX_SCROLL_ATTEMPTS = 15  # 防止无限滚动
            print(f"[JIMENG-SCAN] [{account_id}] 滚动加载视频，目标 {TARGET_VIDEO_COUNT} 个...")
            previous_count = 0
            scroll_attempts = 0
            no_change_count = 0  # 连续无变化次数

            while scroll_attempts < MAX_SCROLL_ATTEMPTS:
                current_records = page.locator("div[class*='video-record'][class*='nlt6eI']")
                current_count = await current_records.count()

                print(f"[JIMENG-SCAN] [{account_id}] 滚动 {scroll_attempts + 1}/{MAX_SCROLL_ATTEMPTS}，当前 {current_count} 个视频")

                # 已达到目标数量，停止滚动
                if current_count >= TARGET_VIDEO_COUNT:
                    print(f"[JIMENG-SCAN] [{account_id}] 已达到目标数量 {TARGET_VIDEO_COUNT}，停止滚动")
                    break

                # 连续2次数量无变化，说明所有视频已加载完毕（不足20个的情况）
                if current_count > 0 and current_count == previous_count:
                    no_change_count += 1
                    if no_change_count >= 2:
                        print(f"[JIMENG-SCAN] [{account_id}] 视频数量连续未增加（共 {current_count} 个），已全部加载")
                        break
                else:
                    no_change_count = 0

                previous_count = current_count

                # 滚动加载：优先滚动视频列表容器，fallback 到 window
                await page.evaluate("""() => {
                    const container = document.querySelector('[class*="record-list"]')
                        || document.querySelector('[class*="video-list"]')
                        || document.querySelector('[class*="scroll"]');
                    if (container && container.scrollHeight > container.clientHeight) {
                        container.scrollTop = container.scrollHeight;
                    } else {
                        window.scrollTo(0, document.body.scrollHeight);
                    }
                }""")
                await page.wait_for_timeout(1500)

                scroll_attempts += 1

            videos = []

            # 查找所有视频记录卡片
            video_records = page.locator("div[class*='video-record'][class*='nlt6eI']")
            record_count = await video_records.count()
            print(f"[JIMENG-SCAN] [{account_id}] 最终找到 {record_count} 个视频记录")

            for i in range(record_count):
                record = video_records.nth(i)
                video_info = {"status": JIMENG_STATUS_UNKNOWN, "progress": 0}

                try:
                    # 获取提示词 - prompt-value-container 内的 span（带超时保护）
                    prompt_el = record.locator("[class*='prompt-value-container'] > span").first
                    if await prompt_el.count() > 0:
                        video_info["prompt"] = (await prompt_el.text_content(timeout=3000) or "").strip()

                    # 优先通过订单追踪ID精确匹配
                    if order_id is not None:
                        card_prompt = video_info.get("prompt", "")
                        extracted_id = extract_jimeng_order_id(card_prompt)
                        if extracted_id != order_id:
                            continue
                        # 匹配成功，去掉追踪标识还原原始提示词
                        video_info["prompt"] = re.sub(r'\s*\(以下内容请忽略.*?\[' + JIMENG_ORDER_TAG_PREFIX + r'\d+\]\)', '', card_prompt).strip()
                        video_info["order_id"] = order_id
                    elif prompt is not None:
                        # 兜底：无 order_id 时用标准化精确匹配
                        card_prompt = video_info.get("prompt", "")
                        norm_prompt = re.sub(r'\s+', ' ', prompt.strip())
                        norm_card = re.sub(r'\s+', ' ', card_prompt.strip())
                        if norm_prompt != norm_card:
                            continue

                    print(f"[JIMENG-SCAN] [{account_id}] 视频 {i+1} 提示词: {video_info.get('prompt', '')[:30]}...")

                    # 获取模型 - 第一个 label
                    label_el = record.locator("[class*='label-lhnDlt']").first
                    if await label_el.count() > 0:
                        video_info["model"] = await label_el.text_content(timeout=3000) or ""

                    # 优先检查失败状态
                    error_tips = record.locator("[class*='error-tips']").first
                    if await error_tips.count() > 0:
                        error_text = await error_tips.text_content(timeout=3000) or ""
                        video_info["status"] = "failed"
                        video_info["progress"] = 0
                        video_info["error"] = error_text.strip()
                        print(f"[JIMENG-SCAN] [{account_id}] 视频 {i+1} 失败: {error_text[:50]}")
                        videos.append(video_info)
                        continue

                    # 检测进度状态
                    progress_badge = record.locator("[class*='progress-badge']").first
                    if await progress_badge.count() > 0:
                        badge_text = (await progress_badge.text_content(timeout=3000) or "").strip()
                        print(f"[JIMENG-SCAN] [{account_id}] 视频 {i+1} badge: {badge_text}")

                        if "排队中" in badge_text or "排队加速中" in badge_text:
                            video_info["status"] = JIMENG_STATUS_QUEUING
                            video_info["progress"] = 0
                        elif "造梦中" in badge_text:
                            video_info["status"] = JIMENG_STATUS_GENERATING
                            # 提取进度百分比 - 支持 "28%造梦中" 和 "造梦中 28%" 两种格式
                            match = re.search(r"(\d+)%", badge_text)
                            if match:
                                video_info["progress"] = int(match.group(1))
                            else:
                                video_info["progress"] = 0
                    else:
                        # 没有 progress-badge，检查是否有视频（已完成）
                        # 注意：要排除加载动画视频
                        video_el = record.locator("video:not([class*='loading-animation'])").first
                        if await video_el.count() > 0:
                            video_src = await video_el.get_attribute("src", timeout=3000) or await video_el.get_attribute("data-src", timeout=3000) or ""
                            # 确保不是加载动画的视频
                            if video_src and "loading-animation" not in video_src:
                                video_info["status"] = JIMENG_STATUS_COMPLETED
                                video_info["progress"] = 100
                                video_info["video_url"] = video_src
                                print(f"[JIMENG-SCAN] [{account_id}] 视频 {i+1} 已完成: {video_src[:80]}...")

                    videos.append(video_info)

                except Exception as e:
                    print(f"[JIMENG-SCAN] [{account_id}] 解析视频记录 {i+1} 失败: {str(e)[:50]}")

            print(f"[JIMENG-SCAN] [{account_id}] 扫描完成，找到 {len(videos)} 个视频")
            return {"success": True, "videos": videos}

        except Exception as e:
            print(f"[JIMENG-SCAN] [{account_id}] 扫描失败: {e}")
            return {"success": False, "error": str(e)}
        finally:
            await browser.close()
