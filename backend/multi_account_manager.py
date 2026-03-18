"""
海螺AI多账号管理器 - 一个浏览器支持多个账号
使用Browser Context隔离不同账号的Session和Cookie
"""
import asyncio
import os
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from pathlib import Path


@dataclass
class AccountConfig:
    """账号配置"""
    account_id: str          # 账号标识
    phone_number: str        # 手机号
    display_name: str        # 显示名称
    priority: int = 1        # 优先级 (1-10, 10最高)
    is_active: bool = True   # 是否启用
    max_concurrent: int = 3  # 最大并发任务数
    current_tasks: int = 0   # 当前任务数
    series: str = "2.3"      # 绑定的模型系列 ("2.3" 或 "3.1")


class MultiAccountManager:
    """多账号管理器"""
    
    def __init__(self, data_dir: str = "./browser_data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        # 单个浏览器实例
        self.browser: Optional[Browser] = None
        
        # 每个账号对应一个Context
        self.contexts: Dict[str, BrowserContext] = {}
        self.pages: Dict[str, Page] = {}
        
        # 账号配置
        self.accounts: Dict[str, AccountConfig] = {}
        
        # 任务分配
        self.account_queues: Dict[str, asyncio.Queue] = {}
        
        # 已验证登录的账号集合（只有真正通过页面验证的才算）
        self._verified_accounts: set = set()
        
        # 登录失败计数器（用于心跳保护，连续失败N次才标记掉线）
        self._login_fail_count: Dict[str, int] = {}
        LOGIN_FAIL_THRESHOLD = 3
    
    async def init_browser(self):
        """初始化单个浏览器实例"""
        if self.browser:
            return
            
        self.playwright = await async_playwright().start()
        
        # 浏览器启动参数
        browser_args = [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",  # Linux内存优化
            "--disable-gpu",  # Linux无GPU环境
            "--disable-web-security",
            "--disable-features=VizDisplayCompositor",
            "--disable-blink-features=AutomationControlled",
            "--disable-extensions",
            "--disable-plugins",
            "--disable-images",  # 节省带宽和内存
            "--disable-javascript-harmony-shipping",
            "--disable-background-timer-throttling",
            "--disable-renderer-backgrounding",
            "--disable-backgrounding-occluded-windows",
            "--disable-features=TranslateUI",
            "--disable-ipc-flooding-protection",
            "--window-size=1280,720",
            "--max_old_space_size=512",  # 限制内存使用
        ]
        
        # 智能检测是否应该使用headless模式
        use_headless = self._should_use_headless()
        
        self.browser = await self.playwright.chromium.launch(
            headless=use_headless,
            args=browser_args,
            slow_mo=100,  # 降低操作频率
        )
        
        print(f"[MULTI-ACCOUNT] 浏览器已启动 (Headless: {use_headless})")
    
    def _should_use_headless(self) -> bool:
        """智能检测是否应该使用headless模式"""
        import platform
        
        # 环境变量强制指定
        env_headless = os.getenv("AUTOMATION_HEADLESS", "").lower()
        if env_headless in ["true", "1"]:
            print("[MULTI-ACCOUNT] 环境变量强制启用headless模式")
            return True
        elif env_headless in ["false", "0"]:
            print("[MULTI-ACCOUNT] 环境变量强制禁用headless模式")
            return False
        
        # Linux环境自动检测
        if platform.system() == "Linux":
            # 检查是否有DISPLAY环境变量（X11图形界面）
            if not os.getenv("DISPLAY"):
                print("[MULTI-ACCOUNT] 🐧 检测到Linux无界面环境，自动启用headless模式")
                return True
            else:
                print("[MULTI-ACCOUNT] 🐧 检测到Linux图形环境，使用有界面模式")
                return False
        
        # Windows/Mac默认使用有界面模式（开发环境）
        print(f"[MULTI-ACCOUNT] 检测到{platform.system()}环境，默认使用有界面模式")
        return False
    
    def load_accounts_config(self, config_file: str = "accounts.json"):
        """加载账号配置"""
        config_path = self.data_dir / config_file
        
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for account_data in data.get("accounts", []):
                    account = AccountConfig(**account_data)
                    self.accounts[account.account_id] = account
        else:
            # 创建默认配置
            default_accounts = [
                AccountConfig(
                    account_id="hailuo_main",
                    phone_number="17366935232",
                    display_name="主账号",
                    priority=10,
                    max_concurrent=5
                ),
                # 可以添加更多账号
                # AccountConfig(
                #     account_id="account_2", 
                #     phone_number="138xxxxxxxx",
                #     display_name="备用账号",
                #     priority=5,
                #     max_concurrent=3
                # )
            ]
            
            self.save_accounts_config(default_accounts, config_file)
    
    def save_accounts_config(self, accounts: List[AccountConfig], config_file: str = "accounts.json"):
        """保存账号配置"""
        config_path = self.data_dir / config_file
        
        data = {
            "accounts": [
                {
                    "account_id": acc.account_id,
                    "phone_number": acc.phone_number,
                    "display_name": acc.display_name,
                    "priority": acc.priority,
                    "is_active": acc.is_active,
                    "max_concurrent": acc.max_concurrent,
                    "current_tasks": 0,
                    "series": acc.series
                }
                for acc in accounts
            ]
        }
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    async def create_account_context(self, account_id: str) -> BrowserContext:
        """为指定账号创建独立的浏览器上下文"""
        # 如果已存在上下文，先关闭旧的防止内存泄漏
        if account_id in self.contexts:
            print(f"[MULTI-ACCOUNT] 账号 {account_id} 已有上下文，跳过创建")
            return self.contexts[account_id]
        
        if not self.browser:
            await self.init_browser()
        
        # 每个账号使用独立的存储目录来保存cookies等状态
        storage_dir = self.data_dir / "profiles" / account_id
        storage_dir.mkdir(parents=True, exist_ok=True)
        
        # 尝试加载已保存的登录状态
        storage_state_file = storage_dir / "storage_state.json"
        context_options = {
            "viewport": {"width": 1280, "height": 720},
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "bypass_csp": True,
            "permissions": ["clipboard-read", "clipboard-write"],
        }
        
        # 如果存在已保存的状态，加载它
        if storage_state_file.exists():
            try:
                context_options["storage_state"] = str(storage_state_file)
                print(f"[MULTI-ACCOUNT] 加载已保存的登录状态: {account_id}")
            except Exception as e:
                print(f"[MULTI-ACCOUNT] 加载状态文件失败: {e}")
        else:
            # 尝试从旧格式迁移
            await self._migrate_old_login_state(account_id, storage_state_file)
        
        # 创建上下文
        context = await self.browser.new_context(**context_options)
        
        # 注意：不拦截图片，因为登录页面可能需要加载验证码图片等资源
        
        self.contexts[account_id] = context
        
        # 创建页面
        page = await context.new_page()
        self.pages[account_id] = page
        
        print(f"[MULTI-ACCOUNT] 账号 {account_id} 上下文已创建")
        return context
    
    async def login_account(self, account_id: str) -> bool:
        """登录指定账号"""
        if account_id not in self.accounts:
            print(f"[MULTI-ACCOUNT] 账号 {account_id} 未配置")
            return False
        
        account = self.accounts[account_id]
        
        # 创建上下文（如果不存在）
        if account_id not in self.contexts:
            await self.create_account_context(account_id)
        
        page = self.pages[account_id]
        
        try:
            print(f"[MULTI-ACCOUNT] 🔍 检查账号登录状态: {account.display_name}")
            
            # 严格检查是否已经登录 - 不依赖Cookie，直接检查页面状态
            if await self.check_login_status(account_id):
                print(f"[MULTI-ACCOUNT] ✅ 账号 {account.display_name} 已确认登录")
                await self._save_cookies(account_id)
                self.mark_account_logged_in(account_id)  # 标记已验证登录
                return True
            
            # 未登录，需要验证码登录流程
            print(f"[MULTI-ACCOUNT] ❌ 账号 {account.display_name} 未登录")
            print(f"[MULTI-ACCOUNT] 📱 需要通过管理后台进行验证码登录")
            print(f"[MULTI-ACCOUNT] 账号手机号: {account.phone_number}")
            
            # 返回False，表示需要验证码登录
            return False
            
        except Exception as e:
            print(f"[MULTI-ACCOUNT] 账号 {account.display_name} 登录检查失败: {e}")
            return False

    async def send_verification_code(self, account_id: str) -> bool:
        """发送验证码到账号手机 - 参考automation.py已验证的选择器"""
        if account_id not in self.accounts:
            print(f"[MULTI-ACCOUNT] 账号 {account_id} 未配置")
            return False
        
        account = self.accounts[account_id]
        
        # 创建上下文（如果不存在）
        if account_id not in self.contexts:
            await self.create_account_context(account_id)
        
        page = self.pages[account_id]
        
        try:
            print(f"[MULTI-ACCOUNT] 发送验证码: {account.display_name}")
            
            # 1. 导航到海螺AI主页
            await page.goto("https://hailuoai.com", timeout=30000)
            await page.wait_for_timeout(2000)
            
            current_url = page.url
            page_title = await page.title()
            print(f"[LOGIN] 页面已加载: {current_url} | 标题: {page_title}")
            
            # 2. 点击登录按钮（与automation.py一致）
            login_btn = page.locator("div.border-hl_line_00:has-text('登录')").first
            try:
                await login_btn.wait_for(state="visible", timeout=10000)
                await login_btn.click()
                print(f"[LOGIN] 已点击登录按钮")
            except:
                # 兜底：尝试其他选择器
                fallback_selectors = ["button:has-text('登录')", "a:has-text('登录')", "span:has-text('登录')"]
                clicked = False
                for sel in fallback_selectors:
                    try:
                        btn = page.locator(sel).first
                        if await btn.is_visible():
                            await btn.click()
                            clicked = True
                            print(f"[LOGIN] 兜底点击登录按钮: {sel}")
                            break
                    except:
                        continue
                if not clicked:
                    print("[LOGIN] 未找到登录按钮")
                    return False
            
            
            # 3. 切换到手机登录tab（与automation.py一致）
            phone_tab = page.locator("#rc-tabs-0-tab-phone")
            try:
                if await phone_tab.is_visible():
                    await phone_tab.click()
                    print(f"[LOGIN] 已切换到手机号登录")
                else:
                    print(f"[LOGIN] 默认为手机登录模式")
            except:
                print(f"[LOGIN] 手机登录tab未找到，可能默认就是手机登录")
            
            # 4. 填写手机号（与automation.py一致：input#phone）
            phone_input = page.locator("input#phone")
            try:
                await phone_input.wait_for(state="visible", timeout=5000)
                await phone_input.fill(account.phone_number)
                print(f"[LOGIN] 已输入手机号: {account.phone_number}")
            except:
                # 兜底选择器
                fallback_phone = ["input[placeholder*='手机']", "input[type='tel']", "input[maxlength='11']"]
                entered = False
                for sel in fallback_phone:
                    try:
                        inp = page.locator(sel).first
                        if await inp.is_visible():
                            await inp.fill(account.phone_number)
                            entered = True
                            print(f"[LOGIN] 兜底输入手机号: {sel}")
                            break
                    except:
                        continue
                if not entered:
                    print("[LOGIN] 未找到手机号输入框")
                    return False
            
            # 5. 点击获取验证码（不需要提前勾选协议，登录时会弹出"同意并登录"）
            
            get_code_btn = page.locator("button:has-text('获取验证码')").first
            try:
                await get_code_btn.wait_for(state="visible", timeout=5000)
                await get_code_btn.click()
                print(f"[LOGIN] 已点击获取验证码按钮")
                
                await page.wait_for_timeout(1000)

                return True
            except:
                # 兜底
                fallback_code = ["button:has-text('发送验证码')", "button:has-text('获取短信验证码')"]
                for sel in fallback_code:
                    try:
                        btn = page.locator(sel).first
                        if await btn.is_visible():
                            await btn.click()
                            print(f"[LOGIN] 兜底点击验证码按钮: {sel}")
                            return True
                    except:
                        continue
                print("[LOGIN] 未找到获取验证码按钮")
                return False
            
        except Exception as e:
            print(f"[MULTI-ACCOUNT] 发送验证码失败 {account.display_name}: {e}")
            return False

    async def verify_code_and_login(self, account_id: str, verification_code: str) -> bool:
        """使用验证码完成登录 - 参考automation.py已验证的选择器"""
        if account_id not in self.accounts:
            return False
        
        if account_id not in self.pages:
            print(f"[MULTI-ACCOUNT] 账号 {account_id} 没有浏览器页面，无法验证")
            return False
        
        account = self.accounts[account_id]
        page = self.pages[account_id]
        
        try:
            print(f"[MULTI-ACCOUNT] 验证码登录: {account.display_name}")
            
            # 1. 填写验证码（与automation.py一致：input#code）
            code_input = page.locator("input#code")
            try:
                await code_input.wait_for(state="visible", timeout=5000)
                await code_input.fill(verification_code)
                print(f"[LOGIN] 已输入验证码")
            except:
                # 兜底选择器
                fallback_code = ["input[placeholder*='验证码']", "input[type='text'][maxlength='6']"]
                entered = False
                for sel in fallback_code:
                    try:
                        inp = page.locator(sel).first
                        if await inp.is_visible():
                            await inp.fill(verification_code)
                            entered = True
                            print(f"[LOGIN] 兜底输入验证码: {sel}")
                            break
                    except:
                        continue
                if not entered:
                    print("[LOGIN] 未找到验证码输入框")
                    return False
            
            # 2. 点击登录按钮（与automation.py一致：button.login-btn）
            login_btn = page.locator("button.login-btn")
            try:
                await login_btn.wait_for(state="visible", timeout=5000)
                await login_btn.click()
                print(f"[LOGIN] 已提交登录")
            except:
                # 兜底
                fallback_submit = ["button:has-text('登录')", "button[type='submit']"]
                for sel in fallback_submit:
                    try:
                        btn = page.locator(sel).first
                        if await btn.is_visible():
                            await btn.click()
                            print(f"[LOGIN] 兜底点击登录: {sel}")
                            break
                    except:
                        continue
            
            # 3. 点击登录后会弹出用户协议弹窗，点击“同意并登录”
            try:
                agree_login_btn = page.locator("button:has-text('同意并登录')").first
                await agree_login_btn.wait_for(state="visible", timeout=5000)
                await agree_login_btn.click()
                print(f"[LOGIN] 已点击'同意并登录'")
            except:
                print(f"[LOGIN] 未弹出协议窗口（可能已同意）")
            
            # 4. 等待登录完成
            print(f"[LOGIN] 等待登录验证...")
            await page.wait_for_timeout(3000)

            # 5. 验证登录结果：出现头像或会员标识 = 登录成功
            avatar_loc = page.locator("div.cursor-pointer.overflow-hidden.rounded-full img[alt*='avatar']")
            vip_loc = page.locator("span.text-hl_brand_01:has-text('尊享会员'), span:has-text('尊享会员')")
            login_confirmed = False
            for _ in range(10):
                await page.wait_for_timeout(1000)
                try:
                    if await avatar_loc.count() > 0 or await vip_loc.count() > 0:
                        login_confirmed = True
                        break
                except Exception:
                    pass
            if not login_confirmed:
                self.mark_account_logged_out(account_id)
                print(f"[MULTI-ACCOUNT] 账号 {account.display_name} 登录验证失败 - 未找到登录标识")
                return False
            print(f"[LOGIN] 已找到登录标识，登录成功")

            # 关闭可能的弹窗
            try:
                close_btn = page.locator("button.ant-modal-close")
                if await close_btn.is_visible():
                    await close_btn.click(force=True)
                    print(f"[LOGIN] 已关闭弹窗")
            except:
                pass

            await self._save_cookies(account_id)
            self.mark_account_logged_in(account_id)
            print(f"[MULTI-ACCOUNT] 账号 {account.display_name} 验证码登录成功")
            return True
                
        except Exception as e:
            print(f"[MULTI-ACCOUNT] 验证码登录失败 {account.display_name}: {e}")
            return False

    async def check_login_status(self, account_id: str) -> bool:
        """检查账号登录状态 - 不导航页面，避免打断正在进行的任务"""
        if account_id not in self.pages:
            return False

        page = self.pages[account_id]
        account = self.accounts.get(account_id)

        try:
            # 如果账号正在处理任务，跳过检查，视为在线
            if account and account.current_tasks > 0:
                print(f"[MULTI-ACCOUNT] ⏭️ 账号 {account_id} 正在处理任务，跳过登录检查")
                return True

            print(f"[MULTI-ACCOUNT] 🔍 检查账号 {account_id} 登录状态...")

            # 先检查页面是否还活着（尽量不导航，避免打断正在进行的任务）
            try:
                current_url = page.url
                if not current_url or current_url == "about:blank":
                    # 页面空白，需要导航
                    await page.goto("https://hailuoai.com/create/image-to-video", timeout=15000)
                    await page.wait_for_timeout(2000)
                elif "hailuoai.com" not in current_url:
                    # 不在海螺AI页面，导航过去
                    await page.goto("https://hailuoai.com/create/image-to-video", timeout=15000)
                    await page.wait_for_timeout(2000)
                # 已经在海螺AI页面，不reload，直接检查当前页面状态
            except Exception as nav_e:
                print(f"[MULTI-ACCOUNT] ⚠️ 页面导航失败 {account_id}: {str(nav_e)[:80]}")
                # 导航失败不直接判定掉线，可能是临时网络问题
                return account_id in self._verified_accounts  # 保持之前的状态

            # 核心判断：找到头像或会员标识 = 已登录
            # 头像：div.rounded-full 内有来自 cdn.hailuoai.com 的 img
            avatar_locator = page.locator("div.cursor-pointer.overflow-hidden.rounded-full img[alt*='avatar']")
            # 会员标识
            vip_locator = page.locator("span.text-hl_brand_01:has-text('尊享会员'), span:has-text('尊享会员')")
            try:
                avatar_count = await avatar_locator.count()
                vip_count = await vip_locator.count()
                if avatar_count > 0 or vip_count > 0:
                    print(f"[MULTI-ACCOUNT] ✅ 账号 {account_id} 确认已登录（头像:{avatar_count} 会员:{vip_count}）")
                    return True
                else:
                    print(f"[MULTI-ACCOUNT] ❌ 账号 {account_id} 未找到登录标识，未登录状态")
                    return False
            except Exception as check_e:
                print(f"[MULTI-ACCOUNT] ⚠️ 登录状态检查异常 {account_id}: {str(check_e)[:80]}")
                return False

        except Exception as e:
            print(f"[MULTI-ACCOUNT] 检查登录状态异常 {account_id}: {str(e)[:80]}")
            # 异常时保持之前的状态，不轻易判定掉线
            return account_id in self._verified_accounts

    async def get_account_credits(self, account_id: str) -> int:
        """获取账号剩余积分 - 通过 fetch billing/credit API"""
        if account_id not in self.pages:
            return -1

        page = self.pages[account_id]

        try:
            credits = await page.evaluate("""async () => {
                try {
                    const resp = await fetch('/v1/api/billing/credit', {credentials: 'include'});
                    const data = await resp.json();
                    if (data && data.data && typeof data.data.total_credit === 'number') {
                        return data.data.total_credit;
                    }
                    return -1;
                } catch(e) {
                    return -1;
                }
            }""")

            if credits >= 0:
                print(f"[MULTI-ACCOUNT] ✅ 账号 {account_id} 积分: {credits}")
            else:
                print(f"[MULTI-ACCOUNT] ⚠️ 账号 {account_id} 获取积分失败")

            return credits

        except Exception as e:
            print(f"[MULTI-ACCOUNT] 获取积分失败 {account_id}: {e}")
            return -1

    async def _save_cookies(self, account_id: str):
        """保存完整的存储状态（cookies + localStorage）到文件"""
        try:
            context = self.contexts[account_id]
            
            # 获取完整的存储状态
            storage_state = await context.storage_state()
            
            # 保存存储状态到文件
            storage_file = self.data_dir / "profiles" / account_id / "storage_state.json"
            storage_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(storage_file, 'w', encoding='utf-8') as f:
                json.dump(storage_state, f, ensure_ascii=False, indent=2)
            
            print(f"[MULTI-ACCOUNT] 存储状态已保存: {account_id}")
            
        except Exception as e:
            print(f"[MULTI-ACCOUNT] 保存存储状态失败 {account_id}: {e}")

    async def _load_cookies(self, account_id: str):
        """检查是否存在已保存的存储状态（已在create_account_context中处理）"""
        try:
            storage_file = self.data_dir / "profiles" / account_id / "storage_state.json"
            return storage_file.exists()
        except Exception as e:
            print(f"[MULTI-ACCOUNT] 检查存储状态失败 {account_id}: {e}")
            return False
    
    def get_best_account_for_task(self, task_priority: int = 5, model_name: str = "", account_credits: dict = None) -> Optional[str]:
        """智能选择最适合执行任务的账号

        model_name: 模型名称，3系列模型需要积分
        account_credits: 账号积分缓存 {account_id: credits}
        """
        available_accounts = []
        is_model_v3 = model_name.startswith("Hailuo 3") or "3." in model_name
        required_series = "3.1" if is_model_v3 else "2.3"
        if account_credits is None:
            account_credits = {}

        for account_id, account in self.accounts.items():
            if (account.is_active and
                account.current_tasks < account.max_concurrent and
                account_id in self._verified_accounts and
                account.series == required_series):  # 必须已登录且系列匹配

                # 计算账号负载率
                load_rate = account.current_tasks / account.max_concurrent if account.max_concurrent > 0 else 0

                # 计算综合评分 (优先级 + 负载反向 + 任务匹配度)
                score = account.priority * 10 - load_rate * 100

                # 高优先级任务匹配高优先级账号
                if task_priority >= 8 and account.priority >= 8:
                    score += 20
                elif task_priority <= 3 and account.priority <= 5:
                    score += 10

                # 3系列模型：积分充足的账号大幅加分，积分为0的降权
                if is_model_v3:
                    credits = account_credits.get(account_id, -1)
                    if credits > 0:
                        score += 50  # 有积分的账号优先
                    elif credits == 0:
                        score -= 200  # 积分为0的账号几乎不分配

                available_accounts.append((account_id, account, score, load_rate))

        if not available_accounts:
            return None

        # 按评分排序，评分高的优先
        available_accounts.sort(key=lambda x: -x[2])

        best_account = available_accounts[0]
        print(f"[SCHEDULER] 选择账号 {best_account[1].display_name} (负载: {best_account[3]:.1%}, 评分: {best_account[2]:.1f}{', 3系列模型' if is_model_v3 else ''})")

        return best_account[0]

    async def auto_check_and_recover_accounts(self, skip_accounts: set = None):
        """自动检查和恢复失效账号"""
        print("[SCHEDULER] 开始检查账号登录状态...")

        for account_id, account in self.accounts.items():
            if not account.is_active:
                continue
            # 跳过正在被扫描的账号，防止与扫描循环争抢同一个页面
            if skip_accounts and account_id in skip_accounts:
                print(f"[SCHEDULER] ⏭️ 账号 {account.display_name} 正在扫描中，跳过健康检查")
                continue
            # 只检查已有上下文的账号
            if account_id in self.contexts:
                is_logged_in = await self.check_login_status(account_id)

                if is_logged_in:
                    self._login_fail_count[account_id] = 0
                    self.mark_account_logged_in(account_id)
                else:
                    self._login_fail_count[account_id] = self._login_fail_count.get(account_id, 0) + 1
                    if self._login_fail_count[account_id] >= 3:
                        self.mark_account_logged_out(account_id)
                        print(f"[SCHEDULER] ⚠️ 账号 {account.display_name} 连续{self._login_fail_count[account_id]}次检查失败，标记掉线")
                    else:
                        print(f"[SCHEDULER] ⚠️ 账号 {account.display_name} 检查失败({self._login_fail_count[account_id]}/3)，暂不标记掉线")
    
    def get_system_performance_stats(self) -> Dict[str, Any]:
        """获取系统性能统计"""
        total_capacity = 0
        current_load = 0
        active_accounts = 0
        logged_in_accounts = 0
        
        for account_id, account in self.accounts.items():
            if account.is_active:
                active_accounts += 1
                total_capacity += account.max_concurrent
                current_load += account.current_tasks
                
                if account_id in self._verified_accounts:
                    logged_in_accounts += 1
        
        utilization = current_load / total_capacity if total_capacity > 0 else 0
        
        # 性能等级
        if utilization < 0.3:
            performance_level = "优秀"
        elif utilization < 0.6:
            performance_level = "良好"
        elif utilization < 0.8:
            performance_level = "一般"
        else:
            performance_level = "繁忙"
        
        return {
            "total_accounts": len(self.accounts),
            "active_accounts": active_accounts,
            "logged_in_accounts": logged_in_accounts,
            "total_capacity": total_capacity,
            "current_load": current_load,
            "utilization": utilization,
            "performance_level": performance_level,
            "available_slots": total_capacity - current_load,
            "efficiency_score": (logged_in_accounts / active_accounts * 100) if active_accounts > 0 else 0
        }
    
    async def submit_task(self, prompt: str, model_name: str = "hailuo_1_0") -> Optional[str]:
        """提交视频生成任务"""
        # 选择最佳账号
        account_id = self.get_best_account_for_task()
        if not account_id:
            print("[MULTI-ACCOUNT] 没有可用的账号")
            return None
        
        account = self.accounts[account_id]
        page = self.pages[account_id]
        
        try:
            # 增加任务计数
            account.current_tasks += 1
            
            print(f"[MULTI-ACCOUNT] 使用账号 {account.display_name} 执行任务")
            
            # 执行任务提交逻辑
            # 这里实现具体的视频生成提交流程
            
            return f"task_id_{account_id}_{int(asyncio.get_event_loop().time())}"
            
        except Exception as e:
            print(f"[MULTI-ACCOUNT] 任务提交失败: {e}")
            return None
        finally:
            # 减少任务计数
            account.current_tasks -= 1
    
    async def close_account(self, account_id: str):
        """关闭指定账号的上下文"""
        if account_id in self.contexts:
            try:
                await self.contexts[account_id].close()
            except Exception as e:
                print(f"[MULTI-ACCOUNT] 关闭上下文失败 {account_id}: {e}")
            del self.contexts[account_id]
            
        if account_id in self.pages:
            del self.pages[account_id]
        
        # 清除登录验证状态
        self.mark_account_logged_out(account_id)
    
    async def close_all(self):
        """关闭所有账号和浏览器"""
        for account_id in list(self.contexts.keys()):
            await self.close_account(account_id)
        
        if self.browser:
            await self.browser.close()
            self.browser = None
        
        if hasattr(self, 'playwright'):
            await self.playwright.stop()
        
        print("[MULTI-ACCOUNT] 所有账号已关闭")
    
    def get_account_status(self) -> Dict[str, Any]:
        """获取所有账号状态"""
        status = {}
        for account_id, account in self.accounts.items():
            # 更严格的登录状态检查：只有通过真实验证的才算已登录
            is_logged_in = self._verify_real_login_status(account_id)
            
            status[account_id] = {
                "display_name": account.display_name,
                "is_active": account.is_active,
                "current_tasks": account.current_tasks,
                "max_concurrent": account.max_concurrent,
                "is_logged_in": is_logged_in,
                "utilization": account.current_tasks / account.max_concurrent if account.max_concurrent > 0 else 0
            }
        return status

    def _verify_real_login_status(self, account_id: str) -> bool:
        """严格验证账号的真实登录状态 - 只有通过check_login_status验证的才算"""
        return account_id in self._verified_accounts

    def mark_account_logged_in(self, account_id: str):
        """标记账号已验证登录"""
        self._verified_accounts.add(account_id)
        print(f"[MULTI-ACCOUNT] ✅ 标记账号 {account_id} 已验证登录")

    def mark_account_logged_out(self, account_id: str):
        """标记账号已登出"""
        self._verified_accounts.discard(account_id)
        print(f"[MULTI-ACCOUNT] ❌ 标记账号 {account_id} 已登出")

    def _check_saved_login_state(self, account_id: str) -> bool:
        """检查是否存在已保存的登录状态（兼容新旧格式）"""
        try:
            # 新格式：单个storage_state.json文件（每个账号独立）
            storage_file = self.data_dir / "profiles" / account_id / "storage_state.json"
            if storage_file.exists():
                return True
            
            # 兼容旧格式：只对主账号有效（旧格式是全局文件，不属于特定账号）
            if account_id == "hailuo_main":
                old_cookies_file = Path("login_state") / "cookies.json"
                old_localStorage_file = Path("login_state") / "localStorage.json"
                if old_cookies_file.exists() and old_localStorage_file.exists():
                    print(f"[MULTI-ACCOUNT] 检测到旧格式登录状态文件，账号 {account_id}")
                    return True
            
            return False
        except Exception:
            return False

    async def _migrate_old_login_state(self, account_id: str, target_file: Path):
        """从旧格式迁移登录状态到新格式（只迁移给主账号）"""
        try:
            # 旧格式只有一份cookie，只能迁移给主账号
            if account_id != "hailuo_main":
                return
            
            old_cookies_file = Path("login_state") / "cookies.json"
            old_localStorage_file = Path("login_state") / "localStorage.json"
            
            if old_cookies_file.exists() and old_localStorage_file.exists():
                print(f"[MULTI-ACCOUNT] 🔄 迁移旧格式登录状态到新格式: {account_id}")
                
                # 读取旧格式文件
                with open(old_cookies_file, 'r', encoding='utf-8') as f:
                    cookies = json.load(f)
                
                with open(old_localStorage_file, 'r', encoding='utf-8') as f:
                    localStorage_data = json.load(f)
                
                # 转换为新格式
                storage_state = {
                    "cookies": cookies,
                    "origins": [{
                        "origin": "https://hailuoai.com",
                        "localStorage": [
                            {"name": key, "value": value} 
                            for key, value in localStorage_data.items()
                        ]
                    }]
                }
                
                # 保存为新格式
                target_file.parent.mkdir(parents=True, exist_ok=True)
                with open(target_file, 'w', encoding='utf-8') as f:
                    json.dump(storage_state, f, ensure_ascii=False, indent=2)
                
                print(f"[MULTI-ACCOUNT] ✅ 旧格式登录状态迁移完成: {account_id}")
                
        except Exception as e:
            print(f"[MULTI-ACCOUNT] ⚠️ 迁移旧格式登录状态失败 {account_id}: {e}")


# 全局多账号管理器实例
multi_account_manager = MultiAccountManager()


# ============ 使用示例 ============

async def example_usage():
    """使用示例"""
    manager = MultiAccountManager()
    
    # 加载配置
    manager.load_accounts_config()
    
    # 登录所有激活的账号
    for account_id, account in manager.accounts.items():
        if account.is_active:
            await manager.login_account(account_id)
    
    # 提交任务
    task_id = await manager.submit_task("一只可爱的小猫在花园里玩耍")
    print(f"任务已提交: {task_id}")
    
    # 查看状态
    status = manager.get_account_status()
    print("账号状态:", json.dumps(status, ensure_ascii=False, indent=2))
    
    # 关闭
    await manager.close_all()


if __name__ == "__main__":
    asyncio.run(example_usage())
