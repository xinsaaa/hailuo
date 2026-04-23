from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs

from testnewpay import create_payment


HTML_PAGE = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>支付测试</title>
  <style>
    :root {
      --bg: #f5f7fb;
      --card: #ffffff;
      --text: #1f2937;
      --muted: #6b7280;
      --line: #dbe3ef;
      --primary: #1677ff;
      --primary-2: #0f5fd6;
      --green: #14b86a;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      background:
        radial-gradient(circle at top left, #dfeaff 0, transparent 35%),
        radial-gradient(circle at bottom right, #dff7ea 0, transparent 30%),
        var(--bg);
      color: var(--text);
      min-height: 100vh;
      display: grid;
      place-items: center;
      padding: 24px;
    }
    .card {
      width: 100%;
      max-width: 560px;
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 20px;
      box-shadow: 0 18px 50px rgba(20, 36, 62, 0.08);
      padding: 28px;
    }
    h1 {
      margin: 0 0 8px;
      font-size: 28px;
    }
    p {
      margin: 0 0 20px;
      color: var(--muted);
      line-height: 1.6;
    }
    label {
      display: block;
      margin: 14px 0 8px;
      font-size: 14px;
      font-weight: 600;
    }
    input, select {
      width: 100%;
      padding: 12px 14px;
      border: 1px solid var(--line);
      border-radius: 12px;
      font-size: 15px;
      outline: none;
      background: #fff;
    }
    input:focus, select:focus {
      border-color: var(--primary);
      box-shadow: 0 0 0 4px rgba(22, 119, 255, 0.12);
    }
    .row {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 14px;
    }
    .actions {
      display: flex;
      gap: 12px;
      margin-top: 22px;
      flex-wrap: wrap;
    }
    button {
      border: 0;
      border-radius: 12px;
      padding: 12px 18px;
      font-size: 15px;
      font-weight: 700;
      cursor: pointer;
      transition: transform 0.12s ease;
    }
    button:hover { transform: translateY(-1px); }
    .primary {
      background: var(--primary);
      color: white;
    }
    .wechat {
      background: var(--green);
      color: white;
    }
    .hint {
      margin-top: 16px;
      font-size: 13px;
      color: var(--muted);
    }
    @media (max-width: 640px) {
      .row {
        grid-template-columns: 1fr;
      }
      .card {
        padding: 20px;
        border-radius: 16px;
      }
    }
  </style>
</head>
<body>
  <div class="card">
    <h1>支付测试页</h1>
    <p>点击按钮后，由本地服务端生成签名并创建订单，然后直接跳转到平台收银台。</p>
    <form method="post" action="/create-order">
      <div class="row">
        <div>
          <label for="money">金额</label>
          <input id="money" name="money" value="1.00" required>
        </div>
        <div>
          <label for="pay_type">支付方式</label>
          <select id="pay_type" name="pay_type">
            <option value="wxpay">微信支付</option>
            <option value="alipay">支付宝</option>
          </select>
        </div>
      </div>

      <label for="name">商品名称</label>
      <input id="name" name="name" value="VIP会员测试" required>

      <label for="param">扩展参数</label>
      <input id="param" name="param" value="">

      <div class="actions">
        <button class="wechat" type="submit" onclick="document.getElementById('pay_type').value='wxpay'">微信下单</button>
        <button class="primary" type="submit" onclick="document.getElementById('pay_type').value='alipay'">支付宝下单</button>
      </div>
    </form>
    <div class="hint">如果点击后没有回调，请把回调地址换成你真实可访问的域名。</div>
  </div>
</body>
</html>
"""


class PaymentTestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/":
            self.send_error(404, "Not Found")
            return

        body = HTML_PAGE.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/create-order":
            self.send_error(404, "Not Found")
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length).decode("utf-8")
        form = parse_qs(raw_body)

        pay_type = form.get("pay_type", ["wxpay"])[0]
        money = form.get("money", ["1.00"])[0]
        name = form.get("name", ["VIP会员测试"])[0]
        param = form.get("param", [""])[0]

        if pay_type not in {"wxpay", "alipay"}:
            self.send_error(400, "Unsupported pay_type")
            return

        try:
            result = create_payment(pay_type=pay_type, money=money, name=name, param=param)
        except Exception as exc:
            self.send_response(500)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(f"创建订单失败: {exc}".encode("utf-8"))
            return

        cashier_url = result["cashier_url"]
        if not cashier_url:
            self.send_response(500)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(f"未解析到收银台地址:\n{result['response_text']}".encode("utf-8"))
            return

        self.send_response(302)
        self.send_header("Location", cashier_url)
        self.end_headers()


def main():
    host = "127.0.0.1"
    port = 8787
    server = HTTPServer((host, port), PaymentTestHandler)
    print(f"支付测试页已启动: http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
