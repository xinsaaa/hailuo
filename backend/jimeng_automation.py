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
                await page.wait_for_timeout(1000)
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
                await asyncio.sleep(3)
                await auth_page.screenshot(path=_debug_path("04_auth_popup"))

                # ===== 步骤 5：截取二维码图片 =====
                print(f"[JIMENG-LOGIN] [{self.account_id}] 步骤5: 截取二维码")
                # 等待二维码图片加载（最多等待 15 秒）
                qr_img = auth_page.locator("img.semi-image-img").first
                try:
                    await qr_img.wait_for(state="visible", timeout=15000)
                except Exception:
                    await auth_page.screenshot(path=_debug_path("05_qr_not_found"))
                    self.status = "failed"
                    self.error = "未找到二维码图片"
                    return
                await auth_page.screenshot(path=_debug_path("05_qr_page"))

                qr_bytes = await qr_img.screenshot()
                self.qr_base64 = base64.b64encode(qr_bytes).decode()
                self.status = "scanning"
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
                await page.screenshot(path=_debug_path("06_popup_closed"))

                # ===== 步骤 7：等待头像出现，判定登录成功 =====
                print(f"[JIMENG-LOGIN] [{self.account_id}] 步骤7: 检测头像登录态")
                avatar = page.locator("img.dreamina-component-avatar")
                try:
                    await avatar.wait_for(state="visible", timeout=20000)
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
    first_frame_url: Optional[str] = None,
    last_frame_url: Optional[str] = None,
) -> dict:
    """
    提交即梦视频生成任务
    
    参数:
        account: 账号信息，包含 cookie
        prompt: 提示词
        model: 模型名称，支持 "Seedance 2.0 Fast" 和 "Seedance 2.0"
        first_frame_url: 首帧图片URL（可选，用于图生视频）
        last_frame_url: 尾帧图片URL（可选，用于图生视频）
    
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
            await page.wait_for_timeout(3000)
            
            # 步骤1.5：关闭可能的"绑定剪映账号"弹窗
            try:
                bind_modal = page.locator("[class*='bind-capcut-account-first-screen-modal-content']")
                if await bind_modal.count() > 0:
                    print(f"[JIMENG-SUBMIT] [{account_id}] 检测到绑定剪映弹窗，尝试关闭")
                    close_btn = bind_modal.locator("[class*='close-icon']").first
                    if await close_btn.is_visible(timeout=2000):
                        await close_btn.click()
                        await page.wait_for_timeout(1000)
                        print(f"[JIMENG-SUBMIT] [{account_id}] 已关闭绑定剪映弹窗")
            except Exception as e:
                print(f"[JIMENG-SUBMIT] [{account_id}] 关闭弹窗异常（继续）: {e}")
            
            await page.screenshot(path=_debug_path("submit_01_gen_page"))

            # 步骤2：选择模型（稳定写法）
            print(f"[JIMENG-SUBMIT] [{account_id}] 选择模型: {model}")
            await _select_video_model(page, model, account_id)

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
            await page.wait_for_timeout(1000)  # 输入后等待1秒
            await page.screenshot(path=_debug_path("submit_02_prompt_filled"))

            # 步骤4：点击生成按钮
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
            
            await page.wait_for_timeout(2000)
            
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
    选择视频模型
    
    页面有多个下拉框，class 类型一致，需要根据上方的标签文字来定位
    模型选择器上方通常有"模型"或相关标签文字
    """
    supported_models = ["Seedance 2.0 Fast", "Seedance 2.0"]
    if target_model not in supported_models:
        print(f"[JIMENG-SUBMIT] [{account_id}] 不支持的模型: {target_model}，使用默认模型")
        target_model = "Seedance 2.0 Fast"
    
    try:
        await page.wait_for_timeout(1500)
        await page.screenshot(path=_debug_path("model_00_before_select"))
        
        print(f"[JIMENG-SUBMIT] [{account_id}] 查找模型选择器...")
        
        # 方法1：通过标签文字定位模型选择器
        # 查找包含"模型"文字的标签，然后找其下方的下拉框
        model_labels = ["模型", "视频模型", "Model"]
        
        for label_text in model_labels:
            try:
                # 找到包含标签文字的元素
                label = page.get_by_text(label_text, exact=True).first
                if await label.count() > 0:
                    # 获取父容器，然后找下拉框
                    parent = label.locator("xpath=ancestor::div[contains(@class, 'lv-form-item') or contains(@class, 'form-item')]").first
                    if await parent.count() > 0:
                        selector = parent.locator(".lv-select-view").first
                        if await selector.count() > 0:
                            print(f"[JIMENG-SUBMIT] [{account_id}] 通过标签 '{label_text}' 找到模型选择器")
                            
                            # 点击打开下拉框
                            selector_btn = selector.locator(".lv-select-view-selector")
                            if await selector_btn.count() > 0:
                                await selector_btn.click()
                            else:
                                await selector.click()
                            await page.wait_for_timeout(800)
                            await page.screenshot(path=_debug_path("model_01_dropdown_open"))
                            
                            # 点击目标模型
                            target_option = page.get_by_text(target_model, exact=True)
                            await target_option.first.click()
                            await page.wait_for_timeout(500)
                            await page.screenshot(path=_debug_path("model_02_selected"))
                            
                            print(f"[JIMENG-SUBMIT] [{account_id}] 模型已切换为 {target_model}")
                            return
            except Exception as e:
                print(f"[JIMENG-SUBMIT] [{account_id}] 标签 '{label_text}' 定位失败: {str(e)[:50]}")
        
        # 方法2：遍历所有下拉框，通过打开后检查选项来判断
        print(f"[JIMENG-SUBMIT] [{account_id}] 方法1失败，尝试遍历下拉框...")
        
        all_selects = page.locator(".lv-select-view")
        select_count = await all_selects.count()
        print(f"[JIMENG-SUBMIT] [{account_id}] 页面上找到 {select_count} 个下拉框")
        
        for i in range(select_count):
            current_select = all_selects.nth(i)
            
            try:
                # 点击打开下拉框
                selector_btn = current_select.locator(".lv-select-view-selector")
                if await selector_btn.count() > 0:
                    await selector_btn.click()
                else:
                    await current_select.click()
                await page.wait_for_timeout(500)
                
                # 检查是否出现了 Seedance 选项
                seedance_option = page.get_by_text("Seedance 2.0", exact=True)
                fast_option = page.get_by_text("Seedance 2.0 Fast", exact=True)
                
                if await seedance_option.count() > 0 or await fast_option.count() > 0:
                    print(f"[JIMENG-SUBMIT] [{account_id}] 第 {i+1} 个下拉框是模型选择器")
                    await page.screenshot(path=_debug_path("model_01_dropdown_open"))
                    
                    # 点击目标模型
                    target_option = page.get_by_text(target_model, exact=True)
                    await target_option.first.click()
                    await page.wait_for_timeout(500)
                    await page.screenshot(path=_debug_path("model_02_selected"))
                    
                    print(f"[JIMENG-SUBMIT] [{account_id}] 模型已切换为 {target_model}")
                    return
                else:
                    # 不是模型选择器，关闭下拉框
                    await page.keyboard.press("Escape")
                    await page.wait_for_timeout(300)
                    
            except Exception as e:
                print(f"[JIMENG-SUBMIT] [{account_id}] 第 {i+1} 个下拉框检查失败: {str(e)[:50]}")
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(300)
        
        print(f"[JIMENG-SUBMIT] [{account_id}] 未找到模型选择器")
        
    except Exception as e:
        print(f"[JIMENG-SUBMIT] [{account_id}] 模型选择失败（继续）: {str(e)[:100]}")
        await page.screenshot(path=_debug_path("model_error"))


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
