"""
海螺AI HTTP API 客户端
纯接口调用，无需 Playwright 浏览器自动化

签名算法 yy:
  pub_params -> query_string -> fullPath
  inner = md5(str(unix_ms))
  raw   = quote(fullPath) + '_' + body_str + inner + 'ooui'
  yy    = md5(raw)
"""
import base64
import hashlib
import hmac
import json
import os
import re
import time
import uuid as _uuid
from email.utils import formatdate
from typing import Optional
from urllib.parse import urlencode, quote

import httpx

# ============ 常量 ============

BASE_URL = "https://hailuoai.com"
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/136.0.0.0 Safari/537.36"
)

# ============ 签名工具 ============

def _md5(s: str) -> str:
    return hashlib.md5(s.encode()).hexdigest()


def _build_public_params(unix_ms: int, uuid: str, device_id: str) -> dict:
    return {
        "device_platform": "web",
        "app_id":          "3001",
        "version_code":    "22203",
        "biz_id":          "0",
        "unix":            str(unix_ms),
        "lang":            "zh-Hans",
        "uuid":            uuid,
        "device_id":       device_id,
        "os_name":         "Windows",
        "browser_name":    "chrome",
        "device_memory":   "8",
        "cpu_core_num":    "24",
        "browser_language": "zh-CN",
        "browser_platform": "Win32",
        "screen_width":    "1920",
        "screen_height":   "1080",
    }


def _generate_yy(url_path: str, body_str: str, unix_ms: int, uuid: str, device_id: str):
    """生成请求签名 yy，返回 (yy, full_path_with_qs)"""
    pub = _build_public_params(unix_ms, uuid, device_id)
    qs = urlencode(pub)
    full_path = url_path + "?" + qs
    inner = _md5(str(unix_ms))
    raw = quote(full_path, safe="") + "_" + body_str + inner + "ooui"
    yy = _md5(raw)
    return yy, full_path


def verify_signature() -> bool:
    """验证签名算法与抓包一致"""
    UNIX = 1774152401000
    UUID = "91e58793-9f30-4d52-899c-34a6ae4a2278"
    DEVICE_ID = "464835835103178752"
    body = json.dumps({
        "quantity": 1,
        "parameter": {
            "modelID": "23204",
            "desc": "原神",
            "fileList": [],
            "useOriginPrompt": False,
            "resolution": "768",
            "duration": 6,
            "aspectRatio": "",
        },
        "videoExtra": {
            "promptStruct": '{"value":[{"type":"paragraph","children":[{"text":"\u539f\u795e"}]}],"length":2,"plainLength":2,"rawLength":2}'
        },
        "projectID": "0",
    }, ensure_ascii=False, separators=(',', ':'))
    yy, _ = _generate_yy("/v2/api/multimodal/generate/video", body, UNIX, UUID, DEVICE_ID)
    expected = "f083fff6e011bfee00c50deadcd46c7a"
    if yy == expected:
        print("[HailuoAPI] OK 签名算法验证通过")
        return True
    else:
        print(f"[HailuoAPI] FAIL 签名算法验证失败: got={yy} expected={expected}")
        return False


# ============ 工具函数 ============

def _extract_jwt(cookie: str) -> str:
    """从 Cookie 字符串中提取 _token JWT"""
    m = re.search(r'_token=([^;\s]+)', cookie)
    return m.group(1) if m else cookie


def _build_prompt_struct(text: str) -> str:
    struct = {
        "value": [{"type": "paragraph", "children": [{"text": text}]}],
        "length": len(text),
        "plainLength": len(text),
        "rawLength": len(text),
    }
    return json.dumps(struct, ensure_ascii=False)


# ============ 主客户端 ============

class HailuoApiClient:
    """
    单账号海螺 API 客户端
    cookie   : 完整 Cookie 字符串（含 _token=...）
    uuid     : 账号的 localStorage uuid
    device_id: 账号的 localStorage device_id
    """

    def __init__(self, cookie: str, uuid: str, device_id: str):
        self.cookie = cookie
        self.uuid = uuid
        self.device_id = device_id
        self.jwt = _extract_jwt(cookie)
        self._client = httpx.AsyncClient(
            base_url=BASE_URL,
            timeout=30.0,
            follow_redirects=True,
        )

    def _common_headers(self) -> dict:
        return {
            "User-Agent":   DEFAULT_UA,
            "Cookie":       self.cookie,
            "token":        self.jwt,
            "Content-Type": "application/json",
            "Origin":       "https://hailuoai.com",
            "Referer":      "https://hailuoai.com/create/image-to-video",
        }

    async def _post(self, url_path: str, body: dict) -> dict:
        unix_ms = int(time.time() * 1000)
        body_str = json.dumps(body, ensure_ascii=False, separators=(',', ':'))
        yy, full_path = _generate_yy(url_path, body_str, unix_ms, self.uuid, self.device_id)
        headers = self._common_headers()
        headers["yy"] = yy
        resp = await self._client.post(
            full_path,
            content=body_str.encode("utf-8"),
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json()

    async def _get(self, url_path: str) -> dict:
        unix_ms = int(time.time() * 1000)
        yy, full_path = _generate_yy(url_path, "", unix_ms, self.uuid, self.device_id)
        headers = self._common_headers()
        headers["yy"] = yy
        resp = await self._client.get(full_path, headers=headers)
        resp.raise_for_status()
        return resp.json()

    # ---------- 公开接口 ----------

    async def get_credits(self) -> Optional[int]:
        """查询贝壳积分余额，返回积分数值，失败返回 None"""
        try:
            resp = await self._get("/v1/api/billing/credit")
            # 响应格式: {"code":0,"data":{"amount":12345,...}}
            data = resp.get("data") or {}
            return data.get("amount")
        except Exception as e:
            print(f"[HailuoAPI] get_credits 失败: {e}")
            return None

    async def generate_video(
        self,
        desc: str,
        model_id: str = "23204",
        duration: int = 6,
        resolution: str = "768",
        aspect_ratio: str = "",
        file_list: Optional[list] = None,
        quantity: int = 1,
    ) -> dict:
        """
        提交视频生成任务
        返回原始响应，成功时 data.tasks 含 [{taskID, ...}, ...]
        """
        if file_list is None:
            file_list = []
        body = {
            "quantity": quantity,
            "parameter": {
                "modelID":        model_id,
                "desc":           desc,
                "fileList":       file_list,
                "useOriginPrompt": False,
                "resolution":     resolution,
                "duration":       duration,
                "aspectRatio":    aspect_ratio,
            },
            "videoExtra": {
                "promptStruct": _build_prompt_struct(desc),
            },
            "projectID": "0",
        }
        return await self._post("/v2/api/multimodal/generate/video", body)

    async def get_processing_tasks(self) -> dict:
        """查询生成中的任务列表"""
        return await self._post("/api/feed/creation/my/processing", {})

    async def get_tasks_by_ids(self, task_ids: list) -> dict:
        """按 taskID 批量查询视频状态"""
        body = {"ids": task_ids}
        return await self._post("/api/feed/creation/my/batch", body)

    async def upload_image(self, image_path: str) -> Optional[dict]:
        """
        上传图片用于首帧/尾帧，返回 {id, url, type}；失败返回 None
        三步流程：
          1. GET /v1/api/files/request_policy  → OSS STS 凭证
          2. PUT 直传到阿里云 OSS（HMAC-SHA1 签名）
          3. POST /v1/api/files/policy_callback → 获取 fileID
        """
        try:
            # Step 1: 获取 OSS STS 凭证
            policy_resp = await self._get("/v1/api/files/request_policy")
            status_code = (policy_resp.get("statusInfo") or {}).get("code", -1)
            if status_code != 0:
                print(f"[HailuoAPI] request_policy 失败: {policy_resp}")
                return None
            d = policy_resp.get("data") or {}
            access_key_id     = d["accessKeyId"]
            access_key_secret = d["accessKeySecret"]
            security_token    = d["securityToken"]
            oss_dir           = d["dir"].rstrip("/")   # e.g. "user/xxx/video"
            endpoint          = d["endpoint"]           # e.g. "oss-cn-wulanchabu.aliyuncs.com"
            bucket_name       = d["bucketName"]

            # Step 2: PUT 直传到 OSS（STS HMAC-SHA1 签名）
            ext = os.path.splitext(image_path)[1].lstrip(".").lower() or "jpg"
            mime = "image/png" if ext == "png" else "image/jpeg"
            new_filename = f"{_uuid.uuid4()}.{ext}"
            oss_key      = f"{oss_dir}/{new_filename}"

            with open(image_path, "rb") as f:
                file_data = f.read()
            file_size = len(file_data)

            date_str = formatdate(usegmt=True)
            # CanonicalizedOSSHeaders 必须排序
            oss_header_key = "x-oss-security-token"
            canonicalized_oss_headers = f"{oss_header_key}:{security_token}\n"
            canonicalized_resource    = f"/{bucket_name}/{oss_key}"
            string_to_sign = (
                f"PUT\n\n{mime}\n{date_str}\n"
                f"{canonicalized_oss_headers}"
                f"{canonicalized_resource}"
            )
            signature = base64.b64encode(
                hmac.new(
                    access_key_secret.encode(),
                    string_to_sign.encode(),
                    hashlib.sha1,
                ).digest()
            ).decode()

            oss_url = f"https://{bucket_name}.{endpoint}/{oss_key}"
            put_headers = {
                "Content-Type":         mime,
                "Date":                 date_str,
                "x-oss-security-token": security_token,
                "Authorization":        f"OSS {access_key_id}:{signature}",
            }
            async with httpx.AsyncClient(timeout=60.0) as oss_client:
                oss_resp = await oss_client.put(oss_url, content=file_data, headers=put_headers)
            if oss_resp.status_code not in (200, 204):
                print(f"[HailuoAPI] OSS上传失败: {oss_resp.status_code} {oss_resp.text[:200]}")
                return None

            # Step 3: policy_callback 通知海螺，获取 fileID
            cb_body = {
                "fileName":       new_filename,
                "originFileName": os.path.basename(image_path),
                "dir":            d["dir"],
                "endpoint":       endpoint,
                "bucketName":     bucket_name,
                "size":           str(file_size),
                "mimeType":       mime,
                "fileScene":      10,
            }
            cb_resp = await self._post("/v1/api/files/policy_callback", cb_body)
            cb_status = (cb_resp.get("statusInfo") or {}).get("code", -1)
            if cb_status != 0:
                print(f"[HailuoAPI] policy_callback 失败: {cb_resp}")
                return None

            cb_data  = cb_resp.get("data") or {}
            file_id  = cb_data.get("fileID") or cb_data.get("id", "")
            file_url = cb_data.get("ossPath") or cb_data.get("url") or oss_url
            return {"id": file_id, "url": file_url, "type": ext}

        except Exception as e:
            print(f"[HailuoAPI] upload_image 失败: {e}")
            return None

    async def close(self):
        await self._client.aclose()


# ============ 登录接口 ============

async def send_sms_code(phone: str, uuid: str, device_id: str) -> dict:
    """
    Step 1: 发送短信验证码
    POST /v1/api/user/login/sms/send
    成功时 statusInfo.code == 0
    """
    url_path = "/v1/api/user/login/sms/send"
    body = {"phone": phone}
    body_str = json.dumps(body, ensure_ascii=False, separators=(',', ':'))
    unix_ms = int(time.time() * 1000)
    yy, full_path = _generate_yy(url_path, body_str, unix_ms, uuid, device_id)
    headers = {
        "User-Agent":   DEFAULT_UA,
        "Content-Type": "application/json",
        "yy":           yy,
    }
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        resp = await client.post(full_path, content=body_str.encode(), headers=headers)
        resp.raise_for_status()
        return resp.json()


async def login_with_sms(phone: str, code: str, uuid: str, device_id: str) -> dict:
    """
    Step 2: 短信验证码登录
    POST /v1/api/user/login/phone
    成功时返回 data.token / data.deviceID / data.realUserID
    返回 {"json": ..., "cookies": "cookie字符串"}
    """
    url_path = "/v1/api/user/login/phone"
    body = {"phone": phone, "code": code, "loginType": ""}
    body_str = json.dumps(body, ensure_ascii=False, separators=(',', ':'))
    unix_ms = int(time.time() * 1000)
    yy, full_path = _generate_yy(url_path, body_str, unix_ms, uuid, device_id)
    headers = {
        "User-Agent":   DEFAULT_UA,
        "Content-Type": "application/json",
        "yy":           yy,
    }
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        resp = await client.post(full_path, content=body_str.encode(), headers=headers)
        resp.raise_for_status()
        # 收集 Set-Cookie
        cookie_parts = [f"{k}={v}" for k, v in resp.cookies.items()]
        return {"json": resp.json(), "cookies": "; ".join(cookie_parts)}


# ============ 快捷函数（供 worker 用）============

def load_account_client(account_cfg: dict) -> HailuoApiClient:
    """
    从账号配置 dict 构建客户端
    配置字段: cookie, uuid, device_id
    """
    return HailuoApiClient(
        cookie=account_cfg["cookie"],
        uuid=account_cfg["uuid"],
        device_id=account_cfg["device_id"],
    )


if __name__ == "__main__":
    verify_signature()
