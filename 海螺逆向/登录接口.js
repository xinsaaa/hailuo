/**
 * 海螺AI 手机号登录流程
 * step1: 发送验证码 POST /v1/api/user/login/sms/send
 * step2: 验证码登录 POST /v1/api/user/login/phone  -> 返回 token
 *
 * 用法: node test_login.js
 *   1. 脚本会先发送验证码到手机
 *   2. 等待你在终端输入收到的验证码
 *   3. 完成登录并打印 token
 */

const https   = require('https');
const crypto  = require('crypto');
const readline = require('readline');

// ─── 填入你的手机号 ───────────────────────────────────────────
const PHONE = '15781806380';
// ──────────────────────────────────────────────────────────────

const UUID      = '047ba553-d411-4252-8f16-05483eaa07b2';
const DEVICE_ID = '491984954473402375';

const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36';

function md5(s) {
    return crypto.createHash('md5').update(s).digest('hex');
}

function buildPublicParams(unix) {
    return new URLSearchParams({
        device_platform: 'web',
        app_id:          '3001',
        version_code:    '22203',
        biz_id:          '0',
        unix:            String(unix),
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
    }).toString();
}

function generateYY(path, body, unix) {
    const pub     = buildPublicParams(unix);
    const fullPath = path + '?' + pub;
    const bodyStr  = body ? JSON.stringify(body) : '{}';
    const inner    = md5(String(unix));
    const raw      = encodeURIComponent(fullPath) + '_' + bodyStr + inner + 'ooui';
    return { yy: md5(raw), query: pub };
}

function httpsPost(path, body) {
    return new Promise((resolve, reject) => {
        const unix    = Date.now();
        const { yy, query } = generateYY(path, body, unix);
        const bodyStr = JSON.stringify(body);
        const fullPath = path + '?' + query;

        console.log(`>>> POST ${path}`);
        console.log(`>>> yy: ${yy}`);

        const options = {
            hostname: 'hailuoai.com',
            path:     fullPath,
            method:   'POST',
            headers: {
                'Content-Type':   'application/json',
                'Content-Length': Buffer.byteLength(bodyStr),
                'User-Agent':     UA,
                'Accept':         'application/json, text/plain, */*',
                'Referer':        'https://hailuoai.com/',
                'yy':             yy,
                'token':          '',
            },
        };

        const req = https.request(options, (res) => {
            let data = '';
            res.on('data', c => data += c);
            res.on('end', () => {
                console.log(`<<< Status: ${res.statusCode}`);
                try { resolve(JSON.parse(data)); }
                catch { resolve(data); }
            });
        });
        req.on('error', reject);
        req.write(bodyStr);
        req.end();
    });
}

function askCode(prompt) {
    return new Promise(resolve => {
        const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
        rl.question(prompt, ans => { rl.close(); resolve(ans.trim()); });
    });
}

(async () => {
    // Step 1: 发送验证码
    console.log(`\n[Step 1] 向 ${PHONE} 发送验证码...`);
    const smsRes = await httpsPost('/v1/api/user/login/sms/send', { phone: PHONE });
    if (smsRes.statusInfo?.code !== 0) {
        console.error('发送验证码失败:', JSON.stringify(smsRes, null, 2));
        process.exit(1);
    }
    console.log('验证码已发送!\n');

    // Step 2: 输入验证码
    const code = await askCode('请输入收到的验证码: ');

    // Step 3: 登录
    console.log('\n[Step 3] 提交登录...');
    const loginRes = await httpsPost('/v1/api/user/login/phone', {
        phone:     PHONE,
        code:      code,
        loginType: '',
    });

    if (loginRes.statusInfo?.code !== 0) {
        console.error('登录失败:', JSON.stringify(loginRes, null, 2));
        process.exit(1);
    }

    const d = loginRes.data;
    console.log('\n========== 登录成功 ==========');
    console.log('用户名:  ', d.webName || d.username);
    console.log('userID:  ', d.realUserID);
    console.log('deviceID:', d.deviceID);
    console.log('token:   ', d.token);
    console.log('================================\n');
    console.log('// 使用时在请求头中加:');
    console.log(`//   token: '${d.token}'`);
})();
