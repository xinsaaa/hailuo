#!/usr/bin/env python3
"""
调试模型选择器 - 查看页面实际内容
"""

import asyncio
from playwright.async_api import async_playwright
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

async def debug_page_content():
    """调试页面内容，查看模型选择相关元素"""
    
    async with async_playwright() as p:
        # 启动浏览器
        browser = await p.chromium.launch(headless=False, slow_mo=1000)
        context = await browser.new_context()
        page = await context.new_page()
        
        try:
            # 访问海螺AI页面
            logger.info("🌐 访问海螺AI页面...")
            await page.goto("https://hailuoai.com/create/image-to-video")
            await page.wait_for_timeout(5000)
            
            # 截图保存
            await page.screenshot(path="debug_page.png")
            logger.info("📸 保存页面截图: debug_page.png")
            
            # 1. 搜索所有包含"Hailuo"的元素
            logger.info("\n🔍 搜索所有包含'Hailuo'的元素:")
            hailuo_elements = await page.locator("*:has-text('Hailuo')").all()
            for i, element in enumerate(hailuo_elements[:15]):
                try:
                    text = await element.text_content()
                    tag_name = await element.evaluate("el => el.tagName")
                    class_name = await element.get_attribute("class")
                    is_visible = await element.is_visible()
                    
                    if text and text.strip():
                        logger.info(f"  {i+1}. [{tag_name}] {text[:80]} (visible: {is_visible})")
                        if class_name:
                            logger.info(f"      classes: {class_name[:100]}")
                except:
                    continue
            
            # 2. 搜索所有包含"模型"的元素  
            logger.info("\n🔍 搜索所有包含'模型'的元素:")
            model_elements = await page.locator("*:has-text('模型')").all()
            for i, element in enumerate(model_elements[:10]):
                try:
                    text = await element.text_content()
                    tag_name = await element.evaluate("el => el.tagName")
                    is_visible = await element.is_visible()
                    
                    if text and text.strip():
                        logger.info(f"  {i+1}. [{tag_name}] {text[:80]} (visible: {is_visible})")
                except:
                    continue
                    
            # 3. 搜索所有button元素
            logger.info("\n🔍 搜索所有button元素:")
            button_elements = await page.locator("button").all()
            for i, element in enumerate(button_elements[:20]):
                try:
                    text = await element.text_content()
                    is_visible = await element.is_visible()
                    class_name = await element.get_attribute("class")
                    
                    if is_visible and text and text.strip():
                        logger.info(f"  {i+1}. {text[:50]} (visible: {is_visible})")
                        if class_name:
                            logger.info(f"      classes: {class_name[:100]}")
                except:
                    continue
            
            # 4. 搜索包含cursor-pointer的元素
            logger.info("\n🔍 搜索包含'cursor-pointer'的元素:")
            try:
                clickable_elements = await page.locator(".cursor-pointer").all()
                for i, element in enumerate(clickable_elements[:15]):
                    try:
                        text = await element.text_content()
                        is_visible = await element.is_visible()
                        
                        if is_visible and text and len(text.strip()) < 200:
                            logger.info(f"  {i+1}. {text[:80]} (visible: {is_visible})")
                    except:
                        continue
            except Exception as e:
                logger.warning(f"搜索cursor-pointer失败: {e}")
            
            # 5. 搜索页面底部区域
            logger.info("\n🔍 搜索页面底部区域:")
            try:
                # 获取页面高度
                page_height = await page.evaluate("document.body.scrollHeight")
                logger.info(f"页面高度: {page_height}px")
                
                # 滚动到底部
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(2000)
                
                # 再次搜索Hailuo相关元素
                bottom_hailuo = await page.locator("*:has-text('Hailuo')").all()
                logger.info(f"底部区域找到 {len(bottom_hailuo)} 个Hailuo元素")
                
                for i, element in enumerate(bottom_hailuo[:10]):
                    try:
                        text = await element.text_content()
                        is_visible = await element.is_visible()
                        if text and text.strip() and is_visible:
                            logger.info(f"  底部{i+1}. {text[:80]}")
                    except:
                        continue
                        
            except Exception as e:
                logger.warning(f"搜索页面底部失败: {e}")
            
            # 6. 尝试查找ant-popover相关元素
            logger.info("\n🔍 搜索ant-popover相关元素:")
            try:
                popover_elements = await page.locator("[class*='ant-popover']").all()
                logger.info(f"找到 {len(popover_elements)} 个popover元素")
                
                for i, element in enumerate(popover_elements[:5]):
                    try:
                        class_name = await element.get_attribute("class")
                        is_visible = await element.is_visible()
                        logger.info(f"  {i+1}. classes: {class_name} (visible: {is_visible})")
                    except:
                        continue
            except Exception as e:
                logger.warning(f"搜索popover失败: {e}")
            
            # 保持浏览器打开以便手动检查
            logger.info("\n🔍 保持浏览器打开，按回车键关闭...")
            input("按回车键关闭浏览器...")
            
        except Exception as e:
            logger.error(f"调试过程出错: {e}")
            
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(debug_page_content())
