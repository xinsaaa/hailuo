<script setup>
import { ref, onMounted } from 'vue'
import { getPublicConfig } from './api'

const isMobile = ref(false)
const blockMobile = ref(false)
const blockMessage = ref('暂不支持移动端访问，请使用电脑浏览器')
const configLoaded = ref(false)

const maintenanceMode = ref(false)
const maintenanceMessage = ref('系统维护中，请稍后再试')
const maintenancePassword = ref('')
const maintenanceBypassed = ref(false)
const pwdInput = ref('')
const pwdError = ref(false)

onMounted(async () => {
  // 检测是否为移动设备
  const userAgent = navigator.userAgent || navigator.vendor || window.opera
  const mobileRegex = /android|webos|iphone|ipad|ipod|blackberry|iemobile|opera mini|mobile|tablet/i
  isMobile.value = mobileRegex.test(userAgent.toLowerCase())

  // 加载公共配置
  try {
    const config = await getPublicConfig()
    if (config) {
      // 设置标签页标题并缓存站点名称
      if (config.site_name) {
        document.title = config.site_name
        localStorage.setItem('site_name', config.site_name)
      }
      // 手机端拦截
      if (isMobile.value) {
        blockMobile.value = config.block_mobile_users === true
        if (config.block_mobile_message) blockMessage.value = config.block_mobile_message
      }
      // 维护模式
      maintenanceMode.value = config.maintenance_mode === true
      if (config.maintenance_message) maintenanceMessage.value = config.maintenance_message
      maintenancePassword.value = config.maintenance_password || ''
      // 检查本地是否已绕过
      if (localStorage.getItem('maintenance_bypass') === '1') {
        maintenanceBypassed.value = true
      }
    }
  } catch (e) {
    blockMobile.value = false
  }

  configLoaded.value = true
})

function verifyPassword() {
  if (maintenancePassword.value && pwdInput.value === maintenancePassword.value) {
    localStorage.setItem('maintenance_bypass', '1')
    maintenanceBypassed.value = true
  } else {
    pwdError.value = true
    setTimeout(() => { pwdError.value = false }, 2000)
  }
}
</script>

<template>
  <!-- 等待配置加载 -->
  <div v-if="!configLoaded" class="fixed inset-0 bg-[#0f1115] flex items-center justify-center">
    <div class="w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin"></div>
  </div>

  <!-- 移动设备拦截页面（仅当后台开启拦截时） -->
  <div v-else-if="isMobile && blockMobile" class="fixed inset-0 bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 flex items-center justify-center p-6">
    <div class="text-center max-w-md">
      <div class="mb-6">
        <svg class="w-24 h-24 mx-auto text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
        </svg>
      </div>
      <h1 class="text-2xl font-bold text-white mb-3">请使用电脑访问</h1>
      <p class="text-gray-300 mb-6 leading-relaxed">{{ blockMessage }}</p>
      <div class="bg-white/10 backdrop-blur-xl rounded-xl p-4 border border-white/10">
        <p class="text-sm text-gray-400">
          <span class="text-purple-400 font-medium">💡 提示：</span>
          复制当前网址到电脑浏览器打开即可
        </p>
      </div>
    </div>
  </div>

  <!-- 维护模式页面 -->
  <div v-else-if="maintenanceMode && !maintenanceBypassed" class="fixed inset-0 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center p-6">
    <div class="w-full max-w-sm">
      <!-- 图标 -->
      <div class="flex justify-center mb-6">
        <div class="w-20 h-20 rounded-full bg-amber-500/10 border border-amber-500/30 flex items-center justify-center">
          <svg class="w-10 h-10 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
        </div>
      </div>

      <!-- 标题和说明 -->
      <div class="text-center mb-8">
        <h1 class="text-2xl font-bold text-white mb-2">系统维护中</h1>
        <p class="text-gray-400 text-sm leading-relaxed">{{ maintenanceMessage }}</p>
      </div>

      <!-- 密码输入卡片 -->
      <div class="bg-slate-800/80 backdrop-blur rounded-2xl border border-slate-700/50 p-6">
        <p class="text-xs text-gray-500 mb-3 text-center">内部人员可输入密码继续访问</p>
        <div class="space-y-3">
          <input
            v-model="pwdInput"
            type="password"
            placeholder="请输入访问密码"
            :class="[
              'w-full px-4 py-3 rounded-xl text-white text-sm placeholder-gray-600 outline-none transition-all',
              pwdError
                ? 'bg-red-900/30 border border-red-500/60 animate-shake'
                : 'bg-slate-700/60 border border-slate-600/50 focus:border-amber-500/60'
            ]"
            @keydown.enter="verifyPassword"
          />
          <p v-if="pwdError" class="text-red-400 text-xs text-center">密码错误，请重试</p>
          <button
            @click="verifyPassword"
            class="w-full py-3 bg-amber-500/80 hover:bg-amber-500 text-white text-sm font-medium rounded-xl transition-colors"
          >
            确认进入
          </button>
        </div>
      </div>
    </div>
  </div>

  <!-- 正常内容 -->
  <router-view v-else></router-view>
</template>

<style scoped>
@keyframes shake {
  0%, 100% { transform: translateX(0); }
  20%, 60% { transform: translateX(-6px); }
  40%, 80% { transform: translateX(6px); }
}
.animate-shake {
  animation: shake 0.4s ease-in-out;
}
</style>
