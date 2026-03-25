/**
 * 海螺AI (hailuoai.com) - yy 请求头签名生成
 * 逆向来源: prod-zh-0.1.620
 * 文件: 6296-6dfacab77079e9db.js
 *
 * 签名算法:
 *   step1: bodyStr  = POST/DELETE时 JSON.stringify(body), 否则 '{}'
 *   step2: bodyForYY = headers.yy 存在时使用它, 否则用 bodyStr
 *   step3: urlWithParams = encodeURIComponent(url + '?' + publicParams)
 *   step4: inner = MD5(timestamp.toString())
 *   step5: raw = urlWithParams + '_' + bodyForYY + inner + 'ooui'
 *   step6: yy = MD5(raw)
 *
 * 公共参数 (public params) 附加到每个请求的 query string:
 *   device_platform, app_id, version_code, biz_id, unix,
 *   lang, uuid, device_id, os_name, browser_name,
 *   device_memory, cpu_core_num, browser_language,
 *   browser_platform, screen_width, screen_height
 */

const crypto = require('crypto');

function md5(str) {
    return crypto.createHash('md5').update(str).digest('hex');
}

/**
 * 构造公共参数对象 (对应 JS 里的 mC 函数)
 */
function buildPublicParams(unixMs, options = {}) {
    const {
        uuid = '',
        device_id = '',
        lang = 'zh-Hans',
        os_name = 'Windows',
        browser_name = 'chrome',
        device_memory = 8,
        cpu_core_num = 24,
        browser_language = 'zh-CN',
        browser_platform = 'Win32',
        screen_width = 1920,
        screen_height = 1080,
    } = options;

    const params = {
        device_platform: 'web',
        app_id: '3001',
        version_code: '22203',
        biz_id: '0',
        unix: unixMs,
        lang,
    };
    if (uuid)            params.uuid = uuid;
    if (device_id)       params.device_id = device_id;
    params.os_name          = os_name;
    params.browser_name     = browser_name;
    params.device_memory    = device_memory;
    params.cpu_core_num     = cpu_core_num;
    params.browser_language = browser_language;
    params.browser_platform = browser_platform;
    params.screen_width     = screen_width;
    params.screen_height    = screen_height;
    return params;
}

/**
 * 将公共参数拼接到 URL (对应 JS 里的 wQ 函数)
 */
function appendParamsToUrl(url, params) {
    const qs = new URLSearchParams(
        Object.entries(params).map(([k, v]) => [k, String(v)])
    ).toString();
    return url.includes('?') ? `${url}&${qs}` : `${url}?${qs}`;
}

/**
 * 生成 yy 签名头 (对应 JS 里的 _ 函数)
 *
 * @param {object} opts
 * @param {string}  opts.url        - API path, e.g. '/v1/api/billing/credit'
 * @param {string}  opts.method     - HTTP method, e.g. 'get' | 'post'
 * @param {any}     opts.body       - Request body (object or null)
 * @param {number}  opts.time       - Unix timestamp in milliseconds
 * @param {object}  opts.publicParams - Output of buildPublicParams()
 * @param {string|null} [opts.bodyToYY] - Override body for yy calc (rare)
 * @returns {{ yy: string, bodyString: string, fullUrl: string }}
 */
function generateYY(opts) {
    const { url, method, body, time, publicParams, bodyToYY = null } = opts;

    // step1: build body string
    let bodyObj = {};
    const m = (method || 'get').toLowerCase();
    if (m === 'post' || m === 'delete') {
        bodyObj = body || {};
    }
    const bodyString = JSON.stringify(bodyObj);

    // step2: body used for yy
    const bodyForYY = bodyToYY !== null ? bodyToYY : bodyString;

    // step3: full URL with public params
    const fullUrl = appendParamsToUrl(url, publicParams);

    // step4: inner hash
    const inner = md5(String(time));

    // step5+6: final yy
    const raw = encodeURIComponent(fullUrl) + '_' + bodyForYY + inner + 'ooui';
    const yy = md5(raw);

    return { yy, bodyString, fullUrl };
}

// ─── Demo ────────────────────────────────────────────────────────────────────

const time  = Date.now();
const uuid  = '91e58793-9f30-4d52-899c-34a6ae4a2278';
const devId = '464835835103178752';

const publicParams = buildPublicParams(time, { uuid, device_id: devId });

const { yy, fullUrl } = generateYY({
    url: '/v1/api/billing/credit',
    method: 'get',
    body: null,
    time,
    publicParams,
});

console.log('Full URL :', fullUrl);
console.log('yy header:', yy);

// Usage with node-fetch / axios:
// headers: { yy, token: '<your-auth-token>' }
