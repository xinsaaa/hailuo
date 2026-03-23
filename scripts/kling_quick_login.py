"""
可灵快速登录脚本（非交互式）
用法: python scripts/kling_quick_login.py
二维码链接出现后用快手APP扫码即可，账号自动保存为 kling_main
"""
import asyncio
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.kling_api import (
    _gen_did, _gen_risk_id, _make_headers,
    qr_start, qr_scan_result, qr_accept_result,
    check_login, save_kling_account, save_kling_credentials,
)

ACCOUNT_ID = "kling_main"
DISPLAY_NAME = "主号"

async def main():
    did = _gen_did()
    risk_id = _gen_risk_id()
    print(f"did={did}")

    # 1. 获取二维码
    print("\n[1] 请求二维码...")
    result = await qr_start(did, risk_id)
    if result.get("result") != 1:
        print(f"[FAIL] {result}")
        return

    qr_url = result["qrUrl"]
    token = result["qrLoginToken"]
    signature = result["qrLoginSignature"]
    expire_time = result["expireTime"]
    session_cookies = result.get("_session_cookies", {})

    remaining = int((expire_time / 1000) - time.time())
    print(f"[OK] 二维码链接:")
    print(f"  >>> {qr_url} <<<")
    print(f"  过期: {time.strftime('%H:%M:%S', time.localtime(expire_time / 1000))}  (剩余 {remaining} 秒)")

    # 终端显示二维码
    try:
        import qrcode
        qr = qrcode.QRCode(box_size=1, border=1)
        qr.add_data(qr_url)
        qr.make(fit=True)
        print(f"\n  请用快手APP扫描以下二维码:\n")
        qr.print_ascii(invert=True)
    except Exception:
        pass

    print(f"\n  请用快手APP扫描上面的二维码！\n")

    # 2. 轮询等待扫码
    for i in range(90):
        await asyncio.sleep(2)
        try:
            data = await qr_scan_result(did, risk_id, token, signature, session_cookies)
        except Exception as e:
            continue

        rc = data.get("result", 0)
        if rc == 1:
            print(f"\n[OK] 已扫码! 获取凭据中...")
            break
        elif rc == 707:
            print(f"\n[EXPIRED] 二维码已过期，请重新运行")
            return
        else:
            elapsed = (i + 1) * 2
            print(f"  等待扫码... {elapsed}s", end="\r")
    else:
        print("\n[TIMEOUT] 等待超时")
        return

    # 3. 获取 cookie
    try:
        cred = await qr_accept_result(did, risk_id, token, signature, session_cookies)
    except Exception as e:
        print(f"[FAIL] acceptResult: {e}")
        return

    cookie = cred["cookie"]
    print(f"[OK] 获取 cookie 成功 ({len(cookie)} chars)")

    # 4. 验证
    ok = await check_login(cookie)
    print(f"[{'OK' if ok else 'WARN'}] 登录验证: {'通过' if ok else '返回False但已保存'}")

    # 5. 保存
    save_kling_account(ACCOUNT_ID, DISPLAY_NAME)
    save_kling_credentials(ACCOUNT_ID, cookie, did)
    print(f"\n[SAVED] 账号 {ACCOUNT_ID} 已保存!")
    print("现在可以运行: python scripts/kling_api_test.py upload <图片路径>")

if __name__ == "__main__":
    asyncio.run(main())
