<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { sendEmailCode, forgotPassword } from '../api'

const router = useRouter()

const email = ref('')
const emailCode = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const loading = ref(false)
const emailCodeLoading = ref(false)
const emailCodeCountdown = ref(0)
const step = ref(1) // 1: 输入邮箱, 2: 输入验证码和新密码

// 提示消息
const showModal = ref(false)
const modalMessage = ref('')
const modalType = ref('error')

const showAlert = (message, type = 'error') => {
  modalMessage.value = message
  modalType.value = type
  showModal.value = true
  setTimeout(() => { showModal.value = false }, 3000)
}

// 发送验证码
const handleSendCode = async () => {
  if (!email.value) {
    showAlert('请输入邮箱地址')
    return
  }
  
  const emailRegex = /^[\w\.-]+@[\w\.-]+\.\w+$/
  if (!emailRegex.test(email.value)) {
    showAlert('请输入正确的邮箱格式')
    return
  }
  
  emailCodeLoading.value = true
  try {
    await sendEmailCode(email.value, 'reset_password')
    showAlert('验证码已发送，请查收邮件', 'success')
    step.value = 2
    
    // 倒计时
    emailCodeCountdown.value = 60
    const timer = setInterval(() => {
      emailCodeCountdown.value--
      if (emailCodeCountdown.value <= 0) {
        clearInterval(timer)
      }
    }, 1000)
  } catch (err) {
    showAlert(err.response?.data?.detail || '发送失败')
  } finally {
    emailCodeLoading.value = false
  }
}

// 重置密码
const handleResetPassword = async () => {
  if (!emailCode.value) {
    showAlert('请输入验证码')
    return
  }
  if (!newPassword.value || newPassword.value.length < 6) {
    showAlert('密码长度不能少于6位')
    return
  }
  if (newPassword.value !== confirmPassword.value) {
    showAlert('两次密码输入不一致')
    return
  }
  
  loading.value = true
  try {
    await forgotPassword(email.value, emailCode.value, newPassword.value)
    showAlert('密码重置成功！', 'success')
    setTimeout(() => {
      router.push('/login')
    }, 2000)
  } catch (err) {
    showAlert(err.response?.data?.detail || '重置失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
<div class="min-h-screen bg-gradient-to-br from-gray-900 via-slate-900 to-gray-900 flex items-center justify-center p-4">
  <!-- 提示弹窗 -->
  <Transition>
    <div v-if="showModal" 
      class="fixed top-6 left-1/2 -translate-x-1/2 z-50 px-6 py-3 rounded-xl shadow-xl backdrop-blur-md"
      :class="modalType === 'error' ? 'bg-red-500/90 text-white' : 'bg-green-500/90 text-white'"
    >
      {{ modalMessage }}
    </div>
  </Transition>

  <div class="w-full max-w-md">
    <div class="bg-white/5 backdrop-blur-xl rounded-2xl p-8 border border-white/10 shadow-2xl">
      <!-- 标题 -->
      <div class="text-center mb-8">
        <h1 class="text-2xl font-bold text-white mb-2">找回密码</h1>
        <p class="text-gray-400 text-sm">通过邮箱重置您的密码</p>
      </div>

      <!-- Step 1: 输入邮箱 -->
      <div v-if="step === 1" class="space-y-5">
        <div>
          <label class="block text-xs font-medium text-gray-400 uppercase tracking-wider mb-2">邮箱地址</label>
          <input 
            v-model="email"
            type="email" 
            placeholder="请输入注册时的邮箱" 
            class="w-full px-4 py-3.5 rounded-xl bg-black/20 border border-white/10 text-white placeholder-gray-500 outline-none focus:border-cyan-500/50 focus:ring-2 focus:ring-cyan-500/20 transition-all"
            @keyup.enter="handleSendCode"
          />
        </div>
        
        <button 
          @click="handleSendCode"
          :disabled="emailCodeLoading"
          class="w-full py-3.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-500 text-white font-semibold hover:opacity-90 transition-all disabled:opacity-50"
        >
          {{ emailCodeLoading ? '发送中...' : '获取验证码' }}
        </button>
      </div>

      <!-- Step 2: 输入验证码和新密码 -->
      <div v-else class="space-y-5">
        <div class="text-sm text-gray-400 mb-4">
          验证码已发送至 <span class="text-cyan-400">{{ email }}</span>
        </div>
        
        <div>
          <label class="block text-xs font-medium text-gray-400 uppercase tracking-wider mb-2">验证码</label>
          <div class="flex gap-3">
            <input 
              v-model="emailCode"
              type="text" 
              placeholder="请输入验证码" 
              class="flex-1 px-4 py-3.5 rounded-xl bg-black/20 border border-white/10 text-white placeholder-gray-500 outline-none focus:border-cyan-500/50 transition-all"
            />
            <button 
              @click="handleSendCode"
              :disabled="emailCodeCountdown > 0"
              class="px-4 py-3 rounded-xl bg-gray-700 text-white text-sm hover:bg-gray-600 transition-all disabled:opacity-50 whitespace-nowrap"
            >
              {{ emailCodeCountdown > 0 ? `${emailCodeCountdown}s` : '重新发送' }}
            </button>
          </div>
        </div>
        
        <div>
          <label class="block text-xs font-medium text-gray-400 uppercase tracking-wider mb-2">新密码</label>
          <input 
            v-model="newPassword"
            type="password" 
            placeholder="请输入新密码（至少6位）" 
            class="w-full px-4 py-3.5 rounded-xl bg-black/20 border border-white/10 text-white placeholder-gray-500 outline-none focus:border-cyan-500/50 transition-all"
          />
        </div>
        
        <div>
          <label class="block text-xs font-medium text-gray-400 uppercase tracking-wider mb-2">确认密码</label>
          <input 
            v-model="confirmPassword"
            type="password" 
            placeholder="请再次输入新密码" 
            class="w-full px-4 py-3.5 rounded-xl bg-black/20 border border-white/10 text-white placeholder-gray-500 outline-none focus:border-cyan-500/50 transition-all"
            @keyup.enter="handleResetPassword"
          />
        </div>
        
        <button 
          @click="handleResetPassword"
          :disabled="loading"
          class="w-full py-3.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-500 text-white font-semibold hover:opacity-90 transition-all disabled:opacity-50"
        >
          {{ loading ? '重置中...' : '重置密码' }}
        </button>
      </div>

      <!-- 返回登录 -->
      <div class="mt-6 text-center">
        <router-link to="/login" class="text-cyan-400 hover:text-cyan-300 text-sm">
          ← 返回登录
        </router-link>
      </div>
    </div>
  </div>
</div>
</template>

<style scoped>
.v-enter-active, .v-leave-active {
  transition: all 0.3s ease;
}
.v-enter-from, .v-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(-20px);
}
</style>
