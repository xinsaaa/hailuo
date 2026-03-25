/**
 * 海螺AI - 查询生成批次列表
 * POST /api/feed/creation/my/batch
 *
 * 算法验证: unix=1774153004000 → yy=97fb4fe0717a7be0e5e117bf32dfed9f ✓
 *
 * 返回字段说明:
 *   data.batchFeeds[].batchID          批次ID
 *   data.batchFeeds[].batchCreateTime  创建时间(ms)
 *   data.batchFeeds[].feeds[].commonInfo.status  状态(2=成功)
 *   data.batchFeeds[].feeds[].metaInfo.videoMetaInfo.mediaInfo.url  播放链接
 *   data.batchFeeds[].feeds[].metaInfo.videoMetaInfo.downloadURL.withoutWatermarkURL  无水印下载
 *   data.batchFeeds[].feeds[].metaInfo.videoMetaInfo.downloadURL.watermarkURL        带水印下载
 *   data.batchFeeds[].feeds[].feedCoverInfo.coverURL  封面
 *
 * 用法: node test_batch.js
 */

const https  = require('https');
const crypto = require('crypto');

// ─── 填入你的信息 ───────────────────────────────────────────────
const COOKIE    = 'sensorsdata2015jssdkchannel=%7B%22prop%22%3A%7B%22_sa_channel_landing_url%22%3A%22%22%7D%7D; sensorsdata2015jssdkcross=%7B%22distinct_id%22%3A%227PO57LZPjOpK%22%2C%22first_id%22%3A%2219b920957a8aca-0d6492ed8756e1-26061a51-1338645-19b920957a92656%22%2C%22props%22%3A%7B%22%24latest_traffic_source_type%22%3A%22%E7%9B%B4%E6%8E%A5%E6%B5%81%E9%87%8F%22%2C%22%24latest_search_keyword%22%3A%22%E6%9C%AA%E5%8F%96%E5%88%B0%E5%80%BC_%E7%9B%B4%E6%8E%A5%E6%89%93%E5%BC%80%22%2C%22%24latest_referrer%22%3A%22%22%7D%2C%22identities%22%3A%22eyIkaWRlbnRpdHlfY29va2llX2lkIjoiMTliOTIwOTU3YThhY2EtMGQ2NDkyZWQ4NzU2ZTEtMjYwNjFhNTEtMTMzODY0NS0xOWI5MjA5NTdhOTI2NTYiLCIkaWRlbnRpdHlfbG9naW5faWQiOiI3UE81N0xaUGpPcEsifQ%3D%3D%22%2C%22history_login_id%22%3A%7B%22name%22%3A%22%24identity_login_id%22%2C%22value%22%3A%227PO57LZPjOpK%22%7D%2C%22%24device_id%22%3A%2219b920957a8aca-0d6492ed8756e1-26061a51-1338645-19b920957a92656%22%7D; _gc_usr_id_cs0_d0_sec0_part0=012ffb5a-318b-4f57-9723-6dd68cd9f354; _token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3Nzc2MDgwMDYsInVzZXIiOnsiaWQiOiIzNjI2NDI5MzU3MjgyNzU0NjEiLCJuYW1lIjoi5o6i57Si6ICFNTQ2MSIsImF2YXRhciI6Imh0dHBzOi8vY2RuLmhhaWx1b2FpLmNvbS9wcm9kLzIwMjUtMDMtMTItMjAvdXNlcl9hdmF0YXIvMTc0MTc4MTQ3NDM0NDY4MDc5Mi0yMTExOTE4Nzk0ODY2Njg4MDFvdmVyc2l6ZS5wbmciLCJkZXZpY2VJRCI6IjQ2NDgzNTgzNTEwMzE3ODc1MiIsImlzQW5vbnltb3VzIjpmYWxzZX19.uEvaM7Jpz8rJU_oWNIIfyQ_gLBm0p_hubqFbOhfLKqo; _gc_s_cs0_d0_sec0_part0=rum=0&expire=1774153894158';
const UUID      = '91e58793-9f30-4d52-899c-34a6ae4a2278';
const DEVICE_ID = '464835835103178752';
// ──────────────────────────────────────────────────────────────

// ─── 分页参数 ──────────────────────────────────────────────────
const CURSOR     = '';        // 第一页留空，翻页时填上一页返回的 cursor
const LIMIT      = 30;
const TYPE       = 'next';    // 'next' 或 'prev'
const SCENE      = 'create';  // 场景
const PROJECT_ID = '0';
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
                    // 打印简洁摘要
                    printSummary(json);
                    // 同时保存完整 JSON
                    const fs = require('fs');
                    fs.writeFileSync('batch_result.json', JSON.stringify(json, null, 2), 'utf8');
                    console.log('\n完整结果已保存到 batch_result.json');
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

function printSummary(json) {
    if (!json.data) { console.log(JSON.stringify(json, null, 2)); return; }
    const batches = json.data.batchFeeds || [];
    console.log(`\n共 ${batches.length} 个批次:`);
    for (const batch of batches) {
        const t = new Date(Number(batch.batchCreateTime)).toLocaleString('zh-CN');
        console.log(`\n  BatchID: ${batch.batchID}  (${t})`);
        for (const feed of (batch.feeds || [])) {
            const ci      = feed.commonInfo || {};
            const vm      = feed.metaInfo?.videoMetaInfo;
            const dlObj   = vm?.mediaInfo?.downloadURL || {};
            const playUrl = vm?.mediaInfo?.url || '-';
            const dlUrl   = dlObj.withoutWatermarkURL || dlObj.watermarkURL || '-';
            const cover   = feed.feedCoverInfo?.coverURL || '-';
            const tags    = (feed.feedTags || []).map(t => t.tagText).join(', ');
            const msg     = feed.feedMessage?.message || '';
            console.log(`    feedID:  ${ci.id || '-'}  batchID: ${ci.batchID || '-'}`);
            console.log(`    status:  ${ci.status}  tags: ${tags}${msg ? '  msg: ' + msg : ''}`);
            console.log(`    play:    ${playUrl}`);
            console.log(`    dl(无水印): ${dlUrl}`);
            console.log(`    cover:   ${cover}`);
        }
    }
    // 翻页 cursor
    if (json.data.cursor) console.log(`\n下一页 cursor: ${json.data.cursor}`);
    else console.log('\n(已是最后一页)');
}

(async () => {
    const body = {
        cursor:    CURSOR,
        limit:     LIMIT,
        type:      TYPE,
        scene:     SCENE,
        projectID: PROJECT_ID,
    };
    await httpsPost('/api/feed/creation/my/batch', body);
})();
