<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { getCurrentUser } from '../api'

const router = useRouter()
const user = ref(null)
const loading = ref(false)

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

const loadUser = async () => {
    try {
        user.value = await getCurrentUser()
    } catch (err) {
        if (err.response?.status === 401) {
            router.push('/login')
        }
    }
}

const copyInviteCode = () => {
  if (!user.value || !user.value.invite_code) return
  const inviteLink = `${window.location.origin}/register?invite=${user.value.invite_code}`

  // 优先使用 Clipboard API
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(inviteLink).then(() => {
      showNotification('邀请链接已复制！快去分享吧', 'success')
    }).catch(() => {
      fallbackCopy(inviteLink)
    })
  } else {
    // 降级方案
    fallbackCopy(inviteLink)
  }
}

const fallbackCopy = (text) => {
  try {
    const textArea = document.createElement("textarea")
    textArea.value = text
    textArea.style.top = "0"
    textArea.style.left = "0"
    textArea.style.position = "fixed"
    textArea.style.opacity = "0"
    
    document.body.appendChild(textArea)
    textArea.focus()
    textArea.select()
    
    const successful = document.execCommand('copy')
    document.body.removeChild(textArea)
    
    if (successful) {
      showNotification('邀请链接已复制！快去分享吧', 'success')
    } else {
      showNotification('复制失败，请手动复制', 'error')
    }
  } catch (err) {
    showNotification('复制失败，请手动复制', 'error')
  }
}

const handleLogout = () => {
  localStorage.removeItem('token')
  router.push('/login')
}

onMounted(loadUser)
</script>

<template>
  <div class="min-h-screen relative overflow-hidden flex flex-col bg-[#0f1115]">
    <!-- Toast Notification -->
    <Transition name="toast">
      <div v-if="showToast" class="fixed top-6 left-1/2 transform -translate-x-1/2 z-50">
        <div :class="{
            'bg-red-500/80 text-white border-red-500/50 shadow-red-900/50': toastType === 'error',
            'bg-green-500/80 text-white border-green-500/50 shadow-green-900/50': toastType === 'success',
            'bg-blue-500/80 text-white border-blue-500/50 shadow-blue-900/50': toastType === 'info'
        }" class="flex items-center gap-3 px-6 py-3 rounded-xl border shadow-lg backdrop-blur-xl">
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
    
    <!-- Main Content -->
    <div class="flex-grow flex items-center justify-center p-4 relative z-10">
       <div class="absolute inset-0 overflow-hidden pointer-events-none">
          <div class="absolute top-1/4 left-1/4 w-96 h-96 bg-purple-500/10 rounded-full blur-[100px]"></div>
          <div class="absolute bottom-1/4 right-1/4 w-96 h-96 bg-cyan-500/10 rounded-full blur-[100px]"></div>
       </div>

       <div class="max-w-4xl w-full grid grid-cols-1 md:grid-cols-2 gap-8 items-center">
          <!-- Left: Info -->
          <div class="space-y-6">
             <h1 class="text-4xl md:text-5xl font-black text-white leading-tight">
               邀请好友<br/>
               <span class="text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-purple-400">共享 AI 创作之力</span>
             </h1>
             <p class="text-gray-400 text-lg leading-relaxed">
               每邀请一位好友注册，双方各得 <span class="text-white font-bold bg-white/10 px-2 py-0.5 rounded">¥3.00</span> 余额奖励。
               奖励无上限，邀请越多，创作越多。
             </p>
             
             <div class="flex flex-col gap-4">
               <div class="flex items-center gap-3 text-gray-300">
                  <div class="w-8 h-8 rounded-full bg-cyan-500/20 flex items-center justify-center text-cyan-400 border border-cyan-500/20">1</div>
                  <span>复制您的专属邀请链接</span>
               </div>
               <div class="flex items-center gap-3 text-gray-300">
                  <div class="w-8 h-8 rounded-full bg-purple-500/20 flex items-center justify-center text-purple-400 border border-purple-500/20">2</div>
                  <span>分享给好友或社交媒体</span>
               </div>
               <div class="flex items-center gap-3 text-gray-300">
                  <div class="w-8 h-8 rounded-full bg-green-500/20 flex items-center justify-center text-green-400 border border-green-500/20">3</div>
                  <span>好友注册，双方立即获得奖励</span>
               </div>
             </div>
          </div>
          
          <!-- Right: Card -->
          <div class="relative group">
              <div class="absolute -inset-1 bg-gradient-to-r from-cyan-500 to-purple-600 rounded-3xl blur opacity-30 group-hover:opacity-60 transition duration-1000"></div>
              <div class="relative bg-black/40 backdrop-blur-2xl border border-white/10 rounded-2xl p-8 shadow-2xl">
                  <div class="text-center mb-8">
                     <p class="text-sm text-gray-400 uppercase tracking-widest mb-2 font-bold">您的专属邀请码</p>
                     <div class="text-4xl font-mono font-bold text-white tracking-widest drop-shadow-lg">
                        {{ user?.invite_code || '---' }}
                     </div>
                  </div>
                  
                  <button 
                    @click="copyInviteCode"
                    class="w-full py-4 bg-white text-black rounded-xl font-bold text-lg hover:bg-gray-100 transition-all shadow-lg active:scale-95 flex items-center justify-center gap-2 group/btn"
                  >
                    <svg class="w-5 h-5 text-gray-600 group-hover/btn:scale-110 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"></path></svg>
                    复制邀请链接
                  </button>
                  
                  <div class="mt-6 pt-6 border-t border-white/10 text-center">
                     <p class="text-xs text-gray-500">已有 <span class="text-white font-bold">{{ user?.invited_count || 0 }}</span> 位好友通过您的邀请加入</p>
                  </div>
              </div>
          </div>
       </div>
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
