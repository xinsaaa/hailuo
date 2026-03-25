/**
 * 海螺AI - 生成视频
 * POST /v2/api/multimodal/generate/video
 *
 * 算法验证: unix=1774152401000 → yy=f083fff6e011bfee00c50deadcd46c7a ✓
 *
 * 用法: node test_generate_video.js
 */

const https  = require('https');
const crypto = require('crypto');

// ─── 填入你的信息 ───────────────────────────────────────────────
const COOKIE    = 'sensorsdata2015jssdkchannel=%7B%22prop%22%3A%7B%22_sa_channel_landing_url%22%3A%22%22%7D%7D; sensorsdata2015jssdkcross=%7B%22distinct_id%22%3A%227PO57LZPjOpK%22%2C%22first_id%22%3A%2219b920957a8aca-0d6492ed8756e1-26061a51-1338645-19b920957a92656%22%2C%22props%22%3A%7B%22%24latest_traffic_source_type%22%3A%22%E7%9B%B4%E6%8E%A5%E6%B5%81%E9%87%8F%22%2C%22%24latest_search_keyword%22%3A%22%E6%9C%AA%E5%8F%96%E5%88%B0%E5%80%BC_%E7%9B%B4%E6%8E%A5%E6%89%93%E5%BC%80%22%2C%22%24latest_referrer%22%3A%22%22%7D%2C%22identities%22%3A%22eyIkaWRlbnRpdHlfY29va2llX2lkIjoiMTliOTIwOTU3YThhY2EtMGQ2NDkyZWQ4NzU2ZTEtMjYwNjFhNTEtMTMzODY0NS0xOWI5MjA5NTdhOTI2NTYiLCIkaWRlbnRpdHlfbG9naW5faWQiOiI3UE81N0xaUGpPcEsifQ%3D%3D%22%2C%22history_login_id%22%3A%7B%22name%22%3A%22%24identity_login_id%22%2C%22value%22%3A%227PO57LZPjOpK%22%7D%2C%22%24device_id%22%3A%2219b920957a8aca-0d6492ed8756e1-26061a51-1338645-19b920957a92656%22%7D; _gc_usr_id_cs0_d0_sec0_part0=012ffb5a-318b-4f57-9723-6dd68cd9f354; _token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3Nzc2MDgwMDYsInVzZXIiOnsiaWQiOiIzNjI2NDI5MzU3MjgyNzU0NjEiLCJuYW1lIjoi5o6i57Si6ICFNTQ2MSIsImF2YXRhciI6Imh0dHBzOi8vY2RuLmhhaWx1b2FpLmNvbS9wcm9kLzIwMjUtMDMtMTItMjAvdXNlcl9hdmF0YXIvMTc0MTc4MTQ3NDM0NDY4MDc5Mi0yMTExOTE4Nzk0ODY2Njg4MDFvdmVyc2l6ZS5wbmciLCJkZXZpY2VJRCI6IjQ2NDgzNTgzNTEwMzE3ODc1MiIsImlzQW5vbnltb3VzIjpmYWxzZX19.uEvaM7Jpz8rJU_oWNIIfyQ_gLBm0p_hubqFbOhfLKqo; _gc_s_cs0_d0_sec0_part0=rum=0&expire=1774153301128';
const UUID      = '91e58793-9f30-4d52-899c-34a6ae4a2278';
const DEVICE_ID = '464835835103178752';
// ──────────────────────────────────────────────────────────────

// ─── 视频生成参数 ───────────────────────────────────────────────
const VIDEO_DESC       = '原神';        // 提示词
const VIDEO_DURATION   = 6;            // 时长(秒): 6 or 10
const VIDEO_RESOLUTION = '768';        // 分辨率
const MODEL_ID         = '23204';      // 模型ID
const ASPECT_RATIO     = '';           // 宽高比, 留空则自动
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
        app_id:          '3001',
        version_code:    '22203',
        biz_id:          '0',
        unix:            String(unixMs),
        lang:            'zh-Hans',
        uuid:            UUID,
        device_id:       DEVICE_ID,
        os_name:         'Windows',
        browser_name:    'chrome',
        device_memory:   '8',
        cpu_core_num:    '24',
        browser_language:'zh-CN',
        browser_platform:'Win32',
        screen_width:    '1920',
        screen_height:   '1080',
    };
}

function generateYY({ urlPath, bodyStr, time }) {
    const pub      = buildPublicParams(time);
    const qs       = new URLSearchParams(pub).toString();
    const fullPath = urlPath + '?' + qs;
    const inner    = md5(String(time));
    const raw      = encodeURIComponent(fullPath) + '_' + bodyStr + inner + 'ooui';
    return { yy: md5(raw), fullPath };
}

// ─── 内置验证 ──────────────────────────────────────────────────
function verify() {
    const UNIX = 1774152401000;
    const body = JSON.stringify({
        quantity: 1,
        parameter: { modelID: '23204', desc: '原神', fileList: [], useOriginPrompt: false, resolution: '768', duration: 6, aspectRatio: '' },
        videoExtra: { promptStruct: '{"value":[{"type":"paragraph","children":[{"text":"原神"}]}],"length":2,"plainLength":2,"rawLength":2}' },
        projectID: '0',
    });
    const pub      = buildPublicParams(UNIX);
    const qs       = new URLSearchParams(pub).toString();
    const fullPath = '/v2/api/multimodal/generate/video?' + qs;
    const inner    = md5(String(UNIX));
    const raw      = encodeURIComponent(fullPath) + '_' + body + inner + 'ooui';
    const yy       = md5(raw);
    const EXPECTED = 'f083fff6e011bfee00c50deadcd46c7a';
    if (yy === EXPECTED) {
        console.log('[verify] OK - 算法与抓包一致 ✓');
    } else {
        console.warn('[verify] MISMATCH!', 'got:', yy, 'expected:', EXPECTED);
    }
}
verify();

// ─── 构造 promptStruct ─────────────────────────────────────────
function buildPromptStruct(text) {
    const struct = {
        value: [{ type: 'paragraph', children: [{ text }] }],
        length: text.length,
        plainLength: text.length,
        rawLength: text.length,
    };
    return JSON.stringify(struct);
}

// ─── 发起请求 ──────────────────────────────────────────────────
function httpsPost(urlPath, bodyObj) {
    return new Promise((resolve, reject) => {
        const time    = Date.now();
        const bodyStr = JSON.stringify(bodyObj);
        const { yy, fullPath } = generateYY({ urlPath, bodyStr, time });
        const JWT     = extractToken(COOKIE);

        console.log('\n>>> POST', urlPath);
        console.log('>>> yy:', yy);

        const options = {
            hostname: 'hailuoai.com',
            path:     fullPath,
            method:   'POST',
            headers: {
                'Content-Type':    'application/json',
                'Content-Length':  Buffer.byteLength(bodyStr),
                'token':           JWT,
                'yy':              yy,
                'Cookie':          COOKIE,
                'User-Agent':      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
                'Origin':          'https://hailuoai.com',
                'Referer':         'https://hailuoai.com/create/image-to-video',
            },
        };

        const req = https.request(options, (res) => {
            let data = '';
            res.on('data', c => data += c);
            res.on('end', () => {
                console.log('<<< Status:', res.statusCode);
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
        req.write(bodyStr);
        req.end();
    });
}

(async () => {
    const body = {
        quantity: 1,
        parameter: {
            modelID:        MODEL_ID,
            desc:           VIDEO_DESC,
            fileList:       [],
            useOriginPrompt:false,
            resolution:     VIDEO_RESOLUTION,
            duration:       VIDEO_DURATION,
            aspectRatio:    ASPECT_RATIO,
        },
        videoExtra: {
            promptStruct: buildPromptStruct(VIDEO_DESC),
        },
        projectID: '0',
    };

    await httpsPost('/v2/api/multimodal/generate/video', body);
})();
