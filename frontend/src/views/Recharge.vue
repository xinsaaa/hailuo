<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getCurrentUser, createPayment, getPublicConfig, confirmPayment } from '../api'

const route = useRoute()
const router = useRouter()

// State
const user = ref(null)
const loading = ref(false)

// Toast 状态
const showToast = ref(false)
const toastMessage = ref('')
const toastType = ref('info')

// 系统配置
const config = ref({
  bonus_rate: 0.2,
  bonus_min_amount: 10,
  min_recharge: 0.01,
  max_recharge: 10000
})

// 鼠标跟随效果
const mouseX = ref(0)
const mouseY = ref(0)

const handleMouseMove = (e) => {
  mouseX.value = e.clientX
  mouseY.value = e.clientY
}

// 充值选项（赠送金额根据后端配置的bonus_rate动态计算）
const rechargeOptions = computed(() => {
  const rate = config.value.bonus_rate || 0.2
  const minAmount = config.value.bonus_min_amount || 10
  const amounts = [10, 30, 50, 100]
  const gradients = [
    'from-blue-500 to-cyan-500',
    'from-orange-500 to-red-500',
    'from-yellow-500 to-orange-500',
    'from-green-500 to-emerald-500'
  ]
  return amounts.map((amount, i) => ({
    amount,
    bonus: amount >= minAmount ? Math.round(amount * rate * 100) / 100 : 0,
    gradient: gradients[i],
    ...(amount === 100 ? { popular: true } : {})
  }))
})

// 自定义充值金额
const customAmount = ref(null)

const showNotification = (message, type = 'info') => {
  toastMessage.value = message
  toastType.value = type
  showToast.value = true
  setTimeout(() => { showToast.value = false }, 3000)
}

const handleLogout = () => {
  localStorage.removeItem('token')
  router.push('/login')
}

const handleRecharge = async (amount) => {
  loading.value = true
  try {
    const result = await createPayment(amount)
    window.location.href = result.pay_url
  } catch (err) {
    showNotification(err.response?.data?.detail || '创建支付订单失败', 'error')
    loading.value = false
  }
}

const handleCustomRecharge = async () => {
  const min = config.value.min_recharge
  if (!customAmount.value || customAmount.value < min) {
    showNotification(`最低充值金额为 ${min} 元`, 'error')
    return
  }
  handleRecharge(customAmount.value)
}

const checkPaymentStatus = async () => {
  const { out_trade_no, trade_no, trade_status, sign } = route.query
  if (out_trade_no && trade_no && trade_status && sign) {
    try {
      loading.value = true
      const result = await confirmPayment(route.query)
      if (result.status === 'success' || result.status === 'already_paid') {
        showNotification('充值成功！', 'success')
        user.value = await getCurrentUser()
        router.replace('/recharge')
      }
    } catch (err) {
      showNotification(err.response?.data?.detail || '支付确认失败', 'error')
    } finally {
      loading.value = false
    }
  }
}

onMounted(async () => {
  window.addEventListener('mousemove', handleMouseMove)
  try {
    const [userData, configData] = await Promise.all([
      getCurrentUser(),
      getPublicConfig().catch(() => null)
    ])
    user.value = userData
    if (configData) config.value = configData
    await checkPaymentStatus()
  } catch (err) {
    if (err.response?.status === 401) {
      router.push('/login')
    }
  }
})

onUnmounted(() => {
  window.removeEventListener('mousemove', handleMouseMove)
})
</script>

<template>
  <div class="min-h-screen relative overflow-hidden flex flex-col">
    <!-- Toast Notification -->
    <Transition name="toast">
      <div v-if="showToast" class="fixed top-6 left-1/2 transform -translate-x-1/2 z-50">
        <div :class="{
            'bg-red-500/80 text-white border-red-500/50 shadow-red-900/50': toastType === 'error',
            'bg-green-500/80 text-white border-green-500/50 shadow-green-900/50': toastType === 'success',
            'bg-blue-500/80 text-white border-blue-500/50 shadow-blue-900/50': toastType === 'info'
        }" class="flex items-center gap-3 px-6 py-3 rounded-xl border shadow-lg backdrop-blur-xl">
          <svg v-if="toastType === 'error'" xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
          </svg>
          <svg v-else-if="toastType === 'success'" xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
          </svg>
          <span class="font-medium text-sm">{{ toastMessage }}</span>
        </div>
      </div>
    </Transition>
    
    <!-- Navbar -->
    <nav class="relative z-20 px-8 py-4 border-b border-white/10 bg-black/20 backdrop-blur-md">
      <div class="max-w-7xl mx-auto flex justify-between items-center">
        <div class="text-2xl font-extrabold cursor-pointer flex items-center gap-2" @click="router.push('/dashboard')">
          <span class="text-white drop-shadow-md">大帝</span><span class="text-cyan-400 drop-shadow-md">AI</span>
        </div>
        <div class="flex items-center gap-6">
          <router-link to="/dashboard" class="text-sm text-gray-400 hover:text-white transition-colors">控制台</router-link>
          <router-link to="/invite" class="text-sm text-gray-400 hover:text-white transition-colors">邀请</router-link>
          <div v-if="user" class="text-sm text-gray-300 bg-black/40 px-4 py-2 rounded-xl border border-white/10 backdrop-blur-sm shadow-inner">
            余额: <span class="font-bold text-white text-shadow-sm">¥{{ user.balance.toFixed(2) }}</span>
          </div>
          <button @click="handleLogout" class="text-sm text-gray-300 hover:text-white transition-colors hover:drop-shadow-sm">退出</button>
        </div>
      </div>
    </nav>
    
    <!-- Main Content -->
    <div class="flex-grow flex items-center justify-center p-4 relative z-10">
      <div class="max-w-md w-full">
        <div class="relative group">
          <!-- 卡片发光边框 -->
          <div class="absolute -inset-1 bg-gradient-to-r from-cyan-500/30 via-purple-500/30 to-pink-500/30 rounded-3xl blur-xl opacity-50"></div>
          
          <div class="relative bg-black/40 backdrop-blur-xl border border-white/10 rounded-2xl p-8 shadow-2xl">
            <div class="text-center mb-8">
              <h1 class="text-2xl font-bold text-white mb-2">账户充值</h1>
              <p class="text-gray-400 text-sm">
                满<span class="text-cyan-400 font-bold">{{ config.bonus_min_amount }}</span>元送<span class="text-cyan-400 font-bold">{{ config.bonus_rate * 100 }}%</span>
              </p>
              <div class="mt-3 inline-flex items-center gap-2 bg-green-500/10 text-green-400 text-xs px-3 py-1.5 rounded-full border border-green-500/20">
                <svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M8.691 2.188C3.891 2.188 0 5.476 0 9.53c0 2.212 1.17 4.203 3.002 5.55a.59.59 0 0 1 .213.665l-.39 1.48c-.019.07-.048.141-.048.213 0 .163.13.295.29.295a.326.326 0 0 0 .167-.054l1.903-1.114a.864.864 0 0 1 .717-.098 10.16 10.16 0 0 0 2.837.403c.276 0 .543-.027.811-.05-.857-2.578.157-4.972 1.932-6.446 1.703-1.415 3.882-1.98 5.853-1.838-.576-3.583-4.196-6.348-8.596-6.348zM5.785 5.991c.642 0 1.162.529 1.162 1.18a1.17 1.17 0 0 1-1.162 1.178A1.17 1.17 0 0 1 4.623 7.17c0-.651.52-1.18 1.162-1.18zm5.813 0c.642 0 1.162.529 1.162 1.18a1.17 1.17 0 0 1-1.162 1.178 1.17 1.17 0 0 1-1.162-1.178c0-.651.52-1.18 1.162-1.18zm5.34 2.867c-1.797-.052-3.746.512-5.28 1.786-1.72 1.428-2.687 3.72-1.78 6.22.942 2.453 3.666 4.229 6.884 4.229.826 0 1.622-.12 2.361-.336a.722.722 0 0 1 .598.082l1.584.926a.272.272 0 0 0 .14.047c.134 0 .24-.111.24-.247 0-.06-.023-.12-.038-.177l-.327-1.233a.495.495 0 0 1-.01-.153.489.489 0 0 1 .186-.396C23.157 18.353 24 16.769 24 15.042c0-3.39-3.407-6.184-6.938-6.184zm-2.74 3.12c.535 0 .969.44.969.982a.976.976 0 0 1-.969.983.976.976 0 0 1-.969-.983c0-.542.434-.983.97-.983zm4.844 0c.535 0 .969.44.969.982a.976.976 0 0 1-.97.983.976.976 0 0 1-.968-.983c0-.542.433-.983.969-.983z"/>
                </svg>
                仅支持微信支付
              </div>
            </div>

            <div class="space-y-4">
              <button 
                v-for="opt in rechargeOptions" 
                :key="opt.amount"
                @click="handleRecharge(opt.amount)"
                :disabled="loading"
                class="w-full group/btn bg-white/5 hover:bg-white/10 border border-white/10 hover:border-white/20 rounded-xl p-4 transition-all duration-300 text-left hover:scale-[1.02] hover:shadow-lg hover:shadow-cyan-500/10"
              >
                <div class="flex justify-between items-center">
                  <div>
                    <div class="font-bold text-white text-lg">¥ {{ opt.amount }}</div>
                    <div :class="`text-xs font-semibold bg-gradient-to-r ${opt.gradient} bg-clip-text text-transparent`">
                      赠送 ¥{{ opt.bonus }}
                    </div>
                  </div>
                  <div class="h-10 w-10 rounded-full bg-white/5 flex items-center justify-center group-hover/btn:bg-cyan-500/20 transition-all duration-300 group-hover/btn:scale-110">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-gray-400 group-hover/btn:text-cyan-400 transition-colors" viewBox="0 0 20 20" fill="currentColor">
                      <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-11a1 1 0 10-2 0v2H7a1 1 0 100 2h2v2a1 1 0 102 0v-2h2a1 1 0 100-2h-2V7z" clip-rule="evenodd" />
                    </svg>
                  </div>
                </div>
              </button>
            </div>
            
            <!-- 自定义金额 -->
            <div class="mt-6 pt-6 border-t border-white/5">
              <label class="text-gray-400 text-xs uppercase tracking-wider font-bold mb-3 block">自定义金额</label>
              <div class="flex gap-2">
                <div class="flex-1 relative">
                  <span class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">¥</span>
                  <input 
                    v-model.number="customAmount" 
                    type="number"
                    :min="config.min_recharge"
                    :step="config.min_recharge"
                    :placeholder="String(config.min_recharge)"
                    class="w-full bg-white/5 border border-white/10 rounded-xl py-3 pl-8 pr-4 text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500/50 focus:ring-2 focus:ring-cyan-500/20 transition-all"
                  />
                </div>
                <button 
                  @click="handleCustomRecharge"
                  :disabled="loading || !customAmount || customAmount < config.min_recharge"
                  class="px-6 bg-gradient-to-r from-cyan-500 to-purple-500 text-white rounded-xl font-medium hover:opacity-90 disabled:opacity-40 transition-all flex items-center shadow-lg shadow-cyan-500/25 hover:shadow-cyan-500/40 hover:scale-105"
                >
                  <span v-if="loading" class="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full mr-2"></span>
                  {{ loading ? '处理中' : '充值' }}
                </button>
              </div>
              <Transition name="fade">
                <p v-if="customAmount >= config.bonus_min_amount" class="text-xs text-cyan-400 mt-2 flex items-center gap-1">
                  <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                    <path fill-rule="evenodd" d="M5 2a2 2 0 00-2 2v14l3.5-2 3.5 2 3.5-2 3.5 2V4a2 2 0 00-2-2H5zm2.5 3a1.5 1.5 0 100 3 1.5 1.5 0 000-3zm6.207.293a1 1 0 00-1.414 0l-6 6a1 1 0 101.414 1.414l6-6a1 1 0 000-1.414zM12.5 10a1.5 1.5 0 100 3 1.5 1.5 0 000-3z" clip-rule="evenodd" />
                  </svg>
                  将获得 ¥{{ (customAmount * config.bonus_rate).toFixed(2) }} 赠送
                </p>
              </Transition>
            </div>
            
            <div class="mt-6 pt-4 border-t border-white/5 text-center">
              <button @click="router.push('/dashboard')" class="text-sm text-gray-500 hover:text-white transition-colors flex items-center gap-2 mx-auto">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                  <path fill-rule="evenodd" d="M9.707 16.707a1 1 0 01-1.414 0l-6-6a1 1 0 010-1.414l6-6a1 1 0 011.414 1.414L5.414 9H17a1 1 0 110 2H5.414l4.293 4.293a1 1 0 010 1.414z" clip-rule="evenodd" />
                </svg>
                返回控制台
              </button>
            </div>
          </div>
        </div>
        
        <!-- 安全提示 -->
        <div class="mt-4 text-center">
          <p class="text-xs text-gray-600 flex items-center justify-center gap-1">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z" clip-rule="evenodd" />
            </svg>
            支付系统安全加密
          </p>
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

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
