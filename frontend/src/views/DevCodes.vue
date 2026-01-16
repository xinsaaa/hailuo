<template>
  <div class="min-h-screen bg-gradient-to-br from-gray-900 via-blue-900 to-indigo-900 py-8">
    <div class="container mx-auto px-4">
      <!-- 页面标题 -->
      <div class="text-center mb-8">
        <h1 class="text-4xl font-bold text-white mb-4">📱 验证码监控</h1>
        <p class="text-gray-300">实时查看服务器收到的验证码</p>
      </div>

      <!-- 最新验证码卡片 -->
      <div class="max-w-2xl mx-auto mb-8">
        <div class="bg-white/10 backdrop-blur-sm border border-white/20 rounded-2xl p-6 shadow-2xl">
          <h2 class="text-2xl font-bold text-white mb-4 flex items-center">
            🔥 最新验证码
            <button 
              @click="refreshLatest" 
              class="ml-auto px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-white text-sm transition-colors duration-200"
            >
              🔄 刷新
            </button>
          </h2>
          
          <div v-if="latestCode.code" class="text-center">
            <div class="text-6xl font-mono font-bold text-green-400 mb-4 tracking-wider">
              {{ latestCode.code }}
            </div>
            <div class="text-gray-300">
              <p>⏰ 时间: {{ latestCode.created_at }}</p>
              <p>📱 来源: {{ latestCode.source }}</p>
            </div>
          </div>
          
          <div v-else class="text-center py-8">
            <div class="text-4xl mb-4">😴</div>
            <p class="text-gray-400">暂无验证码</p>
          </div>
        </div>
      </div>

      <!-- 历史验证码列表 -->
      <div class="max-w-4xl mx-auto">
        <div class="bg-white/10 backdrop-blur-sm border border-white/20 rounded-2xl p-6 shadow-2xl">
          <div class="flex justify-between items-center mb-6">
            <h2 class="text-2xl font-bold text-white">📋 历史验证码</h2>
            <button 
              @click="refreshHistory" 
              class="px-4 py-2 bg-green-600 hover:bg-green-700 rounded-lg text-white text-sm transition-colors duration-200"
            >
              🔄 刷新历史
            </button>
          </div>

          <div class="space-y-3">
            <div 
              v-for="code in codes" 
              :key="code.id"
              class="flex items-center justify-between p-4 bg-white/5 border border-white/10 rounded-xl hover:bg-white/10 transition-colors duration-200"
            >
              <div class="flex items-center space-x-4">
                <div class="text-2xl font-mono font-bold text-cyan-400">
                  {{ code.code }}
                </div>
                <div class="text-sm text-gray-400">
                  <div>⏰ {{ code.created_at }}</div>
                  <div>📱 {{ code.source }}</div>
                </div>
              </div>
              
              <div class="flex items-center space-x-3">
                <span :class="{
                  'px-3 py-1 rounded-full text-xs font-medium': true,
                  'bg-green-500/20 text-green-400': code.used,
                  'bg-yellow-500/20 text-yellow-400': !code.used
                }">
                  {{ code.used ? '✅ 已使用' : '⭐ 未使用' }}
                </span>
                
                <button 
                  @click="copyCode(code.code)" 
                  class="px-3 py-1 bg-blue-600 hover:bg-blue-700 rounded-lg text-white text-xs transition-colors duration-200"
                >
                  📋 复制
                </button>
              </div>
            </div>
          </div>

          <div v-if="codes.length === 0" class="text-center py-8">
            <div class="text-4xl mb-4">📭</div>
            <p class="text-gray-400">暂无历史验证码</p>
          </div>
        </div>
      </div>

      <!-- 自动刷新开关 -->
      <div class="max-w-2xl mx-auto mt-8 text-center">
        <label class="inline-flex items-center">
          <input 
            type="checkbox" 
            v-model="autoRefresh" 
            class="form-checkbox h-5 w-5 text-blue-600 rounded"
          >
          <span class="ml-2 text-white">🔄 自动刷新 (每5秒)</span>
        </label>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import axios from 'axios'

const latestCode = ref({ code: null, created_at: '', source: '' })
const codes = ref([])
const autoRefresh = ref(false)
let refreshInterval = null

// API 基础URL - 正确的服务器地址
const API_BASE = 'http://152.32.213.113:8000'

// 获取最新验证码
const refreshLatest = async () => {
  try {
    const response = await axios.get(`${API_BASE}/api/dev/latest-code`)
    latestCode.value = response.data
  } catch (error) {
    console.error('获取最新验证码失败:', error)
  }
}

// 获取历史验证码
const refreshHistory = async () => {
  try {
    const response = await axios.get(`${API_BASE}/api/dev/codes`)
    codes.value = response.data
  } catch (error) {
    console.error('获取历史验证码失败:', error)
  }
}

// 复制验证码
const copyCode = async (code) => {
  try {
    await navigator.clipboard.writeText(code)
    alert(`验证码 ${code} 已复制到剪贴板！`)
  } catch (error) {
    console.error('复制失败:', error)
    alert('复制失败，请手动复制')
  }
}

// 监听自动刷新开关
const toggleAutoRefresh = () => {
  if (autoRefresh.value) {
    refreshInterval = setInterval(() => {
      refreshLatest()
      refreshHistory()
    }, 5000)
  } else {
    if (refreshInterval) {
      clearInterval(refreshInterval)
      refreshInterval = null
    }
  }
}

// 初始化
onMounted(() => {
  refreshLatest()
  refreshHistory()
})

// 清理
onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
})

// 监听自动刷新变化
import { watch } from 'vue'
watch(autoRefresh, toggleAutoRefresh)
</script>
