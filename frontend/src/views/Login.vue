<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { login, register, getCaptcha, getSecurityStatus, sendEmailCode, getPublicConfig } from '../api'
import { useUserStore } from '../stores/user'
import SliderCaptcha from '../components/SliderCaptcha.vue'

const router = useRouter()
const userStore = useUserStore()

const isLoginMode = ref(true)
const siteConfig = ref({ allow_register: true, site_name: '大帝AI' })
const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const email = ref('')
const emailCode = ref('')
const emailCodeSent = ref(false)
const emailCodeLoading = ref(false)
const emailCodeCountdown = ref(0)
const loading = ref(false)

// 验证码相关（5参数加密）
const captchaRef = ref(null)
const captchaVerified = ref(false)
const captchaData = ref(null) // 后端返回的5参数加密数据
const captchaPosition = ref(0)
const needCaptcha = ref(false)

// 鼠标跟随效果
const mouseX = ref(0)

// 用户名验证（与后端规则保持一致：支持中文、字母、数字、下划线，最少3位）
const usernameError = ref('')
const validateUsername = (username) => {
  if (!username) {
    return '请输入用户名'
  }
  
  // 长度检查（与后端一致：3-20）
  if (username.length < 3) {
    return '用户名至少需要3个字符'
  }
  if (username.length > 20) {
    return '用户名不能超过20个字符'
  }
  
  // 字符检查 - 支持中文、字母、数字、下划线
  if (!/^[\u4e00-\u9fa5a-zA-Z0-9_]+$/.test(username)) {
    return '用户名只能包含中文、字母、数字和下划线'
  }
  
  // 不能全是数字
  if (/^\d+$/.test(username)) {
    return '用户名不能全是数字'
  }
  
  // 系统保留词检查（只禁止系统关键词，与后端一致）
  const forbiddenWords = ['admin', 'administrator', 'root', 'system']
  
  const usernameLower = username.toLowerCase()
  if (forbiddenWords.includes(usernameLower)) {
    return '该用户名为系统保留词，请换一个'
  }
  
  return ''
}
const mouseY = ref(0)

// 邀请码（从 URL 参数获取）
const inviteCode = ref('')

// 生成增强版设备指纹（收集更多特征用于风控）
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
    navigator.hardwareConcurrency || 0,  // CPU 核心数
    navigator.deviceMemory || 0,  // 设备内存
    navigator.maxTouchPoints || 0,  // 触控点数
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
  
  // 从 URL 提取邀请码（如 ?invite=ABC123）
  const urlParams = new URLSearchParams(window.location.search)
  const urlInviteCode = urlParams.get('invite')
  if (urlInviteCode) {
    inviteCode.value = urlInviteCode
    isLoginMode.value = false // 有邀请码自动切换到注册模式
    console.log('[Login] 检测到邀请码:', urlInviteCode)
  }
  
  // 加载公共配置
  try {
    const cfg = await getPublicConfig()
    if (cfg) siteConfig.value = { ...siteConfig.value, ...cfg }
    if (!cfg.allow_register && !isLoginMode.value) isLoginMode.value = true
  } catch (e) {}
  
  // 首次加载等待后端服务就绪
  await new Promise(resolve => setTimeout(resolve, 500))
  
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
  if (!isLoginMode.value) {
    isLoginMode.value = true
  } else {
    if (!siteConfig.value.allow_register) {
      showAlert('系统暂未开放注册', 'error')
      return
    }
    isLoginMode.value = false
  }
}

const showAlert = (message, type = 'error') => {
  modalMessage.value = message
  modalType.value = type
  showModal.value = true
  setTimeout(() => { showModal.value = false }, 3000)
}

// 发送邮箱验证码
const handleSendEmailCode = async () => {
  if (!email.value) {
    showAlert('请先输入邮箱地址')
    return
  }
  
  // 验证邮箱格式
  const emailRegex = /^[\w\.-]+@[\w\.-]+\.\w+$/
  if (!emailRegex.test(email.value)) {
    showAlert('请输入正确的邮箱格式')
    return
  }
  
  emailCodeLoading.value = true
  try {
    await sendEmailCode(email.value, 'register')
    emailCodeSent.value = true
    showAlert('验证码已发送，请查收邮件', 'success')
    
    // 开始倒计时 60 秒
    emailCodeCountdown.value = 60
    const timer = setInterval(() => {
      emailCodeCountdown.value--
      if (emailCodeCountdown.value <= 0) {
        clearInterval(timer)
        emailCodeSent.value = false
      }
    }, 1000)
  } catch (err) {
    showAlert(err.response?.data?.detail || '发送失败，请稍后重试')
  } finally {
    emailCodeLoading.value = false
  }
}

// 是否显示验证码
const showCaptchaComponent = computed(() => {
  return !isLoginMode.value || needCaptcha.value
})

// 监听用户名变化，实时验证
watch(username, (newValue) => {
  if (!isLoginMode.value && newValue) {
    usernameError.value = validateUsername(newValue)
  } else {
    usernameError.value = ''
  }
})

const handleSubmit = async () => {
  if (!username.value || !password.value) {
    showAlert('请填写用户名和密码')
    return
  }
  
  // 注册时验证用户名格式
  if (!isLoginMode.value) {
    const usernameValidationError = validateUsername(username.value)
    if (usernameValidationError) {
      showAlert(usernameValidationError)
      return
    }
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
      // 注册：验证邮箱和邮箱验证码
      if (!email.value || !emailCode.value) {
        showAlert('请填写邮箱并获取验证码')
        loading.value = false
        return
      }
      result = await register(
        username.value,
        email.value,
        emailCode.value,
        password.value,
        captchaData.value,
        captchaPosition.value,
        generateFingerprint(),  // 设备指纹
        inviteCode.value || null  // 邀请码
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
  <div class="min-h-screen flex items-center justify-center relative overflow-hidden">
    <!-- Toast Alert -->
    <Transition name="toast">
      <div v-if="showModal" class="fixed top-6 left-1/2 transform -translate-x-1/2 z-50">
        <div :class="modalType === 'error' ? 'bg-red-500/80 text-white border-red-500/50 shadow-red-900/50' : 'bg-green-500/80 text-white border-green-500/50 shadow-green-900/50'" 
             class="flex items-center gap-3 px-6 py-3 rounded-xl border shadow-lg backdrop-blur-xl">
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
      <div class="absolute -inset-1 bg-gradient-to-br from-cyan-500/20 to-blue-500/20 rounded-3xl opacity-40 blur-2xl"></div>
      
      <div class="relative bg-white/5 border border-white/10 border-t-white/20 p-10 rounded-3xl shadow-2xl backdrop-blur-3xl">
        
        <!-- Logo -->
        <div class="text-center mb-8">
          <div class="text-3xl font-extrabold mb-2 flex justify-center items-center gap-2">
            <span class="text-white drop-shadow-md">大帝</span><span class="text-cyan-400 drop-shadow-md">AI</span>
          </div>
          <p class="text-gray-400 text-sm">
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
              :class="[
                'w-full px-4 py-3.5 rounded-xl bg-black/20 border text-white placeholder-gray-500 outline-none transition-all shadow-inner backdrop-blur-sm',
                !isLoginMode && usernameError 
                  ? 'border-red-500/50 focus:border-red-500/70 focus:ring-2 focus:ring-red-500/20' 
                  : 'border-white/10 focus:border-cyan-500/50 focus:ring-2 focus:ring-cyan-500/20'
              ]"
              @keyup.enter="handleSubmit"
            />
            <!-- 用户名错误提示 -->
            <div v-if="!isLoginMode && usernameError" class="mt-2 text-red-400 text-xs flex items-center gap-1">
              <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
              </svg>
              {{ usernameError }}
            </div>
            
            <!-- 用户名格式说明 -->
            <div v-if="!isLoginMode && !usernameError && username" class="mt-2 text-green-400 text-xs flex items-center gap-1">
              <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
              </svg>
              用户名格式正确
            </div>
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-400 uppercase tracking-wider mb-2">密码</label>
            <input 
              v-model="password"
              type="password" 
              placeholder="请输入密码" 
              class="w-full px-4 py-3.5 rounded-xl bg-black/20 border border-white/10 text-white placeholder-gray-500 outline-none focus:border-cyan-500/50 focus:ring-2 focus:ring-cyan-500/20 transition-all shadow-inner backdrop-blur-sm"
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
          
          <!-- 邮箱（注册时必填） -->
          <div v-if="!isLoginMode">
            <label class="block text-xs font-medium text-gray-400 uppercase tracking-wider mb-2">邮箱</label>
            <input 
              v-model="email"
              type="email" 
              placeholder="请输入邮箱地址" 
              class="w-full px-4 py-3.5 rounded-xl bg-white/5 border border-white/10 text-white placeholder-gray-500 outline-none focus:border-cyan-500/50 focus:ring-2 focus:ring-cyan-500/20 transition-all"
            />
          </div>
          
          <!-- 邮箱验证码 -->
          <div v-if="!isLoginMode">
            <label class="block text-xs font-medium text-gray-400 uppercase tracking-wider mb-2">邮箱验证码</label>
            <div class="flex gap-3">
              <input 
                v-model="emailCode"
                type="text" 
                placeholder="请输入验证码" 
                class="flex-1 px-4 py-3.5 rounded-xl bg-white/5 border border-white/10 text-white placeholder-gray-500 outline-none focus:border-cyan-500/50 focus:ring-2 focus:ring-cyan-500/20 transition-all"
              />
              <button 
                type="button"
                @click="handleSendEmailCode"
                :disabled="emailCodeLoading || emailCodeCountdown > 0"
                class="px-4 py-3 rounded-xl bg-cyan-600/80 text-white text-sm font-medium hover:bg-cyan-500 transition-all disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
              >
                {{ emailCodeCountdown > 0 ? `${emailCodeCountdown}s` : (emailCodeLoading ? '发送中...' : '获取验证码') }}
              </button>
            </div>
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
        
        <!-- Forgot Password Link (login mode only) -->
        <div v-if="isLoginMode" class="mt-3 text-center">
          <router-link to="/forgot-password" class="text-sm text-gray-500 hover:text-cyan-400 transition-colors">
            忘记密码?
          </router-link>
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
