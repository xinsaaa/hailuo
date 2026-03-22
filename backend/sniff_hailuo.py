"""
抓包脚本：拦截海螺AI所有API请求，打印请求和响应
用法: python backend/sniff_hailuo.py
运行后在打开的浏览器里手动操作，控制台会打印所有API请求
"""
import asyncio
import json
from playwright.async_api import async_playwright

# 只过滤 /api/ 路径，跳过静态资源
SKIP_EXT = (".js", ".css", ".png", ".jpg", ".webp", ".ico", ".woff", ".svg", ".gif")


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        async def on_request(request):
            url = request.url
            if "hailuoai.com" not in url:
                return
            if any(url.endswith(ext) for ext in SKIP_EXT):
                return
            if "/api/" not in url and "/v1/" not in url and "/v2/" not in url:
                return
            print(f"\n{'='*60}")
            print(f"[请求] {request.method} {url}")
            try:
                body = request.post_data
                if body:
                    try:
                        parsed = json.loads(body)
                        print(f"[请求体]\n{json.dumps(parsed, ensure_ascii=False, indent=2)}")
                    except Exception:
                        print(f"[请求体(multipart/raw)] {body[:300]}")
            except Exception as e:
                print(f"[请求体读取失败] {e}")

        async def on_response(response):
            url = response.url
            if "hailuoai.com" not in url:
                return
            if any(url.endswith(ext) for ext in SKIP_EXT):
                return
            if "/api/" not in url and "/v1/" not in url and "/v2/" not in url:
                return
            try:
                data = await response.json()
                print(f"[响应 {response.status}]\n{json.dumps(data, ensure_ascii=False, indent=2)}")
            except Exception:
                pass

        page.on("request", on_request)
        page.on("response", on_response)

        await page.goto("https://hailuoai.com")
        print("浏览器已打开，请手动登录并操作")
        print("按 Ctrl+C 退出")

        try:
            await asyncio.sleep(600)
        except KeyboardInterrupt:
            pass

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
