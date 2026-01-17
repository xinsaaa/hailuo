#!/usr/bin/env python3
"""
完整的模型选择测试 - 测试从触发到选择的完整流程
"""

from playwright.sync_api import sync_playwright
import time
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def test_full_model_selection():
    """测试完整的模型选择流程"""
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=1000)
        page = browser.new_page()
        
        try:
            # 访问页面
            logger.info("🌐 访问海螺AI页面...")
            page.goto("https://hailuoai.com/create/image-to-video", timeout=30000)
            page.wait_for_timeout(5000)
            
            # 第一步：查找并点击模型选择下拉框
            logger.info("🔍 第一步：查找模型选择下拉框...")
            
            # 使用最成功的选择器（基于测试结果）
            dropdown_selectors = [
                'div.flex.h-full.w-full.items-center.overflow-hidden:has(img[alt*="AI Video model"]):has(div.text-hl_text_00:has-text("Hailuo"))',
                'img[alt="AI Video model Image by Hailuo AI Video Generator"]',
                'div.text-hl_text_00:has-text("Hailuo")',
                '*:has(img[src*="hailuoai.com"]):has(div:has-text("Hailuo"))'
            ]
            
            dropdown_clicked = False
            
            for i, selector in enumerate(dropdown_selectors):
                if dropdown_clicked:
                    break
                    
                try:
                    logger.info(f"尝试选择器 {i+1}: {selector[:60]}...")
                    elements = page.locator(selector).all()
                    
                    for element in elements:
                        if element.is_visible():
                            text = element.text_content() or ""
                            if "hailuo" in text.lower() and len(text.strip()) < 50:
                                logger.info(f"👆 点击下拉框: {text.strip()}")
                                element.click()
                                page.wait_for_timeout(3000)
                                dropdown_clicked = True
                                break
                                
                except Exception as e:
                    logger.warning(f"选择器 {i+1} 失败: {e}")
                    continue
            
            if not dropdown_clicked:
                logger.error("❌ 未能点击下拉框")
                return False
            
            # 第二步：检查弹框是否出现
            logger.info("🔍 第二步：检查弹框是否出现...")
            
            popover_selectors = [
                ".ant-popover:not(.ant-popover-hidden)",
                ".model-selection-options:not(.ant-popover-hidden)",
                "[class*='popover']:not([class*='hidden'])"
            ]
            
            popover = None
            for selector in popover_selectors:
                try:
                    element = page.locator(selector).first
                    if element.is_visible():
                        popover = element
                        logger.info(f"✅ 找到弹框: {selector}")
                        break
                except:
                    continue
            
            if not popover:
                logger.error("❌ 弹框未出现")
                return False
            
            # 第三步：查找并选择目标模型
            logger.info("🔍 第三步：在弹框中查找模型选项...")
            
            target_model = "Hailuo 2.3"
            logger.info(f"🎯 目标模型: {target_model}")
            
            # 查找弹框中的可点击选项
            clickable_selectors = [
                "div.cursor-pointer",
                "button",
                "[role='option']",
                "*[class*='hover']",
                "div:has-text('Hailuo')"
            ]
            
            model_options = []
            
            for selector in clickable_selectors:
                try:
                    options = popover.locator(selector).all()
                    for option in options:
                        if option.is_visible():
                            text = option.text_content() or ""
                            # 过滤出看起来像模型选项的元素
                            if ("hailuo" in text.lower() and 
                                20 <= len(text.strip()) <= 100 and
                                not any(existing.text_content() == text for existing in model_options)):
                                model_options.append(option)
                except:
                    continue
            
            logger.info(f"找到 {len(model_options)} 个可能的模型选项:")
            
            # 显示所有找到的选项
            for i, option in enumerate(model_options):
                try:
                    text = option.text_content() or ""
                    logger.info(f"  选项 {i+1}: {text[:80]}")
                except:
                    logger.info(f"  选项 {i+1}: <无法读取文本>")
            
            # 尝试匹配并点击目标模型
            target_lower = target_model.lower()
            model_selected = False
            
            for i, option in enumerate(model_options):
                try:
                    text = option.text_content() or ""
                    text_lower = text.lower()
                    
                    # 检查是否匹配目标模型
                    if target_lower in text_lower:
                        logger.info(f"✅ 找到匹配的模型: {text[:50]}")
                        logger.info(f"👆 点击选择模型...")
                        
                        option.click()
                        page.wait_for_timeout(2000)
                        
                        logger.info(f"✅ 已选择模型: {target_model}")
                        model_selected = True
                        break
                        
                except Exception as e:
                    logger.warning(f"处理选项 {i+1} 失败: {e}")
                    continue
            
            # 如果没找到精确匹配，选择第一个包含Hailuo的选项
            if not model_selected and model_options:
                try:
                    first_option = model_options[0]
                    text = first_option.text_content() or ""
                    logger.info(f"📋 未找到精确匹配，选择第一个选项: {text[:50]}")
                    
                    first_option.click()
                    page.wait_for_timeout(2000)
                    
                    logger.info("✅ 已选择备用模型")
                    model_selected = True
                    
                except Exception as e:
                    logger.error(f"选择备用模型失败: {e}")
            
            # 结果
            if model_selected:
                logger.info("🎉 模型选择流程完成！")
                page.screenshot(path="model_selection_success.png")
                return True
            else:
                logger.error("❌ 模型选择失败")
                page.screenshot(path="model_selection_failed.png")
                return False
            
        except Exception as e:
            logger.error(f"测试失败: {e}")
            page.screenshot(path="model_selection_error.png")
            return False
            
        finally:
            input("按回车键关闭浏览器...")
            browser.close()

if __name__ == "__main__":
    success = test_full_model_selection()
    print(f"\n测试结果: {'成功' if success else '失败'}")
