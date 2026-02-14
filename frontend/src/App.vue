<script setup>
import { ref, onMounted } from 'vue'
import { getPublicConfig } from './api'

const isMobile = ref(false)
const blockMobile = ref(false)
const blockMessage = ref('暂不支持移动端访问，请使用电脑浏览器')
const configLoaded = ref(false)

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
    }
  } catch (e) {
    blockMobile.value = false
  }
  
  configLoaded.value = true
})
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
  
  <!-- 正常内容 -->
  <router-view v-else></router-view>
</template>
