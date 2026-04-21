"""
SeeDance 模型 - 真实 API 调用测试
包含：短信登录 → 验证登录 → 查询积分 → 发送生成请求 → 打印原始响应
注意：生成请求会消耗积分！
"""
import sys
import os
import json
import asyncio
import uuid as _uuid

ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, ROOT)

from backend.hailuo_api import (
    HailuoApiClient, build_generate_video_body, build_client_auto,
    send_sms_code, login_with_sms, save_hailuo_credentials, save_hailuo_account,
    update_hailuo_account,
)


async def do_login() -> tuple:
    """交互式短信登录，返回 (account_id, client)"""
    print("═══ 短信验证码登录 ═══\n")
    phone = input("📱 请输入手机号: ").strip()
    if not phone:
        print("❌ 手机号不能为空")
        return None

    # 生成 uuid 和 device_id
    user_uuid = str(_uuid.uuid4())
    device_id = str(int(_uuid.uuid4().int >> 64))[:18]  # 18位数字
    print(f"   uuid:      {user_uuid}")
    print(f"   device_id: {device_id}")

    # Step 1: 发送验证码
    print(f"\n📤 发送验证码到 {phone} ...")
    try:
        sms_resp = send_sms_code(phone, user_uuid, device_id)
        if asyncio.iscoroutine(sms_resp):
            sms_resp = await sms_resp
        print(f"📥 发送验证码响应:")
        print(json.dumps(sms_resp, ensure_ascii=False, indent=2))
        
        sms_code = (sms_resp.get("statusInfo") or {}).get("code", -1)
        if sms_code != 0:
            print(f"❌ 发送验证码失败: {sms_resp}")
            return None
        print("✅ 验证码发送成功！\n")
    except Exception as e:
        print(f"❌ 发送验证码异常: {e}")
        return None

    # Step 2: 输入验证码并登录
    code = input("🔑 请输入收到的验证码: ").strip()
    if not code:
        print("❌ 验证码不能为空")
        return None

    print(f"\n📤 验证码登录中...")
    try:
        login_resp = login_with_sms(phone, code, user_uuid, device_id)
        if asyncio.iscoroutine(login_resp):
            login_resp = await login_resp
        print(f"📥 登录响应:")
        print(json.dumps(login_resp, ensure_ascii=False, indent=2))
        
        login_json = login_resp.get("json", {})
        login_code = (login_json.get("statusInfo") or {}).get("code", -1)
        if login_code != 0:
            print(f"❌ 登录失败: code={login_code}")
            return None
        
        # 提取 cookie
        cookies_str = login_resp.get("cookies", "")
        token = (login_json.get("data") or {}).get("token", "")
        if token:
            cookies_str = f"_token={token}; {cookies_str}" if cookies_str else f"_token={token}"
        
        print(f"\n✅ 登录成功！")
        print(f"   token: {token[:30]}..." if len(token) > 30 else f"   token: {token}")
        print(f"   cookies: {cookies_str[:60]}..." if len(cookies_str) > 60 else f"   cookies: {cookies_str}")
        
    except Exception as e:
        print(f"❌ 登录异常: {e}")
        return None

    # 保存凭证到 data/hailuo_accounts.json
    account_id = f"test_{phone[-4:]}"
    save_hailuo_account(account_id, display_name=f"测试账号 {phone[-4:]}")
    save_hailuo_credentials(account_id, cookie=cookies_str, uuid=user_uuid, device_id=device_id)
    update_hailuo_account(account_id, is_logged_in=True)
    print(f"   已保存账号凭证: {account_id}\n")

    client = HailuoApiClient(cookie=cookies_str, uuid=user_uuid, device_id=device_id)
    return account_id, client


async def do_manual_creds() -> tuple:
    """手动输入抓包凭证"""
    print("═══ 手动输入抓包凭证 ═══\n")
    token = input("🔑 token (JWT): ").strip()
    user_uuid = input("📋 uuid: ").strip()
    device_id = input("📋 device_id: ").strip()
    
    if not all([token, user_uuid, device_id]):
        print("❌ 所有字段都不能为空")
        return None
    
    cookie = f"_token={token}"
    client = HailuoApiClient(cookie=cookie, uuid=user_uuid, device_id=device_id)
    return "manual", client


async def main():
    print("选择凭证来源:")
    print("  1. 自动使用已有账号")
    print("  2. 短信验证码登录")
    print("  3. 手动输入抓包凭证 (token/uuid/device_id)")
    choice = input("\n请选择 [1/2/3]: ").strip()
    
    if choice == "3":
        result = await do_manual_creds()
        if not result:
            return
        account_id, client = result
    elif choice == "2":
        result = await do_login()
        if not result:
            return
        account_id, client = result
    else:
        result = build_client_auto()
        if result:
            account_id, client = result
            print(f"✅ 使用已有账号: {account_id}")
        else:
            print("⚠️  没有已登录的海螺账号，尝试登录\n")
            result = await do_login()
            if not result:
                return
            account_id, client = result

    # 验证登录
    logged_in = await client.check_login()
    if not logged_in:
        print("❌ 登录状态无效")
        return
    print("✅ 登录状态有效\n")
    
    # 查询积分
    credits = await client.get_credits()
    print(f"💰 当前积分: {credits}\n")
    
    # ============================================
    # 测试用例：每个模型各发一个请求，打印原始响应
    # ============================================
    test_cases = [
        {
            "label": "【对比】Hailuo 2.3 - 文生视频 768p 6s 16:9",
            "model_id": "23204",
            "desc": "一个穿红裙子的女孩在草地上翩翩起舞",
            "duration": 6,
            "resolution": "768",
            "aspect_ratio": "16:9",
        },
        {
            "label": "SeeDance 2.0 Fast - 文生视频 480p 4s 16:9",
            "model_id": "seedance2.0-fast-t2v",
            "desc": "一个穿红裙子的女孩在草地上翩翩起舞",
            "duration": 4,
            "resolution": "480",
            "aspect_ratio": "16:9",
        },
        {
            "label": "SeeDance 2.0 Fast - 文生视频 720p 6s 9:16",
            "model_id": "seedance2.0-fast-t2v",
            "desc": "一只猫咪在桌上优雅地伸懒腰",
            "duration": 6,
            "resolution": "720",
            "aspect_ratio": "9:16",
        },
        {
            "label": "SeeDance 2.0 - 文生视频 720p 5s 1:1",
            "model_id": "seedance2.0-t2v",
            "desc": "一位舞者在舞台上跳芭蕾舞",
            "duration": 5,
            "resolution": "720",
            "aspect_ratio": "1:1",
        },
        {
            "label": "SeeDance 2.0 - 文生视频 1080p 4s 16:9",
            "model_id": "seedance2.0-t2v",
            "desc": "夕阳下海浪拍打沙滩的慢动作",
            "duration": 4,
            "resolution": "1080",
            "aspect_ratio": "16:9",
        },
    ]
    
    for i, tc in enumerate(test_cases, 1):
        print(f"{'='*60}")
        print(f"📤 测试 {i}: {tc['label']}")
        print(f"{'='*60}")
        
        # 打印请求体
        body = build_generate_video_body(
            desc=tc["desc"],
            model_id=tc["model_id"],
            duration=tc["duration"],
            resolution=tc["resolution"],
            aspect_ratio=tc["aspect_ratio"],
        )
        print(f"\n📋 请求体:")
        print(json.dumps(body, ensure_ascii=False, indent=2))
        
        # 发送请求
        try:
            resp = await client.generate_video(
                desc=tc["desc"],
                model_id=tc["model_id"],
                duration=tc["duration"],
                resolution=tc["resolution"],
                aspect_ratio=tc["aspect_ratio"],
            )
            print(f"\n📥 原始响应:")
            print(json.dumps(resp, ensure_ascii=False, indent=2))
            
            # 解析关键字段
            status_info = resp.get("statusInfo", {})
            code = status_info.get("code", -1)
            message = status_info.get("message", "")
            data = resp.get("data", {})
            tasks = data.get("tasks", [])
            
            if code == 0:
                print(f"\n✅ 成功！code={code}")
                for t in tasks:
                    print(f"   taskID={t.get('taskID')}  status={t.get('status')}")
            else:
                print(f"\n❌ 失败！code={code} message={message}")
                
        except Exception as e:
            print(f"\n❌ 请求异常: {e}")
        
        print()
    
    # 再查一次积分
    credits_after = await client.get_credits()
    print(f"💰 测试后积分: {credits_after}")
    if credits is not None and credits_after is not None:
        print(f"💸 消耗积分: {credits - credits_after}")


if __name__ == "__main__":
    asyncio.run(main())
