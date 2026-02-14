<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { getCurrentUser, getInviteStats } from '../api'

const router = useRouter()
const user = ref(null)
const inviteData = ref(null)
const loading = ref(true)
const copied = ref(false)

// Toast
const showToast = ref(false)
const toastMessage = ref('')
const toastType = ref('info')

const showNotification = (message, type = 'info') => {
  toastMessage.value = message
  toastType.value = type
  showToast.value = true
  setTimeout(() => { showToast.value = false }, 3000)
}

const inviteLink = computed(() => {
  if (!inviteData.value?.invite_code) return ''
  return `${window.location.origin}/login?invite=${inviteData.value.invite_code}`
})

const loadData = async () => {
  loading.value = true
  try {
    const [userData, statsData] = await Promise.all([
      getCurrentUser(),
      getInviteStats()
    ])
    user.value = userData
    inviteData.value = statsData
  } catch (err) {
    if (err.response?.status === 401) router.push('/login')
  } finally {
    loading.value = false
  }
}

const copyInviteLink = () => {
  if (!inviteLink.value) return
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(inviteLink.value).then(() => {
      copied.value = true
      showNotification('邀请链接已复制！快去分享吧', 'success')
      setTimeout(() => { copied.value = false }, 2000)
    }).catch(() => fallbackCopy(inviteLink.value))
  } else {
    fallbackCopy(inviteLink.value)
  }
}

const copyInviteCode = () => {
  if (!inviteData.value?.invite_code) return
  const code = inviteData.value.invite_code
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(code).then(() => {
      showNotification('邀请码已复制', 'success')
    }).catch(() => fallbackCopy(code))
  } else {
    fallbackCopy(code)
  }
}

const fallbackCopy = (text) => {
  try {
    const ta = document.createElement("textarea")
    ta.value = text
    ta.style.cssText = "position:fixed;top:0;left:0;opacity:0"
    document.body.appendChild(ta)
    ta.focus(); ta.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(ta)
    if (ok) {
      copied.value = true
      showNotification('已复制', 'success')
      setTimeout(() => { copied.value = false }, 2000)
    } else {
      showNotification('复制失败，请手动复制', 'error')
    }
  } catch (err) {
    showNotification('复制失败，请手动复制', 'error')
  }
}

const relativeTime = (dateStr) => {
  if (!dateStr) return ''
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return '刚刚'
  if (mins < 60) return `${mins}分钟前`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}小时前`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days}天前`
  return new Date(dateStr).toLocaleDateString()
}

const handleLogout = () => {
  localStorage.removeItem('token')
  router.push('/login')
}

onMounted(loadData)
</script>

<template>
  <div class="min-h-screen relative overflow-hidden flex flex-col bg-[#0f1115]">
    <!-- Background -->
    <div class="fixed inset-0 z-0 pointer-events-none">
      <div class="absolute top-0 left-1/4 w-[500px] h-[500px] bg-purple-900/15 rounded-full blur-[120px]"></div>
      <div class="absolute bottom-0 right-1/4 w-[500px] h-[500px] bg-cyan-900/15 rounded-full blur-[120px]"></div>
    </div>

    <!-- Toast -->
    <Transition name="toast">
      <div v-if="showToast" class="fixed top-6 left-1/2 transform -translate-x-1/2 z-50">
        <div :class="{
            'bg-red-500/80 border-red-500/50': toastType === 'error',
            'bg-green-500/80 border-green-500/50': toastType === 'success',
            'bg-blue-500/80 border-blue-500/50': toastType === 'info'
        }" class="text-white flex items-center gap-3 px-6 py-3 rounded-xl border shadow-lg backdrop-blur-xl">
          <span class="font-medium text-sm">{{ toastMessage }}</span>
        </div>
      </div>
    </Transition>
    
    <!-- Navbar -->
    <nav class="relative z-20 px-8 py-4 border-b border-white/10 bg-black/20 backdrop-blur-md">
      <div class="max-w-7xl mx-auto flex justify-between items-center">
        <div class="text-2xl font-extrabold cursor-pointer flex items-center gap-2" @click="router.push('/')">
          <span class="text-white drop-shadow-md">大帝</span><span class="text-cyan-400 drop-shadow-md">AI</span>
        </div>
        <div class="flex items-center gap-6">
          <router-link to="/dashboard" class="text-sm text-gray-400 hover:text-white transition-colors">控制台</router-link>
          <router-link to="/tickets" class="text-sm text-gray-400 hover:text-white transition-colors">工单</router-link>
          <div class="text-sm text-white font-bold border-b-2 border-cyan-500 pb-0.5">邀请</div>
          <router-link to="/recharge" class="px-4 py-1.5 bg-gradient-to-r from-cyan-600 to-blue-600 text-white text-xs font-bold rounded-lg hover:brightness-110 transition-all shadow-lg shadow-cyan-900/40">充值</router-link>
          <button @click="handleLogout" class="text-sm text-gray-300 hover:text-white transition-colors">退出</button>
        </div>
      </div>
    </nav>
    
    <!-- Main -->
    <div class="flex-grow w-full max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-10 relative z-10 space-y-8">
      
      <!-- Loading -->
      <div v-if="loading" class="flex items-center justify-center py-20">
        <div class="w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin"></div>
      </div>

      <template v-else>
        <!-- Header -->
        <div class="text-center space-y-3">
          <h1 class="text-3xl md:text-4xl font-black text-white">
            邀请好友，<span class="text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-purple-400">共享创作之力</span>
          </h1>
          <p class="text-gray-400 max-w-lg mx-auto">每邀请一位好友注册，双方各得 <span class="text-white font-bold">¥{{ inviteData?.invite_reward || 3 }}</span> 余额奖励，奖励无上限</p>
        </div>

        <!-- 统计卡片 -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div class="bg-[#1a1d24]/80 backdrop-blur-xl border border-white/10 rounded-2xl p-6 text-center">
            <div class="w-12 h-12 mx-auto mb-3 rounded-xl bg-cyan-500/10 flex items-center justify-center">
              <svg class="w-6 h-6 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"></path></svg>
            </div>
            <p class="text-3xl font-black text-white">{{ inviteData?.total_invited || 0 }}</p>
            <p class="text-sm text-gray-500 mt-1">已邀请好友</p>
          </div>
          <div class="bg-[#1a1d24]/80 backdrop-blur-xl border border-white/10 rounded-2xl p-6 text-center">
            <div class="w-12 h-12 mx-auto mb-3 rounded-xl bg-green-500/10 flex items-center justify-center">
              <svg class="w-6 h-6 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
            </div>
            <p class="text-3xl font-black text-green-400">¥{{ (inviteData?.total_earnings || 0).toFixed(1) }}</p>
            <p class="text-sm text-gray-500 mt-1">累计获得奖励</p>
          </div>
          <div class="bg-[#1a1d24]/80 backdrop-blur-xl border border-white/10 rounded-2xl p-6 text-center">
            <div class="w-12 h-12 mx-auto mb-3 rounded-xl bg-purple-500/10 flex items-center justify-center">
              <svg class="w-6 h-6 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v13m0-13V6a2 2 0 112 2h-2zm0 0V5.5A2.5 2.5 0 109.5 8H12zm-7 4h14M5 12a2 2 0 110-4h14a2 2 0 110 4M5 12v7a2 2 0 002 2h10a2 2 0 002-2v-7"></path></svg>
            </div>
            <p class="text-3xl font-black text-purple-400">¥{{ inviteData?.invite_reward || 3 }}</p>
            <p class="text-sm text-gray-500 mt-1">每次邀请奖励</p>
          </div>
        </div>

        <!-- 邀请卡片 -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <!-- 左：邀请链接 -->
          <div class="relative group">
            <div class="absolute -inset-0.5 bg-gradient-to-r from-cyan-500 to-purple-600 rounded-2xl blur opacity-20 group-hover:opacity-40 transition duration-500"></div>
            <div class="relative bg-[#1a1d24] border border-white/10 rounded-2xl p-6 space-y-5">
              <div>
                <p class="text-xs text-gray-500 uppercase tracking-widest font-bold mb-2">专属邀请码</p>
                <div class="flex items-center gap-3">
                  <span class="text-3xl font-mono font-black text-white tracking-[0.2em]">{{ inviteData?.invite_code || '---' }}</span>
                  <button @click="copyInviteCode" class="text-gray-500 hover:text-cyan-400 transition-colors" title="复制邀请码">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"></path></svg>
                  </button>
                </div>
              </div>

              <div>
                <p class="text-xs text-gray-500 mb-2">邀请链接</p>
                <div class="flex items-center gap-2 bg-black/30 rounded-lg px-3 py-2 border border-white/5">
                  <span class="text-xs text-gray-400 truncate flex-1 font-mono">{{ inviteLink || '---' }}</span>
                </div>
              </div>

              <button 
                @click="copyInviteLink"
                class="w-full py-3.5 rounded-xl font-bold text-base transition-all active:scale-[0.98] flex items-center justify-center gap-2"
                :class="copied 
                  ? 'bg-green-500 text-white' 
                  : 'bg-white text-black hover:bg-gray-100 shadow-lg'"
              >
                <svg v-if="!copied" class="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"></path></svg>
                <svg v-else class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
                {{ copied ? '已复制' : '复制邀请链接' }}
              </button>
            </div>
          </div>

          <!-- 右：操作步骤 -->
          <div class="bg-[#1a1d24]/80 border border-white/10 rounded-2xl p-6 flex flex-col justify-center">
            <h3 class="text-lg font-bold text-white mb-5">如何邀请？</h3>
            <div class="space-y-4">
              <div class="flex items-start gap-4">
                <div class="w-8 h-8 rounded-full bg-cyan-500/20 flex items-center justify-center text-cyan-400 border border-cyan-500/20 shrink-0 text-sm font-bold">1</div>
                <div>
                  <p class="text-white font-medium">复制邀请链接</p>
                  <p class="text-xs text-gray-500 mt-0.5">点击上方按钮一键复制您的专属链接</p>
                </div>
              </div>
              <div class="flex items-start gap-4">
                <div class="w-8 h-8 rounded-full bg-purple-500/20 flex items-center justify-center text-purple-400 border border-purple-500/20 shrink-0 text-sm font-bold">2</div>
                <div>
                  <p class="text-white font-medium">分享给好友</p>
                  <p class="text-xs text-gray-500 mt-0.5">通过微信、QQ、社交媒体等渠道分享</p>
                </div>
              </div>
              <div class="flex items-start gap-4">
                <div class="w-8 h-8 rounded-full bg-green-500/20 flex items-center justify-center text-green-400 border border-green-500/20 shrink-0 text-sm font-bold">3</div>
                <div>
                  <p class="text-white font-medium">好友注册成功</p>
                  <p class="text-xs text-gray-500 mt-0.5">好友通过链接注册后，双方各得 ¥{{ inviteData?.invite_reward || 3 }} 奖励</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 邀请记录 -->
        <div class="bg-[#1a1d24]/80 backdrop-blur-xl border border-white/10 rounded-2xl overflow-hidden">
          <div class="px-6 py-4 border-b border-white/10 flex items-center justify-between">
            <h3 class="text-base font-bold text-white flex items-center gap-2">
              <svg class="w-5 h-5 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"></path></svg>
              邀请记录
            </h3>
            <span class="text-xs text-gray-500">共 {{ inviteData?.total_invited || 0 }} 条</span>
          </div>

          <div v-if="!inviteData?.invite_list?.length" class="p-12 text-center">
            <div class="w-16 h-16 bg-white/5 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg class="w-8 h-8 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"></path></svg>
            </div>
            <p class="text-gray-500 mb-1">还没有邀请记录</p>
            <p class="text-xs text-gray-600">快去分享邀请链接，邀请好友一起创作吧！</p>
          </div>

          <div v-else class="divide-y divide-white/5">
            <div v-for="(item, idx) in inviteData.invite_list" :key="idx" class="px-6 py-4 flex items-center justify-between">
              <div class="flex items-center gap-3">
                <div class="w-9 h-9 rounded-full bg-gradient-to-tr from-cyan-900 to-blue-900 flex items-center justify-center text-xs text-cyan-200 font-bold border border-white/5">
                  {{ item.username?.charAt(0).toUpperCase() }}
                </div>
                <div>
                  <p class="text-sm text-white font-medium">{{ item.username }}</p>
                  <p class="text-xs text-gray-600">{{ relativeTime(item.created_at) }} 注册</p>
                </div>
              </div>
              <span class="text-sm font-bold text-green-400">+¥{{ inviteData.invite_reward }}</span>
            </div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.toast-enter-active,
.toast-leave-active {
  transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}
.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translate(-50%, -20px);
}
</style>
