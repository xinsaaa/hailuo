"""
可灵 AI HTTP API 客户端
纯接口调用，无需 Playwright 浏览器自动化

登录流程：
  1. POST /rest/c/infra/ks/qr/start        → 获取二维码 URL、token、signature
  2. 展示二维码给用户扫描
  3. 轮询 POST /rest/c/infra/ks/qr/scanResult → result=1 时用户已扫码
  4. POST /rest/c/infra/ks/qr/acceptResult  → 获取登录 cookie
"""
import asyncio
import base64
import io
import json
import logging
import random
import string
import time
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# ============ 常量 ============

ID_BASE = "https://id.klingai.com"
APP_BASE = "https://app.klingai.com"
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/146.0.0.0 Safari/537.36"
)

DATA_DIR = Path(__file__).parent
KLING_ACCOUNTS_FILE = DATA_DIR / "kling_accounts.json"

# ============ 工具函数 ============

def _gen_did() -> str:
    chars = string.ascii_lowercase + string.digits
    suffix = "".join(random.choices(chars, k=32))
    return f"web_{suffix}"


def _gen_risk_id() -> str:
    return "".join(random.choices(string.digits, k=24))


def _url_to_qr_base64(url: str) -> str:
    """将 URL 转成二维码 base64 图片字符串"""
    try:
        import qrcode  # type: ignore
        qr = qrcode.QRCode(box_size=6, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    except ImportError:
        return ""


# ============ 账号文件存储 ============

def _load_accounts() -> dict:
    if not KLING_ACCOUNTS_FILE.exists():
        default = {"accounts": {}, "credentials": {}}
        _save_accounts(default)
        return default
    with open(KLING_ACCOUNTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_accounts(data: dict):
    with open(KLING_ACCOUNTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_kling_account(account_id: str) -> Optional[dict]:
    data = _load_accounts()
    return data["accounts"].get(account_id)


def get_kling_credentials(account_id: str) -> Optional[dict]:
    data = _load_accounts()
    return data["credentials"].get(account_id)


def list_kling_accounts() -> list:
    data = _load_accounts()
    accounts = []
    for aid, acc in data["accounts"].items():
        creds = data["credentials"].get(aid)
        accounts.append({
            **acc,
            "is_logged_in": creds is not None,
        })
    return accounts


def save_kling_account(account_id: str, display_name: str, priority: int = 5,
                       max_concurrent: int = 3) -> dict:
    data = _load_accounts()
    acc = {
        "account_id": account_id,
        "display_name": display_name,
        "priority": priority,
        "is_active": True,
        "max_concurrent": max_concurrent,
        "current_tasks": 0,
    }
    data["accounts"][account_id] = acc
    _save_accounts(data)
    return acc


def save_kling_credentials(account_id: str, cookie: str, did: str):
    data = _load_accounts()
    data["credentials"][account_id] = {"cookie": cookie, "did": did}
    _save_accounts(data)


def delete_kling_account(account_id: str):
    data = _load_accounts()
    data["accounts"].pop(account_id, None)
    data["credentials"].pop(account_id, None)
    _save_accounts(data)


def update_kling_account(account_id: str, **kwargs):
    data = _load_accounts()
    if account_id not in data["accounts"]:
        return None
    data["accounts"][account_id].update(kwargs)
    _save_accounts(data)
    return data["accounts"][account_id]


# ============ HTTP 客户端 ============

def _make_headers(kwfv1: str = "") -> dict:
    h = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "zh-CN",
        "referer": "https://app.klingai.com/",
        "time-zone": "Asia/Shanghai",
        "user-agent": DEFAULT_UA,
        "sec-ch-ua": '"Chromium";v="143", "Not A(Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
    }
    if kwfv1:
        h["kww"] = kwfv1
    return h


def _build_initial_cookies(did: str, risk_id: str) -> dict:
    return {
        "did": did,
        "__risk_web_device_id": risk_id,
        "accept-language": "zh-CN",
        "KLING_LAST_ACCESS_REGION": "cn",
        "kwpsecproductname": "kling-web",
        "teamId": "",
    }


# ============ QR 登录流程 ============

async def qr_start(did: str, risk_id: str) -> dict:
    """
    启动二维码登录，返回 {data: {...}, session_cookies: {...}}
    先访问主页初始化 session（获取 kwfv1/kwssectoken/kwscode），再请求 qr/start
    """
    init_cookies = dict(_build_initial_cookies(did, risk_id))
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        # 步骤0：访问主页，触发服务端下发 kwfv1/kwssectoken/kwscode
        try:
            resp_init = await client.get(
                f"{APP_BASE}/",
                headers=_make_headers(),
                cookies=init_cookies,
            )
        except Exception:
            resp_init = None
        session_cookies = dict(init_cookies)
        if resp_init is not None:
            for k, v in resp_init.cookies.items():
                session_cookies[k] = v

        # 步骤1：请求 qr/start
        resp = await client.post(
            f"{ID_BASE}/rest/c/infra/ks/qr/start",
            headers=_make_headers(session_cookies.get("kwfv1", "")),
            cookies=session_cookies,
            data={
                "sid": "kuaishou.ai.portal",
                "type": "KELING_WEB",
                "channelType": "UNKNOWN",
            },
        )
        resp.raise_for_status()
        for k, v in resp.cookies.items():
            session_cookies[k] = v
        body = resp.json()
        body["_session_cookies"] = session_cookies
        return body


async def qr_scan_result(did: str, risk_id: str, token: str, signature: str, session_cookies: dict = None) -> dict:
    """
    轮询扫码状态，返回原始响应 JSON
    result=0: 未扫码；result=1: 已扫码待确认
    """
    cookies = session_cookies or _build_initial_cookies(did, risk_id)
    kwfv1 = cookies.get("kwfv1", "")
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{ID_BASE}/rest/c/infra/ks/qr/scanResult",
            headers=_make_headers(kwfv1),
            cookies=cookies,
            data={
                "qrLoginToken": token,
                "qrLoginSignature": signature,
                "channelType": "UNKNOWN",
            },
        )
        resp.raise_for_status()
        return resp.json()


async def qr_accept_result(did: str, risk_id: str, token: str, signature: str, session_cookies: dict = None) -> dict:
    """
    两步获取登录 cookie：
    1. POST qr/acceptResult  → 得到 qrToken
    2. POST pass/kuaishou/login/qr/callback + qrToken → 得到 portal cookie
    返回 {body, cookie, kwfv1}
    """
    cookies = dict(session_cookies) if session_cookies else dict(_build_initial_cookies(did, risk_id))
    kwfv1 = cookies.get("kwfv1", "")

    # 步骤1: acceptResult
    async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
        resp = await client.post(
            f"{ID_BASE}/rest/c/infra/ks/qr/acceptResult",
            headers=_make_headers(kwfv1),
            cookies=cookies,
            data={
                "sid": "kuaishou.ai.portal",
                "qrLoginToken": token,
                "qrLoginSignature": signature,
                "channelType": "UNKNOWN",
            },
        )
        resp.raise_for_status()
        body1 = resp.json()
        # 合并 Set-Cookie
        for k, v in resp.cookies.items():
            cookies[k] = v

    qr_token = body1.get("qrToken", "")
    if not qr_token:
        # 直接包含 portal_st（极少数情况）
        portal_st = body1.get("kuaishou.ai.portal_st", "")
        if portal_st:
            cookies["kuaishou.ai.portal_st"] = portal_st
            cookies["passToken"] = body1.get("passToken", "")
            cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
            return {"body": body1, "cookie": cookie_str, "kwfv1": cookies.get("kwfv1", "")}
        raise RuntimeError(f"acceptResult 未返回 qrToken: {body1}")

    # 步骤2: callback 用 qrToken 换 portal cookie
    kwfv1 = cookies.get("kwfv1", "")
    async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
        resp2 = await client.post(
            f"{ID_BASE}/pass/kuaishou/login/qr/callback",
            headers=_make_headers(kwfv1),
            cookies=cookies,
            data={
                "qrToken": qr_token,
                "sid": "kuaishou.ai.portal",
                "channelType": "UNKNOWN",
            },
        )
        resp2.raise_for_status()
        body2 = resp2.json()
        for cookie in resp2.cookies.jar:
            cookies[cookie.name] = cookie.value

    # 从 body2 提取 portal 登录字段
    for field in ("kuaishou.ai.portal_st", "passToken", "kuaishou.ai.portal.at", "userId", "ssecurity"):
        val = body2.get(field, "")
        if val:
            cookies[field] = val

    cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
    return {
        "body": body2,
        "cookie": cookie_str,
        "kwfv1": cookies.get("kwfv1", ""),
    }


async def _sign_url(url_path: str, query: dict = None, request_body: dict = None) -> str:
    """
    调用 Node.js sign_cli.js 生成带签名的完整 URL。
    返回 signedUrl，形如 https://api-app-cn.klingai.com/api/...?__NS_hxfalcon=...&caver=2&key=val...
    注意: sign_cli 生成的 signedUrl 只包含 __NS_hxfalcon 和 caver，
    额外的 query 参数需要手动追加。
    """
    import asyncio
    import json as _json
    from urllib.parse import urlencode

    sign_cli = Path(__file__).parent.parent / "可灵逆向" / "sign_cli.js"
    sign_input = {"url": url_path, "query": query or {}}
    if request_body:
        sign_input["requestBody"] = request_body
    payload = _json.dumps(sign_input)
    proc = await asyncio.create_subprocess_exec(
        "node", str(sign_cli),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(payload.encode()), timeout=10)
    if proc.returncode != 0:
        raise RuntimeError(f"sign_cli error: {stderr.decode()}")
    result = _json.loads(stdout.decode().strip())
    signed_url = result["signedUrl"]
    # 追加额外的 query 参数到签名URL后面
    if query:
        extra = urlencode(query)
        signed_url += "&" + extra
    return signed_url


async def check_login(cookie: str) -> bool:
    """用保存的 cookie + NS 签名验证登录状态"""
    try:
        signed_url = await _sign_url("/api/user/isLogin")
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                signed_url,
                headers={
                    **_make_headers(),
                    "Cookie": cookie,
                },
            )
            data = resp.json()
            d = data.get("data") or {}
            is_ok = d.get("isLogin") is True or d.get("login") is True
            if not is_ok:
                logger.warning(f"[check_login] 验证失败, resp={data}")
            return is_ok
    except Exception as e:
        logger.error(f"[check_login] 异常: {e}")
        return False


# ============ 图片上传 ============

async def upload_image(cookie: str, image_path: str) -> str:
    """
    上传图片到可灵，返回 CDN URL。
    流程：issue/token → POST fragment → POST complete → verify/token 轮询
    """
    import hashlib
    path = Path(image_path)
    file_bytes = path.read_bytes()
    file_md5 = hashlib.md5(file_bytes).hexdigest()
    filename = path.name

    # 1. 获取上传 token
    signed_issue = await _sign_url("/api/upload/issue/token", {"filename": filename})
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(signed_issue, headers={**_make_headers(), "Cookie": cookie})
        r.raise_for_status()
        issue_data = r.json()
    if issue_data.get("result") != 1:
        raise RuntimeError(f"issue/token failed: {issue_data}")
    upload_token = issue_data["data"]["token"]
    endpoints = issue_data["data"].get("httpEndpoints", ["upload.kuaishouzt.com"])
    upload_host = endpoints[0] if endpoints else "upload.kuaishouzt.com"
    upload_base = f"https://{upload_host}"
    upload_headers = {"x-token": upload_token, "User-Agent": DEFAULT_UA}

    # 2. 上传文件（POST fragment）
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{upload_base}/api/upload/fragment",
            headers={**upload_headers, "Content-Type": "application/octet-stream"},
            params={"fragment_id": 0, "upload_token": upload_token},
            content=file_bytes,
        )
        r.raise_for_status()
        frag_data = r.json()
    if frag_data.get("result") != 1:
        raise RuntimeError(f"upload fragment failed: {frag_data}")

    # 3. 通知上传完成（POST complete）
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(
            f"{upload_base}/api/upload/complete",
            headers=upload_headers,
            params={"upload_token": upload_token, "fragment_count": 1, "md5": file_md5},
        )
        r.raise_for_status()
        complete_data = r.json()
    if complete_data.get("result") != 1:
        raise RuntimeError(f"upload complete failed: {complete_data}")

    # 4. 轮询 verify/token 直到 status=3，获取 CDN URL
    for _ in range(30):
        await asyncio.sleep(2)
        signed_verify = await _sign_url("/api/upload/verify/token", {
            "token": upload_token, "type": "image"
        })
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(signed_verify, headers={**_make_headers(), "Cookie": cookie})
            r.raise_for_status()
            verify_data = r.json()
        vd = verify_data.get("data", {})
        if vd.get("status") == 3:
            return vd["url"]
    raise TimeoutError("upload verify timed out")


# ============ 任务提交与轮询 ============

_CAMERA_JSON = json.dumps({
    "type": "empty", "horizontal": 0, "vertical": 0,
    "zoom": 0, "tilt": 0, "pan": 0, "roll": 0
})


async def submit_task(
    cookie: str,
    prompt: str,
    image_url: str = "",
    duration: int = 5,
    version: str = "3.0",
    mode: str = "std",
    negative_prompt: str = "",
    tail_image_url: str = "",
    aspect_ratio: str = "16:9",
) -> str:
    """
    提交视频生成任务，返回 task_id。
    image_url 为空时提交文生视频，否则提交图生视频。统一使用 m2v_aio2video 类型。
    """
    is_img2video = bool(image_url)

    arguments = [
        {"name": "negative_prompt", "value": negative_prompt},
        {"name": "duration", "value": str(duration)},
        {"name": "imageCount", "value": "1"},
        {"name": "kling_version", "value": version},
        {"name": "prompt", "value": prompt},
        {"name": "rich_prompt", "value": prompt},
        {"name": "cfg", "value": "0.5"},
        {"name": "camera_json", "value": _CAMERA_JSON},
        {"name": "camera_control_enabled", "value": "false"},
        {"name": "prefer_multi_shots", "value": "true"},
        {"name": "biz", "value": "klingai"},
        {"name": "enable_audio", "value": "true"},
        {"name": "model_mode", "value": mode},
    ]
    if not is_img2video:
        arguments.append({"name": "aspect_ratio", "value": aspect_ratio})

    body = {
        "type": "m2v_aio2video",
        "arguments": arguments,
        "inputs": [],
    }
    if is_img2video:
        body["inputs"].append({"inputType": "URL", "url": image_url, "name": "input"})
        if tail_image_url:
            body["inputs"].append({"inputType": "URL", "url": tail_image_url, "name": "tail_image"})

    # 先查询价格（task/price），获取 showPrice
    price_body = {"type": body["type"], "arguments": body["arguments"], "inputs": body["inputs"]}
    signed_price_url = await _sign_url("/api/task/price", request_body=price_body)
    headers = {**_make_headers(), "Cookie": cookie, "Content-Type": "application/json"}
    show_price = 0
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            pr = await client.post(signed_price_url, headers=headers, json=price_body)
            pr.raise_for_status()
            price_data = pr.json()
            show_price = price_data.get("data", {}).get("price", {}).get("payAmount", 0)
        except Exception:
            pass  # 价格查询失败不阻塞提交

    # 把 showPrice 追加到 arguments
    if show_price:
        body["arguments"].append({"name": "showPrice", "value": show_price})

    signed_url = await _sign_url("/api/task/submit", request_body=body)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(signed_url, headers=headers, json=body)
        r.raise_for_status()
        data = r.json()
    result_code = data.get("result", -1)
    if result_code != 1 or data.get("data") is None:
        err = data.get("error", {})
        msg = err.get("detail") or data.get("message") or str(data)
        raise RuntimeError(f"task/submit failed (result={result_code}, status={data.get('status')}): {msg}")
    return str(data["data"]["task"]["id"])


async def poll_task(cookie: str, task_id: str, timeout: int = 600, interval: int = 5) -> dict:
    """
    轮询任务状态，返回 {task_id, status, video_url, cover_url}。
    status 50 = 成功，status 9x = 失败。
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        await asyncio.sleep(interval)
        signed_url = await _sign_url("/api/task/status", {"taskId": task_id})
        headers = {**_make_headers(), "Cookie": cookie}
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(signed_url, headers=headers)
            r.raise_for_status()
            data = r.json()
        d = data.get("data") or {}
        status = d.get("status", 0)
        works = d.get("works") or []
        # status >= 50 means terminal state; works populated means success
        if works:
            w = works[0]
            resource = w.get("resource", {})
            return {
                "task_id": task_id,
                "status": status,
                "video_url": resource.get("resource", ""),
                "cover_url": w.get("cover", {}).get("resource", ""),
                "width": resource.get("width", 0),
                "height": resource.get("height", 0),
                "duration": resource.get("duration", 0),
            }
        if status >= 90:
            raise RuntimeError(f"task {task_id} failed with status {status}: {d.get('message', '')}")
    raise TimeoutError(f"task {task_id} timed out after {timeout}s")


async def get_user_points(cookie: str) -> dict:
    """
    查询可灵账号积分，返回 {total, expireIn5DaysAmount}。
    利用 user/works/personal/feeds 接口（响应中附带 userPoints）。
    """
    signed_url = await _sign_url("/api/user/works/personal/feeds", {
        "pageSize": "1", "contentType": "", "favored": "false",
        "pageDirection": "NEXT", "extra": "BASE_WORK",
    })
    headers = {**_make_headers(), "Cookie": cookie}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(signed_url, headers=headers)
        r.raise_for_status()
        data = r.json()
    points = data.get("data", {}).get("userPoints", {})
    return {
        "total": points.get("total", 0) / 100,
        "expireIn5DaysAmount": points.get("expireIn5DaysAmount", 0) / 100,
    }


# ============ 账号状态监测 ============

_monitor_task: Optional[asyncio.Task] = None


async def _monitor_loop(interval: int = 300):
    """
    后台循环，每隔 interval 秒检查所有可灵账号的登录状态，
    并将结果写入 kling_credentials.json 的 is_logged_in 字段。
    """
    import logging
    logger = logging.getLogger("kling_monitor")
    while True:
        try:
            accounts = list_kling_accounts()
            for acc in accounts:
                aid = acc["account_id"]
                creds = get_kling_credentials(aid)
                if not creds:
                    continue
                cookie = creds.get("cookie", "")
                if not cookie:
                    continue
                ok = await check_login(cookie)
                # 更新 is_logged_in 标记
                _data = _load_accounts()
                if aid in _data["accounts"]:
                    _data["accounts"][aid]["is_logged_in"] = ok
                _save_accounts(_data)
                logger.info(f"[kling_monitor] {aid} isLogin={ok}")
        except Exception as e:
            logger.warning(f"[kling_monitor] 检查异常: {e}")
        await asyncio.sleep(interval)


def start_monitor(interval: int = 300):
    """在当前 event loop 中启动监测后台任务（只启动一次）"""
    global _monitor_task
    if _monitor_task is None or _monitor_task.done():
        _monitor_task = asyncio.create_task(_monitor_loop(interval))


def stop_monitor():
    global _monitor_task
    if _monitor_task and not _monitor_task.done():
        _monitor_task.cancel()
        _monitor_task = None
