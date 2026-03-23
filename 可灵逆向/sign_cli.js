'use strict';
// ================================================================
// 可灵签名 CLI — 从 stdin 读 JSON，输出签名结果到 stdout
// 输入: { url, query, form, requestBody, projectInfo }
// 输出: { signResult, signInput, signedUrl }
// ================================================================

global.window = global;
global.document = {
  scripts: { length: 3 },
  createElement: () => ({})
};
Object.defineProperty(global, 'navigator', {
  value: {
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
    sendBeacon: () => {}
  },
  writable: true, configurable: true
});
global.performance = { now: () => Date.now() };
global.localStorage = { getItem: () => null, setItem: () => {} };

const fs = require('fs');
const vm = require('vm');
const path = require('path');

const sdkSrc = fs.readFileSync(path.join(__dirname, 'sdk_block.js'), 'utf8');
const ctx = vm.createContext(global);
vm.runInContext(sdkSrc, ctx);

const Ga = ctx.Ga;
if (!Ga) {
  process.stderr.write('ERROR: Ga not found\n');
  process.exit(1);
}

const DEFAULT_PROJECT = { appKey: '8M3oUipD76', radarId: '91e99da176' };
const API_BASE = 'https://api-app-cn.klingai.com';

function sign(url, query = {}, form = null, requestBody = null, projectInfo = DEFAULT_PROJECT) {
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

async function main() {
  let raw = '';
  process.stdin.setEncoding('utf8');
  for await (const chunk of process.stdin) raw += chunk;

  let req;
  try {
    req = JSON.parse(raw);
  } catch (e) {
    process.stderr.write('ERROR: invalid JSON input\n');
    process.exit(1);
  }

  const { url, query = {}, form = null, requestBody = null, projectInfo = DEFAULT_PROJECT } = req;

  try {
    const { signResult, signInput } = await sign(url, query, form, requestBody, projectInfo);
    const sep = url.includes('?') ? '&' : '?';
    const signedUrl = `${API_BASE}${url}${sep}__NS_hxfalcon=${encodeURIComponent(signResult)}&caver=2`;
    process.stdout.write(JSON.stringify({ signResult, signInput, signedUrl }) + '\n');
  } catch (e) {
    process.stderr.write('ERROR: ' + String(e) + '\n');
    process.exit(1);
  }
}

main();
