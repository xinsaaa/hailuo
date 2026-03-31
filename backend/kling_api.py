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
import os
import random
import string
import time
from pathlib import Path
from typing import Optional

import httpx
from backend.email_service import send_email

logger = logging.getLogger(__name__)

# ============ 常量 ============

ID_BASE = "https://id.klingai.com"
APP_BASE = "https://app.klingai.com"
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/146.0.0.0 Safari/537.36"
)

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
KLING_ACCOUNTS_FILE = DATA_DIR / "kling_accounts.json"

# Monitor safety controls
DEFAULT_MONITOR_INTERVAL = 1800  # 30 minutes
REFRESH_MAX_FAILS = 3
REFRESH_BACKOFF_BASE = 900       # 15 minutes
REFRESH_BACKOFF_MAX = 21600      # 6 hours
KLING_ALERT_EMAIL = os.getenv("KLING_ALERT_EMAIL", "758045020@qq.com")

# 自动迁移：如果旧路径有数据但新路径没有，复制过来
_OLD_ACCOUNTS_FILE = Path(__file__).parent / "kling_accounts.json"
if _OLD_ACCOUNTS_FILE.exists() and not KLING_ACCOUNTS_FILE.exists():
    import shutil
    shutil.copy2(_OLD_ACCOUNTS_FILE, KLING_ACCOUNTS_FILE)
    logger.info(f"已迁移 kling_accounts.json 到 {KLING_ACCOUNTS_FILE}")

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
        # 优先使用 check_login 更新的 is_logged_in 状态，没有凭据则一定未登录
        is_logged = acc.get("is_logged_in", False) if creds else False
        accounts.append({
            **acc,
            "is_logged_in": is_logged,
            "refresh_fail_count": int(acc.get("refresh_fail_count", 0) or 0),
            "refresh_paused": bool(acc.get("refresh_paused", False)),
            "needs_relogin": bool(acc.get("needs_relogin", False)),
            "next_refresh_retry_at": int(acc.get("next_refresh_retry_at", 0) or 0),
            "monitor_message": acc.get("monitor_message", ""),
            "offline_alert_sent": bool(acc.get("offline_alert_sent", False)),
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
        "refresh_fail_count": 0,
        "refresh_paused": False,
        "needs_relogin": False,
        "next_refresh_retry_at": 0,
        "monitor_message": "",
        "offline_alert_sent": False,
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
        "origin": "https://app.klingai.com",
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


def _cookie_value(cookie_str: str, key: str, default: str = "") -> str:
    """Get one value from a raw `k1=v1; k2=v2` cookie string."""
    for part in cookie_str.split(";"):
        part = part.strip()
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        if k.strip() == key:
            return v.strip()
    return default


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
    """用实际业务接口验证 cookie 是否有效（isLogin 接口太宽松，会误判）"""
    try:
        signed_url = await _sign_url("/api/user/works/personal/feeds", {
            "pageSize": "1", "contentType": "", "favored": "false",
            "pageDirection": "NEXT", "extra": "BASE_WORK",
        })
        headers = {**_make_headers(), "Cookie": cookie}
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(signed_url, headers=headers)
            logger.debug(f"[check_login] feeds HTTP {resp.status_code}")
            if resp.status_code == 401:
                logger.warning(f"[check_login] cookie token无效 (401)")
                return False
            if resp.status_code != 200:
                logger.warning(f"[check_login] 非200状态: {resp.status_code}")
                return False
            data = resp.json()
            if data.get("result") == -401:
                logger.warning(f"[check_login] token value error: {data}")
                return False
            return data.get("status") == 200 or data.get("data") is not None
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
    logger.debug(f"[upload] issue/token resp={issue_data}")
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
    logger.debug(f"[upload] fragment resp={frag_data}")
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
    logger.debug(f"[upload] complete resp={complete_data}")
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
        logger.debug(f"[upload] verify status={vd.get('status')}, resp={verify_data}")
        if vd.get("status") == 3:
            cdn_url = vd["url"]
            logger.info(f"[upload] 图片上传成功, CDN URL={cdn_url}")
            return cdn_url
    raise TimeoutError("upload verify timed out")


# ============ 任务提交与轮询 ============

_CAMERA_JSON = json.dumps({
    "type": "empty", "horizontal": 0, "vertical": 0,
    "zoom": 0, "tilt": 0, "pan": 0, "roll": 0
})


def _build_task_body(
    prompt: str,
    image_url: str,
    tail_image_url: str,
    duration: int,
    version: str,
    mode: str,
    negative_prompt: str,
    aspect_ratio: str,
) -> dict:
    """根据版本号构建不同的 task body（type + arguments + inputs）"""
    is_img2video = bool(image_url)

    if version == "3.0":
        # v3.0 统一用 m2v_aio2video，支持文生视频和图生视频
        task_type = "m2v_aio2video"
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
    else:
        # v2.6 / v2.5 等旧版本
        task_type = "m2v_img2video_hq" if is_img2video else "m2v_txt2video_hq"
        arguments = [
            {"name": "duration", "value": str(duration)},
            {"name": "imageCount", "value": "1"},
            {"name": "kling_version", "value": version},
            {"name": "prompt", "value": prompt},
            {"name": "rich_prompt", "value": prompt},
            {"name": "camera_json", "value": _CAMERA_JSON},
            {"name": "camera_control_enabled", "value": "false"},
            {"name": "prefer_multi_shots", "value": "true"},
            {"name": "biz", "value": "klingai"},
            {"name": "enable_audio", "value": "true"},
            {"name": "model_mode", "value": mode},
        ]
        if not is_img2video:
            arguments.append({"name": "aspect_ratio", "value": aspect_ratio})

    body = {"type": task_type, "arguments": arguments, "inputs": []}
    if is_img2video:
        body["inputs"].append({"inputType": "URL", "url": image_url, "name": "input"})
        if tail_image_url:
            body["inputs"].append({"inputType": "URL", "url": tail_image_url, "name": "tail_image"})
    return body


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
    v3.0 统一用 m2v_aio2video；v2.6/v2.5 图生视频用 m2v_img2video_hq，文生视频用 m2v_txt2video_hq。
    """
    body = _build_task_body(prompt, image_url, tail_image_url, duration,
                            version, mode, negative_prompt, aspect_ratio)

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
            logger.debug(f"[submit] task/price resp={price_data}")
            show_price = price_data.get("data", {}).get("price", {}).get("payAmount", 0)
        except Exception as e:
            logger.warning(f"[submit] task/price 查询失败: {e}")

    # 把 showPrice 追加到 arguments
    if show_price:
        body["arguments"].append({"name": "showPrice", "value": show_price})

    signed_url = await _sign_url("/api/task/submit", request_body=body)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(signed_url, headers=headers, json=body)
        r.raise_for_status()
        data = r.json()
    logger.debug(f"[submit] task/submit resp={data}")
    result_code = data.get("result", -1)
    if result_code != 1 or data.get("data") is None:
        err = data.get("error", {})
        msg = err.get("detail") or data.get("message") or str(data)
        logger.error(f"[submit] task/submit FAILED: result={result_code}, status={data.get('status')}, msg={msg}")
        raise RuntimeError(f"task/submit failed (result={result_code}, status={data.get('status')}): {msg}")
    task_id = str(data["data"]["task"]["id"])
    logger.info(f"[submit] 任务提交成功, task_id={task_id}")
    return task_id


async def poll_task(cookie: str, task_id: str, timeout: int = 600, interval: int = 10) -> dict:
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
        logger.debug(f"[poll] task={task_id}, status={status}, works_count={len(works)}")
        # works 可能在 status<50 时就有占位条目（resource为空），必须检查实际URL
        if works:
            w = works[0]
            resource = w.get("resource", {})
            video_url = resource.get("resource", "")
            if video_url:
                creative_id = str(w.get("creativeId", ""))
                logger.info(f"[poll] task={task_id} 完成, status={status}, creativeId={creative_id}, video_url={video_url[:80]}...")
                return {
                    "task_id": task_id,
                    "status": status,
                    "video_url": video_url,
                    "creative_id": creative_id,
                    "cover_url": w.get("cover", {}).get("resource", ""),
                    "width": resource.get("width", 0),
                    "height": resource.get("height", 0),
                    "duration": resource.get("duration", 0),
                }
            else:
                logger.debug(f"[poll] task={task_id} works存在但resource为空, status={status}, 继续轮询")
        if status >= 90:
            logger.error(f"[poll] task={task_id} FAILED: status={status}, data={d}")
            raise RuntimeError(f"task {task_id} failed with status {status}: {d.get('message', '')}")
    raise TimeoutError(f"task {task_id} timed out after {timeout}s")


def _build_lip_sync_task_body(
    video_url: str,
    audio_url: str,
    face_id_key: str,
    face_image_url: str,
    face_id: str = "0",
    from_work_id: Optional[int] = None,
    face_start_time: int = 0,
    face_end_time: int = 3000,
    audio_start_time_in_video: int = 0,
    audio_start_time: int = 0,
    audio_end_time: int = 3000,
    include_original_audio: bool = False,
    speech_volume: float = 1.0,
    original_audio_volume: float = 1.0,
    tts_text: str = "",
    tts_speed: str = "1",
    tts_timbre: str = "",
    tts_emotion: str = "",
    did: str = "",
) -> dict:
    face_id_list = {
        "face_id_key": face_id_key,
        "face_id_list": [face_id],
        "face_data": {
            face_id: {
                "id": face_id,
                "start_time": int(face_start_time),
                "end_time": int(face_end_time),
                "face_image": face_image_url,
            }
        },
    }
    face_id_choose = {
        "id": face_id,
        "audio_start_time_in_video": int(audio_start_time_in_video),
        "audio_start_time": int(audio_start_time),
        "audio_end_time": int(audio_end_time),
        "include_original_audio": bool(include_original_audio),
        "speech_volume": float(speech_volume),
        "original_audio_volume": float(original_audio_volume),
    }

    duration_seconds = max(1, int((int(audio_end_time) - int(audio_start_time) + 999) / 1000))
    arguments = [
        {"name": "biz", "value": "klingai"},
        {"name": "faceIdKey", "value": face_id_key},
        {"name": "faceIdList", "value": json.dumps(face_id_list, ensure_ascii=False, separators=(",", ":"))},
        {"name": "faceIdChoose", "value": json.dumps(face_id_choose, ensure_ascii=False, separators=(",", ":"))},
        {"name": "__ttsText", "value": tts_text or ""},
        {"name": "__ttsSpeed", "value": str(tts_speed)},
        {"name": "__ttsTimbre", "value": tts_timbre or ""},
        {"name": "__ttsEmotion", "value": tts_emotion or ""},
        {"name": "prefer_multi_shots", "value": "false"},
        {"name": "duration", "value": str(duration_seconds)},
        {"name": "__deviceType", "value": DEFAULT_UA},
        {"name": "__effect", "value": "m2v_video_lip_sync_v2"},
        {"name": "__locale", "value": "zh_CN"},
        {"name": "__platform", "value": "WEB"},
    ]
    if did:
        arguments.append({"name": "__did", "value": did})

    video_input = {"name": "video", "inputType": "URL", "url": video_url}
    if from_work_id is not None:
        video_input["fromWorkId"] = int(from_work_id)

    return {
        "type": "m2v_video_lip_sync",
        "arguments": arguments,
        "inputs": [
            video_input,
            {"name": "audio", "inputType": "URL", "url": audio_url},
        ],
        "callbackPayloads": [],
    }


async def lip_sync_tts(
    cookie: str,
    text: str,
    speaker_id: str,
    speed: str = "1",
    emotion: str = "",
) -> dict:
    """Call Kling lip-sync TTS endpoint and return audio url + duration(ms)."""
    body = {
        "text": text,
        "speakerId": speaker_id,
        "speed": str(speed),
        "emotion": emotion or "",
    }
    signed_url = await _sign_url("/api/lip/sync/tts", request_body=body)
    headers = {
        **_make_headers(),
        "Cookie": cookie,
        "Content-Type": "application/json",
        "origin": "https://app.klingai.com",
        "referer": "https://app.klingai.com/",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(signed_url, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()

    if data.get("result") != 1 or not data.get("data"):
        raise RuntimeError(f"lip sync tts failed: {data}")

    tts_data = data["data"]
    return {
        "audio_url": tts_data.get("resource", ""),
        "duration_ms": int(tts_data.get("duration", 0) or 0),
        "status": int(tts_data.get("status", 0) or 0),
        "raw": data,
    }


async def submit_lip_sync_task(
    cookie: str,
    video_url: str,
    audio_url: str,
    face_id_key: str,
    face_image_url: str,
    face_id: str = "0",
    from_work_id: Optional[int] = None,
    face_start_time: int = 0,
    face_end_time: int = 3000,
    audio_start_time_in_video: int = 0,
    audio_start_time: int = 0,
    audio_end_time: int = 3000,
    include_original_audio: bool = False,
    speech_volume: float = 1.0,
    original_audio_volume: float = 1.0,
    tts_text: str = "",
    tts_speed: str = "1",
    tts_timbre: str = "",
    tts_emotion: str = "",
) -> dict:
    """Submit Kling lip-sync task."""
    did = _cookie_value(cookie, "did", "")
    body = _build_lip_sync_task_body(
        video_url=video_url,
        audio_url=audio_url,
        face_id_key=face_id_key,
        face_image_url=face_image_url,
        face_id=face_id,
        from_work_id=from_work_id,
        face_start_time=face_start_time,
        face_end_time=face_end_time,
        audio_start_time_in_video=audio_start_time_in_video,
        audio_start_time=audio_start_time,
        audio_end_time=audio_end_time,
        include_original_audio=include_original_audio,
        speech_volume=speech_volume,
        original_audio_volume=original_audio_volume,
        tts_text=tts_text,
        tts_speed=tts_speed,
        tts_timbre=tts_timbre,
        tts_emotion=tts_emotion,
        did=did,
    )

    headers = {
        **_make_headers(),
        "Cookie": cookie,
        "Content-Type": "application/json",
        "origin": "https://klingai.com",
        "referer": "https://klingai.com/",
    }

    show_price = 0
    signed_price_url = await _sign_url("/api/task/price", request_body=body)
    async with httpx.AsyncClient(timeout=20) as client:
        try:
            price_resp = await client.post(signed_price_url, headers=headers, json=body)
            price_resp.raise_for_status()
            price_data = price_resp.json()
            show_price = int(price_data.get("data", {}).get("price", {}).get("payAmount", 0) or 0)
        except Exception as e:
            logger.warning(f"[lip_sync] task/price failed: {e}")

    if show_price:
        body["arguments"].append({"name": "showPrice", "value": show_price})

    signed_submit_url = await _sign_url("/api/task/submit", request_body=body)
    async with httpx.AsyncClient(timeout=30) as client:
        submit_resp = await client.post(signed_submit_url, headers=headers, json=body)
        submit_resp.raise_for_status()
        submit_data = submit_resp.json()

    if submit_data.get("result") != 1 or not submit_data.get("data"):
        err = submit_data.get("error", {})
        msg = err.get("detail") or submit_data.get("message") or str(submit_data)
        raise RuntimeError(f"lip sync submit failed: {msg}")

    task = submit_data["data"].get("task", {})
    return {
        "task_id": str(task.get("id", "")),
        "status": int(submit_data["data"].get("status", 0) or 0),
        "raw": submit_data,
    }


async def get_lip_sync_status(cookie: str, task_id: str) -> dict:
    """Get Kling lip-sync task status via personal feeds endpoint."""
    query = {
        "pageSize": "1",
        "contentType": "",
        "favored": "false",
        "taskId": str(task_id),
        "extra": "BASE_WORK",
    }
    signed_url = await _sign_url("/api/user/works/personal/feeds", query=query)
    headers = {
        **_make_headers(),
        "Cookie": cookie,
        "origin": "https://klingai.com",
        "referer": f"https://klingai.com/app/ai-human/video/{task_id}",
    }

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(signed_url, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    if data.get("result") != 1 or not data.get("data"):
        raise RuntimeError(f"lip sync status failed: {data}")

    history = data.get("data", {}).get("history") or []
    if not history:
        return {
            "task_id": str(task_id),
            "task_status": 0,
            "lip_sync_status": 0,
            "video_url": "",
            "cover_url": "",
            "done": False,
            "raw": data,
        }

    item = history[0]
    task = item.get("task") or {}
    works = item.get("works") or []
    work = works[0] if works else {}
    resource = work.get("resource") or {}
    cover = work.get("cover") or {}

    video_url = resource.get("resource", "") or ""
    task_status = int(task.get("status", 0) or 0)
    lip_sync_status = int(work.get("lipSyncStatus", 0) or 0)
    done = bool(video_url)
    failed = (task_status >= 90) and (not done)

    return {
        "task_id": str(task_id),
        "task_status": task_status,
        "lip_sync_status": lip_sync_status,
        "video_url": video_url,
        "cover_url": cover.get("resource", "") or "",
        "done": done,
        "failed": failed,
        "raw": data,
    }


async def poll_lip_sync_task(cookie: str, task_id: str, timeout: int = 600, interval: int = 5) -> dict:
    """Poll lip-sync task until completed (video_url exists), failed, or timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = await get_lip_sync_status(cookie, task_id)
        if status.get("done"):
            return status
        if status.get("failed"):
            raise RuntimeError(f"lip sync task {task_id} failed: {status}")
        await asyncio.sleep(interval)
    raise TimeoutError(f"lip sync task {task_id} timed out after {timeout}s")


async def download_creative(cookie: str, creative_id: str) -> str:
    """
    调用无水印下载接口，返回无水印视频URL。
    前提：账号已开启 user_remove_aigc_watermark 和 user_watermark_switch。
    """
    body = {
        "creatives": [{"creativeId": creative_id, "creativeType": "WORK"}],
        "fwm": False,
        "fileTypes": ["MP4"],
    }
    signed_url = await _sign_url("/api/creatives/download", request_body=body)
    headers = {**_make_headers(), "Cookie": cookie, "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(signed_url, headers=headers, json=body)
        r.raise_for_status()
        data = r.json()

    logger.info(f"[download] creativeId={creative_id} resp: {data}")

    # 解析响应：期望 data.data 中包含下载链接
    d = data.get("data")
    if not d:
        logger.warning(f"[download] creativeId={creative_id} 响应无data，原始: {data}")
        return ""

    # 可能的结构: data 是 url 字符串
    if isinstance(d, str):
        return d

    # 可能的结构: data 是 dict，包含 cdnUrl / url / downloadUrl / resource
    if isinstance(d, dict):
        for key in ("cdnUrl", "url", "downloadUrl", "resource", "download_url"):
            if d.get(key):
                return d[key]
        # 可能包含 creatives 列表
        creatives = d.get("creatives") or []
        if creatives and isinstance(creatives, list):
            c = creatives[0]
            for key in ("url", "downloadUrl", "resource", "download_url"):
                if c.get(key):
                    return c[key]

    # 可能的结构: data 是 list
    if isinstance(d, list) and d:
        item = d[0]
        if isinstance(item, str):
            return item
        if isinstance(item, dict):
            for key in ("url", "downloadUrl", "resource", "download_url"):
                if item.get(key):
                    return item[key]

    logger.warning(f"[download] creativeId={creative_id} 无法解析下载链接，data={d}")
    return ""


async def get_user_points(cookie: str) -> dict:
    """
    查询可灵账号积分，返回 {total, expireIn5DaysAmount}。
    利用 user/works/personal/feeds 接口（响应中附带 userPoints）。
    """
    signed_url = await _sign_url("/api/user/works/personal/feeds", {
        "pageSize": "1", "contentType": "", "favored": "false",
        "pageDirection": "NEXT", "extra": "BASE_WORK",
    })
    logger.info(f"[points] cookie长度={len(cookie)}, cookie前50={cookie[:50]}...")
    headers = {**_make_headers(), "Cookie": cookie}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(signed_url, headers=headers)
        logger.info(f"[points] HTTP {r.status_code}, resp_len={len(r.text)}")
        if r.status_code == 401:
            logger.error(f"[points] 401响应体: {r.text[:500]}")
            raise RuntimeError("cookie已过期或无效，请重新登录该账号")
        r.raise_for_status()
        data = r.json()
    logger.debug(f"[points] user/works/personal/feeds resp keys={list(data.get('data', {}).keys())}")
    points = data.get("data", {}).get("userPoints", {})
    return {
        "total": points.get("total", 0) / 100,
        "expireIn5DaysAmount": points.get("expireIn5DaysAmount", 0) / 100,
    }


async def init_remove_watermark(cookie: str):
    """
    首次登录后初始化去水印设置（两个开关都要打开）：
    1. GET  user_remove_aigc_watermark  查询 → POST 设置为 true
    2. POST user_watermark_switch       设置为 true
    """
    headers = {**_make_headers(), "Cookie": cookie}
    post_headers = {**headers, "Content-Type": "application/json"}
    body = {"value": "true"}

    # 开关1: user_remove_aigc_watermark（去除AI水印）
    path1 = "/api/user/extra-details/user_remove_aigc_watermark"
    try:
        signed_get = await _sign_url(path1)
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(signed_get, headers=headers)
        logger.info(f"[watermark] GET user_remove_aigc_watermark: {r.json()}")
    except Exception as e:
        logger.warning(f"[watermark] GET user_remove_aigc_watermark 失败: {e}")

    try:
        signed_post = await _sign_url(path1, request_body=body)
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(signed_post, headers=post_headers, json=body)
        logger.info(f"[watermark] POST user_remove_aigc_watermark=true: {r.json()}")
    except Exception as e:
        logger.warning(f"[watermark] POST user_remove_aigc_watermark 失败: {e}")

    # 开关2: user_watermark_switch（水印总开关）
    path2 = "/api/user/extra-details/user_watermark_switch"
    try:
        signed_post2 = await _sign_url(path2, request_body=body)
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(signed_post2, headers=post_headers, json=body)
        logger.info(f"[watermark] POST user_watermark_switch=true: {r.json()}")
    except Exception as e:
        logger.warning(f"[watermark] POST user_watermark_switch 失败: {e}")


# ============ Token 刷新 ============

def _parse_cookie_str(cookie_str: str) -> dict:
    """将 'k1=v1; k2=v2' 格式的 cookie 字符串解析为 dict"""
    result = {}
    for part in cookie_str.split(";"):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            result[k.strip()] = v.strip()
    return result


def _dict_to_cookie_str(d: dict) -> str:
    return "; ".join(f"{k}={v}" for k, v in d.items())


async def refresh_token(cookie_str: str) -> Optional[str]:
    """
    用 passToken 刷新 portal_st，返回新的 cookie 字符串。
    快手体系：POST /pass/kuaishou/login/passToken 携带旧 cookie，
    响应返回新的 st/at，Set-Cookie 返回新 passToken。
    失败返回 None。
    """
    cookies = _parse_cookie_str(cookie_str)
    pass_token = cookies.get("passToken", "")
    if not pass_token:
        logger.warning("[refresh_token] 无 passToken，无法刷新")
        return None

    try:
        kwfv1 = cookies.get("kwfv1", "")
        async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
            resp = await client.post(
                f"{ID_BASE}/pass/kuaishou/login/passToken",
                headers=_make_headers(kwfv1),
                cookies=cookies,
                data={
                    "sid": "kuaishou.ai.portal",
                    "channelType": "UNKNOWN",
                },
            )
            resp.raise_for_status()
            body = resp.json()

            # 从 Set-Cookie 更新 passToken 等
            for c in resp.cookies.jar:
                cookies[c.name] = c.value

            # 从 body 提取新的 portal 字段
            for field in ("kuaishou.ai.portal_st", "passToken",
                          "kuaishou.ai.portal.at", "userId", "ssecurity"):
                val = body.get(field, "")
                if val:
                    cookies[field] = val

            new_cookie = _dict_to_cookie_str(cookies)

            # 验证新 cookie 是否有效
            ok = await check_login(new_cookie)
            if ok:
                logger.info("[refresh_token] 刷新成功")
                return new_cookie
            else:
                logger.warning(f"[refresh_token] 刷新后验证失败, body={body}")
                return None
    except Exception as e:
        logger.error(f"[refresh_token] 刷新异常: {e}")
        return None


# ============ 账号状态监测 ============

_monitor_task: Optional[asyncio.Task] = None


def _next_refresh_retry_at(fail_count: int) -> int:
    # Exponential backoff avoids refresh loops that trigger risk-control.
    step = max(fail_count - 1, 0)
    delay = min(REFRESH_BACKOFF_BASE * (2 ** step), REFRESH_BACKOFF_MAX)
    return int(time.time()) + delay


async def _send_offline_alert_email(account_id: str, display_name: str, fail_count: int) -> None:
    if not KLING_ALERT_EMAIL:
        return
    subject = f"[Kling Monitor] 账号需重登: {display_name or account_id}"
    body = f"""
    <h3>可灵账号掉线告警</h3>
    <p><b>账号ID:</b> {account_id}</p>
    <p><b>显示名称:</b> {display_name or account_id}</p>
    <p><b>状态:</b> 连续刷新失败 {fail_count} 次，已自动暂停刷新，需扫码重登</p>
    <p><b>时间:</b> {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}</p>
    """
    try:
        ok = await asyncio.to_thread(send_email, KLING_ALERT_EMAIL, subject, body)
        if ok:
            logger.info(f"[kling_monitor] offline alert email sent: account={account_id}, to={KLING_ALERT_EMAIL}")
        else:
            logger.warning(f"[kling_monitor] offline alert email failed: account={account_id}, to={KLING_ALERT_EMAIL}")
    except Exception as e:
        logger.warning(f"[kling_monitor] offline alert email exception: account={account_id}, err={e}")


async def _monitor_loop(interval: int = DEFAULT_MONITOR_INTERVAL):
    import logging
    logger = logging.getLogger("kling_monitor")
    while True:
        try:
            accounts = list_kling_accounts()
            now_ts = int(time.time())
            for acc in accounts:
                aid = acc["account_id"]
                creds = get_kling_credentials(aid)
                if not creds:
                    continue
                cookie = creds.get("cookie", "")
                if not cookie:
                    continue

                ok = await check_login(cookie)
                if ok:
                    update_kling_account(
                        aid,
                        is_logged_in=True,
                        refresh_fail_count=0,
                        refresh_paused=False,
                        needs_relogin=False,
                        next_refresh_retry_at=0,
                        monitor_message="",
                        offline_alert_sent=False,
                    )
                    logger.info(f"[kling_monitor] {aid} isLogin=True")
                    await asyncio.sleep(5)
                    continue

                refresh_paused = bool(acc.get("refresh_paused", False))
                refresh_fail_count = int(acc.get("refresh_fail_count", 0) or 0)
                next_retry_at = int(acc.get("next_refresh_retry_at", 0) or 0)
                offline_alert_sent = bool(acc.get("offline_alert_sent", False))

                # Paused mode: keep only low-frequency check_login and do not refresh token.
                if refresh_paused:
                    update_kling_account(
                        aid,
                        is_logged_in=False,
                        needs_relogin=True,
                        monitor_message="Please scan QR to re-login (auto refresh paused)",
                    )
                    logger.warning(f"[kling_monitor] {aid} refresh paused, waiting for re-login")
                    await asyncio.sleep(5)
                    continue

                # Backoff window: skip token refresh attempts to avoid risk-control loops.
                if next_retry_at > now_ts:
                    wait_sec = next_retry_at - now_ts
                    update_kling_account(
                        aid,
                        is_logged_in=False,
                        monitor_message=f"Login invalid, retry refresh in {wait_sec}s",
                    )
                    logger.info(f"[kling_monitor] {aid} in refresh backoff, wait={wait_sec}s")
                    await asyncio.sleep(5)
                    continue

                logger.info(f"[kling_monitor] {aid} cookie invalid, trying refresh_token")
                new_cookie = await refresh_token(cookie)
                if new_cookie:
                    save_kling_credentials(aid, new_cookie, creds.get("did", ""))
                    update_kling_account(
                        aid,
                        is_logged_in=True,
                        refresh_fail_count=0,
                        refresh_paused=False,
                        needs_relogin=False,
                        next_refresh_retry_at=0,
                        monitor_message="",
                        offline_alert_sent=False,
                    )
                    logger.info(f"[kling_monitor] {aid} token refresh success")
                else:
                    fail_count = refresh_fail_count + 1
                    if fail_count >= REFRESH_MAX_FAILS:
                        update_kling_account(
                            aid,
                            is_logged_in=False,
                            refresh_fail_count=fail_count,
                            refresh_paused=True,
                            needs_relogin=True,
                            next_refresh_retry_at=0,
                            monitor_message=(
                                f"Refresh failed {fail_count} times; auto refresh paused. "
                                "Please scan QR to re-login"
                            ),
                            offline_alert_sent=True,
                        )
                        logger.warning(
                            f"[kling_monitor] {aid} refresh failed {fail_count} times, pause auto refresh"
                        )
                        if not offline_alert_sent:
                            await _send_offline_alert_email(
                                account_id=aid,
                                display_name=str(acc.get("display_name", "") or aid),
                                fail_count=fail_count,
                            )
                    else:
                        retry_at = _next_refresh_retry_at(fail_count)
                        wait_sec = max(retry_at - int(time.time()), 0)
                        update_kling_account(
                            aid,
                            is_logged_in=False,
                            refresh_fail_count=fail_count,
                            refresh_paused=False,
                            needs_relogin=False,
                            next_refresh_retry_at=retry_at,
                            monitor_message=(
                                f"token refresh failed ({fail_count}/{REFRESH_MAX_FAILS}), "
                                f"auto retry in {wait_sec}s"
                            ),
                            offline_alert_sent=False,
                        )
                        logger.warning(
                            f"[kling_monitor] {aid} refresh failed ({fail_count}/{REFRESH_MAX_FAILS}), "
                            f"retry in {wait_sec}s"
                        )

                await asyncio.sleep(5)
        except Exception as e:
            logger.warning(f"[kling_monitor] monitor error: {e}")
        await asyncio.sleep(interval)


def start_monitor(interval: int = DEFAULT_MONITOR_INTERVAL):
    """在当前 event loop 中启动监测后台任务（只启动一次）"""
    global _monitor_task
    if _monitor_task is None or _monitor_task.done():
        _monitor_task = asyncio.create_task(_monitor_loop(interval))


def stop_monitor():
    global _monitor_task
    if _monitor_task and not _monitor_task.done():
        _monitor_task.cancel()
        _monitor_task = None
