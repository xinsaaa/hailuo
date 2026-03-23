'use strict';
// ================================================================
// 可灵 AI __NS_hxfalcon 签名参数 Node.js 实现
// 逆向自 vendor-yoda-js-2zVeYfZs.js (yoda-js SDK v1.0.2)
// ================================================================

// --- Mock 浏览器环境 ---
global.window = global;
global.document = {
  scripts: { length: 3 },
  createElement: () => ({})
};
Object.defineProperty(global, 'navigator', {
  value: { userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36', sendBeacon: () => {} },
  writable: true, configurable: true
});
global.performance = { now: () => Date.now() };
global.localStorage = { getItem: () => null, setItem: () => {} };

// --- 执行 SDK ---
const fs = require('fs');
const vm = require('vm');
const sdkSrc = fs.readFileSync(__dirname + '/sdk_block.js', 'utf8');
const ctx = vm.createContext(global);
vm.runInContext(sdkSrc, ctx);

// Ga = new lr() 已在 sdk_block.js 末尾初始化
const Ga = ctx.Ga;
if (!Ga) throw new Error('Ga (lr instance) not found');

/**
 * 生成 __NS_hxfalcon 签名
 * @param {string} url - 不含域名的路径，如 /api/user/isLogin
 * @param {object} query - 请求的 query 参数（不含 caver）
 * @param {object|null} form - form 参数
 * @param {object|null} requestBody - 请求体（POST JSON）
 * @param {object} projectInfo - { appKey, radarId }
 * @returns {Promise<{signResult: string, signInput: string}>}
 */
function sign(url, query = {}, form = null, requestBody = null, projectInfo = { appKey: '8M3oUipD76', radarId: '91e99da176' }) {
  return new Promise((resolve, reject) => {
    const input = {
      url,
      query: { caver: '2', ...query },
      form: form || null,
      requestBody: requestBody || {},
      projectInfo: { ...projectInfo, debug: false }
    };
    Ga.call('$encode', [input, {
      suc: (signResult, signInput) => resolve({ signResult, signInput }),
      err: (e) => reject(e)
    }]);
  });
}

/**
 * 构建完整的带签名的 URL
 * @param {string} path - API 路径
 * @param {object} query - 额外 query 参数
 * @returns {Promise<string>}
 */
async function buildSignedUrl(path, query = {}, projectInfo) {
  const { signResult } = await sign(path, query, null, null, projectInfo);
  const sep = path.includes('?') ? '&' : '?';
  return `https://api-app-cn.klingai.com${path}${sep}__NS_hxfalcon=${signResult}&caver=2`;
}

// --- 测试 ---
(async () => {
  try {
    console.log('=== 可灵 AI __NS_hxfalcon 签名测试 ===\n');

    // Test 1: isLogin
    const r1 = await sign('/api/user/isLogin', {});
    console.log('[isLogin]');
    console.log('  signInput:', r1.signInput);
    console.log('  signResult:', r1.signResult);

    // Test 2: pay/package
    const r2 = await sign('/api/pay/package/v2', { irclickid: '', invitationCode: '', inviterToken: '' });
    console.log('\n[pay/package/v2]');
    console.log('  signInput:', r2.signInput);
    console.log('  signResult:', r2.signResult);

    // Test 3: Full signed URL
    const url = await buildSignedUrl('/api/user/isLogin', {});
    console.log('\n[Full Signed URL]:');
    console.log(' ', url);

    console.log('\n=== 成功! ===');
  } catch(e) {
    console.error('Error:', e);
  }
})();
