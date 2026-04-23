import base64
import random
import re
import string
import time
from urllib.parse import urljoin

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

# ================= 配置区域 =================

# 1. 填入你的商户私钥 (PEM格式)
MERCHANT_PRIVATE_KEY = """
-----BEGIN PRIVATE KEY-----
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQCzgT06z3cPk0jETUzrN3IH6OPEjvfAqwQC4901yki3Vrv9WrW+UKryC49TG7DiTeQQkfBwwSc/h8n3EtPkJjxrdWT2DWZsYyfUJtaCsaGbjO5rvWmoK1j08UsdkfqHmof3Xfblh6oOxN9eK1kQD9aJdoGJStOEzqPH5U4Xl7ZQ5I8MiK7rC4eRMNgxFd1pMF4FjSdf4ZbdmJXsTyzA2i+6a4rMkIanNAgiACX6PVQsuON3m27SWtYmhhFn7PDY2S16+uY/XIQeS7xWe/oqJXJQuIJvHJNNhK5TnQyScvKhVqBZfGTRchHGvwF/5I/gzH8UhvUox169fvccD2sNnFxtAgMBAAECggEAViWEGSFP5m2s0mi2rXvigeFGziI+zHxGZIyusQ3vb+10MtbBuiBEqfzaP+xeK31uInWnirVn/JlSV/z1K90dygSA+4TaztGXX71z3S0afehY0+QHPOnwuzzB6+MO9N04u4Kg5u8Asi3RdQQgrhCryTTSXe1HLclt2JU3sSLiIFeCS9m5R+CUn7pmvXCpaxOHyQUM9z3vcspqxmWE7KVN3Sz1LxVzX+L3FTfcPVS3c7GgBdvHYl0DtwRApmnmhjIt+gKcGzaSlhEoQFj2TYmlUL+8qvIb1jBZ6S3LaJTnaBNNTHaYfGBovMzBi0L6b4Is19avr+SVppQjskh7YxxaAQKBgQDf3jMAjLkuRPJNwZ/kh8smk3TTvBHDub8/FgUVt8Xi0YHVE+/CSkmdqHtl7zAR9w7CZ8sPJFIwss0adU429RqunXB/4fsr8K54jwjqGZ4m5BqKLz2NSBQbIhr2ivuFnyRL3bhfD16F9VCBOW/NkTI/mNPRwBUQKRR4cg6GfQf7zQKBgQDNRPZHPuN0J8FWPzclOdi1HQPt9dVOGp65Dns5j7gcDaW+N+gUo5Q+lerWueDHVYeWgETzxERwBlyqrR8XyOk1rKq+rbXhuoaFTiFSXStch7JGK6Fek0qcsA/N5RVMJmk+UE1gBBiEtfDf/og/R3VK1FNCnFSgVqwcvmpl86eDIQKBgQDBHjZTGBI7NuDrcMeU5gu6uGOEr+2HMXooWr+CL6k2dFMS1AL1UQ5WQdxJX9/Q75Y84DrMUiHQvr2uQFl7kU82KLy+pNv+2L45Y/JluDm1BPtcD0qC0RX/Hhmyasx1RYaTJ65/2otI9gk/oKOw6rs1H4pCm/fPnBB7orCjFcLIVQKBgQCS59L2BE0WmUkl55IY40BzxjNEv5aMEkMcIAASnwfdk+rVqv8+nh9/dx2d1WPIZS7niB9Q8lskbXkucT36cMBuuIdudbXgufSCPPteDe31h+wPijQwEmvonZyB93x5hlf1z9TAbc36VJfyRyDNYN/R0QlRd76dDcqZu7E8C9gL4QKBgBd6B0EAVdWrTwGXagYSdwE1S3ek+7Up55vVnZWANURjW96H9vGeEdX1RRIpEO9SMvxHxkMB2cT/b0lW4Vi4wb4wWJDmeTFiKU0BPaMoPIFdT9RvCrEXQjsf9f4zqcPK1tTbD5tfCwUr4TNkxeIGEKuNtudUsXFLH7cI8spVFYrl
-----END PRIVATE KEY-----
"""

# 2. 接口地址
API_URL = "https://pay.lxsd.cn/api/pay/submit"

# 3. 本地测试回调地址
NGROK_URL = "https://你的-ngrok-地址.io"


# ================= 核心签名逻辑 =================

def generate_sign(params, private_key_str):
    filtered_params = {}
    for key, value in params.items():
        if value is not None and value != "" and key not in ["sign", "sign_type"]:
            filtered_params[key] = value

    sorted_keys = sorted(filtered_params.keys())
    str_to_sign = "&".join([f"{key}={filtered_params[key]}" for key in sorted_keys])

    print(f"--- 待签名字符串 ---\n{str_to_sign}\n")

    private_key = serialization.load_pem_private_key(
        private_key_str.encode("utf-8"),
        password=None,
    )

    signature = private_key.sign(
        str_to_sign.encode("utf-8"),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )

    return base64.b64encode(signature).decode("utf-8")


def extract_cashier_url(response_text, base_url):
    """从返回脚本里解析出完整收银台地址。"""
    match = re.search(r"window\.location\.replace\('([^']+)'\)", response_text)
    if not match:
        return None
    return urljoin(base_url, match.group(1))


# ================= 构建请求 =================

def build_payload(pay_type="wxpay", money="1.00", name="VIP会员测试", param=""):
    current_timestamp = int(time.time())
    random_suffix = "".join(random.choices(string.digits, k=4))
    out_trade_no = f"{current_timestamp}{random_suffix}"
    return {
        "pid": 1326,
        "type": pay_type,
        "out_trade_no": out_trade_no,
        "notify_url": f"{NGROK_URL}/notify",
        "return_url": f"{NGROK_URL}/return",
        "name": name,
        "money": money,
        "param": param,
        "timestamp": str(current_timestamp),
        "sign_type": "RSA",
    }


def create_payment(pay_type="wxpay", money="1.00", name="VIP会员测试", param=""):
    payload = build_payload(pay_type=pay_type, money=money, name=name, param=param)
    sign = generate_sign(payload, MERCHANT_PRIVATE_KEY)
    payload["sign"] = sign

    print(f"--- 正在请求: {API_URL} ---")
    response = requests.post(API_URL, data=payload, timeout=10)
    cashier_url = extract_cashier_url(response.text, API_URL)
    return {
        "payload": payload,
        "response_text": response.text,
        "cashier_url": cashier_url,
    }


def main():
    try:
        result = create_payment(pay_type="wxpay")
        print("--- 响应结果 ---")
        print(result["response_text"])

        print("\n--- 收银台地址 ---")
        if result["cashier_url"]:
            print(result["cashier_url"])
        else:
            print("未解析到收银台跳转地址")
    except Exception as exc:
        print(f"请求出错: {exc}")


if __name__ == "__main__":
    main()
