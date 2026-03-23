"""
可灵 AI API 全流程测试脚本 — 从零开始，完全交互式
用法: python scripts/run_full_test.py

完整流程:
  Step 1. 签名系统初始化
  Step 2. 扫码登录（从零获取 cookie）
  Step 3. 验证登录状态
  Step 4. 查询账号积分
  Step 5. 选择生成模式（文生视频 / 图生视频）
  Step 6. 输入提示词和参数
  Step 7. 上传图片（图生视频时）
  Step 8. 提交任务
  Step 9. 轮询任务状态
  Step 10. 结果展示

不依赖任何已保存的 cookie / 账号数据，每次从零开始。
"""
import asyncio
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.kling_api import (
    _gen_did, _gen_risk_id, _sign_url, _make_headers,
    qr_start, qr_scan_result, qr_accept_result,
    check_login, submit_task, poll_task, upload_image,
    get_user_points,
)

# ============ 颜色输出 ============
def green(s):  return f"\033[92m{s}\033[0m"
def red(s):    return f"\033[91m{s}\033[0m"
def yellow(s): return f"\033[93m{s}\033[0m"
def cyan(s):   return f"\033[96m{s}\033[0m"
def bold(s):   return f"\033[1m{s}\033[0m"

def section(n, title):
    print(f"\n{'━'*56}")
    print(f"  {bold(yellow(f'Step {n}'))}  {bold(cyan(title))}")
    print(f"{'━'*56}")

def ok(msg):   print(f"  {green('✓')} {msg}")
def fail(msg): print(f"  {red('✗')} {msg}")
def warn(msg): print(f"  {yellow('!')} {msg}")
def info(msg): print(f"  {cyan('→')} {msg}")

def ask(prompt, default=""):
    """交互式输入，支持默认值"""
    if default:
        val = input(f"  {prompt} [{default}]: ").strip()
        return val if val else default
    return input(f"  {prompt}: ").strip()

def ask_choice(prompt, options, default=0):
    """交互式选择"""
    print(f"  {prompt}")
    for i, (label, val) in enumerate(options):
        marker = f" {green('*')}" if i == default else ""
        print(f"    [{i}] {label}{marker}")
    choice = input(f"  选择 (回车默认 {default}): ").strip()
    try:
        idx = int(choice)
        return options[idx][1] if 0 <= idx < len(options) else options[default][1]
    except (ValueError, IndexError):
        return options[default][1]


# ============ Step 1: 签名 ============
async def step_sign():
    section(1, "签名系统初始化")
    try:
        url = await _sign_url("/api/user/isLogin")
        ok("NS 签名正常")
        info(f"示例: {url[:70]}...")
        return True
    except Exception as e:
        fail(f"签名失败: {e}")
        info("请确保 node 可用且 可灵逆向/sign_cli.js 存在")
        return False


# ============ Step 2: 扫码登录 ============
async def step_login() -> str:
    """从零扫码登录，返回 cookie"""
    section(2, "扫码登录")

    did = _gen_did()
    risk_id = _gen_risk_id()
    info(f"生成设备ID: {did[:20]}...")

    # 获取二维码
    info("请求二维码...")
    try:
        result = await qr_start(did, risk_id)
    except Exception as e:
        fail(f"请求二维码失败: {e}")
        return ""

    if result.get("result") != 1:
        fail(f"返回异常: {result}")
        return ""

    qr_url = result["qrUrl"]
    token = result["qrLoginToken"]
    signature = result["qrLoginSignature"]
    expire_time = result["expireTime"]
    session_cookies = result.get("_session_cookies", {})

    ok("二维码获取成功")
    info(f"过期时间: {time.strftime('%H:%M:%S', time.localtime(expire_time / 1000))}")

    # 终端显示二维码
    try:
        import qrcode
        qr = qrcode.QRCode(box_size=1, border=1)
        qr.add_data(qr_url)
        qr.make(fit=True)
        print(f"\n  {bold(yellow('>>> 请用快手 APP 扫描以下二维码 <<<'))}\n")
        qr.print_ascii(invert=True)
    except ImportError:
        print(f"\n  {bold(yellow('>>> 请用快手 APP 扫描此链接 <<<'))}")
        print(f"  {qr_url}")
        warn("安装 qrcode 库可在终端显示二维码: pip install qrcode")

    # 轮询扫码
    print(f"\n  等待扫码", end="", flush=True)
    scanned = False
    for i in range(90):
        await asyncio.sleep(2)
        try:
            data = await qr_scan_result(did, risk_id, token, signature, session_cookies)
        except Exception:
            print(".", end="", flush=True)
            continue

        rc = data.get("result", 0)
        if rc == 1:
            print()
            ok("已扫码！等待确认...")
            scanned = True
            break
        elif rc == 707:
            print()
            fail("二维码已过期，请重新运行脚本")
            return ""
        else:
            print(".", end="", flush=True)

    if not scanned:
        print()
        fail("等待扫码超时（3分钟）")
        return ""

    # 获取登录凭据
    info("获取登录凭据...")
    try:
        cred = await qr_accept_result(did, risk_id, token, signature, session_cookies)
    except Exception as e:
        fail(f"获取凭据失败: {e}")
        return ""

    cookie = cred["cookie"]
    ok(f"登录成功！cookie 长度 = {len(cookie)}")
    return cookie


# ============ Step 3: 验证登录 ============
async def step_check(cookie: str) -> bool:
    section(3, "验证登录状态")
    logged = await check_login(cookie)
    if logged:
        ok("登录状态有效")
    else:
        fail("登录验证失败")
    return logged


# ============ Step 4: 查询积分 ============
async def step_points(cookie: str) -> int:
    section(4, "查询账号积分")
    try:
        pts = await get_user_points(cookie)
        total = pts.get("total", 0)
        expire = pts.get("expireIn5DaysAmount", 0)
        ok(f"总积分: {bold(green(str(total)))}")
        if expire > 0:
            warn(f"5天内过期: {expire}")
        return total
    except Exception as e:
        fail(f"查询失败: {e}")
        return 0


# ============ Step 5: 选择模式 ============
def step_mode():
    section(5, "选择生成模式")
    mode = ask_choice("视频生成模式:", [
        ("文生视频 (纯文字描述)", "text"),
        ("图生视频 (上传首帧图片)", "image"),
    ], default=0)
    ok(f"已选择: {'文生视频' if mode == 'text' else '图生视频'}")
    return mode


# ============ Step 6: 输入参数 ============
def step_params(gen_mode: str):
    section(6, "输入生成参数")

    # 提示词
    print()
    prompt = ask("输入视频描述 (prompt)")
    while not prompt:
        warn("提示词不能为空")
        prompt = ask("输入视频描述 (prompt)")
    info(f"Prompt: {prompt}")

    # 时长
    print()
    duration = ask_choice("视频时长:", [
        ("5 秒", 5),
        ("10 秒", 10),
    ], default=0)
    info(f"时长: {duration}s")

    # 版本
    print()
    version = ask_choice("可灵版本:", [
        ("Kling 3.0", "3.0"),
        ("Kling 2.6", "2.6"),
    ], default=0)
    info(f"版本: {version}")

    # 模式
    print()
    mode = ask_choice("生成模式:", [
        ("标准 (std)", "std"),
        ("专业 (pro)", "pro"),
    ], default=0)
    info(f"模式: {mode}")

    # 宽高比（仅文生视频）
    aspect_ratio = "16:9"
    if gen_mode == "text":
        print()
        aspect_ratio = ask_choice("宽高比:", [
            ("16:9 横屏", "16:9"),
            ("9:16 竖屏", "9:16"),
            ("1:1 方形", "1:1"),
        ], default=0)
        info(f"宽高比: {aspect_ratio}")

    # 首帧图片（仅图生视频）
    image_path = ""
    if gen_mode == "image":
        print()
        image_path = ask("输入首帧图片路径")
        if image_path:
            image_path = image_path.strip('"').strip("'")
        while not image_path or not os.path.isfile(image_path):
            if image_path:
                warn(f"文件不存在: {image_path}")
            image_path = ask("输入首帧图片路径").strip('"').strip("'")
        info(f"图片: {image_path} ({os.path.getsize(image_path)/1024:.1f} KB)")

    # 尾帧（可选）
    tail_image_path = ""
    if gen_mode == "image":
        print()
        tail_image_path = ask("输入尾帧图片路径 (可选，回车跳过)", "")
        if tail_image_path:
            tail_image_path = tail_image_path.strip('"').strip("'")
            if not os.path.isfile(tail_image_path):
                warn(f"文件不存在: {tail_image_path}，跳过尾帧")
                tail_image_path = ""
            else:
                info(f"尾帧: {tail_image_path} ({os.path.getsize(tail_image_path)/1024:.1f} KB)")

    return {
        "prompt": prompt,
        "duration": duration,
        "version": version,
        "mode": mode,
        "aspect_ratio": aspect_ratio,
        "image_path": image_path,
        "tail_image_path": tail_image_path,
    }


# ============ Step 7: 上传图片 ============
async def step_upload(cookie: str, image_path: str, tail_path: str = ""):
    section(7, "上传图片到 CDN")

    if not image_path:
        info("文生视频模式，无需上传图片")
        return "", ""

    # 首帧
    info(f"上传首帧: {image_path}")
    info("流程: issue/token → fragment → complete → verify/token")
    try:
        cdn_url = await upload_image(cookie, image_path)
        ok(f"首帧上传成功!")
        info(f"CDN: {cdn_url[:80]}...")
    except Exception as e:
        fail(f"首帧上传失败: {e}")
        return "", ""

    # 尾帧
    tail_cdn = ""
    if tail_path:
        info(f"上传尾帧: {tail_path}")
        try:
            tail_cdn = await upload_image(cookie, tail_path)
            ok(f"尾帧上传成功!")
            info(f"CDN: {tail_cdn[:80]}...")
        except Exception as e:
            warn(f"尾帧上传失败: {e}，继续不含尾帧")

    return cdn_url, tail_cdn


# ============ Step 8: 提交任务 ============
async def step_submit(cookie: str, params: dict, image_url: str, tail_url: str):
    section(8, "提交视频生成任务")

    info(f"类型    : m2v_aio2video")
    info(f"Prompt  : {params['prompt']}")
    info(f"时长    : {params['duration']}s")
    info(f"版本    : {params['version']}")
    info(f"模式    : {params['mode']}")
    if image_url:
        info(f"首帧    : {image_url[:50]}...")
    if tail_url:
        info(f"尾帧    : {tail_url[:50]}...")
    if not image_url:
        info(f"宽高比  : {params['aspect_ratio']}")

    print()
    confirm = ask("确认提交? (y/n)", "y")
    if confirm.lower() not in ("y", "yes", ""):
        warn("已取消提交")
        return ""

    info("提交中...")
    try:
        task_id = await submit_task(
            cookie=cookie,
            prompt=params["prompt"],
            image_url=image_url,
            tail_image_url=tail_url,
            duration=params["duration"],
            version=params["version"],
            mode=params["mode"],
            aspect_ratio=params["aspect_ratio"],
        )
        ok(f"任务提交成功!")
        info(f"task_id = {bold(green(task_id))}")
        return task_id
    except Exception as e:
        err_str = str(e)
        if "PointNotEnough" in err_str:
            fail("积分不足，无法提交任务")
        else:
            fail(f"提交失败: {e}")
        return ""


# ============ Step 9: 轮询 ============
async def step_poll(cookie: str, task_id: str):
    section(9, "轮询任务状态")

    if not task_id:
        warn("无 task_id，跳过轮询")
        return None

    info(f"task_id = {task_id}")
    info("最长等待 10 分钟，每 10 秒查询一次...")
    info("按 Ctrl+C 可中断轮询")
    print()

    start = time.time()
    try:
        result = await poll_task(cookie, task_id, timeout=600, interval=10)
        elapsed = time.time() - start
        ok(f"任务完成! 耗时 {elapsed:.0f}s")
        return result
    except TimeoutError:
        warn("10分钟内未完成")
        info(f"可稍后手动轮询: python scripts/kling_api_test.py poll {task_id}")
        return None
    except RuntimeError as e:
        fail(f"任务失败: {e}")
        return None
    except KeyboardInterrupt:
        warn("用户中断轮询")
        info(f"可稍后手动轮询: python scripts/kling_api_test.py poll {task_id}")
        return None


# ============ Step 10: 结果展示 ============
def step_result(result: dict):
    section(10, "生成结果")

    if not result:
        warn("无结果")
        return

    print()
    info(f"Status   : {result.get('status')}")
    video_url = result.get("video_url", "")
    if video_url:
        print(f"\n  {bold(green('视频地址:'))}")
        print(f"  {video_url}")
    cover_url = result.get("cover_url", "")
    if cover_url:
        print(f"\n  {bold('封面地址:')}")
        print(f"  {cover_url}")
    info(f"尺寸 : {result.get('width', '?')}x{result.get('height', '?')}")
    info(f"时长 : {result.get('duration', '?')}s")


# ============ 主流程 ============
async def main():
    print(f"\n{'━'*56}")
    print(f"  {bold(cyan('可灵 AI API 全流程测试'))}")
    print(f"  完全从零开始 · 交互式")
    print(f"{'━'*56}")

    # Step 1: 签名
    if not await step_sign():
        return

    # Step 2: 扫码登录
    cookie = await step_login()
    if not cookie:
        return

    # Step 3: 验证
    if not await step_check(cookie):
        return

    # Step 4: 积分
    points = await step_points(cookie)
    if points <= 0:
        warn("积分为 0，后续任务可能无法提交")
        cont = ask("是否继续? (y/n)", "y")
        if cont.lower() not in ("y", "yes", ""):
            return

    # Step 5: 选择模式
    gen_mode = step_mode()

    # Step 6: 输入参数
    params = step_params(gen_mode)

    # Step 7: 上传图片
    image_url, tail_url = await step_upload(
        cookie, params["image_path"], params["tail_image_path"]
    )
    if gen_mode == "image" and not image_url:
        fail("图片上传失败，无法继续")
        return

    # Step 8: 提交
    task_id = await step_submit(cookie, params, image_url, tail_url)

    # Step 9: 轮询
    result = await step_poll(cookie, task_id)

    # Step 10: 结果
    step_result(result)

    print(f"\n{'━'*56}")
    print(f"  {bold(cyan('测试完成'))}")
    print(f"{'━'*56}\n")


if __name__ == "__main__":
    asyncio.run(main())
