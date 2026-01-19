<script setup>
import { ref, onMounted } from 'vue'

const isMobile = ref(false)

onMounted(() => {
  // 检测是否为移动设备
  const userAgent = navigator.userAgent || navigator.vendor || window.opera
  const mobileRegex = /android|webos|iphone|ipad|ipod|blackberry|iemobile|opera mini|mobile|tablet/i
  isMobile.value = mobileRegex.test(userAgent.toLowerCase())
})
</script>

<template>
  <!-- 移动设备拦截页面 -->
  <div v-if="isMobile" class="fixed inset-0 bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 flex items-center justify-center p-6">
    <div class="text-center max-w-md">
      <!-- 图标 -->
      <div class="mb-6">
        <svg class="w-24 h-24 mx-auto text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
        </svg>
      </div>
      
      <!-- 标题 -->
      <h1 class="text-2xl font-bold text-white mb-3">请使用电脑访问</h1>
      
      <!-- 说明 -->
      <p class="text-gray-300 mb-6 leading-relaxed">
        为了获得最佳的 AI 视频生成体验，请使用电脑浏览器访问本站。
      </p>
      
      <!-- 提示 -->
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
