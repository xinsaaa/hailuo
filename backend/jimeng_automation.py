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
        browser = await p.chromium.launch(headless=False)  # 测试时使用非无头模式
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
            # 步骤1：直接跳转到视频生成页（通过 URL 参数控制模式，更稳定）
            print(f"[JIMENG-SUBMIT] [{account_id}] 进入视频生成页")
            await page.goto(JIMENG_VIDEO_URL, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(1500)
            
            # 步骤1.5：关闭可能的"绑定剪映账号"弹窗
            print(f"[JIMENG-SUBMIT] [{account_id}] 检查是否有绑定剪映弹窗...")
            try:
                # 等待页面稳定
                await page.wait_for_timeout(1000)
                
                # 多种方式检测弹窗
                bind_modal = page.locator("[class*='bind-capcut-account']")
                modal_count = await bind_modal.count()
                print(f"[JIMENG-SUBMIT] [{account_id}] 找到 {modal_count} 个可能的弹窗元素")
                
                if modal_count > 0:
                    print(f"[JIMENG-SUBMIT] [{account_id}] 检测到绑定剪映弹窗，尝试关闭")
                    
                    # 方式1：点击关闭按钮
                    close_btn = bind_modal.first.locator("[class*='close-icon'], [class*='close-btn'], button[aria-label*='关闭']").first
                    if await close_btn.count() > 0:
                        await close_btn.click()
                        await page.wait_for_timeout(500)
                        print(f"[JIMENG-SUBMIT] [{account_id}] 已点击关闭按钮")
                    else:
                        # 方式2：点击弹窗外区域
                        await page.keyboard.press("Escape")
                        await page.wait_for_timeout(500)
                        print(f"[JIMENG-SUBMIT] [{account_id}] 已按Escape键关闭弹窗")
                    
                    await page.wait_for_timeout(500)
                    print(f"[JIMENG-SUBMIT] [{account_id}] 已关闭绑定剪映弹窗")
                else:
                    print(f"[JIMENG-SUBMIT] [{account_id}] 未检测到绑定剪映弹窗")
            except Exception as e:
                print(f"[JIMENG-SUBMIT] [{account_id}] 关闭弹窗异常（继续）: {e}")
            
            await page.screenshot(path=_debug_path("submit_01_gen_page"))

            # 步骤2：选择模型（稳定写法）
            print(f"[JIMENG-SUBMIT] [{account_id}] 选择模型: {model}")
            await _select_video_model(page, model, account_id)

            # 步骤2.1：选择比例（按钮形式）
            print(f"[JIMENG-SUBMIT] [{account_id}] 选择比例: {ratio}")
            await _select_resolution_ratio(page, ratio, account_id)

            # 步骤2.2：选择时长（第四个下拉框）
            print(f"[JIMENG-SUBMIT] [{account_id}] 选择时长: {duration}s")
            await _select_duration(page, duration, account_id)

            # 步骤2.5：上传首帧和尾帧图片（如果有）
            if first_frame_url or last_frame_url:
                print(f"[JIMENG-SUBMIT] [{account_id}] 上传参考图片")
                await _upload_reference_images(page, first_frame_url, last_frame_url, account_id)

            # 步骤3：输入提示词
            print(f"[JIMENG-SUBMIT] [{account_id}] 输入提示词")
            # 通过固定的 class 元素定位提示词输入框
            prompt_input = page.locator("textarea[class*='prompt-textarea']").first
            if await prompt_input.count() == 0:
                # 备用方案：通过 placeholder 定位
                prompt_input = page.get_by_placeholder("输入文字，描述你想创作的画面内容")
            if await prompt_input.count() == 0:
                # 再备用：通过 class 组合定位
                prompt_input = page.locator(".lv-textarea.prompt-textarea, textarea.lv-textarea").first
            await prompt_input.click()
            await prompt_input.fill(prompt)
            await page.wait_for_timeout(500)  # 输入后等待
            await page.screenshot(path=_debug_path("submit_02_prompt_filled"))

            # 步骤4：点击生成按钮
            if skip_generate:
                print(f"[JIMENG-SUBMIT] [{account_id}] 跳过点击生成按钮（测试模式）")
                await page.screenshot(path=_debug_path("submit_03_before_generate"))
            else:
                print(f"[JIMENG-SUBMIT] [{account_id}] 点击生成按钮")
                await page.wait_for_timeout(500)
                
                # 通过固定的 class 元素定位提交按钮
                submit_btns = page.locator("button[class*='submit-button']")
                btn_count = await submit_btns.count()
                print(f"[JIMENG-SUBMIT] [{account_id}] 找到 {btn_count} 个 submit-button 元素")
                
                if btn_count > 0:
                    # 遍历找到可见的按钮
                    for i in range(btn_count):
                        btn = submit_btns.nth(i)
                        is_visible = await btn.is_visible()
                        btn_class = await btn.get_attribute("class") or ""
                        print(f"[JIMENG-SUBMIT] [{account_id}] 按钮 {i+1}: visible={is_visible}, class={btn_class[:50]}...")
                        if is_visible:
                            await btn.click()
                            print(f"[JIMENG-SUBMIT] [{account_id}] 已点击按钮 {i+1}")
                            break
                else:
                    # 备用方案：通过文字定位
                    print(f"[JIMENG-SUBMIT] [{account_id}] 未找到 submit-button，尝试备用方案")
                    generate_btn = page.get_by_role("button", name="生成")
                    if await generate_btn.count() > 0:
                        await generate_btn.click()
                    else:
                        # 再备用：通过组合 class 定位
                        generate_btn = page.locator(".lv-btn-primary").first
                        await generate_btn.click()
                
                await page.wait_for_timeout(1000)
                
                # 步骤4.5：点击确认弹窗（如果有）
                try:
                    confirm_btn = page.get_by_role("button", name="确认")
                    if await confirm_btn.count() > 0 and await confirm_btn.is_visible():
                        print(f"[JIMENG-SUBMIT] [{account_id}] 检测到确认弹窗，点击确认")
                        await confirm_btn.click()
                        await page.wait_for_timeout(1000)
                except Exception as e:
                    print(f"[JIMENG-SUBMIT] [{account_id}] 确认弹窗处理: {str(e)[:50]}")
                
                await page.screenshot(path=_debug_path("submit_03_after_generate"))

            return {"success": True, "task_id": f"jimeng_{int(time.time())}"}

        except Exception as e:
            await page.screenshot(path=_debug_path("submit_error"))
            print(f"[JIMENG-SUBMIT] [{account_id}] 提交失败: {e}")
            return {"success": False, "error": str(e)}
        finally:
            await browser.close()


async def _select_video_model(page: Page, target_model: str, account_id: str):
    """
    选择视频模型（第二个下拉框）
    
    下拉框顺序：
    1. 第一个：选择模式（忽略）
    2. 第二个：选择模型
    """
    supported_models = ["Seedance 2.0 Fast", "Seedance 2.0"]
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
                except Exception as e:
                    print(f"[JIMENG-SUBMIT] [{account_id}] 检查选项 {i+1} 失败: {str(e)[:30]}")
            
            if not found:
                # 方法2：直接用 get_by_role 点击
                print(f"[JIMENG-SUBMIT] [{account_id}] 方法1未找到，尝试方法2...")
                
                # 尝试点击包含 Seedance 的选项
                seedance_options = page.get_by_role("option")
                opt_count = await seedance_options.count()
                print(f"[JIMENG-SUBMIT] [{account_id}] 找到 {opt_count} 个 role=option")
                
                for i in range(opt_count):
                    opt = seedance_options.nth(i)
                    opt_text = await opt.text_content() or ""
                    if "Seedance" in opt_text:
                        if ("Fast" in target_model and "Fast" in opt_text) or ("Fast" not in target_model and "Fast" not in opt_text):
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
        """下载图片并上传"""
        try:
            # 下载图片到临时文件
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url)
                response.raise_for_status()
            
            # 获取文件扩展名
            content_type = response.headers.get("content-type", "image/png")
            ext = content_type.split("/")[-1] if "/" in content_type else "png"
            if ext not in ["jpg", "jpeg", "png", "webp", "bmp"]:
                ext = "png"
            
            # 保存到临时文件
            with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
                tmp.write(response.content)
                tmp_path = tmp.name
            
            print(f"[JIMENG-SUBMIT] [{account_id}] 上传{label}: {url[:50]}...")
            
            # 上传文件
            await input_locator.set_input_files(tmp_path)
            await page.wait_for_timeout(1000)
            
            # 删除临时文件
            os.unlink(tmp_path)
            
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
JIMENG_STATUS_UNKNOWN = "unknown"        # 未知


async def scan_video_status(
    account: dict,
    prompt: Optional[str] = None,
) -> dict:
    """
    扫描即梦视频生成状态
    
    参数:
        account: 账号信息，包含 cookie
        prompt: 提示词（可选，用于匹配特定视频）
    
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

            videos = []

            # 查找所有视频记录卡片 - 直接找包含 progress-badge 或 video 标签的容器
            # 每个视频卡片都有 video-record-nlt6eI 这个 class
            video_records = page.locator("div[class*='video-record'][class*='nlt6eI']")
            record_count = await video_records.count()
            print(f"[JIMENG-SCAN] [{account_id}] 找到 {record_count} 个视频记录")

            for i in range(record_count):
                record = video_records.nth(i)
                video_info = {"status": JIMENG_STATUS_UNKNOWN, "progress": 0}

                try:
                    # 调试：打印记录的 HTML 结构
                    if i == 0:
                        html = await record.inner_html()
                        print(f"[JIMENG-SCAN] [{account_id}] 第一个记录 HTML 预览: {html[:200]}...")

                    # 获取提示词 - prompt-value-container 内的 span
                    prompt_el = record.locator("[class*='prompt-value-container'] > span").first
                    if await prompt_el.count() > 0:
                        video_info["prompt"] = await prompt_el.text_content() or ""
                    else:
                        # 备用：直接找 prompt-value-container
                        prompt_el = record.locator("[class*='prompt-value-container']").first
                        if await prompt_el.count() > 0:
                            video_info["prompt"] = await prompt_el.text_content() or ""
                    
                    print(f"[JIMENG-SCAN] [{account_id}] 视频 {i+1} 提示词: {video_info.get('prompt', '')[:30]}...")

                    # 获取模型 - 第一个 label
                    label_el = record.locator("[class*='label-lhnDlt']").first
                    if await label_el.count() > 0:
                        video_info["model"] = await label_el.text_content() or ""

                    # 检测状态
                    progress_badge = record.locator("[class*='progress-badge']").first
                    if await progress_badge.count() > 0:
                        badge_text = await progress_badge.text_content() or ""
                        print(f"[JIMENG-SCAN] [{account_id}] 视频 {i+1} badge: {badge_text[:30]}")
                        
                        if "排队中" in badge_text:
                            video_info["status"] = JIMENG_STATUS_QUEUING
                            video_info["progress"] = -1
                        elif "造梦中" in badge_text:
                            video_info["status"] = JIMENG_STATUS_GENERATING
                            # 提取进度百分比
                            match = re.search(r"(\d+)%", badge_text)
                            if match:
                                video_info["progress"] = int(match.group(1))
                    else:
                        # 没有 progress-badge，检查是否有视频（已完成）
                        video_el = record.locator("video")
                        if await video_el.count() > 0:
                            video_info["status"] = JIMENG_STATUS_COMPLETED
                            video_info["progress"] = 100
                            video_src = await video_el.first.get_attribute("src") or ""
                            if video_src:
                                video_info["video_url"] = video_src

                    # 如果指定了提示词，只返回匹配的视频
                    if prompt is None or prompt in video_info.get("prompt", ""):
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
