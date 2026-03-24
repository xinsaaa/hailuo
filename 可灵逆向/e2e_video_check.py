"""
可灵视频捕获验证（零积分消耗版）

策略：
1. 查询历史作品列表（/api/user/works/personal/feeds），找到已完成的视频任务
2. 用该任务的taskId调用 /api/task/status，打印完整原始响应
3. 验证代码中 works[0].resource.resource 路径能否拿到视频URL
4. 如果指定了 --task-id，直接查询该任务状态

所有API返回的原始JSON都完整打印，不做任何裁剪。

用法:
  python 可灵逆向/e2e_video_check.py --accounts-file backend/kling_accounts.json
  python 可灵逆向/e2e_video_check.py --accounts-file backend/kling_accounts.json --task-id 306329708257035
"""
import asyncio
import json
import sys
import argparse
from pathlib import Path
from urllib.parse import urlencode

import httpx

API_BASE = "https://api-app-cn.klingai.com"
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/146.0.0.0 Safari/537.36"
)
SIGN_CLI = Path(__file__).parent / "sign_cli.js"


def make_headers(cookie: str) -> dict:
    return {
        "accept": "application/json, text/plain, */*",
        "accept-language": "zh-CN",
        "referer": "https://app.klingai.com/",
        "time-zone": "Asia/Shanghai",
        "user-agent": DEFAULT_UA,
        "Cookie": cookie,
    }


async def sign_url(url_path: str, query: dict = None, request_body: dict = None) -> str:
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


def get_cookie(args) -> str:
    if args.cookie:
        return args.cookie
    if args.accounts_file:
        with open(args.accounts_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        accounts = data.get("accounts", {})
        credentials = data.get("credentials", {})
        for acc_id, acc in accounts.items():
            if acc.get("is_active") and acc_id in credentials:
                cookie = credentials[acc_id].get("cookie", "")
                if cookie:
                    print(f"使用账号: {acc.get('display_name', acc_id)}")
                    return cookie
    print("错误: 无可用cookie")
    sys.exit(1)


def dump(label: str, data):
    """带标签完整打印JSON"""
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    print(json.dumps(data, ensure_ascii=False, indent=2))
    print()


async def api_get(cookie: str, path: str, query: dict = None, print_raw: bool = True) -> dict:
    """签名+GET，返回原始JSON"""
    url = await sign_url(path, query)
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url, headers=make_headers(cookie))
        data = r.json()
    if print_raw:
        dump(f"GET {path}  HTTP {r.status_code}", data)
    else:
        print(f"\n  GET {path}  HTTP {r.status_code}  (原始JSON太大，只打印结构分析)")
    return data


async def find_and_analyze_feeds(cookie: str) -> str:
    """从历史作品列表分析数据结构，找到已完成的视频任务"""
    print("\n[步骤1] 查询历史作品列表（不消耗积分）...")
    query = {
        "pageSize": "10",
        "contentType": "",
        "favored": "false",
        "pageDirection": "NEXT",
        "extra": "BASE_WORK",
    }
    data = await api_get(cookie, "/api/user/works/personal/feeds", query, print_raw=False)

    # feeds 顶层: data -> { works: [...], userPoints, ... }
    feed_data = data.get("data") or {}
    print(f"\n  data 顶层key: {list(feed_data.keys())}")

    # data 可能有 works 或 history
    feed_items = feed_data.get("works") or []
    if not feed_items:
        for k in ["history", "feeds", "list", "items", "records"]:
            val = feed_data.get(k)
            if val and isinstance(val, list):
                feed_items = val
                print(f"  works为空，使用 data.{k} ({len(feed_items)} 条)")
                break

    print(f"  作品数量: {len(feed_items)}")

    found_task_id = ""
    for i, item in enumerate(feed_items):
        print(f"\n  === 作品[{i}] ===")
        print(f"  顶层key: {list(item.keys())}")

        # 任务信息
        task = item.get("task") or {}
        task_id = str(task.get("id", ""))
        task_status = task.get("status", "N/A")
        task_type = task.get("type", "N/A")
        print(f"  task.id={task_id}, task.status={task_status}, task.type={task_type}")

        # 作品内的 works 列表（这才是视频资源）
        inner_works = item.get("works") or []
        print(f"  inner works 数量: {len(inner_works)}")

        for j, w in enumerate(inner_works):
            print(f"\n    -- works[{j}] --")
            print(f"    顶层key: {list(w.keys())}")

            # 关键路径: works[j].resource.resource
            resource = w.get("resource") or {}
            if isinstance(resource, dict):
                video_url = resource.get("resource", "")
                print(f"    resource keys: {list(resource.keys())}")
                print(f"    resource.resource = {video_url[:150] if video_url else '(空)'}")
                print(f"    resource.width={resource.get('width')}, height={resource.get('height')}, duration={resource.get('duration')}")

                # 检查是否有 multiResList（多分辨率）
                multi_res = resource.get("multiResList") or []
                if multi_res:
                    print(f"    resource.multiResList: {len(multi_res)} 个分辨率")
                    for mr in multi_res:
                        print(f"      {mr.get('qualityType','?')}: {mr.get('url','')[:80]}...")

                if video_url and not found_task_id:
                    found_task_id = task_id
                    # 验证可访问性
                    print(f"\n    [验证视频URL可访问性]")
                    try:
                        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                            head = await client.head(video_url)
                            print(f"      HTTP {head.status_code}, Content-Type={head.headers.get('content-type','?')}, Len={head.headers.get('content-length','?')}")
                    except Exception as e:
                        print(f"      访问失败: {e}")
            else:
                print(f"    resource 非dict: {type(resource).__name__}")

            # cover 路径
            cover = w.get("cover") or {}
            if isinstance(cover, dict):
                cover_url = cover.get("resource", "")
                print(f"    cover.resource = {cover_url[:100] if cover_url else '(空)'}")

    if found_task_id:
        print(f"\n  ✅ 找到有视频URL的任务: taskId={found_task_id}")
    else:
        print(f"\n  ⚠️ 没有找到有视频URL的已完成任务")
        # 取第一个有 taskId 的
        for item in feed_items:
            task = item.get("task") or {}
            tid = str(task.get("id", ""))
            if tid:
                found_task_id = tid
                print(f"  使用第一个taskId: {found_task_id}")
                break

    return found_task_id


async def check_task_status(cookie: str, task_id: str):
    """查询任务状态，打印完整原始响应，验证代码提取逻辑"""
    print(f"\n[步骤2] 查询任务状态 taskId={task_id}...")
    data = await api_get(cookie, "/api/task/status", {"taskId": task_id})

    d = data.get("data") or {}
    status = d.get("status", "N/A")
    works = d.get("works") or []
    
    print(f"\n[解析结果]")
    print(f"  data.status  = {status}")
    print(f"  data.works   = {len(works)} 条")

    if not works:
        print(f"\n  ⚠️ works为空（可能任务还在排队或已过期）")
        # 打印data的所有顶层key帮助分析
        print(f"  data顶层key: {list(d.keys())}")
        return

    # 逐条分析works
    for i, w in enumerate(works):
        print(f"\n  --- works[{i}] ---")
        print(f"  顶层key: {list(w.keys())}")
        
        # 代码路径: works[0].resource.resource
        resource = w.get("resource", {})
        if isinstance(resource, dict):
            video_url = resource.get("resource", "")
            print(f"  resource (dict) keys: {list(resource.keys())}")
            print(f"  resource.resource (video_url) = {video_url[:200] if video_url else '(空)'}")
            print(f"  resource.width    = {resource.get('width')}")
            print(f"  resource.height   = {resource.get('height')}")
            print(f"  resource.duration = {resource.get('duration')}")
        else:
            print(f"  resource 类型异常: {type(resource).__name__} = {str(resource)[:200]}")

        # cover路径: works[0].cover.resource
        cover = w.get("cover", {})
        if isinstance(cover, dict):
            cover_url = cover.get("resource", "")
            print(f"  cover.resource (cover_url) = {cover_url[:200] if cover_url else '(空)'}")
        
        # 如果有video_url，验证可访问性
        if isinstance(resource, dict) and resource.get("resource"):
            video_url = resource["resource"]
            print(f"\n  [验证视频URL可访问性]")
            try:
                async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                    head = await client.head(video_url)
                    print(f"    HTTP status  = {head.status_code}")
                    print(f"    Content-Type = {head.headers.get('content-type', '?')}")
                    print(f"    Content-Len  = {head.headers.get('content-length', '?')}")
                    if head.status_code == 200:
                        print(f"    ✅ 视频URL可正常下载!")
                    else:
                        print(f"    ⚠️ 非200状态码")
            except Exception as e:
                print(f"    ❌ 访问失败: {e}")

    # 最终结论
    w0 = works[0]
    r0 = w0.get("resource", {})
    v0 = r0.get("resource", "") if isinstance(r0, dict) else ""
    print(f"\n{'='*60}")
    if v0:
        print(f"  结论: ✅ works[0].resource.resource 路径有效")
        print(f"  代码的 poll_task 逻辑可以正确捕获视频URL")
    else:
        print(f"  结论: ❌ works[0].resource.resource 为空")
        print(f"  可能原因: 任务未完成 / 已过期 / 数据结构不同")
        print(f"  请检查上方完整原始JSON确认实际结构")
    print(f"{'='*60}")


async def main():
    parser = argparse.ArgumentParser(description="可灵视频捕获验证（零积分消耗）")
    parser.add_argument("--cookie", default="", help="直接提供cookie")
    parser.add_argument("--accounts-file", default="", help="kling_accounts.json路径")
    parser.add_argument("--task-id", default="", help="直接查询指定taskId状态")
    args = parser.parse_args()

    cookie = get_cookie(args)
    print(f"Cookie长度: {len(cookie)} 字符")

    if args.task_id:
        task_id = args.task_id
    else:
        task_id = await find_and_analyze_feeds(cookie)
        if not task_id:
            print("无法找到可用的taskId，退出")
            sys.exit(1)

    await check_task_status(cookie, task_id)


if __name__ == "__main__":
    asyncio.run(main())
