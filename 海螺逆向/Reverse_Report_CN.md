# 海螺AI (hailuoai.com) — `yy` 签名头逆向报告

> 版本: prod-zh-0.1.620
> 目标文件: `6296-6dfacab77079e9db.js`
> 分析日期: 2026-03-22

---

## 1. 目标

还原所有 API 请求中 `yy` 请求头（HTTP Header）的生成逻辑，以便在 Node.js 环境中自主构造合法请求。

---

## 2. 分析路径

1. 抓取 `https://hailuoai.com/create/image-to-video` 页面，提取所有 JS Bundle URL（共 67 个）。
2. 批量下载 JS 文件，搜索 `interceptors.request.use`，定位 axios 拦截器。
3. 在 `6296-6dfacab77079e9db.js` 找到请求拦截器，发现 `e.headers.yy = u`，`u` 来自函数 `_`。
4. 追踪 `_` 函数的完整实现，以及依赖模块 `62001`（公共参数）和 `99766`（MD5）。

---

## 3. 原始代码片段

### 3.1 拦截器核心（6296-6dfacab77079e9db.js）

```js
// axios 请求拦截器
F.interceptors.request.use(e => {
    e.headers.token = f.KO();                          // 认证 token
    let i = Date.parse(new Date().toString()),          // 当前时间戳(ms)
        l = E.mC(i);                                   // 公共参数对象
    e.params = Object.assign({}, e.params, l);
    let d = E.wQ(e.url ?? "", e.params);               // URL+参数拼接
    let { encrypt: u, bodyString: s } = _({            // 调用签名函数
        time: i,
        body: e.data,
        hasSearchParamsPath: d,
        method: e.method,
        bodyToYY: e.headers?.yy ?? null,
    });
    e.headers.yy = u;   // 赋值 yy 头
    e.data = s;
    e.url  = d;
    e.params = {};
    return e;
});
```

### 3.2 签名函数 `_`

```js
let _ = e => {
    let { hasSearchParamsPath: t, bodyToYY: o, method: n, time: r, body: a } = e;
    let i = {};
    if (n && (n.toLowerCase() === 'post' || n.toLowerCase() === 'delete')) {
        i = a || {};
    }
    let l = i = JSON.stringify(i);  // bodyString
    if (o) i = o;                   // bodyForYY override
    let d = encodeURIComponent(t)   // encodeURIComponent(fullURL)
          + '_'
          + i                       // bodyForYY
          + b()(r?.toString())      // MD5(timestamp)
          + 'ooui';
    return { encrypt: b()(d), bodyString: l };  // { yy: MD5(raw), bodyString }
};
```

> `b` = MD5 函数（来自模块 99766，即 `blueimp-md5`）。

### 3.3 公共参数构造（模块 62001, 函数 mC）

```js
// app 常量 (模块 99273)
app_id       = '3001'
version_code = '22203'
biz_id       = '0'

// mC(unixMs) 返回的公共参数对象
{
  device_platform: 'web',
  app_id:          '3001',
  version_code:    '22203',
  biz_id:          '0',
  unix:            <timestamp_ms>,
  lang:            'zh-Hans',       // 或 'en'
  uuid:            <localStorage uuid>,
  device_id:       <localStorage device_id>,
  os_name:         'Windows',
  browser_name:    'chrome',
  device_memory:   8,
  cpu_core_num:    24,
  browser_language:'zh-CN',
  browser_platform:'Win32',
  screen_width:    1920,
  screen_height:   1080,
}
```

### 3.4 URL 拼接（函数 wQ）

```js
// wQ(url, params) — 把公共参数作为 query string 附到 URL
(url, params) => {
    const qs = new URLSearchParams(params).toString();
    return url.includes('?') ? `${url}&${qs}` : `${url}?${qs}`;
}
```

---

## 4. 完整算法（伪代码）

```
输入: url, method, body(可选), timestamp(ms), publicParams

1. bodyString = (method 是 POST/DELETE) ? JSON.stringify(body||{}) : '{}'
2. bodyForYY  = headers.yy 存在 ? headers.yy : bodyString
3. fullURL    = url + '?' + URLSearchParams(publicParams).toString()
4. inner      = MD5( String(timestamp) )
5. raw        = encodeURIComponent(fullURL) + '_' + bodyForYY + inner + 'ooui'
6. yy         = MD5( raw )
```

---

## 5. 关键参数说明

| 参数 | 来源 | 说明 |
|------|------|------|
| `unix` | `Date.now()` | 请求时刻毫秒时间戳，需与服务器时间接近 |
| `uuid` | localStorage | 首次访问自动生成，建议固定 |
| `device_id` | localStorage | 设备ID，固定值即可 |
| `token` | 登录后返回 | JWT/Bearer，用于身份认证，独立于 yy |
| `yy` | 本算法生成 | 请求完整性校验，无需账号即可构造 |

---

## 6. 实现文件

- [example.js](./example.js) — 完整 Node.js 实现，无任何外部依赖（仅使用内置 `crypto`）

---

## 7. 置信度

**HIGH**