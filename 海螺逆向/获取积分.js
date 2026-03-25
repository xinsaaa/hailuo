/**
 * 海螺AI API 测试脚本
 * 填入 token / uuid / device_id 后直接 node 获取积分.js
 */

const https   = require('https');
const crypto  = require('crypto');

// ─── 在此填入你的信息 ──────────────────────────────────────────
const TOKEN     = 'sensorsdata2015jssdkchannel=%7B%22prop%22%3A%7B%22_sa_channel_landing_url%22%3A%22%22%7D%7D; sensorsdata2015jssdkcross=%7B%22distinct_id%22%3A%227PO57LZPjOpK%22%2C%22first_id%22%3A%2219b920957a8aca-0d6492ed8756e1-26061a51-1338645-19b920957a92656%22%2C%22props%22%3A%7B%22%24latest_traffic_source_type%22%3A%22%E7%9B%B4%E6%8E%A5%E6%B5%81%E9%87%8F%22%2C%22%24latest_search_keyword%22%3A%22%E6%9C%AA%E5%8F%96%E5%88%B0%E5%80%BC_%E7%9B%B4%E6%8E%A5%E6%89%93%E5%BC%80%22%2C%22%24latest_referrer%22%3A%22%22%7D%2C%22identities%22%3A%22eyIkaWRlbnRpdHlfY29va2llX2lkIjoiMTliOTIwOTU3YThhY2EtMGQ2NDkyZWQ4NzU2ZTEtMjYwNjFhNTEtMTMzODY0NS0xOWI5MjA5NTdhOTI2NTYiLCIkaWRlbnRpdHlfbG9naW5faWQiOiI3UE81N0xaUGpPcEsifQ%3D%3D%22%2C%22history_login_id%22%3A%7B%22name%22%3A%22%24identity_login_id%22%2C%22value%22%3A%227PO57LZPjOpK%22%7D%2C%22%24device_id%22%3A%2219b920957a8aca-0d6492ed8756e1-26061a51-1338645-19b920957a92656%22%7D; _gc_usr_id_cs0_d0_sec0_part0=012ffb5a-318b-4f57-9723-6dd68cd9f354; _gc_s_cs0_d0_sec0_part0=rum=0&expire=1774152908078; _token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3Nzc2MDgwMDYsInVzZXIiOnsiaWQiOiIzNjI2NDI5MzU3MjgyNzU0NjEiLCJuYW1lIjoi5o6i57Si6ICFNTQ2MSIsImF2YXRhciI6Imh0dHBzOi8vY2RuLmhhaWx1b2FpLmNvbS9wcm9kLzIwMjUtMDMtMTItMjAvdXNlcl9hdmF0YXIvMTc0MTc4MTQ3NDM0NDY4MDc5Mi0yMTExOTE4Nzk0ODY2Njg4MDFvdmVyc2l6ZS5wbmciLCJkZXZpY2VJRCI6IjQ2NDgzNTgzNTEwMzE3ODc1MiIsImlzQW5vbnltb3VzIjpmYWxzZX19.uEvaM7Jpz8rJU_oWNIIfyQ_gLBm0p_hubqFbOhfLKqo';   // 登录token
const UUID      = '91e58793-9f30-4d52-899c-34a6ae4a2278';   // localStorage 里的 uuid
const DEVICE_ID = '464835835103178752';   // localStorage 里的 device_id
// ──────────────────────────────────────────────────────────────

// 自动从 Cookie 字符串中提取 _token JWT（也兼容直接填 JWT 的情况）
function extractToken(raw) {
    const m = raw.match(/_token=([^;\s]+)/);
    return m ? m[1] : raw;  // 找到则取 JWT，否则原样使用
}
const COOKIE = TOKEN;               // 完整 Cookie 字符串
const JWT    = extractToken(TOKEN); // 纯 JWT，用于 token 请求头

if (!JWT || !UUID || !DEVICE_ID) {
    console.error('请先填写 TOKEN / UUID / DEVICE_ID');
    process.exit(1);
}

// ─── 签名核心（来自逆向） ───────────────────────────────────────
function md5(str) {
    return crypto.createHash('md5').update(str).digest('hex');
}

function buildPublicParams(unixMs) {
    return {
        device_platform: 'web',
        app_id: '3001',
        version_code: '22203',
        biz_id: '0',
        unix: unixMs,
        lang: 'zh-Hans',
        uuid: UUID,
        device_id: DEVICE_ID,
        os_name: 'Windows',
        browser_name: 'chrome',
        device_memory: 8,
        cpu_core_num: 24,
        browser_language: 'zh-CN',
        browser_platform: 'Win32',
        screen_width: 1920,
        screen_height: 1080,
    };
}

function appendParamsToUrl(url, params) {
    const qs = Object.entries(params)
        .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
        .join('&');
    return `${url}?${qs}`;
}

function generateYY(url, method, body, time) {
    const publicParams = buildPublicParams(time);
    const fullUrl = appendParamsToUrl(url, publicParams);

    let bodyObj = {};
    if (['post', 'delete'].includes((method || 'get').toLowerCase())) {
        bodyObj = body || {};
    }
    const bodyString = JSON.stringify(bodyObj);
    const inner = md5(String(time));
    const raw   = encodeURIComponent(fullUrl) + '_' + bodyString + inner + 'ooui';
    const yy    = md5(raw);

    return { yy, fullUrl, publicParams };
}

// ─── 发起请求 ──────────────────────────────────────────────────
function request(path, method = 'GET', body = null) {
    const time = Date.now();
    const { yy, publicParams } = generateYY(path, method, body, time);

    const qs = Object.entries(publicParams)
        .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
        .join('&');
    const fullPath = `${path}?${qs}`;

    const headers = {
        'Content-Type': 'application/json',
        'token': JWT,
        'yy': yy,
        'Cookie': COOKIE,
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Referer': 'https://hailuoai.com/',
        'Origin': 'https://hailuoai.com',
    };

    const postData = body ? JSON.stringify(body) : null;
    if (postData) headers['Content-Length'] = Buffer.byteLength(postData);

    console.log(`
>>> ${method} https://hailuoai.com${fullPath}`);
    console.log('>>> yy:', yy);

    return new Promise((resolve, reject) => {
        const req = https.request({
            hostname: 'hailuoai.com',
            path: fullPath,
            method,
            headers,
        }, res => {
            let data = '';
            res.on('data', chunk => data += chunk);
            res.on('end', () => {
                console.log(`
<<< Status: ${res.statusCode}`);
                try {
                    const json = JSON.parse(data);
                    console.log('<<< Body:', JSON.stringify(json, null, 2));
                    resolve(json);
                } catch {
                    console.log('<<< Raw:', data);
                    resolve(data);
                }
            });
        });
        req.on('error', reject);
        if (postData) req.write(postData);
        req.end();
    });
}

// ─── 测试用例 ──────────────────────────────────────────────────
(async () => {
    // 1. 查询贝壳余额
    await request('/v1/api/billing/credit', 'GET');
})();
