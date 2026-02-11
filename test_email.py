#!/usr/bin/env python3
"""
测试邮件发送功能
"""
import sys
import os

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_email_service():
    """测试邮件发送服务"""
    from backend.email_service import send_email, SMTP_USER, SMTP_PASSWORD, SMTP_HOST, SMTP_PORT
    
    print("=== 邮件服务测试 ===")
    print(f"SMTP服务器: {SMTP_HOST}:{SMTP_PORT}")
    print(f"发送账号: {SMTP_USER}")
    print(f"授权码长度: {len(SMTP_PASSWORD) if SMTP_PASSWORD else 0}")
    print()
    
    if not SMTP_USER or not SMTP_PASSWORD:
        print("❌ SMTP配置缺失!")
        return False
    
    # 测试邮件内容
    test_email = input("请输入测试邮箱地址（回车使用默认: test@qq.com）: ").strip()
    if not test_email:
        test_email = "test@qq.com"
    
    print(f"正在发送测试邮件到: {test_email}")
    
    test_subject = "【大帝AI】邮件服务测试"
    test_content = """
    <h1>邮件服务测试成功！</h1>
    <p>这是一封测试邮件，证明QQ邮箱SMTP服务配置正确。</p>
    <p>时间: """ + str(os.path.exists) + """</p>
    """
    
    success = send_email(test_email, test_subject, test_content)
    
    if success:
        print("✅ 邮件发送成功!")
        return True
    else:
        print("❌ 邮件发送失败!")
        return False

def test_qq_smtp_connection():
    """测试QQ SMTP连接"""
    import smtplib
    
    print("\n=== 测试QQ SMTP连接 ===")
    
    try:
        print("正在连接 smtp.qq.com:587...")
        server = smtplib.SMTP('smtp.qq.com', 587)
        print("✅ 连接成功!")
        
        print("启用TLS加密...")
        server.starttls()
        print("✅ TLS启用成功!")
        
        print("测试登录...")
        server.login('758045020@qq.com', 'tidczqaqsegpbdda')
        print("✅ 登录成功!")
        
        server.quit()
        print("✅ 连接测试完成!")
        return True
        
    except Exception as e:
        print(f"❌ 连接测试失败: {str(e)}")
        return False

if __name__ == "__main__":
    print("开始邮件服务测试...")
    
    # 先测试连接
    conn_ok = test_qq_smtp_connection()
    
    if conn_ok:
        print("\n连接测试通过，开始完整邮件测试...")
        test_email_service()
    else:
        print("\n连接测试失败，请检查:")
        print("1. 网络连接是否正常")  
        print("2. QQ邮箱授权码是否正确")
        print("3. 是否开启了SMTP服务")
