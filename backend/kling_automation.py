"""
可灵AI自动化 - Playwright浏览器自动化
支持：登录检测、QR码登录、表单填写、模型选择、视频生成提交
"""
import asyncio
import base64
import json
import os
import re
import sys
import time
from datetime import datetime
from typing import Dict, Optional, Any
from pathlib import Path

# 确保在Windows下使用UTF-8编码输出
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

# ============ 配置 ============

KLING_URL = "https://app.klingai.com/cn/video/new?ac=1"
KLING_LOGIN_CHECK_API = "api/user/isLogin"
KLING_QR_START_API = "id.klingai.com/rest/c/infra/ks/qr/start"
KLING_QR_CALLBACK_API = "id.klingai.com/pass/kuaishou/login/qr/callback"
KLING_FEEDS_API = "api/user/works/personal/feeds"

# ============ 工具函数 ============

def parse_feeds_url(url: str) -> dict:
    """解析feeds接口URL参数，区分历史列表和任务轮询"""
    from urllib.parse import urlparse, parse_qs
    parsed = parse_qs(urlparse(url).query)
    return {
        "taskId": parsed.get("taskId", [None])[0],
        "pageSize": parsed.get("pageSize", ["1"])[0],
    }

# 模型名称映射
KLING_MODELS = {
    "视频 3.0": "3.0",
    "视频 2.6": "2.6",
    "视频 2.5 Turbo": "2.5",
    "kling_3.0": "3.0",
    "kling_2.6": "2.6",
    "kling_2.5_turbo": "2.5",
}

DATA_DIR = Path("./browser_data/kling")


def log(msg: str, level: str = "info"):
    prefix = {"info": "ℹ️", "success": "✅", "warn": "⚠️", "error": "❌"}.get(level, "")
    print(f"[KLING] {prefix} {msg}", flush=True)


class KlingAutomation:
    """可灵AI浏览器自动化"""

    def __init__(self):
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.playwright = None
        self.is_logged_in = False
        # QR码登录状态
        self.qr_image_base64: Optional[str] = None
        self.qr_login_pending = False
        # API监听结果
        self._submit_event: Optional[asyncio.Event] = None
        self._submit_result: Optional[dict] = None
        self._feeds_data: Optional[dict] = None
        # 任务轮询状态: taskId -> {status, works, ...}
        self._task_polls: Dict[str, dict] = {}
        # 历史列表数据
        self._history_event: Optional[asyncio.Event] = None

    # ============ 浏览器管理 ============

    async def start(self, headless: bool = False):
        """启动浏览器"""
        if self.browser:
            return

        DATA_DIR.mkdir(parents=True, exist_ok=True)

        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=headless,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--window-size=1280,720",
            ],
            slow_mo=100,
        )

        # 创建上下文，加载已保存的登录状态
        storage_file = DATA_DIR / "storage_state.json"
        ctx_opts = {
            "viewport": {"width": 1280, "height": 720},
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
        }
        if storage_file.exists():
            try:
                ctx_opts["storage_state"] = str(storage_file)
                log("加载已保存的登录状态")
            except Exception:
                pass

        self.context = await self.browser.new_context(**ctx_opts)
        self.page = await self.context.new_page()

        # 注册API监听器
        self.page.on("response", self._on_response)

        log("浏览器已启动", "success")

    async def stop(self):
        """关闭浏览器"""
        if self.context:
            await self._save_state()
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        self.browser = None
        self.context = None
        self.page = None
        log("浏览器已关闭")

    async def _save_state(self):
        """保存登录状态"""
        try:
            storage_file = DATA_DIR / "storage_state.json"
            await self.context.storage_state(path=str(storage_file))
            log("登录状态已保存")
        except Exception as e:
            log(f"保存状态失败: {e}", "warn")

    # ============ API响应监听 ============

    async def _on_response(self, response):
        """统一API响应监听器"""
        url = response.url
        try:
            # 只处理成功的JSON响应
            if response.status != 200:
                return

            # 1. 登录状态检测
            if KLING_LOGIN_CHECK_API in url:
                try:
                    data = await response.json()
                except Exception:
                    return
                login_status = data.get("data", {}).get("login", False)
                self.is_logged_in = login_status
                log(f"登录状态: {'已登录' if login_status else '未登录'}")

            # 2. QR码生成
            elif KLING_QR_START_API in url:
                try:
                    data = await response.json()
                except Exception:
                    return
                if data.get("result") == 1:
                    self.qr_image_base64 = data.get("imageData")
                    self.qr_login_pending = True
                    log("QR码已生成，等待扫码...")

            # 3. QR码扫码回调 - 登录成功
            elif KLING_QR_CALLBACK_API in url:
                try:
                    data = await response.json()
                except Exception:
                    return
                if data.get("result") == 1 and data.get("userId"):
                    self.is_logged_in = True
                    self.qr_login_pending = False
                    log(f"QR码登录成功, userId={data['userId']}", "success")
                    await self._save_state()

            # 4. 作品列表 feeds API
            elif KLING_FEEDS_API in url:
                try:
                    data = await response.json()
                except Exception:
                    return
                if data.get("result") == 1:
                    feeds_info = parse_feeds_url(url)
                    task_id = feeds_info["taskId"]

                    if task_id:
                        # 轮询特定任务状态
                        history = data.get("data", {}).get("history", [])
                        if history:
                            item = history[0]
                            task = item.get("task", {})
                            self._task_polls[task_id] = {
                                "status": task.get("status"),
                                "works": item.get("works", []),
                                "etaTime": item.get("etaTime", 0),
                            }
                            log(f"任务轮询: taskId={task_id}, status={task.get('status')}")
                            # 提交确认
                            if self._submit_event and not self._submit_event.is_set():
                                self._submit_event.set()
                    else:
                        # 历史列表（无taskId）
                        history = data.get("data", {}).get("history", [])
                        log(f"历史列表响应: {len(history)} 条记录")
                        for item in history:
                            task = item.get("task", {})
                            task_info = task.get("taskInfo", {})
                            prompt_val = ""
                            for arg in task_info.get("arguments", []):
                                if arg.get("name") == "prompt":
                                    prompt_val = arg.get("value", "")
                                    break
                            works = item.get("works", [])
                            work_statuses = []
                            for w in works[:3]:
                                video_url = w.get("resource", "") if isinstance(w.get("resource"), str) else w.get("resource", {}).get("resource", "")
                                video_short = video_url[:60] + "..." if len(video_url) > 60 else video_url
                                work_statuses.append(f"workId={w.get('workId')},status={w.get('status')},video={video_short if video_url else 'none'}")
                            log(f"  taskId={task.get('id') or item.get('taskId')}, status={task.get('status') or w.get('status')}, prompt={prompt_val or item.get('works', [{}])[0].get('prompt', '')[:40]}, works=[{', '.join(work_statuses)}]")
                        if history:
                            self._feeds_data = data.get("data", {})
                            if self._history_event and not self._history_event.is_set():
                                self._history_event.set()

        except Exception:
            # 静默忽略导航期间的Protocol error
            pass

    # ============ 登录流程 ============

    async def dismiss_popup(self):
        """关闭可能出现的弹窗"""
        try:
            close_btn = self.page.locator("div.close.all-center svg use[xlink\\:href='#icon-close']").first
            if await close_btn.is_visible(timeout=2000):
                await close_btn.locator("xpath=ancestor::div[contains(@class,'close')]").click()
                await asyncio.sleep(0.5)
                log("已关闭弹窗")
        except Exception:
            pass

    async def navigate_to_kling(self):
        """导航到可灵生成页"""
        await self.page.goto(KLING_URL, timeout=30000, wait_until="domcontentloaded")
        await asyncio.sleep(3)
        await self.dismiss_popup()
        log(f"已导航到可灵: {self.page.url}")

    async def check_login(self) -> bool:
        """检查登录状态 - 通过导航触发isLogin接口监听"""
        self.is_logged_in = False
        await self.navigate_to_kling()
        # isLogin接口会在页面加载时自动触发，等待监听器捕获
        await asyncio.sleep(3)
        return self.is_logged_in

    async def start_qr_login(self) -> Optional[str]:
        """
        发起QR码登录流程
        返回: base64编码的QR码图片数据，或None
        """
        self.qr_image_base64 = None
        self.qr_login_pending = False

        # 点击登录按钮
        login_clicked = False
        for selector in [
            "button:has-text('一键登录')",
            "div:has-text('登录'):not(:has(div))",
            "span:has-text('登录')",
        ]:
            try:
                btn = self.page.locator(selector).first
                if await btn.is_visible(timeout=3000):
                    await btn.click()
                    login_clicked = True
                    log("已点击登录按钮")
                    break
            except Exception:
                continue

        if not login_clicked:
            log("未找到登录按钮", "error")
            return None

        await asyncio.sleep(2)

        # 点击"扫码登录"
        try:
            qr_tab = self.page.locator("div:has-text('扫码登录'):not(:has(div))").first
            await qr_tab.click(timeout=5000)
            log("已点击扫码登录")
        except Exception as e:
            log(f"点击扫码登录失败: {e}", "warn")

        # 等待QR码API响应
        for _ in range(10):
            await asyncio.sleep(1)
            if self.qr_image_base64:
                # 保存QR码图片到本地方便查看
                try:
                    qr_path = DATA_DIR / "qr_login.png"
                    with open(qr_path, "wb") as f:
                        f.write(base64.b64decode(self.qr_image_base64))
                    log(f"QR码已保存到 {qr_path}", "success")
                except Exception:
                    pass
                return self.qr_image_base64

        log("等待QR码超时", "error")
        return None

    async def wait_qr_login(self, timeout: int = 120) -> bool:
        """等待QR码扫码登录完成"""
        log(f"等待扫码登录... (超时{timeout}秒)")
        for _ in range(timeout):
            if self.is_logged_in:
                return True
            await asyncio.sleep(1)
        log("扫码登录超时", "error")
        return False

    # ============ 表单填写 ============

    async def fill_prompt(self, prompt: str) -> bool:
        """填写提示词到contenteditable输入框"""
        try:
            # 可灵使用 ProseMirror 编辑器
            editor = self.page.locator("div.ProseMirror[contenteditable='true']").first
            await editor.wait_for(state="visible", timeout=10000)
            await editor.click()
            await asyncio.sleep(0.3)

            # 清空现有内容
            await self.page.keyboard.press("Control+A")
            await self.page.keyboard.press("Backspace")
            await asyncio.sleep(0.2)

            # 输入提示词
            await self.page.keyboard.type(prompt, delay=30)
            await asyncio.sleep(0.5)

            log(f"提示词已填写: {prompt[:50]}...")
            return True
        except Exception as e:
            log(f"填写提示词失败: {e}", "error")
            return False

    async def upload_first_frame(self, image_path: str) -> bool:
        """上传首帧图片"""
        try:
            # 点击"添加 首尾帧图"
            upload_btn = self.page.locator("p:has-text('添加 首尾帧图')").first
            if not await upload_btn.is_visible(timeout=5000):
                # 备选：通过icon定位
                upload_btn = self.page.locator("div.clickable.click-here").first

            await upload_btn.click()
            await asyncio.sleep(1)

            # 等待文件选择器
            async with self.page.expect_file_chooser(timeout=5000) as fc_info:
                # 可能需要再点一次触发文件选择
                pass
            file_chooser = await fc_info.value
            await file_chooser.set_files(image_path)
            await asyncio.sleep(2)

            log(f"首帧图片已上传: {image_path}", "success")
            return True
        except Exception as e:
            log(f"上传首帧失败: {e}", "error")
            return False

    async def upload_last_frame(self, image_path: str) -> bool:
        """上传尾帧图片（需要先上传首帧）"""
        try:
            upload_btn = self.page.locator("p:has-text('添加 尾帧图')").first
            if not await upload_btn.is_visible(timeout=5000):
                upload_btn = self.page.locator("p:has-text('尾帧图(可选)')").first

            await upload_btn.click()
            await asyncio.sleep(1)

            async with self.page.expect_file_chooser(timeout=5000) as fc_info:
                pass
            file_chooser = await fc_info.value
            await file_chooser.set_files(image_path)
            await asyncio.sleep(2)

            log(f"尾帧图片已上传: {image_path}", "success")
            return True
        except Exception as e:
            log(f"上传尾帧失败: {e}", "error")
            return False

    # ============ 模型选择 ============

    async def select_model(self, model_name: str) -> bool:
        """选择生成模型"""
        target_version = KLING_MODELS.get(model_name, model_name)
        try:
            # 点击模型选择下拉框
            dropdown = self.page.locator("div.el-select__wrapper").first
            await dropdown.click(timeout=5000)
            await asyncio.sleep(1)

            # 在下拉列表中找到目标模型
            # 用 model-name 文本匹配
            if target_version == "3.0":
                option = self.page.locator("li.option span.model-name:has-text('视频 3.0')").first
            elif target_version == "2.6":
                option = self.page.locator("li.option span.model-name:has-text('视频 2.6')").first
            else:
                option = self.page.locator("li.option span.model-name:has-text('视频 2.5')").first

            # 点击选项的父级li
            li = option.locator("xpath=ancestor::li")
            await li.click(timeout=5000)
            await asyncio.sleep(0.5)

            log(f"已选择模型: 视频 {target_version}", "success")
            return True
        except Exception as e:
            log(f"选择模型失败: {e}", "error")
            return False

    # ============ 视频设置（分辨率、时长、数量） ============

    async def open_settings_panel(self) -> bool:
        """打开设置面板（分辨率·时长·数量）"""
        try:
            # 点击设置按钮 "720p · 3s · 1"
            settings_btn = self.page.locator("div.setting-select").first
            await settings_btn.click(timeout=5000)
            await asyncio.sleep(1)
            log("设置面板已打开")
            return True
        except Exception as e:
            log(f"打开设置面板失败: {e}", "error")
            return False

    async def set_resolution(self, resolution: str = "720p") -> bool:
        """设置分辨率: 720p 或 1080p"""
        try:
            option = self.page.locator(f"div.option-tab-item.model_mode div.inner:has-text('{resolution}')").first
            await option.click(timeout=3000)
            await asyncio.sleep(0.3)
            log(f"分辨率已设置: {resolution}")
            return True
        except Exception as e:
            log(f"设置分辨率失败: {e}", "error")
            return False

    async def set_duration(self, seconds: int = 5) -> bool:
        """设置视频时长 (3-15秒)，通过滑块"""
        try:
            # 读取当前时长
            duration_label = self.page.locator("div.option-name:has-text('生成时长')").first
            label_text = await duration_label.text_content()
            current = int(re.search(r"(\d+)", label_text).group(1)) if re.search(r"(\d+)", label_text) else 3

            if current == seconds:
                log(f"时长已是 {seconds}s")
                return True

            # 通过slider设置
            slider = self.page.locator("div.el-slider div.el-slider__runway").first
            slider_box = await slider.bounding_box()
            if not slider_box:
                log("找不到滑块", "error")
                return False

            # 计算目标位置 (3s=0%, 15s=100%)
            ratio = (seconds - 3) / (15 - 3)
            target_x = slider_box["x"] + slider_box["width"] * ratio
            target_y = slider_box["y"] + slider_box["height"] / 2

            await self.page.mouse.click(target_x, target_y)
            await asyncio.sleep(0.5)

            log(f"时长已设置: {seconds}s", "success")
            return True
        except Exception as e:
            log(f"设置时长失败: {e}", "error")
            return False

    async def set_quantity(self, count: int = 1) -> bool:
        """设置生成数量 (1-4)"""
        try:
            option = self.page.locator(f"div.option-tab-item.imageCount div.inner:has-text('{count}')").first
            await option.click(timeout=3000)
            await asyncio.sleep(0.3)
            log(f"生成数量已设置: {count}")
            return True
        except Exception as e:
            log(f"设置数量失败: {e}", "error")
            return False

    async def close_settings_panel(self):
        """关闭设置面板（点击空白处）"""
        try:
            await self.page.mouse.click(640, 200)
            await asyncio.sleep(0.5)
        except Exception:
            pass

    # ============ 提交生成 ============

    async def click_generate(self) -> bool:
        """点击生成按钮"""
        try:
            # 按钮包含"生成"文字
            gen_btn = self.page.locator("button.generic-button.critical:has-text('生成')").first
            await gen_btn.wait_for(state="visible", timeout=5000)
            await gen_btn.click()
            log("已点击生成按钮", "success")
            return True
        except Exception as e:
            log(f"点击生成失败: {e}", "error")
            return False

    async def submit_and_confirm(self, timeout: int = 15) -> Optional[dict]:
        """
        点击生成并等待feeds API确认提交成功
        返回: feeds响应数据 或 None
        """
        self._submit_event = asyncio.Event()
        self._feeds_data = None

        if not await self.click_generate():
            return None

        # 等待feeds API响应确认
        try:
            await asyncio.wait_for(self._submit_event.wait(), timeout=timeout)
            if self._feeds_data:
                history = self._feeds_data.get("history", [])
                if history:
                    task = history[0].get("task", {})
                    log(f"提交确认成功, taskId={task.get('id')}, status={task.get('status')}", "success")
                return self._feeds_data
        except asyncio.TimeoutError:
            log(f"等待提交确认超时({timeout}s)", "warn")

        return None

    # ============ 完整生成流程 ============

    async def generate_video(
        self,
        prompt: str,
        model: str = "视频 3.0",
        resolution: str = "720p",
        duration: int = 5,
        quantity: int = 1,
        first_frame: Optional[str] = None,
        last_frame: Optional[str] = None,
    ) -> Optional[dict]:
        """
        完整的视频生成流程
        返回: feeds确认数据 或 None
        """
        log(f"开始生成视频: model={model}, {resolution}, {duration}s, qty={quantity}")

        # 1. 导航到生成页
        await self.navigate_to_kling()

        # 2. 检查登录
        if not self.is_logged_in:
            log("未登录，无法生成", "error")
            return None

        # 3. 填写提示词
        if not await self.fill_prompt(prompt):
            return None

        # 4. 上传首帧（如果有）
        if first_frame:
            if not await self.upload_first_frame(first_frame):
                return None
            # 上传尾帧（如果有）
            if last_frame:
                await self.upload_last_frame(last_frame)

        # 5. 选择模型
        if not await self.select_model(model):
            return None

        # 6. 设置参数
        if await self.open_settings_panel():
            await self.set_resolution(resolution)
            await self.set_duration(duration)
            await self.set_quantity(quantity)
            await self.close_settings_panel()

        # 7. 提交并确认
        return await self.submit_and_confirm()

    # ============ 查询任务状态 ============

    async def get_task_status(self) -> list:
        """
        导航到生成页获取最新的任务列表（监听带pageSize的feeds请求）
        注意：用goto而非reload，避免导航期间response失效
        返回: [{taskId, status, prompt, works: [...]}]
        """
        self._feeds_data = None
        self._history_event = asyncio.Event()

        # 用goto导航，让页面完整加载并触发feeds API
        await self.page.goto(KLING_URL, timeout=30000, wait_until="domcontentloaded")

        # 等待历史列表API响应（有数据的那个）
        try:
            await asyncio.wait_for(self._history_event.wait(), timeout=20)
        except asyncio.TimeoutError:
            log("等待历史列表API超时", "warn")

        if not self._feeds_data:
            log("未捕获到feeds数据", "warn")
            return []

        results = []
        for item in self._feeds_data.get("history", []):
            task = item.get("task", {})
            task_info = task.get("taskInfo", {})
            # 从arguments中提取prompt
            prompt_val = ""
            for arg in task_info.get("arguments", []):
                if arg.get("name") == "prompt":
                    prompt_val = arg.get("value", "")
                    break

            works = []
            for w in item.get("works", []):
                resource = w.get("resource", "")
                video_url = resource if isinstance(resource, str) else resource.get("resource", "")
                cover = w.get("cover", "")
                cover_url = cover if isinstance(cover, str) else cover.get("resource", "")
                works.append({
                    "workId": w.get("workId"),
                    "status": w.get("status"),
                    "videoUrl": video_url,
                    "coverUrl": cover_url,
                })

            results.append({
                "taskId": task.get("id"),
                "status": task.get("status"),
                "prompt": prompt_val,
                "works": works,
                "etaTime": item.get("etaTime", 0),
            })

        return results


# ============ 测试脚本 ============

async def test_kling():
    """本地测试入口 - 可视化模式，不会真正点击生成"""

    # 让用户设置测试参数
    print("\n========== 可灵自动化测试 ==========")
    prompt = "一只可爱的小猫在阳光下打盹"

    model_map = {"1": "视频 3.0", "2": "视频 2.6", "3": "视频 2.5 Turbo"}
    model = model_map.get("1", "视频 3.0")

    resolution = "720p"

    duration = 5

    quantity = 1

    print(f"\n参数确认: prompt={prompt[:30]}..., model={model}, {resolution}, {duration}s, qty={quantity}")
    confirm = "y"
    if confirm == "n":
        print("已取消")
        return
    print("=========================================\n")

    kling = KlingAutomation()
    await kling.start(headless=False)

    try:
        # === 步骤1: 检查登录 ===
        log("=== 步骤1: 检查登录状态 ===")
        logged_in = await kling.check_login()
        if not logged_in:
            log("需要扫码登录...")
            qr = await kling.start_qr_login()
            if qr:
                log(f"请扫描 {DATA_DIR / 'qr_login.png'} 登录")
                success = await kling.wait_qr_login(timeout=120)
                if not success:
                    log("登录失败", "error")
                    return
            else:
                log("获取QR码失败", "error")
                return

        log("登录成功!", "success")

        # === 步骤2: 测试监听feeds API获取历史视频 ===
        log("=== 步骤2: 刷新页面，监听feeds API获取历史视频 ===")
        tasks = await kling.get_task_status()
        if tasks:
            log(f"获取到 {len(tasks)} 个历史任务:", "success")
            for i, t in enumerate(tasks[:5]):
                status_map = {0: "排队中", 5: "处理中", 10: "已完成", 99: "失败"}
                status_text = status_map.get(t["status"], f"未知({t['status']})")
                log(f"  [{i+1}] taskId={t['taskId']}, status={status_text}, prompt={t['prompt'][:40]}")
                for w in t["works"][:2]:
                    video_info = w.get("videoUrl") or "无视频"
                    log(f"       workId={w['workId']}, status={w['status']}, url={video_info}")
        else:
            log("未获取到历史任务（可能没有生成记录或API未触发）", "warn")

        # === 步骤3: 导航到生成页 ===
        log("=== 步骤3: 导航到生成页 ===")
        await kling.navigate_to_kling()

        # === 步骤4: 填写提示词 ===
        log("=== 步骤4: 填写提示词 ===")
        if await kling.fill_prompt(prompt):
            log("提示词填写成功", "success")
        else:
            log("提示词填写失败", "error")

        # === 步骤5: 选择模型 ===
        log("=== 步骤5: 选择模型 ===")
        if await kling.select_model(model):
            log("模型选择成功", "success")
        else:
            log("模型选择失败", "error")

        # === 步骤6: 设置参数 ===
        log("=== 步骤6: 打开设置面板，设置参数 ===")
        if await kling.open_settings_panel():
            await kling.set_resolution(resolution)
            await kling.set_duration(duration)
            await kling.set_quantity(quantity)
            await kling.close_settings_panel()
            log("参数设置完成", "success")

        # === 停在这里，不点生成 ===
        log("=== 测试完成 ===")
        log("所有步骤已验证，停留在生成按钮前（未点击生成）")
        log("按 Ctrl+C 退出...")

        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        log("用户中断")
    finally:
        await kling.stop()


if __name__ == "__main__":
    asyncio.run(test_kling())
