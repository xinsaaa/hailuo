"""
Z-Pay 支付模块
接口文档：https://member.z-pay.cn/member/doc.html
"""
import hashlib
import time
from typing import Optional
from urllib.parse import urlencode

# ============ 配置 ============
import os
ZPAY_API_URL = os.getenv("ZPAY_API_URL", "https://zpayz.cn/submit.php")
ZPAY_PID = os.getenv("ZPAY_PID", "2026010716484260")
ZPAY_KEY = os.getenv("ZPAY_KEY", "lUpCQ3QrCmcAW8SNLCkXcHiILCybND5V")

# 回调地址（从环境变量读取，支持域名配置）
ZPAY_NOTIFY_URL = os.getenv("ZPAY_NOTIFY_URL", "http://dadiai.cn:8000/api/pay/notify")
ZPAY_RETURN_URL = os.getenv("ZPAY_RETURN_URL", "http://dadiai.cn:8000/recharge")


def generate_sign(params: dict, key: str) -> str:
    """
    生成 MD5 签名
    1. 按参数名 ASCII 码从小到大排序
    2. sign、sign_type 和空值不参与签名
    3. 拼接成 a=b&c=d 格式
    4. 末尾拼接密钥后 MD5 加密，结果小写
    """
    # 过滤空值和签名字段
    filtered = {k: v for k, v in params.items() 
                if v and k not in ['sign', 'sign_type']}
    
    # 按 ASCII 码排序
    sorted_keys = sorted(filtered.keys())
    
    # 拼接成 URL 键值对
    sign_str = '&'.join([f"{k}={filtered[k]}" for k in sorted_keys])
    
    # 拼接密钥并 MD5
    sign_str += key
    return hashlib.md5(sign_str.encode('utf-8')).hexdigest().lower()


def verify_sign(params: dict, key: str, sign: str) -> bool:
    """验证回调签名"""
    calculated_sign = generate_sign(params, key)
    return calculated_sign == sign.lower()


def create_payment_url(
    out_trade_no: str,
    money: float,
    name: str = "余额充值",
    pay_type: str = "wxpay"
) -> str:
    """
    创建支付跳转 URL
    
    参数:
        out_trade_no: 商户订单号（唯一）
        money: 订单金额（保留两位小数）
        name: 商品名称
        pay_type: 支付方式 (wxpay/alipay)
    
    返回:
        支付跳转 URL
    """
    params = {
        "pid": ZPAY_PID,
        "type": pay_type,
        "out_trade_no": out_trade_no,
        "notify_url": ZPAY_NOTIFY_URL,
        "return_url": ZPAY_RETURN_URL,
        "name": name,
        "money": f"{money:.2f}",
        "sign_type": "MD5",
    }
    
    # 生成签名
    params["sign"] = generate_sign(params, ZPAY_KEY)
    
    # 拼接完整 URL
    return f"{ZPAY_API_URL}?{urlencode(params)}"


def generate_order_no() -> str:
    """生成唯一订单号"""
    import random
    timestamp = int(time.time() * 1000)
    random_num = random.randint(1000, 9999)
    return f"HL{timestamp}{random_num}"
