#!/usr/bin/env python3
"""
强制登录测试配置 - 用于测试完整的登录流程
临时文件，解决测试时跳过登录的问题
"""

# 修改后的测试配置，强制进行登录测试
TEST_CONFIG_FORCE_LOGIN = {
    "url": "https://hailuoai.com/create/image-to-video",
    "phone_number": "17366935232",  # 测试用手机号
    "headless": False,
    "timeout": 30000,
    
    # 强制登录选项
    "force_login": True,        # 强制执行登录流程
    "clear_cookies": True,      # 清除所有cookies
    "clear_storage": True,      # 清除localStorage
    "incognito_mode": True,     # 使用无痕模式
    
    # 测试图片路径
    "test_images": {
        "first_frame": "test_images/first_frame.jpg",
        "last_frame": "test_images/last_frame.jpg"
    },
    
    "test_prompt": "一只可爱的小猫在花园里快乐地玩耍，阳光明媚 [TEST]",
    "test_model": "Hailuo 1.0"
}

def clear_all_login_data():
    """清除所有登录相关数据"""
    import os
    import shutil
    
    print("🗑️  清除登录状态数据...")
    
    # 清除登录状态文件
    if os.path.exists("login_state"):
        shutil.rmtree("login_state")
        print("✅ 清除login_state目录")
    
    print("✅ 登录数据清除完成")

def setup_force_login_browser():
    """设置强制登录的浏览器环境"""
    from playwright.sync_api import sync_playwright
    
    print("🧹 启动无痕浏览器进行登录测试...")
    
    p = sync_playwright().start()
    
    # 使用无痕模式启动浏览器
    browser = p.chromium.launch(
        headless=False,
        args=[
            "--incognito",              # 无痕模式
            "--no-first-run",           # 跳过首次运行
            "--disable-background-timer-throttling",
            "--disable-renderer-backgrounding",
            "--disable-backgrounding-occluded-windows"
        ]
    )
    
    # 创建无痕上下文
    context = browser.new_context(
        viewport={"width": 1280, "height": 720},
        # 不保存任何状态
        storage_state=None
    )
    
    page = context.new_page()
    
    print("✅ 无痕浏览器启动完成")
    return browser, context, page

def test_complete_login_flow():
    """测试完整的登录流程"""
    print("🧪 开始完整登录流程测试")
    print("=" * 50)
    
    # 清除登录数据
    clear_all_login_data()
    
    # 启动无痕浏览器
    browser, context, page = setup_force_login_browser()
    
    try:
        # 导航到页面
        print("🌐 导航到图片转视频页面...")
        page.goto(TEST_CONFIG_FORCE_LOGIN["url"], timeout=30000)
        page.wait_for_timeout(3000)
        
        # 强制检查登录状态 - 应该未登录
        print("🔍 检查登录状态...")
        
        # 检查是否需要登录
        try:
            create_input = page.locator("#video-create-input [contenteditable='true']")
            create_input.wait_for(state="visible", timeout=3000)
            print("⚠️  检测到已登录状态 - 这不应该发生在无痕模式中")
            print("💡 可能页面结构已更改，或者有其他登录检测方式")
        except:
            print("✅ 确认未登录状态，需要进行登录")
        
        # 查找登录按钮
        print("🔍 查找登录按钮...")
        login_btn = page.locator("div.border-hl_line_00:has-text('登录')").first
        
        if login_btn.is_visible():
            print("✅ 找到登录按钮")
            
            print("👆 点击登录按钮...")
            login_btn.click()
            page.wait_for_timeout(1000)
            
            # 切换到手机登录
            print("📱 切换到手机登录...")
            try:
                phone_tab = page.locator("#rc-tabs-0-tab-phone")
                if phone_tab.is_visible():
                    phone_tab.click()
                    page.wait_for_timeout(500)
                    print("✅ 已切换到手机登录")
            except:
                print("ℹ️  可能已经在手机登录模式")
            
            # 填写手机号
            print("📞 填写手机号...")
            phone_input = page.locator("input#phone")
            phone_input.fill(TEST_CONFIG_FORCE_LOGIN["phone_number"])
            print(f"✅ 手机号已填写: {TEST_CONFIG_FORCE_LOGIN['phone_number']}")
            
            # 点击获取验证码
            print("📨 点击获取验证码...")
            get_code_btn = page.locator("button:has-text('获取验证码')").first
            get_code_btn.click()
            print("✅ 验证码请求已发送")
            
            # 手动输入验证码
            verification_code = input("\n请输入收到的验证码: ")
            page.locator("input#code").fill(verification_code)
            print(f"✅ 验证码已填写: {verification_code}")
            
            # 勾选协议
            try:
                print("📋 勾选用户协议...")
                page.locator("button.rounded-full:has(svg)").first.click()
                print("✅ 用户协议已勾选")
            except:
                print("⚠️  协议勾选可能已完成")
            
            # 登录
            print("🚀 提交登录...")
            page.locator("button.login-btn").click()
            print("⏳ 等待登录结果...")
            page.wait_for_timeout(5000)
            
            # 验证登录结果
            try:
                page.locator("#video-create-input [contenteditable='true']").wait_for(
                    state="visible", timeout=30000
                )
                print("🎉 登录测试成功！")
                print("✅ 成功进入图片转视频页面")
                
                # 保持浏览器打开以便观察
                input("\n按回车键关闭浏览器...")
                
            except:
                print("❌ 登录验证失败")
                
        else:
            print("❌ 未找到登录按钮")
            print("💡 可能页面已经是登录状态或结构发生变化")
            
            # 截图调试
            page.screenshot(path="debug_no_login_button.png")
            print("📸 已保存调试截图: debug_no_login_button.png")
    
    finally:
        browser.close()
        print("🏁 测试完成")

if __name__ == "__main__":
    test_complete_login_flow()
