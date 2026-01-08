<script setup>
import { ref, onMounted, computed } from 'vue'
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

// 动态计算充值选项
const rechargeOptions = computed(() => {
  const rate = config.value.bonus_rate
  const minAmount = config.value.bonus_min_amount
  return [
    { amount: 10, bonus: 10 >= minAmount ? (10 * rate).toFixed(2) : 0, gradient: 'from-orange-500 to-red-500' },
    { amount: 50, bonus: 50 >= minAmount ? (50 * rate).toFixed(2) : 0, gradient: 'from-yellow-500 to-orange-500' },
    { amount: 100, bonus: 100 >= minAmount ? (100 * rate).toFixed(2) : 0, gradient: 'from-green-500 to-emerald-500' },
  ]
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
        // 重新加载用户信息以更新余额
        user.value = await getCurrentUser()
        // 清除 URL 参数
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
  try {
    const [userData, configData] = await Promise.all([
      getCurrentUser(),
      getPublicConfig().catch(() => null)
    ])
    user.value = userData
    if (configData) config.value = configData
    
    // 检查支付回调
    await checkPaymentStatus()
  } catch (err) {
    if (err.response?.status === 401) {
      router.push('/login')
    }
  }
})
</script>

<template>
  <div class="min-h-screen bg-[#0a0a0f] text-white">
    <!-- Navbar -->
    <nav class="relative z-20 px-8 py-4 border-b border-white/5">
      <div class="max-w-7xl mx-auto flex justify-between items-center">
        <div class="text-2xl font-extrabold cursor-pointer flex items-center gap-2" @click="router.push('/')">
          <span class="text-white">大帝</span><span class="text-cyan-400">AI</span>
        </div>
        <div class="flex items-center gap-6">
          <div v-if="user" class="text-sm text-gray-400 bg-white/5 px-4 py-2 rounded-xl border border-white/10">
            余额: <span class="font-bold text-white">¥{{ user.balance.toFixed(2) }}</span>
          </div>
          <button @click="handleLogout" class="text-sm text-gray-500 hover:text-white transition-colors">退出</button>
        </div>
      </div>
    </nav>
    
    <!-- Main Content -->
    <div class="flex-grow flex items-center justify-center p-4">
      <div class="max-w-md w-full bg-[#12121a] border border-white/10 rounded-2xl p-8">
        <div class="text-center mb-8">
          <h1 class="text-2xl font-bold mb-2">账户充值</h1>
          <p class="text-gray-400 text-sm">满{{ config.bonus_min_amount }}元送{{ config.bonus_rate * 100 }}%</p>
        </div>

        <div class="space-y-4">
          <button 
            v-for="opt in rechargeOptions" 
            :key="opt.amount"
            @click="handleRecharge(opt.amount)"
            :disabled="loading"
            class="w-full group bg-white/5 hover:bg-white/10 border border-white/10 hover:border-white/20 rounded-xl p-4 transition-all text-left"
          >
            <div class="flex justify-between items-center">
              <div>
                <div class="font-bold text-lg">¥ {{ opt.amount }}</div>
                <div class="text-xs font-semibold text-cyan-400">
                  赠送 ¥{{ opt.bonus }}
                </div>
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
                :placeholder="config.min_recharge"
                class="w-full bg-white/5 border border-white/10 rounded-xl py-3 pl-8 pr-4 text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500/50"
              />
            </div>
            <button 
              @click="handleCustomRecharge"
              :disabled="loading || !customAmount || customAmount < config.min_recharge"
              class="px-6 bg-cyan-600 text-white rounded-xl font-medium hover:bg-cyan-500 disabled:opacity-40 transition-all flex items-center"
            >
              {{ loading ? '...' : '充值' }}
            </button>
          </div>
          <p v-if="customAmount >= config.bonus_min_amount" class="text-xs text-cyan-400 mt-2">
            将获得 ¥{{ (customAmount * config.bonus_rate).toFixed(2) }} 赠送
          </p>
        </div>
        
        <div class="mt-6 text-center">
           <button @click="router.push('/')" class="text-sm text-gray-500 hover:text-white transition-colors">返回</button>
        </div>
      </div>
    </div>

    <!-- Toast Notification -->
    <Transition name="toast">
      <div v-if="showToast" class="fixed top-6 left-1/2 transform -translate-x-1/2 z-50">
        <div class="bg-gray-800 text-white px-6 py-3 rounded-xl border border-gray-700">
          <span class="font-medium text-sm">{{ toastMessage }}</span>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.toast-enter-active,
.toast-leave-active {
  transition: all 0.4s ease;
}
.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translate(-50%, -20px);
}
</style>
