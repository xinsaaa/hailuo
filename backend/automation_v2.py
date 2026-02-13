"""
海螺AI自动化 V2 - 多账号版本
基于Browser Context实现多账号隔离，一个浏览器支持多个账号
"""
import asyncio
import json
import os
import time
from typing import Dict, List, Optional, Any
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from sqlmodel import Session, select
from backend.models import VideoOrder, engine
from backend.multi_account_manager import MultiAccountManager, AccountConfig


class HailuoAutomationV2:
    """海螺AI自动化 V2版本 - 支持多账号"""
    
    def __init__(self):
        self.manager = MultiAccountManager()
        self.is_running = False
        self.task_handlers: Dict[str, asyncio.Task] = {}
        
    async def start(self):
        """启动多账号自动化系统"""
        if self.is_running:
            print("[AUTO-V2] 系统已在运行中")
            return
        
        print("[AUTO-V2] 🚀 启动多账号自动化系统...")
        
        try:
            # 加载账号配置
            self.manager.load_accounts_config("accounts.json")
            print(f"[AUTO-V2] 已加载 {len(self.manager.accounts)} 个账号配置")
            
            # 检查是否有可用账号
            active_accounts = [acc for acc in self.manager.accounts.values() if acc.is_active]
            if not active_accounts:
                print("[AUTO-V2] ⚠️ 没有激活的账号，系统无法启动")
                return
            
            # 设置运行状态
            self.is_running = True
            print("[AUTO-V2] ✅ 系统状态已设置为运行中")
            
            # 并行登录所有激活的账号（先加载Cookie再登录）
            login_tasks = []
            print("[AUTO-V2] 开始初始化账号上下文...")
            
            for account_id, account in self.manager.accounts.items():
                if account.is_active:
                    try:
                        print(f"[AUTO-V2] 正在初始化账号: {account.display_name}")
                        # 创建上下文
                        await self.manager.create_account_context(account_id)
                        # 尝试加载Cookie（已在create_account_context中处理）
                        # 添加登录任务
                        login_tasks.append(self.manager.login_account(account_id))
                    except Exception as e:
                        print(f"[AUTO-V2] ❌ 初始化账号 {account.display_name} 失败: {e}")
            
            if login_tasks:
                print(f"[AUTO-V2] 开始登录 {len(login_tasks)} 个账号...")
                # 并行登录
                login_results = await asyncio.gather(*login_tasks, return_exceptions=True)
                success_count = sum(1 for result in login_results if result is True)
                print(f"[AUTO-V2] ✅ 成功登录 {success_count}/{len(login_tasks)} 个账号")
            
            # 启动任务处理循环
            print("[AUTO-V2] 启动任务处理循环...")
            asyncio.create_task(self.task_processing_loop())
            
            # 启动账号健康检查循环
            print("[AUTO-V2] 启动账号健康检查循环...")
            asyncio.create_task(self.account_health_check_loop())
            
            print("[AUTO-V2] 🎉 多账号自动化系统启动成功！")
            
        except Exception as e:
            print(f"[AUTO-V2] ❌ 系统启动失败: {e}")
            self.is_running = False  # 确保启动失败时重置状态
            raise

    async def account_health_check_loop(self):
        """账号健康检查循环"""
        print("[AUTO-V2] 🔍 账号健康检查循环已启动")
        
        while self.is_running:
            try:
                # 每5分钟检查一次
                await asyncio.sleep(300)
                
                if not self.is_running:
                    break
                    
                print("[AUTO-V2] 开始账号健康检查...")
                await self.manager.auto_check_and_recover_accounts()
                
            except Exception as e:
                print(f"[AUTO-V2] 健康检查循环错误: {e}")
                await asyncio.sleep(60)
        
    async def task_processing_loop(self):
        """任务处理主循环"""
        print("[AUTO-V2] 📋 任务处理循环已启动")
        
        while self.is_running:
            try:
                # 检查数据库中的待处理订单
                pending_orders = self.get_pending_orders()
                
                if pending_orders:
                    print(f"[AUTO-V2] 发现 {len(pending_orders)} 个待处理订单")
                    
                    # 为每个订单分配账号并处理
                    for order in pending_orders:
                        account_id = self.manager.get_best_account_for_task()
                        if account_id:
                            # 创建任务处理器
                            task = asyncio.create_task(
                                self.process_order(account_id, order)
                            )
                            self.task_handlers[f"{account_id}_{order.id}"] = task
                        else:
                            print(f"[AUTO-V2] 暂无可用账号处理订单 {order.id}")
                
                # 清理完成的任务
                completed_tasks = [
                    task_id for task_id, task in self.task_handlers.items()
                    if task.done()
                ]
                for task_id in completed_tasks:
                    del self.task_handlers[task_id]
                
                # 等待下一轮
                await asyncio.sleep(5)
                
            except Exception as e:
                print(f"[AUTO-V2] 任务循环错误: {e}")
                await asyncio.sleep(10)
    
    def get_pending_orders(self) -> List[VideoOrder]:
        """获取待处理的订单"""
        with Session(engine) as session:
            orders = session.exec(
                select(VideoOrder).where(
                    VideoOrder.status == "pending"
                ).limit(10)
            ).all()
            return orders
    
    async def process_order(self, account_id: str, order: VideoOrder):
        """处理单个订单"""
        account = self.manager.accounts[account_id]
        page = self.manager.pages[account_id]
        
        print(f"[AUTO-V2] 账号 {account.display_name} 开始处理订单 {order.id}")
        
        try:
            # 增加任务计数
            account.current_tasks += 1
            
            # 更新订单状态
            self.update_order_status(order.id, "processing")
            
            # 导航到海螺AI生成页面
            await page.goto("https://hailuoai.com", timeout=30000)
            await asyncio.sleep(2)
            
            # 等待页面加载
            await page.wait_for_load_state("networkidle")
            
            # 查找输入框并输入提示词
            try:
                # 等待提示词输入框
                prompt_input = await page.wait_for_selector(
                    "textarea, input[placeholder*='请输入'], input[placeholder*='提示词']",
                    timeout=10000
                )
                
                # 清空并输入提示词
                await prompt_input.fill("")
                await prompt_input.type(order.prompt, delay=100)
                
                print(f"[AUTO-V2] 已输入提示词: {order.prompt[:50]}...")
                
                # 选择模型（如果指定了）
                if order.model_name and order.model_name != "hailuo_1_0":
                    await self.select_model(page, order.model_name)
                
                # 点击生成按钮
                generate_btn = await page.wait_for_selector(
                    "button:has-text('生成'), button:has-text('开始生成'), [data-testid='generate-btn']",
                    timeout=5000
                )
                await generate_btn.click()
                
                print(f"[AUTO-V2] 已提交生成任务，订单ID: {order.id}")
                
                # 等待生成完成并获取结果
                result_url = await self.wait_for_generation_complete(page, order.id)
                
                if result_url:
                    # 更新订单结果
                    self.update_order_result(order.id, result_url, "completed")
                    print(f"[AUTO-V2] 订单 {order.id} 生成完成: {result_url}")
                else:
                    self.update_order_status(order.id, "failed")
                    print(f"[AUTO-V2] 订单 {order.id} 生成失败")
                
            except Exception as e:
                print(f"[AUTO-V2] 订单处理失败 {order.id}: {e}")
                self.update_order_status(order.id, "failed")
                
        except Exception as e:
            print(f"[AUTO-V2] 账号 {account.display_name} 处理订单 {order.id} 出错: {e}")
            self.update_order_status(order.id, "failed")
        finally:
            # 减少任务计数
            account.current_tasks -= 1
    
    async def select_model(self, page: Page, model_name: str):
        """选择指定的AI模型"""
        try:
            # 查找模型选择器
            model_selector = await page.wait_for_selector(
                "[data-testid='model-selector'], .model-selector, select[name='model']",
                timeout=5000
            )
            
            # 点击打开模型选择
            await model_selector.click()
            await asyncio.sleep(1)
            
            # 查找指定模型选项
            model_option = await page.wait_for_selector(
                f"[data-value='{model_name}'], option[value='{model_name}'], :text('{model_name}')",
                timeout=5000
            )
            
            await model_option.click()
            print(f"[AUTO-V2] 已选择模型: {model_name}")
            
        except Exception as e:
            print(f"[AUTO-V2] 模型选择失败: {e}")
    
    async def wait_for_generation_complete(self, page: Page, order_id: int, timeout: int = 300) -> Optional[str]:
        """等待视频生成完成并获取结果链接"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                # 检查是否有完成的视频
                video_elements = await page.query_selector_all(
                    "video, .video-result, [data-testid='video-result']"
                )
                
                if video_elements:
                    # 尝试获取分享链接
                    share_buttons = await page.query_selector_all(
                        "button:has-text('分享'), [data-testid='share-btn'], .share-button"
                    )
                    
                    if share_buttons:
                        await share_buttons[0].click()
                        await asyncio.sleep(1)
                        
                        # 获取分享链接
                        share_url = await page.evaluate("""
                            () => {
                                // 尝试从剪贴板获取
                                return navigator.clipboard.readText();
                            }
                        """)
                        
                        if share_url and "hailuoai.com" in share_url:
                            return share_url
                
                await asyncio.sleep(5)
                
            except Exception as e:
                print(f"[AUTO-V2] 等待生成完成时出错: {e}")
                await asyncio.sleep(5)
        
        return None
    
    def update_order_status(self, order_id: int, status: str):
        """更新订单状态"""
        with Session(engine) as session:
            order = session.get(VideoOrder, order_id)
            if order:
                order.status = status
                session.add(order)
                session.commit()
    
    def update_order_result(self, order_id: int, result_url: str, status: str):
        """更新订单结果"""
        with Session(engine) as session:
            order = session.get(VideoOrder, order_id)
            if order:
                order.result_url = result_url
                order.status = status
                session.add(order)
                session.commit()
    
    async def stop(self):
        """停止自动化系统"""
        print("[AUTO-V2] 🛑 停止多账号自动化系统...")
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

async def add_account(account_config: dict):
    """添加新账号"""
    account = AccountConfig(**account_config)
    automation_v2.manager.accounts[account.account_id] = account
    
    # 保存配置
    accounts_list = list(automation_v2.manager.accounts.values())
    automation_v2.manager.save_accounts_config(accounts_list)
    
    # 如果系统正在运行且账号激活，立即登录
    if automation_v2.is_running and account.is_active:
        await automation_v2.manager.login_account(account.account_id)

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
