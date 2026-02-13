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
                    "current_tasks": 0
                }
                for acc in accounts
            ]
        }
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    async def create_account_context(self, account_id: str) -> BrowserContext:
        """为指定账号创建独立的浏览器上下文"""
        if not self.browser:
            await self.init_browser()
        
        # 每个账号使用独立的存储目录来保存cookies等状态
        storage_dir = self.data_dir / "profiles" / account_id
        storage_dir.mkdir(parents=True, exist_ok=True)
        
        # 尝试加载已保存的登录状态
        storage_state_file = storage_dir / "storage_state.json"
        context_options = {
            "viewport": {"width": 1280, "height": 720},
            # 每个账号使用不同的User-Agent
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "bypass_csp": True,
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
        
        # 设置额外的请求拦截（可选）
        await context.route("**/*.{png,jpg,jpeg,gif,webp,svg,ico}", lambda route: route.abort())
        
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
        """发送验证码到账号手机"""
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
            
            # 导航到海螺AI登录页面
            await page.goto("https://hailuoai.com", timeout=30000)
            await page.wait_for_timeout(3000)
            
            # 点击登录按钮
            login_selectors = [
                "button:has-text('登录')",
                "a:has-text('登录')",
                ".login-btn",
                "[data-testid='login-btn']"
            ]
            
            login_clicked = False
            for selector in login_selectors:
                try:
                    login_btn = await page.wait_for_selector(selector, timeout=5000)
                    await login_btn.click()
                    login_clicked = True
                    print(f"[LOGIN] 已点击登录按钮")
                    break
                except:
                    continue
            
            if not login_clicked:
                print("[LOGIN] 未找到登录按钮")
                return False
            
            await page.wait_for_timeout(2000)
            
            # 输入手机号
            phone_selectors = [
                "input[placeholder*='手机']",
                "input[placeholder*='phone']", 
                "input[type='tel']",
                ".phone-input input"
            ]
            
            phone_entered = False
            for selector in phone_selectors:
                try:
                    phone_input = await page.wait_for_selector(selector, timeout=5000)
                    await phone_input.clear()
                    await phone_input.type(account.phone_number, delay=100)
                    print(f"[LOGIN] 已输入手机号: {account.phone_number}")
                    phone_entered = True
                    break
                except:
                    continue
            
            if not phone_entered:
                print("[LOGIN] 未找到手机号输入框")
                return False
            
            # 点击获取验证码
            code_btn_selectors = [
                "button:has-text('获取验证码')",
                "button:has-text('发送验证码')",
                ".send-code-btn",
                "[data-testid='send-code']"
            ]
            
            for selector in code_btn_selectors:
                try:
                    code_btn = await page.wait_for_selector(selector, timeout=5000)
                    await code_btn.click()
                    print(f"[LOGIN] 已点击获取验证码按钮")
                    return True
                except:
                    continue
            
            print("[LOGIN] 未找到验证码按钮")
            return False
            
        except Exception as e:
            print(f"[MULTI-ACCOUNT] 发送验证码失败 {account.display_name}: {e}")
            return False

    async def verify_code_and_login(self, account_id: str, verification_code: str) -> bool:
        """使用验证码完成登录"""
        if account_id not in self.accounts:
            return False
        
        account = self.accounts[account_id]
        page = self.pages[account_id]
        
        try:
            print(f"[MULTI-ACCOUNT] 验证码登录: {account.display_name}")
            
            # 输入验证码
            code_selectors = [
                "input[placeholder*='验证码']",
                "input[placeholder*='code']",
                ".verify-code-input input",
                "input[type='text'][maxlength='6']"
            ]
            
            code_entered = False
            for selector in code_selectors:
                try:
                    code_input = await page.wait_for_selector(selector, timeout=5000)
                    await code_input.clear()
                    await code_input.type(verification_code, delay=100)
                    print(f"[LOGIN] 已输入验证码")
                    code_entered = True
                    break
                except:
                    continue
            
            if not code_entered:
                print("[LOGIN] 未找到验证码输入框")
                return False
            
            # 点击登录提交按钮
            submit_selectors = [
                "button:has-text('登录')",
                "button:has-text('确认')",
                "button[type='submit']",
                ".login-submit-btn"
            ]
            
            for selector in submit_selectors:
                try:
                    submit_btn = await page.wait_for_selector(selector, timeout=5000)
                    await submit_btn.click()
                    print(f"[LOGIN] 已提交登录")
                    break
                except:
                    continue
            
            # 等待登录完成
            await page.wait_for_timeout(5000)
            
            # 检查登录是否成功
            if await self.check_login_status(account_id):
                await self._save_cookies(account_id)
                print(f"[MULTI-ACCOUNT] 账号 {account.display_name} 验证码登录成功")
                return True
            else:
                print(f"[MULTI-ACCOUNT] 账号 {account.display_name} 验证码登录失败")
                return False
                
        except Exception as e:
            print(f"[MULTI-ACCOUNT] 验证码登录失败 {account.display_name}: {e}")
            return False

    async def _perform_login_flow(self, page: Page, account: AccountConfig):
        """执行具体的登录流程"""
        try:
            # 查找并点击登录按钮
            login_selectors = [
                "button:has-text('登录')",
                ".login-btn",
                "[data-testid='login-btn']",
                "a:has-text('登录')"
            ]
            
            login_clicked = False
            for selector in login_selectors:
                try:
                    login_btn = await page.wait_for_selector(selector, timeout=5000)
                    await login_btn.click()
                    login_clicked = True
                    print(f"[LOGIN] 已点击登录按钮")
                    break
                except:
                    continue
            
            if not login_clicked:
                print("[LOGIN] 未找到登录按钮")
                return
            
            await page.wait_for_timeout(2000)
            
            # 输入手机号
            phone_selectors = [
                "input[placeholder*='手机']",
                "input[placeholder*='phone']", 
                "input[type='tel']",
                ".phone-input input"
            ]
            
            for selector in phone_selectors:
                try:
                    phone_input = await page.wait_for_selector(selector, timeout=5000)
                    await phone_input.clear()
                    await phone_input.type(account.phone_number, delay=100)
                    print(f"[LOGIN] 已输入手机号: {account.phone_number}")
                    break
                except:
                    continue
            
            # 点击获取验证码
            code_btn_selectors = [
                "button:has-text('获取验证码')",
                "button:has-text('发送验证码')",
                ".send-code-btn",
                "[data-testid='send-code']"
            ]
            
            for selector in code_btn_selectors:
                try:
                    code_btn = await page.wait_for_selector(selector, timeout=5000)
                    await code_btn.click()
                    print("[LOGIN] 已点击获取验证码")
                    break
                except:
                    continue
            
            # 等待手动输入验证码（或者集成自动化验证码服务）
            print(f"[LOGIN] 请手动输入验证码完成 {account.display_name} 的登录...")
            
            # 等待登录完成（检查URL变化或页面元素）
            await page.wait_for_timeout(30000)  # 给30秒时间手动输入验证码
            
        except Exception as e:
            print(f"[LOGIN] 登录流程执行失败: {e}")

    async def check_login_status(self, account_id: str) -> bool:
        """检查账号登录状态 - 恢复简洁有效的版本"""
        if account_id not in self.pages:
            return False
        
        page = self.pages[account_id]
        
        try:
            print(f"[MULTI-ACCOUNT] 🔍 检查账号 {account_id} 登录状态...")
            
            # 访问海螺AI主页检查登录状态
            await page.goto("https://hailuoai.com", timeout=15000)
            await page.wait_for_timeout(2000)
            
            # 方法1: 检查是否存在登录按钮（如果存在登录按钮 = 未登录）
            try:
                login_btn = await page.wait_for_selector("div.border-hl_line_00:has-text('登录')", timeout=3000)
                if login_btn and await login_btn.is_visible():
                    print(f"[MULTI-ACCOUNT] ❌ 账号 {account_id} 发现登录按钮，未登录状态")
                    return False
            except:
                # 没有找到登录按钮，可能已登录，继续检查
                pass
            
            # 方法2: 访问创建页面检查视频创建输入框（如果存在 = 已登录）
            await page.goto("https://hailuoai.com/create/image-to-video", timeout=15000)
            await page.wait_for_timeout(2000)
            
            try:
                # 检查视频创建输入框
                create_input = await page.wait_for_selector("#video-create-input [contenteditable='true']", timeout=5000)
                if create_input and await create_input.is_visible():
                    print(f"[MULTI-ACCOUNT] ✅ 账号 {account_id} 找到创建输入框，确认已登录")
                    return True
            except:
                pass
            
            print(f"[MULTI-ACCOUNT] ❓ 账号 {account_id} 登录状态不明确，假设未登录")
            return False
            
        except Exception as e:
            print(f"[MULTI-ACCOUNT] 检查登录状态失败 {account_id}: {e}")
            return False

    async def get_account_credits(self, account_id: str) -> int:
        """获取账号剩余积分"""
        if account_id not in self.pages:
            return -1
        
        page = self.pages[account_id]
        
        try:
            print(f"[MULTI-ACCOUNT] 🔍 获取账号 {account_id} 剩余积分...")
            
            # 访问海螺AI主页
            await page.goto("https://hailuoai.com", timeout=15000)
            await page.wait_for_timeout(3000)
            
            # 查找积分元素的选择器
            credit_selectors = [
                "span.text-hl_text_00.select-none.text-\\[12px\\].font-medium.leading-\\[22px\\]",
                ".text-hl_text_00.text-\\[12px\\].font-medium",
                "span:has(~ div:has-text('升级'))",
                "svg + span.text-hl_text_00",
                ".mb-2.flex span.text-hl_text_00"
            ]
            
            for selector in credit_selectors:
                try:
                    # 等待积分元素出现
                    credit_element = await page.wait_for_selector(selector, timeout=5000)
                    if credit_element:
                        # 获取积分文本
                        credit_text = await credit_element.text_content()
                        if credit_text and credit_text.strip().isdigit():
                            credits = int(credit_text.strip())
                            print(f"[MULTI-ACCOUNT] ✅ 账号 {account_id} 剩余积分: {credits}")
                            return credits
                except Exception as e:
                    print(f"[MULTI-ACCOUNT] 积分选择器 {selector} 失败: {e}")
                    continue
            
            # 尝试通过更通用的方式查找
            try:
                # 查找包含升级文本的父元素，然后找相关的数字
                upgrade_elements = await page.query_selector_all("*:has-text('升级')")
                for element in upgrade_elements:
                    parent = await element.query_selector("..")
                    if parent:
                        # 在父元素中查找数字
                        number_spans = await parent.query_selector_all("span")
                        for span in number_spans:
                            span_text = await span.text_content()
                            if span_text and span_text.strip().isdigit():
                                credits = int(span_text.strip())
                                print(f"[MULTI-ACCOUNT] ✅ 账号 {account_id} 剩余积分: {credits}")
                                return credits
            except Exception as e:
                print(f"[MULTI-ACCOUNT] 通用积分查找失败: {e}")
            
            print(f"[MULTI-ACCOUNT] ❌ 账号 {account_id} 无法获取积分信息")
            return -1
            
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
    
    def get_best_account_for_task(self, task_priority: int = 5) -> Optional[str]:
        """智能选择最适合执行任务的账号"""
        available_accounts = []
        
        for account_id, account in self.accounts.items():
            if (account.is_active and 
                account.current_tasks < account.max_concurrent):
                
                # 计算账号负载率
                load_rate = account.current_tasks / account.max_concurrent if account.max_concurrent > 0 else 0
                
                # 计算综合评分 (优先级 + 负载反向 + 任务匹配度)
                score = account.priority * 10 - load_rate * 100
                
                # 高优先级任务匹配高优先级账号
                if task_priority >= 8 and account.priority >= 8:
                    score += 20
                elif task_priority <= 3 and account.priority <= 5:
                    score += 10
                
                available_accounts.append((account_id, account, score, load_rate))
        
        if not available_accounts:
            return None
        
        # 按评分排序，评分高的优先
        available_accounts.sort(key=lambda x: -x[2])
        
        best_account = available_accounts[0]
        print(f"[SCHEDULER] 选择账号 {best_account[1].display_name} (负载: {best_account[3]:.1%}, 评分: {best_account[2]:.1f})")
        
        return best_account[0]

    async def auto_check_and_recover_accounts(self):
        """自动检查和恢复失效账号"""
        print("[SCHEDULER] 开始检查账号登录状态...")
        
        recovery_tasks = []
        for account_id, account in self.accounts.items():
            if not account.is_active:
                continue
                
            # 检查登录状态
            if account_id in self.contexts:
                is_logged_in = await self.check_login_status(account_id)
                
                if not is_logged_in:
                    print(f"[SCHEDULER] 账号 {account.display_name} 登录失效，准备重新登录...")
                    # 先加载Cookie
                    await self._load_cookies(account_id)
                    # 创建重新登录任务
                    recovery_tasks.append(self.login_account(account_id))
        
        # 并行执行恢复任务
        if recovery_tasks:
            results = await asyncio.gather(*recovery_tasks, return_exceptions=True)
            success_count = sum(1 for result in results if result is True)
            print(f"[SCHEDULER] 账号恢复完成，成功 {success_count}/{len(recovery_tasks)} 个")
    
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
                
                if account_id in self.contexts:
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
            await self.contexts[account_id].close()
            del self.contexts[account_id]
            
        if account_id in self.pages:
            del self.pages[account_id]
    
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
            # 检查真实登录状态：需要同时满足有上下文且Cookie文件存在
            has_context = account_id in self.contexts
            has_saved_state = self._check_saved_login_state(account_id)
            
            status[account_id] = {
                "display_name": account.display_name,
                "is_active": account.is_active,
                "current_tasks": account.current_tasks,
                "max_concurrent": account.max_concurrent,
                "is_logged_in": has_context and has_saved_state,
                "utilization": account.current_tasks / account.max_concurrent if account.max_concurrent > 0 else 0
            }
        return status

    def _check_saved_login_state(self, account_id: str) -> bool:
        """检查是否存在已保存的登录状态（兼容新旧格式）"""
        try:
            # 新格式：单个storage_state.json文件
            storage_file = self.data_dir / "profiles" / account_id / "storage_state.json"
            if storage_file.exists():
                return True
            
            # 兼容旧格式：cookies.json + localStorage.json
            old_cookies_file = Path("login_state") / "cookies.json"
            old_localStorage_file = Path("login_state") / "localStorage.json"
            if old_cookies_file.exists() and old_localStorage_file.exists():
                print(f"[MULTI-ACCOUNT] 检测到旧格式登录状态文件，账号 {account_id}")
                return True
            
            return False
        except Exception:
            return False

    async def _migrate_old_login_state(self, account_id: str, target_file: Path):
        """从旧格式迁移登录状态到新格式"""
        try:
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
