/**
 * 海螺AI - 查询生成中任务列表
 * POST /api/feed/creation/my/processing
 *
 * 用法: node test_processing.js
 */

const https  = require('https');
const crypto = require('crypto');

// ─── 填入你的信息 ───────────────────────────────────────────────
const COOKIE    = 'sensorsdata2015jssdkchannel=%7B%22prop%22%3A%7B%22_sa_channel_landing_url%22%3A%22%22%7D%7D; sensorsdata2015jssdkcross=%7B%22distinct_id%22%3A%227PO57LZPjOpK%22%2C%22first_id%22%3A%2219b920957a8aca-0d6492ed8756e1-26061a51-1338645-19b920957a92656%22%2C%22props%22%3A%7B%22%24latest_traffic_source_type%22%3A%22%E7%9B%B4%E6%8E%A5%E6%B5%81%E9%87%8F%22%2C%22%24latest_search_keyword%22%3A%22%E6%9C%AA%E5%8F%96%E5%88%B0%E5%80%BC_%E7%9B%B4%E6%8E%A5%E6%89%93%E5%BC%80%22%2C%22%24latest_referrer%22%3A%22%22%7D%2C%22identities%22%3A%22eyIkaWRlbnRpdHlfY29va2llX2lkIjoiMTliOTIwOTU3YThhY2EtMGQ2NDkyZWQ4NzU2ZTEtMjYwNjFhNTEtMTMzODY0NS0xOWI5MjA5NTdhOTI2NTYiLCIkaWRlbnRpdHlfbG9naW5faWQiOiI3UE81N0xaUGpPcEsifQ%3D%3D%22%2C%22history_login_id%22%3A%7B%22name%22%3A%22%24identity_login_id%22%2C%22value%22%3A%227PO57LZPjOpK%22%7D%2C%22%24device_id%22%3A%2219b920957a8aca-0d6492ed8756e1-26061a51-1338645-19b920957a92656%22%7D; _gc_usr_id_cs0_d0_sec0_part0=012ffb5a-318b-4f57-9723-6dd68cd9f354; _token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3Nzc2MDgwMDYsInVzZXIiOnsiaWQiOiIzNjI2NDI5MzU3MjgyNzU0NjEiLCJuYW1lIjoi5o6i57Si6ICFNTQ2MSIsImF2YXRhciI6Imh0dHBzOi8vY2RuLmhhaWx1b2FpLmNvbS9wcm9kLzIwMjUtMDMtMTItMjAvdXNlcl9hdmF0YXIvMTc0MTc4MTQ3NDM0NDY4MDc5Mi0yMTExOTE4Nzk0ODY2Njg4MDFvdmVyc2l6ZS5wbmciLCJkZXZpY2VJRCI6IjQ2NDgzNTgzNTEwMzE3ODc1MiIsImlzQW5vbnltb3VzIjpmYWxzZX19.uEvaM7Jpz8rJU_oWNIIfyQ_gLBm0p_hubqFbOhfLKqo; _gc_s_cs0_d0_sec0_part0=rum=0&expire=1774153301128';
const UUID      = '91e58793-9f30-4d52-899c-34a6ae4a2278';
const DEVICE_ID = '464835835103178752';
// ──────────────────────────────────────────────────────────────

function md5(str) {
    return crypto.createHash('md5').update(str).digest('hex');
}

function extractToken(cookie) {
    const m = cookie.match(/_token=([^;\s]+)/);
    return m ? m[1] : cookie;
}

function buildPublicParams(unixMs) {
    return {
        device_platform: 'web',
        app_id: '3001',
        version_code: '22203',
        biz_id: '0',
        unix: String(unixMs),
        lang: 'zh-Hans',
        uuid: UUID,
        device_id: DEVICE_ID,
        os_name: 'Windows',
        browser_name: 'chrome',
        device_memory: '8',
        cpu_core_num: '24',
        browser_language: 'zh-CN',
        browser_platform: 'Win32',
        screen_width: '1920',
        screen_height: '1080',
    };
}

function generateYY({ url, method, body, time }) {
    const pub = buildPublicParams(time);
    const qs  = new URLSearchParams(pub).toString();
    const fullPath = url + '?' + qs;

    // bodyStr: POST/DELETE 用 JSON.stringify(body)，其余固定 '{}'
    const isWrite = ['post','delete'].includes(method.toLowerCase());
    const bodyStr = isWrite ? JSON.stringify(body || {}) : '{}';

    const inner = md5(String(time));
    const raw   = encodeURIComponent(fullPath) + '_' + bodyStr + inner + 'ooui';
    return { yy: md5(raw), qs, fullPath };
}

// ─── 内置验证：用抓包数据校验算法正确性 ─────────────────────────
function verify() {
    const KNOWN_UNIX = 1774152401000;
    const KNOWN_BODY = { cursor: '' };  // 17 字节: {"cursor":""}
    const KNOWN_YY   = '394e7e2a18c5336e44dcda7b91c634bf';

    const pub = buildPublicParams(KNOWN_UNIX);
    const qs  = new URLSearchParams(pub).toString();
    const fullPath = '/api/feed/creation/my/processing?' + qs;
    const bodyStr  = JSON.stringify(KNOWN_BODY);
    const inner    = md5(String(KNOWN_UNIX));
    const raw      = encodeURIComponent(fullPath) + '_' + bodyStr + inner + 'ooui';
    const yy       = md5(raw);

    if (yy === KNOWN_YY) {
        console.log('[verify] OK - 算法与抓包一致');
    } else {
        console.warn('[verify] MISMATCH!');
        console.warn('  expected:', KNOWN_YY);
        console.warn('  got:     ', yy);
        console.warn('  raw string:', raw);
    }
}
verify();

// ─── 实际请求 ──────────────────────────────────────────────────
async function request(url, method, body) {
    const time = Date.now();
    const { yy, fullPath } = generateYY({ url, method, body, time });
    const JWT = extractToken(COOKIE);

    const bodyStr = (method.toLowerCase() === 'post' || method.toLowerCase() === 'delete')
        ? JSON.stringify(body || {})
        : null;

    return new Promise((resolve, reject) => {
        const options = {
            hostname: 'hailuoai.com',
            path: fullPath,
            method: method.toUpperCase(),
            headers: {
                'Content-Type': 'application/json',
                'token': JWT,
                'yy': yy,
                'Cookie': COOKIE,
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
                'Origin': 'https://hailuoai.com',
                'Referer': 'https://hailuoai.com/create/image-to-video',
                ...(bodyStr ? { 'Content-Length': Buffer.byteLength(bodyStr) } : {}),
            },
        };

        const req = https.request(options, (res) => {
            let data = '';
            res.on('data', c => data += c);
            res.on('end', () => {
                console.log(`\n[${method.toUpperCase()}] ${url}`);
                console.log('status:', res.statusCode);
                try {
                    const json = JSON.parse(data);
                    console.log(JSON.stringify(json, null, 2));
                    resolve(json);
                } catch {
                    console.log(data);
                    resolve(data);
                }
            });
        });
        req.on('error', reject);
        if (bodyStr) req.write(bodyStr);
        req.end();
    });
}

(async () => {
    // 查询生成中的任务列表
    await request('/api/feed/creation/my/processing', 'POST', { cursor: '' });
})();
