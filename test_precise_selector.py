#!/usr/bin/env python3
"""
测试精确的模型选择器 - 基于用户提供的HTML结构
"""

from playwright.sync_api import sync_playwright
import time
import logging

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_precise_model_selector():
    """测试精确的模型选择器"""
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=500)
        page = browser.new_page()
        
        try:
            # 访问页面
            logger.info("🌐 访问海螺AI页面...")
            page.goto("https://hailuoai.com/create/image-to-video", timeout=30000)
            page.wait_for_timeout(5000)
            
            # 基于用户提供的HTML结构测试选择器
            selectors_to_test = [
                # 1. 精确的结构选择器
                'div.flex.h-full.w-full.items-center.overflow-hidden:has(img[alt*="AI Video model"]):has(div.text-hl_text_00:has-text("Hailuo"))',
                
                # 2. 基于图片的选择器
                'img[alt="AI Video model Image by Hailuo AI Video Generator"]',
                
                # 3. 基于文本的选择器
                'div.text-hl_text_00:has-text("Hailuo")',
                
                # 4. 组合选择器
                'div:has(img[alt*="AI Video model"]):has(div:has-text("Hailuo"))',
                
                # 5. 基于类名的选择器
                'div.bg-hl_bg_05:has(img)',
                
                # 6. 更简单的选择器
                '*:has(img[src*="hailuoai.com"])',
                
                # 7. 父容器选择器
                'div.flex.items-center:has(div.bg-hl_bg_05)'
            ]
            
            logger.info(f"🔍 测试 {len(selectors_to_test)} 个选择器...")
            
            found_elements = []
            
            for i, selector in enumerate(selectors_to_test):
                try:
                    logger.info(f"\n测试选择器 {i+1}: {selector}")
                    elements = page.locator(selector).all()
                    logger.info(f"  找到 {len(elements)} 个元素")
                    
                    for j, element in enumerate(elements):
                        try:
                            if element.is_visible():
                                text = element.text_content() or ""
                                logger.info(f"    元素 {j+1}: 可见 - {text[:80]}")
                                
                                # 如果包含Hailuo，记录这个元素
                                if "hailuo" in text.lower():
                                    found_elements.append((i+1, selector, element, text))
                            else:
                                logger.info(f"    元素 {j+1}: 不可见")
                        except Exception as e:
                            logger.warning(f"    元素 {j+1}: 检查失败 - {e}")
                            
                except Exception as e:
                    logger.warning(f"  选择器 {i+1} 失败: {e}")
            
            logger.info(f"\n✅ 总共找到 {len(found_elements)} 个有效元素:")
            
            for i, (selector_num, selector, element, text) in enumerate(found_elements):
                logger.info(f"  {i+1}. 选择器 {selector_num}: {text[:50]}")
                
                # 尝试点击第一个找到的元素
                if i == 0:
                    logger.info(f"\n🖱️ 尝试点击第一个元素...")
                    try:
                        element.click()
                        page.wait_for_timeout(3000)
                        logger.info("✅ 点击成功，等待3秒...")
                        
                        # 检查是否出现弹框
                        popover_selectors = [
                            ".ant-popover:not(.ant-popover-hidden)",
                            ".model-selection-options:not(.ant-popover-hidden)",
                            "[class*='popover']:not([class*='hidden'])"
                        ]
                        
                        popover_found = False
                        for pop_selector in popover_selectors:
                            try:
                                popover = page.locator(pop_selector).first
                                if popover.is_visible():
                                    logger.info(f"✅ 发现弹框: {pop_selector}")
                                    
                                    # 查看弹框内容
                                    popover_text = popover.text_content() or ""
                                    logger.info(f"弹框内容: {popover_text[:200]}")
                                    
                                    # 查找弹框中的选项
                                    options = popover.locator("*:has-text('Hailuo')").all()
                                    logger.info(f"弹框中找到 {len(options)} 个模型选项:")
                                    
                                    for k, option in enumerate(options[:8]):
                                        try:
                                            option_text = option.text_content() or ""
                                            if option_text.strip():
                                                logger.info(f"  选项 {k+1}: {option_text[:80]}")
                                        except:
                                            pass
                                    
                                    popover_found = True
                                    break
                            except:
                                continue
                        
                        if not popover_found:
                            logger.warning("❌ 点击后未发现弹框")
                            
                    except Exception as e:
                        logger.error(f"❌ 点击失败: {e}")
            
            # 截图保存
            page.screenshot(path="test_precise_selector.png")
            logger.info("\n📸 保存测试截图: test_precise_selector.png")
            
            # 保持浏览器打开
            input("\n按回车键关闭浏览器...")
            
        except Exception as e:
            logger.error(f"测试失败: {e}")
            
        finally:
            browser.close()

if __name__ == "__main__":
    test_precise_model_selector()
