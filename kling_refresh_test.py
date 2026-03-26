"""
测试可灵 Token 刷新功能
从本地 kling_accounts.json 读取第一个账号的 cookie，
依次测试：check_login → refresh_token → check_login
"""
import asyncio
import sys
import os

# 确保能导入 backend 模块
sys.path.insert(0, os.path.dirname(__file__))


async def main():
    from backend.kling_api import (
        list_kling_accounts,
        get_kling_credentials,
        check_login,
        refresh_token,
        _parse_cookie_str,
    )

    accounts = list_kling_accounts()
    if not accounts:
        print("❌ 没有可灵账号，请先在后台添加")
        return

    # 找第一个有凭据的账号
    target = None
    creds = None
    for acc in accounts:
        aid = acc["account_id"]
        c = get_kling_credentials(aid)
        if c and c.get("cookie"):
            target = acc
            creds = c
            break

    if not target:
        print("❌ 没有找到有 cookie 的账号")
        return

    aid = target["account_id"]
    cookie = creds["cookie"]
    print(f"📋 账号: {aid} ({target.get('display_name', '')})")
    print(f"📋 Cookie 长度: {len(cookie)} 字符")

    # 解析 cookie 看看关键字段
    parsed = _parse_cookie_str(cookie)
    portal_st = parsed.get("kuaishou.ai.portal_st", "")
    pass_token = parsed.get("passToken", "")
    print(f"📋 portal_st: {portal_st[:30]}..." if portal_st else "⚠️  无 portal_st")
    print(f"📋 passToken: {pass_token[:30]}..." if pass_token else "⚠️  无 passToken")
    print()

    # Step 1: 检查当前 cookie
    print("=" * 50)
    print("🔍 Step 1: 检查当前 cookie 是否有效...")
    ok = await check_login(cookie)
    print(f"   结果: {'✅ 有效' if ok else '❌ 已失效'}")
    print()

    # Step 2: 尝试刷新 token
    print("=" * 50)
    print("🔄 Step 2: 尝试用 passToken 刷新 token...")
    if not pass_token:
        print("   ⚠️  Cookie 中没有 passToken，无法刷新")
        print("   💡 需要重新扫码登录才能获取 passToken")
        return

    new_cookie = await refresh_token(cookie)
    if new_cookie:
        print(f"   ✅ 刷新成功！新 cookie 长度: {len(new_cookie)} 字符")
        new_parsed = _parse_cookie_str(new_cookie)
        new_st = new_parsed.get("kuaishou.ai.portal_st", "")
        new_pt = new_parsed.get("passToken", "")
        st_changed = new_st != portal_st
        pt_changed = new_pt != pass_token
        print(f"   portal_st 变化: {'是 ✅' if st_changed else '否 ⚠️'}")
        print(f"   passToken 变化: {'是 ✅' if pt_changed else '否'}")
    else:
        print("   ❌ 刷新失败！passToken 可能已过期")
        print("   💡 需要重新扫码登录")
        return

    # Step 3: 验证新 cookie
    print()
    print("=" * 50)
    print("🔍 Step 3: 验证刷新后的新 cookie...")
    ok2 = await check_login(new_cookie)
    print(f"   结果: {'✅ 有效' if ok2 else '❌ 无效'}")
    print()

    # 总结
    print("=" * 50)
    if ok and new_cookie and ok2:
        print("🎉 全部通过！Token 刷新功能正常工作")
        print("   旧 cookie 有效 → 刷新成功 → 新 cookie 有效")
    elif not ok and new_cookie and ok2:
        print("🎉 刷新救回！旧 cookie 已失效但刷新成功")
        print("   旧 cookie 失效 → 刷新成功 → 新 cookie 有效")
    elif not ok and not new_cookie:
        print("💀 完全失效！cookie 和 passToken 都过期了，需要重新扫码")
    else:
        print(f"⚠️  部分异常: check1={ok}, refresh={'OK' if new_cookie else 'FAIL'}, check2={ok2}")


if __name__ == "__main__":
    asyncio.run(main())
