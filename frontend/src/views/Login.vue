<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { login, register, getCaptcha, getSecurityStatus } from '../api'
import { useUserStore } from '../stores/user'
import SliderCaptcha from '../components/SliderCaptcha.vue'

const router = useRouter()
const userStore = useUserStore()

const isLoginMode = ref(true)
const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const loading = ref(false)

// 验证码相关（5参数加密）
const captchaRef = ref(null)
const captchaVerified = ref(false)
const captchaData = ref(null) // 后端返回的5参数加密数据
const captchaPosition = ref(0)
const needCaptcha = ref(false)

// 鼠标跟随效果
const mouseX = ref(0)
const mouseY = ref(0)

const handleMouseMove = (e) => {
  mouseX.value = e.clientX
  mouseY.value = e.clientY
}

// 解密后端加密的 target（加密方式：target ^ 0x5A，Base64）
const decryptHint = (hint) => {
  try {
    const decoded = atob(hint)
    const encrypted = decoded.charCodeAt(0)
    // 逆运算：直接异或 0x5A
    return encrypted ^ 0x5A
  } catch {
    return 50 // 默认值
  }
}

// 加载验证码（获取加密的6参数）
const loadCaptcha = async () => {
  // 先重置状态，避免残留旧值
  captchaVerified.value = false
  captchaPosition.value = 0
  
  try {
    const data = await getCaptcha()
    // 解密 hint 得到 target
    data.target = decryptHint(data.hint)
    captchaData.value = data
    console.log('[Captcha] 加载成功, target=', data.target)
  } catch (err) {
    console.error('Failed to load captcha:', err)
  }
}

// 检查是否需要验证码
const checkSecurityStatus = async () => {
  try {
    const status = await getSecurityStatus()
    needCaptcha.value = status.need_captcha
    // 只在需要验证码且未验证成功时加载（避免覆盖已完成的验证码）
    if ((status.need_captcha || !isLoginMode.value) && !captchaVerified.value) {
      await loadCaptcha()
    }
  } catch (err) {
    console.error('Failed to check security status:', err)
    // 默认加载验证码以防万一
    if (!captchaVerified.value) {
      await loadCaptcha()
    }
  }
}

// 首次加载时的初始化
const initRetryCount = ref(0)
const maxInitRetries = 2

onMounted(async () => {
  window.addEventListener('mousemove', handleMouseMove)
  
  // 首次加载等待后端服务就绪
  await new Promise(resolve => setTimeout(resolve, 1500))
  
  try {
    await checkSecurityStatus()
  } catch (err) {
    console.log('[Login] 首次加载失败，尝试重试...')
    // 如果首次加载失败，等待2秒后刷新重试
    if (initRetryCount.value < maxInitRetries) {
      initRetryCount.value++
      await new Promise(resolve => setTimeout(resolve, 2000))
      window.location.reload()
    }
  }
})

onUnmounted(() => {
  window.removeEventListener('mousemove', handleMouseMove)
})

// 切换模式时重置
watch(isLoginMode, async () => {
  captchaVerified.value = false
  captchaPosition.value = 0
  await checkSecurityStatus()
})

const onCaptchaSuccess = (position) => {
  captchaVerified.value = true
  captchaPosition.value = position
}

const onCaptchaFail = async () => {
  captchaVerified.value = false
  captchaPosition.value = 0
  await loadCaptcha()
}

// 弹窗状态
const showModal = ref(false)
const modalMessage = ref('')
const modalType = ref('error')

const buttonText = computed(() => {
  if (loading.value) return '处理中...'
  return isLoginMode.value ? '登录' : '注册'
})

const toggleMode = () => {
  isLoginMode.value = !isLoginMode.value
}

const showAlert = (message, type = 'error') => {
  modalMessage.value = message
  modalType.value = type
  showModal.value = true
  setTimeout(() => { showModal.value = false }, 3000)
}

// 是否显示验证码
const showCaptchaComponent = computed(() => {
  return !isLoginMode.value || needCaptcha.value
})

const handleSubmit = async () => {
  if (!username.value || !password.value) {
    showAlert('请填写用户名和密码')
    return
  }
  
  if (!isLoginMode.value && password.value !== confirmPassword.value) {
    showAlert('两次密码输入不一致')
    return
  }
  
  // 验证码检查
  if (showCaptchaComponent.value && !captchaVerified.value) {
    showAlert('请先完成滑块验证')
    return
  }
  
  loading.value = true
  
  try {
    let result
    if (isLoginMode.value) {
      // 登录（带或不带验证码）
      result = await login(
        username.value, 
        password.value,
        needCaptcha.value ? captchaData.value : null,
        needCaptcha.value ? captchaPosition.value : null
      )
    } else {
      // 注册（必须带验证码）
      result = await register(
        username.value, 
        password.value,
        captchaData.value,
        captchaPosition.value
      )
    }
    userStore.login(null, result.access_token)
    router.push('/dashboard')
  } catch (err) {
    const detail = err.response?.data?.detail || '操作失败，请重试'
    showAlert(detail)
    // 重新加载验证码
    await loadCaptcha()
    captchaVerified.value = false
    await checkSecurityStatus()
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-[#0a0a0f] relative overflow-hidden">
    
    <!-- 动态网格背景 -->
    <div class="absolute inset-0 bg-[linear-gradient(rgba(6,182,212,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(6,182,212,0.03)_1px,transparent_1px)] bg-[size:50px_50px]"></div>
    
    <!-- 鼠标跟随小球 -->
    <div 
      class="pointer-events-none fixed w-[500px] h-[500px] rounded-full bg-gradient-to-r from-cyan-500/20 to-purple-500/20 blur-[100px] transition-all duration-700 ease-out"
      :style="{ left: mouseX - 250 + 'px', top: mouseY - 250 + 'px' }"
    ></div>

    <!-- Toast Alert -->
    <Transition name="toast">
      <div v-if="showModal" class="fixed top-6 left-1/2 transform -translate-x-1/2 z-50">
        <div :class="modalType === 'error' ? 'bg-red-500/20 text-red-400 border-red-500/30' : 'bg-green-500/20 text-green-400 border-green-500/30'" 
             class="flex items-center gap-3 px-6 py-3 rounded-xl border backdrop-blur-xl">
          <svg v-if="modalType === 'error'" xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
          </svg>
          <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
          </svg>
          <span class="font-medium text-sm">{{ modalMessage }}</span>
        </div>
      </div>
    </Transition>
    
    <!-- Login Card -->
    <div class="relative z-10 w-full max-w-md mx-4">
      <div class="absolute -inset-0.5 bg-gradient-to-r from-cyan-500 via-purple-500 to-pink-500 rounded-3xl opacity-30 blur"></div>
      
      <div class="relative bg-[#12121a] border border-white/10 p-10 rounded-3xl shadow-2xl">
        
        <!-- Logo -->
        <div class="text-center mb-8">
          <div class="text-3xl font-extrabold mb-2">
            <span class="text-white">大帝</span><span class="text-cyan-400">AI</span>
          </div>
          <p class="text-gray-500 text-sm">
            {{ isLoginMode ? '登录开启你的 AI 创作之旅' : '注册即可免费体验 AI 创作' }}
          </p>
        </div>
        
        <!-- Form -->
        <div class="space-y-5">
          <div>
            <label class="block text-xs font-medium text-gray-400 uppercase tracking-wider mb-2">用户名</label>
            <input 
              v-model="username"
              type="text" 
              placeholder="请输入用户名" 
              class="w-full px-4 py-3.5 rounded-xl bg-white/5 border border-white/10 text-white placeholder-gray-500 outline-none focus:border-cyan-500/50 focus:ring-2 focus:ring-cyan-500/20 transition-all"
              @keyup.enter="handleSubmit"
            />
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-400 uppercase tracking-wider mb-2">密码</label>
            <input 
              v-model="password"
              type="password" 
              placeholder="请输入密码" 
              class="w-full px-4 py-3.5 rounded-xl bg-white/5 border border-white/10 text-white placeholder-gray-500 outline-none focus:border-cyan-500/50 focus:ring-2 focus:ring-cyan-500/20 transition-all"
              @keyup.enter="handleSubmit"
            />
          </div>
          <div v-if="!isLoginMode">
            <label class="block text-xs font-medium text-gray-400 uppercase tracking-wider mb-2">确认密码</label>
            <input 
              v-model="confirmPassword"
              type="password" 
              placeholder="请再次输入密码" 
              class="w-full px-4 py-3.5 rounded-xl bg-white/5 border border-white/10 text-white placeholder-gray-500 outline-none focus:border-cyan-500/50 focus:ring-2 focus:ring-cyan-500/20 transition-all"
              @keyup.enter="handleSubmit"
            />
          </div>
          
          <!-- 滑块验证码（后端加密参数，前端解密后使用） -->
          <div v-if="showCaptchaComponent && captchaData" class="pt-2">
            <SliderCaptcha 
              ref="captchaRef"
              :target="captchaData.target"
              @success="onCaptchaSuccess" 
              @fail="onCaptchaFail" 
            />
          </div>
          
          <!-- 安全提示 -->
          <div v-if="isLoginMode && needCaptcha" class="text-xs text-yellow-400/80">
            检测到异常登录，请完成验证
          </div>
        </div>
        
        <!-- Submit Button -->
        <button 
          type="button"
          @click="handleSubmit"
          :disabled="loading"
          class="w-full mt-8 py-4 bg-white text-gray-900 rounded-xl font-semibold text-lg transition-all duration-300 hover:bg-gray-100 disabled:opacity-50 flex justify-center items-center gap-2 shadow-lg"
        >
          <span v-if="loading" class="animate-spin h-5 w-5 border-2 border-gray-900 border-t-transparent rounded-full"></span>
          {{ buttonText }}
        </button>
        
        <!-- Toggle Mode -->
        <div class="mt-6 text-center text-sm text-gray-500">
          <template v-if="isLoginMode">
            还没有账号? 
            <button type="button" @click="toggleMode" class="text-cyan-400 font-medium hover:text-cyan-300 transition-all">立即注册</button>
          </template>
          <template v-else>
            已有账号? 
            <button type="button" @click="toggleMode" class="text-cyan-400 font-medium hover:text-cyan-300 transition-all">直接登录</button>
          </template>
        </div>
        
        <!-- Back to Home -->
        <div class="mt-4 text-center">
          <router-link to="/" class="text-xs text-gray-600 hover:text-gray-400 transition-colors">← 返回首页</router-link>
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
