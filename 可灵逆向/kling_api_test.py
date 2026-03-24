"""
可灵 AI API 参数测试脚本
测试所有关键接口的签名和参数是否正确
判断标准：返回 taskId 即为成功（即使积分不足也会返回 taskId）

用法：
  python kling_api_test.py --cookie "你的cookie字符串"
  或
  python kling_api_test.py --cookie-file path/to/cookie.txt
  或
  python kling_api_test.py --accounts-file path/to/kling_accounts.json
"""

import asyncio
import json
import subprocess
import sys
import os
import argparse
import time
from pathlib import Path
from urllib.parse import urlencode

import httpx

# ============ 常量 ============

API_BASE = "https://api-app-cn.klingai.com"
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/146.0.0.0 Safari/537.36"
)
SIGN_CLI = Path(__file__).parent / "sign_cli.js"
CAMERA_JSON = json.dumps({
    "type": "empty", "horizontal": 0, "vertical": 0,
    "zoom": 0, "tilt": 0, "pan": 0, "roll": 0
})


# ============ 工具函数 ============

def make_headers(cookie: str) -> dict:
    return {
        "accept": "application/json, text/plain, */*",
        "accept-language": "zh-CN",
        "referer": "https://app.klingai.com/",
        "time-zone": "Asia/Shanghai",
        "user-agent": DEFAULT_UA,
        "sec-ch-ua": '"Chromium";v="143", "Not A(Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "Cookie": cookie,
    }


async def sign_url(url_path: str, query: dict = None, request_body: dict = None) -> str:
    """调用 sign_cli.js 生成签名URL"""
    sign_input = {"url": url_path, "query": query or {}}
    if request_body:
        sign_input["requestBody"] = request_body
    payload = json.dumps(sign_input)

    proc = await asyncio.create_subprocess_exec(
        "node", str(SIGN_CLI),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(payload.encode()), timeout=10)
    if proc.returncode != 0:
        raise RuntimeError(f"sign_cli error: {stderr.decode()}")
    result = json.loads(stdout.decode().strip())
    signed_url = result["signedUrl"]
    if query:
        signed_url += "&" + urlencode(query)
    return signed_url


# ============ 测试用例 ============

class TestResult:
    def __init__(self, name: str):
        self.name = name
        self.passed = False
        self.detail = ""
        self.error = ""

    def __str__(self):
        status = "✅ 通过" if self.passed else "❌ 失败"
        s = f"  {status}  {self.name}"
        if self.detail:
            s += f"\n         {self.detail}"
        if self.error:
            s += f"\n         错误: {self.error}"
        return s


async def test_sign_basic():
    """测试1: sign_cli.js 基础签名"""
    t = TestResult("签名生成 (sign_cli.js)")
    try:
        url = await sign_url("/api/user/isLogin")
        if "__NS_hxfalcon=" in url and "caver=2" in url:
            t.passed = True
            t.detail = f"签名URL: {url[:100]}..."
        else:
            t.error = f"签名URL格式不正确: {url}"
    except Exception as e:
        t.error = str(e)
    return t


async def test_check_login(cookie: str):
    """测试2: 检查登录状态 GET /api/user/isLogin"""
    t = TestResult("登录状态检查 (GET /api/user/isLogin)")
    try:
        url = await sign_url("/api/user/isLogin")
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url, headers=make_headers(cookie))
            data = r.json()
        d = data.get("data", {})
        is_login = d.get("isLogin") is True or d.get("login") is True
        if is_login:
            t.passed = True
            t.detail = f"已登录, userId={d.get('userId', 'N/A')}"
        else:
            t.error = f"未登录, resp={json.dumps(data, ensure_ascii=False)[:200]}"
    except Exception as e:
        t.error = str(e)
    return t


async def test_get_points(cookie: str):
    """测试3: 查询积分 GET /api/user/works/personal/feeds"""
    t = TestResult("积分查询 (GET /api/user/works/personal/feeds)")
    try:
        query = {
            "pageSize": "1", "contentType": "", "favored": "false",
            "pageDirection": "NEXT", "extra": "BASE_WORK",
        }
        url = await sign_url("/api/user/works/personal/feeds", query)
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url, headers=make_headers(cookie))
            data = r.json()
        d = data.get("data") or {}
        points = d.get("userPoints") or {}
        total = points.get("total", 0) / 100
        if data.get("result") == 1:
            t.passed = True
            t.detail = f"积分: {total}"
        else:
            t.error = f"查询失败, resp={json.dumps(data, ensure_ascii=False)[:200]}"
    except Exception as e:
        t.error = str(e)
    return t


def build_task_body(version: str, mode: str, duration: int, aspect_ratio: str,
                    prompt: str = "测试视频", is_img2video: bool = False) -> dict:
    """根据版本构建task body，与kling_api.py的_build_task_body保持一致"""
    if version == "3.0":
        task_type = "m2v_aio2video"
        arguments = [
            {"name": "negative_prompt", "value": ""},
            {"name": "duration", "value": str(duration)},
            {"name": "imageCount", "value": "1"},
            {"name": "kling_version", "value": version},
            {"name": "prompt", "value": prompt},
            {"name": "rich_prompt", "value": prompt},
            {"name": "cfg", "value": "0.5"},
            {"name": "camera_json", "value": CAMERA_JSON},
            {"name": "camera_control_enabled", "value": "false"},
            {"name": "prefer_multi_shots", "value": "true"},
            {"name": "biz", "value": "klingai"},
            {"name": "enable_audio", "value": "true"},
            {"name": "model_mode", "value": mode},
        ]
        if not is_img2video:
            arguments.append({"name": "aspect_ratio", "value": aspect_ratio})
    else:
        task_type = "m2v_img2video_hq" if is_img2video else "m2v_txt2video_hq"
        arguments = [
            {"name": "duration", "value": str(duration)},
            {"name": "imageCount", "value": "1"},
            {"name": "kling_version", "value": version},
            {"name": "prompt", "value": prompt},
            {"name": "rich_prompt", "value": prompt},
            {"name": "camera_json", "value": CAMERA_JSON},
            {"name": "camera_control_enabled", "value": "false"},
            {"name": "prefer_multi_shots", "value": "true"},
            {"name": "biz", "value": "klingai"},
            {"name": "enable_audio", "value": "true"},
        ]
        if not is_img2video:
            arguments.append({"name": "aspect_ratio", "value": aspect_ratio})
    return {"type": task_type, "arguments": arguments, "inputs": []}


async def test_task_price(cookie: str, version: str, mode: str, duration: int, aspect_ratio: str):
    """测试4: 查询任务价格 POST /api/task/price"""
    label = f"v{version}/{mode}/{duration}s/{aspect_ratio}"
    t = TestResult(f"任务价格查询 ({label})")
    try:
        body = build_task_body(version, mode, duration, aspect_ratio)
        url = await sign_url("/api/task/price", request_body=body)
        headers = {**make_headers(cookie), "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(url, headers=headers, json=body)
            data = r.json()
        d = data.get("data")
        if data.get("result") == 1 and isinstance(d, dict):
            price = d.get("price") or {}
            t.passed = True
            t.detail = f"价格: {price.get('payAmount', 'N/A')} 积分"
            return t, price.get("payAmount", 0)
        else:
            status = data.get("status", "N/A")
            msg = data.get("message", "")
            t.error = f"status={status}, msg={msg}, resp={json.dumps(data, ensure_ascii=False)[:150]}"
    except Exception as e:
        t.error = str(e)
    return t, 0


async def test_task_submit(cookie: str, version: str, mode: str, duration: int,
                           aspect_ratio: str, show_price: int):
    """测试5: 提交任务 POST /api/task/submit（核心测试）"""
    label = f"v{version}/{mode}/{duration}s/{aspect_ratio}"
    t = TestResult(f"任务提交 ({label})")
    try:
        body = build_task_body(version, mode, duration, aspect_ratio,
                               prompt="一只可爱的小猫在草地上奔跑")
        if show_price:
            body["arguments"].append({"name": "showPrice", "value": show_price})
        url = await sign_url("/api/task/submit", request_body=body)
        headers = {**make_headers(cookie), "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(url, headers=headers, json=body)
            data = r.json()

        result_code = data.get("result", -1)
        status_code = data.get("status", 200)
        task_data = data.get("data")

        if result_code == 1 and task_data and isinstance(task_data, dict):
            task = task_data.get("task") or {}
            tid = task.get("id")
            if tid:
                t.passed = True
                t.detail = f"taskId={tid}, status={task_data.get('status', 'N/A')}"
            else:
                # result=1 但没有task，可能是429限流等
                msg = data.get("message", "")
                t.error = f"result=1但无taskId, http_status={status_code}, msg={msg}"
                if status_code == 429:
                    t.detail = "（被限流429，参数本身可能没问题）"
        else:
            msg = data.get("message", "")
            err_detail = (data.get("error") or {}).get("detail", "")
            t.error = f"result={result_code}, status={status_code}, msg={msg or err_detail}"
            if "积分" in msg or "points" in msg.lower() or "balance" in msg.lower():
                t.passed = True
                t.detail = "积分不足，但签名和参数格式正确 ✓"
            elif status_code == 429:
                t.detail = "（被限流429，参数本身可能没问题）"
    except Exception as e:
        t.error = str(e)
    return t


async def test_task_status(cookie: str, task_id: str):
    """测试6: 查询任务状态 GET /api/task/status"""
    t = TestResult(f"任务状态查询 (taskId={task_id})")
    try:
        url = await sign_url("/api/task/status", {"taskId": task_id})
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url, headers=make_headers(cookie))
            data = r.json()
        d = data.get("data") or {}
        status = d.get("status", "N/A")
        works = d.get("works") or []
        works_count = len(works)
        if data.get("result") == 1:
            t.passed = True
            t.detail = f"status={status}, works_count={works_count}"
        else:
            http_status = data.get("status", "N/A")
            msg = data.get("message", "")
            t.error = f"http_status={http_status}, msg={msg}"
    except Exception as e:
        t.error = str(e)
    return t


async def test_upload_issue_token(cookie: str):
    """测试7: 图片上传token获取 GET /api/upload/issue/token"""
    t = TestResult("上传Token获取 (GET /api/upload/issue/token)")
    try:
        url = await sign_url("/api/upload/issue/token", {"filename": "test.jpg"})
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url, headers=make_headers(cookie))
            data = r.json()
        if data.get("result") == 1 and data.get("data", {}).get("token"):
            token = data["data"]["token"]
            t.passed = True
            t.detail = f"upload_token={token[:30]}..."
        else:
            t.error = f"resp={json.dumps(data, ensure_ascii=False)[:200]}"
    except Exception as e:
        t.error = str(e)
    return t


# ============ 主流程 ============

async def run_all_tests(cookie: str):
    print("=" * 60)
    print("  可灵 AI API 参数测试")
    print("=" * 60)
    print()

    results = []
    task_id = None

    # ---- 测试1: 签名 ----
    print("[1/8] 测试签名生成...")
    r = await test_sign_basic()
    results.append(r)
    print(r)
    if not r.passed:
        print("\n⛔ 签名生成失败，无法继续后续测试")
        return results

    # ---- 测试2: 登录状态 ----
    print("\n[2/8] 测试登录状态...")
    r = await test_check_login(cookie)
    results.append(r)
    print(r)
    if not r.passed:
        print("\n⛔ 未登录，请检查cookie是否有效")
        return results

    # ---- 测试3: 积分查询 ----
    print("\n[3/8] 测试积分查询...")
    r = await test_get_points(cookie)
    results.append(r)
    print(r)

    # ---- 测试4: 上传token ----
    print("\n[4/8] 测试图片上传Token...")
    r = await test_upload_issue_token(cookie)
    results.append(r)
    print(r)

    # ---- 测试5-8: 不同模型参数组合的 price + submit ----
    test_cases = [
        # (version, mode, duration, aspect_ratio, 描述)
        ("3.0", "std", 5,  "16:9", "视频3.0 标准 5秒 16:9"),
        ("3.0", "std", 10, "9:16", "视频3.0 标准 10秒 9:16"),
        ("2.6", "std", 5,  "1:1",  "视频2.6 标准 5秒 1:1"),
        ("2.5", "pro", 5,  "16:9", "视频2.5Turbo 专业 5秒 16:9"),
    ]

    for i, (ver, mode, dur, ar, desc) in enumerate(test_cases):
        idx = 5 + i
        if i > 0:
            print("\n    ⏳ 等待3秒防止限流...")
            await asyncio.sleep(3)
        print(f"\n[{idx}/8] 测试 {desc}...")

        # 先查价格
        r_price, price = await test_task_price(cookie, ver, mode, dur, ar)
        results.append(r_price)
        print(r_price)

        # 再提交任务
        r_submit = await test_task_submit(cookie, ver, mode, dur, ar, price)
        results.append(r_submit)
        print(r_submit)

        # 记录第一个成功的 taskId 用于后续状态查询测试
        if r_submit.passed and not task_id:
            task_id = r_submit.detail.split("taskId=")[1].split(",")[0] if "taskId=" in r_submit.detail else None

    # ---- 如果有 taskId，测试状态查询 ----
    if task_id:
        print(f"\n[额外] 测试任务状态查询 (taskId={task_id})...")
        await asyncio.sleep(2)
        r = await test_task_status(cookie, task_id)
        results.append(r)
        print(r)

    # ---- 汇总 ----
    print("\n" + "=" * 60)
    print("  测试汇总")
    print("=" * 60)
    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)
    print(f"  总计: {len(results)} 项")
    print(f"  通过: {passed} ✅")
    print(f"  失败: {failed} ❌")
    print()

    if failed == 0:
        print("  🎉 所有测试通过！签名和参数完全正确。")
    else:
        print("  ⚠️  部分测试失败，请检查上方错误信息。")
        for r in results:
            if not r.passed:
                print(f"    - {r.name}: {r.error}")

    print()
    return results


def get_cookie_from_args():
    parser = argparse.ArgumentParser(description="可灵AI API参数测试")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--cookie", help="直接传入cookie字符串")
    group.add_argument("--cookie-file", help="从文件读取cookie（文件内容就是cookie字符串）")
    group.add_argument("--accounts-file", help="从kling_accounts.json读取第一个账号的cookie")
    args = parser.parse_args()

    if args.cookie:
        return args.cookie.strip()
    elif args.cookie_file:
        with open(args.cookie_file, "r", encoding="utf-8") as f:
            return f.read().strip()
    elif args.accounts_file:
        with open(args.accounts_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        creds = data.get("credentials", {})
        if not creds:
            print("❌ accounts文件中没有已登录的账号")
            sys.exit(1)
        first_id = next(iter(creds))
        cookie = creds[first_id].get("cookie", "")
        if not cookie:
            print(f"❌ 账号 {first_id} 没有cookie")
            sys.exit(1)
        print(f"使用账号: {first_id}")
        return cookie


if __name__ == "__main__":
    cookie = get_cookie_from_args()
    print(f"Cookie长度: {len(cookie)} 字符")
    print()
    asyncio.run(run_all_tests(cookie))
