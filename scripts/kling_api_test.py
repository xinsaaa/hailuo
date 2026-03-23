"""
可灵 AI API 本地测试脚本
用法: python scripts/kling_api_test.py [命令]

命令:
  sign             测试签名是否正常
  login            扫码登录并保存 cookie
  check            检查已保存 cookie 的登录状态
  submit           提交一个文生视频任务（需已登录）
  upload <path>    上传图片到可灵CDN，返回URL
  img2video <path> 图生视频完整流程：上传图片 + 提交 + 轮询
  poll <id>        轮询指定 task_id 的状态
  full             完整流程（文生视频）：提交 + 轮询到完成
  accounts         列出所有已保存的可灵账号
"""
import asyncio
import json
import sys
import os
import time

# 确保能 import backend 模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.kling_api import (
    _gen_did, _gen_risk_id, _url_to_qr_base64, _make_headers,
    _build_initial_cookies, _sign_url,
    qr_start, qr_scan_result, qr_accept_result,
    check_login, submit_task, poll_task, upload_image,
    list_kling_accounts, get_kling_credentials,
    save_kling_account, save_kling_credentials,
)

# ============ 颜色输出 ============

def green(s): return f"\033[92m{s}\033[0m"
def red(s):   return f"\033[91m{s}\033[0m"
def yellow(s): return f"\033[93m{s}\033[0m"
def cyan(s):  return f"\033[96m{s}\033[0m"

def banner(title):
    print(f"\n{'='*50}")
    print(f"  {cyan(title)}")
    print(f"{'='*50}")

# ============ 测试: 签名 ============

async def cmd_sign():
    banner("测试 NS 签名")
    try:
        url = await _sign_url("/api/user/isLogin")
        print(green("[OK]"), "签名成功")
        print(f"  签名URL: {url[:100]}...")
    except Exception as e:
        print(red("[FAIL]"), f"签名失败: {e}")
        print("  请确保 node 可用，且 可灵逆向/sign_cli.js 存在")
        return False
    return True

# ============ 测试: 扫码登录 ============

async def cmd_login():
    banner("扫码登录可灵")

    # 先测试签名
    if not await cmd_sign():
        return

    did = _gen_did()
    risk_id = _gen_risk_id()
    print(f"\n  did     = {did}")
    print(f"  risk_id = {risk_id}")

    # 1. 获取二维码
    print(f"\n{yellow('[1/4]')} 请求二维码...")
    try:
        result = await qr_start(did, risk_id)
    except Exception as e:
        print(red("[FAIL]"), f"请求二维码失败: {e}")
        return

    if result.get("result") != 1:
        print(red("[FAIL]"), f"返回异常: {result}")
        return

    qr_url = result["qrUrl"]
    token = result["qrLoginToken"]
    signature = result["qrLoginSignature"]
    expire_time = result["expireTime"]
    session_cookies = result.get("_session_cookies", {})

    print(green("[OK]"), f"二维码URL: {qr_url}")
    print(f"  token    = {token[:30]}...")
    print(f"  过期时间 = {time.strftime('%H:%M:%S', time.localtime(expire_time / 1000))}")

    # 终端显示二维码
    try:
        import qrcode  # type: ignore
        qr = qrcode.QRCode(box_size=1, border=1)
        qr.add_data(qr_url)
        qr.make(fit=True)
        print(f"\n{yellow('请用快手 APP 扫描以下二维码:')}\n")
        qr.print_ascii(invert=True)
    except ImportError:
        print(f"\n{yellow('请用快手 APP 扫描此链接:')}")
        print(f"  {qr_url}")
        print(f"  (安装 qrcode 库可在终端显示二维码: pip install qrcode)")

    # 2. 轮询扫码
    print(f"\n{yellow('[2/4]')} 等待扫码...")
    scanned = False
    for i in range(90):  # 最长等3分钟
        await asyncio.sleep(2)
        try:
            data = await qr_scan_result(did, risk_id, token, signature, session_cookies)
        except Exception as e:
            print(f"  轮询异常: {e}")
            continue

        rc = data.get("result", 0)
        if rc == 1:
            print(green("\n[OK]"), "用户已扫码！等待确认...")
            scanned = True
            break
        elif rc == 707:
            print(red("\n[EXPIRED]"), "二维码已过期，请重新执行 login")
            return
        elif rc == 0:
            sys.stdout.write(f"\r  等待中... ({i*2}s)")
            sys.stdout.flush()
        else:
            print(f"\n  未知 result={rc}: {data.get('error_msg', '')}")

    if not scanned:
        print(red("\n[TIMEOUT]"), "等待扫码超时")
        return

    # 3. 获取登录 cookie
    print(f"\n{yellow('[3/4]')} 获取登录凭据...")
    try:
        cred = await qr_accept_result(did, risk_id, token, signature, session_cookies)
    except Exception as e:
        print(red("[FAIL]"), f"acceptResult 失败: {e}")
        return

    cookie = cred["cookie"]
    print(green("[OK]"), f"获取到 cookie ({len(cookie)} chars)")

    # 4. 验证登录
    print(f"\n{yellow('[4/4]')} 验证登录状态...")
    ok = await check_login(cookie)
    if ok:
        print(green("[OK]"), "登录验证通过！")
    else:
        print(yellow("[WARN]"), "check_login 返回 False，cookie 可能需要更多字段，但已保存")

    # 保存
    account_id = input("\n输入账号ID (如 kling_main): ").strip() or "kling_main"
    display_name = input("输入显示名称 (如 主号): ").strip() or "主号"
    save_kling_account(account_id, display_name)
    save_kling_credentials(account_id, cookie, did)
    print(green("\n[SAVED]"), f"账号 {account_id} 已保存到 kling_accounts.json")

# ============ 测试: 检查登录 ============

async def cmd_check():
    banner("检查可灵登录状态")

    accounts = list_kling_accounts()
    if not accounts:
        print(red("[EMPTY]"), "没有已保存的账号，请先执行 login")
        return

    for acc in accounts:
        aid = acc["account_id"]
        creds = get_kling_credentials(aid)
        if not creds:
            print(f"  {aid}: {red('无凭据')}")
            continue

        cookie = creds["cookie"]
        ok = await check_login(cookie)
        status = green("已登录") if ok else red("已失效")
        print(f"  {aid} ({acc.get('display_name', '')}): {status}")

# ============ 测试: 提交任务 ============

async def cmd_submit(prompt=None, duration=5, version="3.0", mode="std"):
    banner("提交可灵视频生成任务")

    # 选账号
    cookie = _pick_cookie()
    if not cookie:
        return None

    if not prompt:
        prompt = input("输入视频描述 (回车用默认): ").strip()
        if not prompt:
            prompt = "一只橘猫在窗台上打瞌睡，阳光洒在它身上，毛发随微风轻拂"

    print(f"\n  Prompt   : {prompt}")
    print(f"  Duration : {duration}s")
    print(f"  Version  : {version}")
    print(f"  Mode     : {mode}")

    print(f"\n{yellow('提交中...')}")
    try:
        task_id = await submit_task(
            cookie=cookie,
            prompt=prompt,
            image_url="",  # 文生视频不需要图片
            duration=duration,
            version=version,
            mode=mode,
        )
        print(green("[OK]"), f"任务已提交！task_id = {task_id}")
        return task_id
    except Exception as e:
        print(red("[FAIL]"), f"提交失败: {e}")
        return None

# ============ 测试: 轮询任务 ============

async def cmd_poll(task_id=None):
    banner("轮询可灵任务状态")

    cookie = _pick_cookie()
    if not cookie:
        return

    if not task_id:
        task_id = input("输入 task_id: ").strip()
        if not task_id:
            print(red("[ERROR]"), "task_id 不能为空")
            return

    print(f"  task_id = {task_id}")
    print(f"\n{yellow('轮询中 (最长10分钟)...')}\n")

    try:
        result = await poll_task(cookie, task_id, timeout=600, interval=5)
        print(green("\n[完成]"))
        print(f"  Status    : {result.get('status')}")
        print(f"  Video URL : {result.get('video_url', 'N/A')}")
        print(f"  Cover URL : {result.get('cover_url', 'N/A')}")
        print(f"  尺寸      : {result.get('width')}x{result.get('height')}")
        print(f"  时长      : {result.get('duration')}s")
    except TimeoutError:
        print(red("[TIMEOUT]"), "轮询超时")
    except RuntimeError as e:
        print(red("[FAIL]"), f"任务失败: {e}")

# ============ 测试: 图片上传 ============

async def cmd_upload(image_path=None):
    banner("上传图片到可灵 CDN")

    cookie = _pick_cookie()
    if not cookie:
        return None

    if not image_path:
        image_path = input("输入图片路径: ").strip()
        if not image_path:
            print(red("[ERROR]"), "图片路径不能为空")
            return None

    # 去掉可能的引号
    image_path = image_path.strip('"').strip("'")

    if not os.path.isfile(image_path):
        print(red("[ERROR]"), f"文件不存在: {image_path}")
        return None

    file_size = os.path.getsize(image_path)
    print(f"  文件 : {image_path}")
    print(f"  大小 : {file_size / 1024:.1f} KB")

    print(f"\n{yellow('上传中...')}")
    try:
        cdn_url = await upload_image(cookie, image_path)
        print(green("[OK]"), "上传成功！")
        print(f"  CDN URL: {cdn_url}")
        return cdn_url
    except Exception as e:
        print(red("[FAIL]"), f"上传失败: {e}")
        return None

# ============ 测试: 图生视频完整流程 ============

async def cmd_img2video(image_path=None):
    banner("图生视频完整流程: 上传 → 提交 → 轮询")

    cookie = _pick_cookie()
    if not cookie:
        return

    if not image_path:
        image_path = input("输入首帧图片路径: ").strip()
        if not image_path:
            print(red("[ERROR]"), "图片路径不能为空")
            return

    image_path = image_path.strip('"').strip("'")
    if not os.path.isfile(image_path):
        print(red("[ERROR]"), f"文件不存在: {image_path}")
        return

    # 1. 上传图片
    print(f"\n{yellow('[1/3]')} 上传图片...")
    file_size = os.path.getsize(image_path)
    print(f"  文件 : {image_path}  ({file_size / 1024:.1f} KB)")
    try:
        cdn_url = await upload_image(cookie, image_path)
        print(green("[OK]"), f"CDN URL: {cdn_url[:80]}...")
    except Exception as e:
        print(red("[FAIL]"), f"上传失败: {e}")
        return

    # 2. 提交图生视频任务
    prompt = input("\n输入视频描述 (回车用默认): ").strip()
    if not prompt:
        prompt = "画面中的内容缓缓运动起来，自然流畅"

    dur_input = input("时长 5/10 (回车默认5): ").strip()
    duration = 10 if dur_input == "10" else 5

    ver_input = input("版本 1.6/2.0/3.0 (回车默认3.0): ").strip()
    version = ver_input if ver_input in ("1.6", "2.0", "3.0") else "3.0"

    print(f"\n{yellow('[2/3]')} 提交图生视频任务...")
    print(f"  Prompt   : {prompt}")
    print(f"  Image    : {cdn_url[:60]}...")
    print(f"  Duration : {duration}s")
    print(f"  Version  : {version}")

    try:
        task_id = await submit_task(
            cookie=cookie,
            prompt=prompt,
            image_url=cdn_url,
            duration=duration,
            version=version,
            mode="std",
        )
        print(green("[OK]"), f"任务已提交！task_id = {task_id}")
    except Exception as e:
        print(red("[FAIL]"), f"提交失败: {e}")
        return

    # 3. 轮询
    print(f"\n{yellow('[3/3]')} 轮询任务状态 (最长10分钟)...\n")
    try:
        result = await poll_task(cookie, task_id, timeout=600, interval=5)
        print(green("\n[完成]"))
        print(f"  Status    : {result.get('status')}")
        print(f"  Video URL : {result.get('video_url', 'N/A')}")
        print(f"  Cover URL : {result.get('cover_url', 'N/A')}")
        print(f"  尺寸      : {result.get('width')}x{result.get('height')}")
        print(f"  时长      : {result.get('duration')}s")
    except TimeoutError:
        print(red("[TIMEOUT]"), "轮询超时")
    except RuntimeError as e:
        print(red("[FAIL]"), f"任务失败: {e}")

# ============ 测试: 完整流程（文生视频） ============

async def cmd_full():
    banner("完整流程（文生视频）: 提交 → 轮询 → 完成")

    task_id = await cmd_submit()
    if not task_id:
        return

    print(f"\n{'─'*50}")
    await cmd_poll(task_id)

# ============ 列出账号 ============

async def cmd_accounts():
    banner("已保存的可灵账号")

    accounts = list_kling_accounts()
    if not accounts:
        print("  (空) 暂无账号，请执行 login 添加")
        return

    for acc in accounts:
        aid = acc["account_id"]
        name = acc.get("display_name", "")
        active = green("启用") if acc.get("is_active") else red("禁用")
        logged = green("有凭据") if acc.get("is_logged_in") else yellow("无凭据")
        priority = acc.get("priority", 5)
        print(f"  [{aid}] {name}  优先级={priority}  {active}  {logged}")

# ============ 工具 ============

def _pick_cookie() -> str:
    """从已保存账号中选一个可用的 cookie"""
    accounts = list_kling_accounts()
    active = [a for a in accounts if a.get("is_active") and a.get("is_logged_in")]

    if not active:
        print(red("[ERROR]"), "没有可用的已登录账号，请先执行 login")
        return ""

    if len(active) == 1:
        aid = active[0]["account_id"]
    else:
        print("可用账号:")
        for i, a in enumerate(active):
            print(f"  [{i}] {a['account_id']} - {a.get('display_name', '')}")
        idx = input(f"选择 (0-{len(active)-1}): ").strip()
        try:
            aid = active[int(idx)]["account_id"]
        except (ValueError, IndexError):
            aid = active[0]["account_id"]

    creds = get_kling_credentials(aid)
    if not creds:
        print(red("[ERROR]"), f"账号 {aid} 无凭据")
        return ""

    print(f"  使用账号: {cyan(aid)}")
    return creds["cookie"]

# ============ 主入口 ============

COMMANDS = {
    "sign":      cmd_sign,
    "login":     cmd_login,
    "check":     cmd_check,
    "submit":    cmd_submit,
    "upload":    cmd_upload,
    "img2video": cmd_img2video,
    "poll":      cmd_poll,
    "full":      cmd_full,
    "accounts":  cmd_accounts,
}

async def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("可用命令:", ", ".join(COMMANDS.keys()))
        return

    cmd = sys.argv[1].lower()
    if cmd not in COMMANDS:
        print(red(f"未知命令: {cmd}"))
        print("可用命令:", ", ".join(COMMANDS.keys()))
        return

    if cmd == "poll" and len(sys.argv) > 2:
        await cmd_poll(sys.argv[2])
    elif cmd == "upload" and len(sys.argv) > 2:
        await cmd_upload(sys.argv[2])
    elif cmd == "img2video" and len(sys.argv) > 2:
        await cmd_img2video(sys.argv[2])
    else:
        await COMMANDS[cmd]()

if __name__ == "__main__":
    asyncio.run(main())
