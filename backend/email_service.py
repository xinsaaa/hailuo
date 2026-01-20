"""
邮件服务模块 - 使用 QQ SMTP 发送邮件
"""
import os
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from sqlmodel import Session, select
from backend.models import EmailVerifyCode, engine

# ============ SMTP 配置（从环境变量读取）============
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.qq.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")  # QQ 邮箱地址
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")  # QQ 邮箱授权码（不是登录密码）
SMTP_SENDER_NAME = os.getenv("SMTP_SENDER_NAME", "大帝AI")

# 验证码有效期（分钟）
CODE_EXPIRE_MINUTES = 5


def generate_code(length: int = 6) -> str:
    """生成随机数字验证码"""
    return ''.join([str(random.randint(0, 9)) for _ in range(length)])


def send_email(to_email: str, subject: str, html_content: str) -> bool:
    """发送邮件"""
    if not SMTP_USER or not SMTP_PASSWORD:
        print("[EMAIL] SMTP 未配置，跳过发送")
        return False
    
    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = f"{SMTP_SENDER_NAME} <{SMTP_USER}>"
        msg['To'] = to_email
        msg['Subject'] = subject
        
        # 添加 HTML 内容
        html_part = MIMEText(html_content, 'html', 'utf-8')
        msg.attach(html_part)
        
        # 连接 SMTP 服务器并发送
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()  # 启用 TLS
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, to_email, msg.as_string())
        
        print(f"[EMAIL] ✅ 邮件已发送至 {to_email}")
        return True
        
    except Exception as e:
        print(f"[EMAIL] ❌ 发送失败: {str(e)}")
        return False


def send_verification_code(email: str, purpose: str = "register") -> tuple[bool, str]:
    """
    发送验证码邮件
    返回: (是否成功, 验证码或错误信息)
    """
    code = generate_code()
    expires_at = datetime.utcnow() + timedelta(minutes=CODE_EXPIRE_MINUTES)
    
    # 存储验证码到数据库
    with Session(engine) as session:
        # 使旧验证码失效
        old_codes = session.exec(
            select(EmailVerifyCode).where(
                EmailVerifyCode.email == email,
                EmailVerifyCode.purpose == purpose,
                EmailVerifyCode.is_used == False
            )
        ).all()
        for old in old_codes:
            old.is_used = True
            session.add(old)
        
        # 创建新验证码
        new_code = EmailVerifyCode(
            email=email,
            code=code,
            purpose=purpose,
            expires_at=expires_at
        )
        session.add(new_code)
        session.commit()
    
    # 根据用途生成不同的邮件内容
    if purpose == "register":
        subject = "【大帝AI】注册验证码"
        action_text = "注册账号"
    else:
        subject = "【大帝AI】重置密码验证码"
        action_text = "重置密码"
    
    html_content = f"""
    <div style="max-width: 600px; margin: 0 auto; font-family: 'Microsoft YaHei', Arial, sans-serif;">
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
            <h1 style="color: white; margin: 0; font-size: 24px;">大帝 AI</h1>
            <p style="color: rgba(255,255,255,0.8); margin: 10px 0 0 0;">AI 视频创作平台</p>
        </div>
        <div style="background: #f8f9fa; padding: 30px; border: 1px solid #e9ecef;">
            <p style="font-size: 16px; color: #333;">您正在{action_text}，验证码为：</p>
            <div style="background: #fff; border: 2px dashed #667eea; padding: 20px; text-align: center; margin: 20px 0; border-radius: 8px;">
                <span style="font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #667eea;">{code}</span>
            </div>
            <p style="font-size: 14px; color: #666;">
                验证码 {CODE_EXPIRE_MINUTES} 分钟内有效，请勿泄露给他人。<br>
                如非本人操作，请忽略此邮件。
            </p>
        </div>
        <div style="background: #333; padding: 15px; text-align: center; border-radius: 0 0 10px 10px;">
            <p style="color: #999; margin: 0; font-size: 12px;">此邮件由系统自动发送，请勿回复</p>
        </div>
    </div>
    """
    
    success = send_email(email, subject, html_content)
    return (True, code) if success else (False, "邮件发送失败，请稍后重试")


def verify_email_code(email: str, code: str, purpose: str = "register") -> tuple[bool, str]:
    """
    验证邮箱验证码
    返回: (是否有效, 消息)
    """
    with Session(engine) as session:
        record = session.exec(
            select(EmailVerifyCode).where(
                EmailVerifyCode.email == email,
                EmailVerifyCode.code == code,
                EmailVerifyCode.purpose == purpose,
                EmailVerifyCode.is_used == False
            )
        ).first()
        
        if not record:
            return (False, "验证码无效或已使用")
        
        if datetime.utcnow() > record.expires_at:
            return (False, "验证码已过期，请重新获取")
        
        # 标记为已使用
        record.is_used = True
        session.add(record)
        session.commit()
        
        return (True, "验证成功")
