<script setup>
import { ref, onMounted } from 'vue'
import { checkRisk } from '../api'

const loading = ref(true)
const riskData = ref(null)
const error = ref(null)

// 生成增强版设备指纹（与 Login.vue 保持一致）
const generateFingerprint = () => {
  // Canvas 指纹
  const canvas = document.createElement('canvas')
  canvas.width = 200
  canvas.height = 50
  const ctx = canvas.getContext('2d')
  ctx.textBaseline = 'top'
  ctx.font = '14px Arial'
  ctx.fillStyle = '#f60'
  ctx.fillRect(125, 1, 62, 20)
  ctx.fillStyle = '#069'
  ctx.fillText('fingerprint', 2, 15)
  ctx.fillStyle = 'rgba(102, 204, 0, 0.7)'
  ctx.fillText('fingerprint', 4, 17)
  const canvasData = canvas.toDataURL()
  
  // WebGL 指纹
  let webglVendor = ''
  let webglRenderer = ''
  try {
    const glCanvas = document.createElement('canvas')
    const gl = glCanvas.getContext('webgl') || glCanvas.getContext('experimental-webgl')
    if (gl) {
      const debugInfo = gl.getExtension('WEBGL_debug_renderer_info')
      if (debugInfo) {
        webglVendor = gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL) || ''
        webglRenderer = gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL) || ''
      }
    }
  } catch (e) { /* ignore */ }
  
  // 收集各种浏览器特征
  const data = [
    navigator.userAgent,
    navigator.language,
    navigator.languages?.join(',') || '',
    screen.width + 'x' + screen.height,
    screen.colorDepth,
    screen.pixelDepth,
    new Date().getTimezoneOffset(),
    Intl.DateTimeFormat().resolvedOptions().timeZone,
    navigator.hardwareConcurrency || 0,
    navigator.deviceMemory || 0,
    navigator.maxTouchPoints || 0,
    !!window.sessionStorage,
    !!window.localStorage,
    !!window.indexedDB,
    webglVendor,
    webglRenderer,
    canvasData
  ].join('|')
  
  // 使用更好的哈希算法
  let hash1 = 0, hash2 = 0
  for (let i = 0; i < data.length; i++) {
    const char = data.charCodeAt(i)
    hash1 = ((hash1 << 5) - hash1) + char
    hash1 = hash1 & hash1
    hash2 = ((hash2 << 7) + hash2) ^ char
  }
  return Math.abs(hash1).toString(16) + Math.abs(hash2).toString(16)
}

const fingerprintInfo = ref({
    userAgent: navigator.userAgent,
    screen: screen.width + 'x' + screen.height,
    language: navigator.language,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    fingerprint: ''
})

const loadRiskData = async () => {
    loading.value = true
    error.value = null
    try {
        const fp = generateFingerprint()
        fingerprintInfo.value.fingerprint = fp
        const data = await checkRisk(fp)
        riskData.value = data
    } catch (err) {
        error.value = '加载失败: ' + (err.response?.data?.detail || err.message)
    } finally {
        loading.value = false
    }
}

onMounted(loadRiskData)
</script>

<template>
<div class="min-h-screen bg-black text-green-400 font-mono p-8 overflow-y-auto">
    <div class="max-w-4xl mx-auto border border-green-500/30 p-6 rounded-lg shadow-[0_0_20px_rgba(0,255,0,0.1)] bg-black/90">
        <h1 class="text-3xl font-bold mb-8 flex items-center gap-3 border-b border-green-500/30 pb-4">
            <span class="animate-pulse">🛡️</span> 
            ENV_RISK_ANALYSIS_TOOL_V1.0
        </h1>

        <div v-if="loading" class="text-center py-20">
            <div class="w-16 h-16 border-4 border-green-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
            <p class="animate-pulse">SCANNING_ENVIRONMENT_PARAMETERS...</p>
        </div>

        <div v-else-if="error" class="text-red-500 p-8 border border-red-500/30 bg-red-900/10 rounded">
            <h2 class="text-xl font-bold mb-2">CRITICAL_ERROR</h2>
            <p>{{ error }}</p>
            <button @click="loadRiskData" class="mt-4 px-4 py-2 border border-red-500 hover:bg-red-500/10 rounded">RETRY_SCAN</button>
        </div>

        <div v-else class="space-y-8">
            <!-- 总体评分 -->
            <div class="flex items-center justify-between p-6 bg-green-900/10 border border-green-500/30 rounded-lg">
                <div>
                    <h2 class="text-sm text-green-600 mb-1">OVERALL RISK LEVEL</h2>
                    <div class="text-4xl font-bold" :class="{
                        'text-green-500': riskData.risk_level === 'LOW',
                        'text-yellow-500': riskData.risk_level === 'MEDIUM',
                        'text-red-500 animate-pulse': riskData.risk_level === 'HIGH'
                    }">
                        {{ riskData.risk_level }}
                    </div>
                </div>
                <div class="text-right">
                    <div class="text-xs text-green-700">SCAN_TIMESTAMP</div>
                    <div>{{ new Date().toISOString() }}</div>
                </div>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <!-- IP 检测 -->
                <div class="border border-green-500/20 p-4 rounded bg-black/50">
                    <h3 class="text-xl font-bold mb-4 flex items-center gap-2">
                        <span class="text-green-500">🌐</span> IP_NETWORK_STATUS
                    </h3>
                    <div class="space-y-3 text-sm">
                        <div class="flex justify-between border-b border-green-500/10 pb-1">
                            <span class="text-gray-500">CLIENT_IP</span>
                            <span class="text-white">{{ riskData.ip }}</span>
                        </div>
                        <div class="flex justify-between border-b border-green-500/10 pb-1">
                            <span class="text-gray-500">IS_BANNED</span>
                            <span :class="riskData.is_ip_banned ? 'text-red-500 font-bold' : 'text-green-500'">{{ riskData.is_ip_banned ? 'YES' : 'NO' }}</span>
                        </div>
                        <div class="flex justify-between border-b border-green-500/10 pb-1">
                            <span class="text-gray-500">IP_REGISTERED</span>
                            <span :class="riskData.is_ip_registered ? 'text-red-500 font-bold' : 'text-green-500'">
                                {{ riskData.is_ip_registered ? 'YES (USED)' : 'NO (CLEAN)' }}
                            </span>
                        </div>
                        <div v-if="riskData.is_ip_registered" class="flex justify-between border-b border-green-500/10 pb-1">
                            <span class="text-gray-500">IP_LINKED_USER</span>
                            <span class="text-red-400">{{ riskData.ip_registered_username }}</span>
                        </div>
                        <div class="flex justify-between border-b border-green-500/10 pb-1">
                            <span class="text-gray-500">FAIL_COUNT</span>
                            <span :class="riskData.ip_fail_count > 0 ? 'text-yellow-500' : 'text-green-500'">{{ riskData.ip_fail_count }}</span>
                        </div>
                    </div>
                </div>

                <!-- 设备检测 -->
                <div class="border border-green-500/20 p-4 rounded bg-black/50">
                    <h3 class="text-xl font-bold mb-4 flex items-center gap-2">
                        <span class="text-green-500">💻</span> DEVICE_FINGERPRINT
                    </h3>
                    <div class="space-y-3 text-sm">
                        <div class="flex justify-between border-b border-green-500/10 pb-1">
                            <span class="text-gray-500">RESULT_HASH</span>
                            <span class="text-white font-mono text-xs">{{ riskData.device_fingerprint }}</span>
                        </div>
                        <div class="flex justify-between border-b border-green-500/10 pb-1">
                            <span class="text-gray-500">REGISTERED</span>
                            <span :class="riskData.is_device_registered ? 'text-red-500 font-bold' : 'text-green-500'">
                                {{ riskData.is_device_registered ? 'YES (USED)' : 'NO (CLEAN)' }}
                            </span>
                        </div>
                        <div v-if="riskData.is_device_registered" class="flex justify-between border-b border-green-500/10 pb-1">
                            <span class="text-gray-500">LINKED_USER</span>
                            <span class="text-red-400">{{ riskData.registered_username }}</span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- 本地环境详情 -->
            <div class="border border-green-500/20 p-4 rounded bg-black/50">
                <h3 class="text-xl font-bold mb-4">RAW_ENVIRONMENT_DATA</h3>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono text-gray-400">
                    <div class="p-2 bg-white/5 rounded">
                        <div class="text-green-600 mb-1">USER_AGENT</div>
                        <div class="break-all">{{ fingerprintInfo.userAgent }}</div>
                    </div>
                    <div class="p-2 bg-white/5 rounded">
                        <div class="text-green-600 mb-1">SCREEN_RES</div>
                        <div>{{ fingerprintInfo.screen }}</div>
                    </div>
                    <div class="p-2 bg-white/5 rounded">
                        <div class="text-green-600 mb-1">LANGUAGE</div>
                        <div>{{ fingerprintInfo.language }}</div>
                    </div>
                    <div class="p-2 bg-white/5 rounded">
                        <div class="text-green-600 mb-1">TIMEZONE</div>
                        <div>{{ fingerprintInfo.timezone }}</div>
                    </div>
                </div>
            </div>

            <div class="text-center pt-8 border-t border-green-500/30">
                <p class="text-green-600 text-xs mb-4">
                    NOTE: This tool analyzes parameters used by the registration firewall (IP + Device Fingerprint).
                    <br>Green indicators mean you are likely to pass the automated checks.
                </p>
                <button @click="loadRiskData" class="px-6 py-2 bg-green-600 hover:bg-green-500 text-black font-bold rounded transition-colors shadow-[0_0_10px_rgba(0,255,0,0.3)]">
                    REFRESH_ANALYSIS
                </button>
            </div>
        </div>
    </div>
</div>
</template>
