#!/usr/bin/env python3
"""
简单的模型选择器测试 - 不依赖复杂逻辑
"""

from playwright.sync_api import sync_playwright
import time
import logging

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_model_selector():
    """测试模型选择器"""
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=1000)  # 慢速执行便于观察
        page = browser.new_page()
        
        try:
            # 访问页面
            logger.info("🌐 访问海螺AI页面...")
            page.goto("https://hailuoai.com/create/image-to-video", timeout=30000)
            page.wait_for_timeout(5000)
            
            # 截图
            page.screenshot(path="test_page_start.png")
            logger.info("📸 保存起始截图")
            
            # 简单策略：点击页面上任何包含"Hailuo"的可见元素
            logger.info("🔍 查找所有包含Hailuo的元素...")
            
            # 获取所有包含Hailuo的元素
            hailuo_elements = page.locator("*:has-text('Hailuo')").all()
            logger.info(f"找到 {len(hailuo_elements)} 个包含Hailuo的元素")
            
            clicked_something = False
            
            for i, element in enumerate(hailuo_elements):
                try:
                    if element.is_visible():
                        text = element.text_content() or ""
                        logger.info(f"元素 {i+1}: {text[:100]}")
                        
                        # 尝试点击这个元素
                        if not clicked_something and len(text.strip()) < 100:
                            logger.info(f"🖱️ 尝试点击: {text[:50]}")
                            element.click()
                            page.wait_for_timeout(3000)
                            
                            # 检查是否有弹框出现
                            try:
                                popover = page.locator(".ant-popover:not(.ant-popover-hidden)").first
                                if popover.is_visible():
                                    logger.info("✅ 发现弹框！")
                                    page.screenshot(path="test_popover_appeared.png")
                                    
                                    # 查找弹框中的选项
                                    options = popover.locator("*:has-text('Hailuo')").all()
                                    logger.info(f"弹框中找到 {len(options)} 个选项")
                                    
                                    for j, option in enumerate(options):
                                        try:
                                            option_text = option.text_content() or ""
                                            if option_text.strip():
                                                logger.info(f"  选项 {j+1}: {option_text[:80]}")
                                        except:
                                            continue
                                    
                                    clicked_something = True
                                    break
                            except:
                                pass
                            
                            # 等待一下再尝试下一个
                            page.wait_for_timeout(1000)
                            
                except Exception as e:
                    logger.warning(f"处理元素 {i+1} 失败: {e}")
                    continue
            
            if not clicked_something:
                logger.warning("❌ 没有找到可点击的模型选择器")
                
                # 尝试查找其他可能的触发器
                logger.info("🔍 查找其他可能的按钮...")
                
                # 查找所有按钮
                buttons = page.locator("button").all()
                for i, button in enumerate(buttons[:20]):  # 只检查前20个按钮
                    try:
                        if button.is_visible():
                            text = button.text_content() or ""
                            if text.strip():
                                logger.info(f"按钮 {i+1}: {text[:50]}")
                                
                                # 如果按钮包含设置、模型等关键词，尝试点击
                                if any(keyword in text.lower() for keyword in ["设置", "模型", "选择", "config"]):
                                    logger.info(f"🖱️ 尝试点击相关按钮: {text[:30]}")
                                    button.click()
                                    page.wait_for_timeout(3000)
                                    
                                    # 检查弹框
                                    try:
                                        popover = page.locator(".ant-popover:not(.ant-popover-hidden)").first
                                        if popover.is_visible():
                                            logger.info("✅ 点击按钮后发现弹框！")
                                            break
                                    except:
                                        pass
                                        
                    except Exception as e:
                        logger.warning(f"处理按钮 {i+1} 失败: {e}")
                        continue
            
            # 最终截图
            page.screenshot(path="test_page_final.png")
            logger.info("📸 保存最终截图")
            
            # 保持浏览器打开
            input("按回车键关闭...")
            
        except Exception as e:
            logger.error(f"测试失败: {e}")
            
        finally:
            browser.close()

if __name__ == "__main__":
    test_model_selector()
