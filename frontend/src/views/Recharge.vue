<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getCurrentUser, createPayment, getPublicConfig, confirmPayment, getTransactions } from '../api'

const route = useRoute()
const router = useRouter()

const user = ref(null)
const loading = ref(false)
const transactions = ref([])
const summary = ref({ total_recharge: 0, total_expense: 0, balance: 0 })
const showHistory = ref(false)

// Toast
const showToast = ref(false)
const toastMessage = ref('')
const toastType = ref('info')

// 配置
const config = ref({
  bonus_rate: 0.2,
  bonus_min_amount: 10,
  min_recharge: 0.01,
  max_recharge: 10000
})

// 选中金额
const selectedAmount = ref(null)
const customAmount = ref(null)

// 充值选项
const rechargeOptions = computed(() => {
  const rate = config.value.bonus_rate || 0.2
  const minAmount = config.value.bonus_min_amount || 10
  const amounts = [10, 30, 50, 100]
  return amounts.map((amount) => ({
    amount,
    bonus: amount >= minAmount ? Math.round(amount * rate * 100) / 100 : 0,
    popular: amount === 100
  }))
})

// 当前选中的实际金额和赠送
const currentBonus = computed(() => {
  const amount = selectedAmount.value || customAmount.value || 0
  if (amount >= config.value.bonus_min_amount) {
    return Math.round(amount * config.value.bonus_rate * 100) / 100
  }
  return 0
})

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

const selectAmount = (amount) => {
  selectedAmount.value = amount
  customAmount.value = null
}

const onCustomInput = () => {
  selectedAmount.value = null
}

const handlePay = async () => {
  const amount = selectedAmount.value || customAmount.value
  if (!amount) {
    showNotification('请选择或输入充值金额', 'error')
    return
  }
  const min = config.value.min_recharge
  const max = config.value.max_recharge
  if (amount < min) { showNotification(`最低充值 ${min} 元`, 'error'); return }
  if (amount > max) { showNotification(`单笔最高 ${max} 元`, 'error'); return }
  
  loading.value = true
  try {
    const result = await createPayment(amount)
    window.location.href = result.pay_url
  } catch (err) {
    showNotification(err.response?.data?.detail || '创建支付订单失败', 'error')
    loading.value = false
  }
}

const checkPaymentStatus = async () => {
  const { out_trade_no, trade_no, trade_status, sign } = route.query
  if (out_trade_no && trade_no && trade_status && sign) {
    try {
      loading.value = true
      const result = await confirmPayment(route.query)
      if (result.status === 'success' || result.status === 'already_paid') {
        showNotification('充值成功！余额已更新', 'success')
        user.value = await getCurrentUser()
        loadTransactions()
        router.replace('/recharge')
      }
    } catch (err) {
      showNotification(err.response?.data?.detail || '支付确认失败', 'error')
    } finally {
      loading.value = false
    }
  }
}

const loadTransactions = async () => {
  try {
    const data = await getTransactions()
    transactions.value = data.transactions || []
    summary.value = data.summary || summary.value
  } catch (e) {}
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

onMounted(async () => {
  try {
    const [userData, configData] = await Promise.all([
      getCurrentUser(),
      getPublicConfig().catch(() => null)
    ])
    user.value = userData
    if (configData) config.value = configData
    loadTransactions()
    await checkPaymentStatus()
  } catch (err) {
    if (err.response?.status === 401) router.push('/login')
  }
})
</script>

<template>
  <div class="min-h-screen relative overflow-hidden flex flex-col bg-[#0f1115]">
    <!-- Background -->
    <div class="fixed inset-0 z-0 pointer-events-none">
      <div class="absolute top-0 right-1/4 w-[500px] h-[500px] bg-cyan-900/15 rounded-full blur-[120px]"></div>
      <div class="absolute bottom-0 left-1/4 w-[500px] h-[500px] bg-purple-900/10 rounded-full blur-[120px]"></div>
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
          <router-link to="/invite" class="text-sm text-gray-400 hover:text-white transition-colors">邀请</router-link>
          <router-link to="/tickets" class="text-sm text-gray-400 hover:text-white transition-colors">工单</router-link>
          <div class="text-sm text-white font-bold border-b-2 border-cyan-500 pb-0.5">充值</div>
          <button @click="handleLogout" class="text-sm text-gray-300 hover:text-white transition-colors">退出</button>
        </div>
      </div>
    </nav>
    
    <!-- Main -->
    <div class="flex-grow w-full max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-10 relative z-10 space-y-8">
      
      <!-- 余额卡片 -->
      <div class="relative group">
        <div class="absolute -inset-0.5 bg-gradient-to-r from-cyan-500 to-purple-600 rounded-2xl blur opacity-20 group-hover:opacity-35 transition duration-500"></div>
        <div class="relative bg-[#1a1d24] border border-white/10 rounded-2xl p-6 md:p-8">
          <div class="flex flex-col md:flex-row md:items-center justify-between gap-6">
            <div>
              <p class="text-sm text-gray-400 mb-1">当前余额</p>
              <p class="text-4xl font-black text-white">¥{{ user?.balance?.toFixed(2) || '0.00' }}</p>
            </div>
            <div class="flex gap-6">
              <div class="text-center">
                <p class="text-xl font-bold text-green-400">¥{{ summary.total_recharge.toFixed(1) }}</p>
                <p class="text-xs text-gray-500 mt-0.5">累计充值</p>
              </div>
              <div class="w-px bg-white/10"></div>
              <div class="text-center">
                <p class="text-xl font-bold text-orange-400">¥{{ summary.total_expense.toFixed(1) }}</p>
                <p class="text-xs text-gray-500 mt-0.5">累计消费</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
        <!-- 左：充值面板 -->
        <div class="md:col-span-2 space-y-6">
          <!-- 快捷充值 -->
          <div class="bg-[#1a1d24]/80 border border-white/10 rounded-2xl p-6">
            <div class="flex items-center justify-between mb-5">
              <h2 class="text-lg font-bold text-white">选择充值金额</h2>
              <div class="flex items-center gap-1.5 text-xs text-cyan-400 bg-cyan-500/10 px-3 py-1 rounded-full border border-cyan-500/20">
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v13m0-13V6a2 2 0 112 2h-2zm0 0V5.5A2.5 2.5 0 109.5 8H12zm-7 4h14M5 12a2 2 0 110-4h14a2 2 0 110 4M5 12v7a2 2 0 002 2h10a2 2 0 002-2v-7"></path></svg>
                满{{ config.bonus_min_amount }}元送{{ (config.bonus_rate * 100).toFixed(0) }}%
              </div>
            </div>

            <div class="grid grid-cols-2 gap-3 mb-5">
              <button
                v-for="opt in rechargeOptions" :key="opt.amount"
                @click="selectAmount(opt.amount)"
                class="relative p-4 rounded-xl border-2 transition-all duration-200 text-left"
                :class="selectedAmount === opt.amount
                  ? 'border-cyan-500 bg-cyan-500/10 shadow-lg shadow-cyan-500/10'
                  : 'border-white/10 bg-white/[0.03] hover:border-white/20 hover:bg-white/[0.05]'"
              >
                <span v-if="opt.popular" class="absolute -top-2 -right-2 text-[10px] bg-gradient-to-r from-orange-500 to-red-500 text-white px-2 py-0.5 rounded-full font-bold">热门</span>
                <p class="text-xl font-black text-white mb-0.5">¥{{ opt.amount }}</p>
                <p v-if="opt.bonus > 0" class="text-xs text-cyan-400">送 ¥{{ opt.bonus }} · 到账 ¥{{ (opt.amount + opt.bonus).toFixed(2) }}</p>
                <p v-else class="text-xs text-gray-500">到账 ¥{{ opt.amount.toFixed(2) }}</p>
              </button>
            </div>

            <!-- 自定义金额 -->
            <div class="flex gap-3">
              <div class="flex-1 relative">
                <span class="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-500 font-bold">¥</span>
                <input
                  v-model.number="customAmount"
                  @input="onCustomInput"
                  type="number"
                  :min="config.min_recharge"
                  :placeholder="`自定义金额 (${config.min_recharge} - ${config.max_recharge})`"
                  class="w-full bg-white/5 border rounded-xl py-3 pl-9 pr-4 text-white placeholder-gray-600 focus:outline-none transition-all"
                  :class="customAmount && !selectedAmount ? 'border-cyan-500/50 ring-1 ring-cyan-500/20' : 'border-white/10'"
                />
              </div>
            </div>

            <Transition name="fade">
              <p v-if="currentBonus > 0" class="text-xs text-cyan-400 mt-2 flex items-center gap-1">
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v13m0-13V6a2 2 0 112 2h-2zm0 0V5.5A2.5 2.5 0 109.5 8H12zm-7 4h14M5 12a2 2 0 110-4h14a2 2 0 110 4M5 12v7a2 2 0 002 2h10a2 2 0 002-2v-7"></path></svg>
                将获得 ¥{{ currentBonus.toFixed(2) }} 赠送，实际到账 ¥{{ ((selectedAmount || customAmount || 0) + currentBonus).toFixed(2) }}
              </p>
            </Transition>

            <!-- 支付按钮 -->
            <button
              @click="handlePay"
              :disabled="loading || (!selectedAmount && !customAmount)"
              class="w-full mt-5 py-3.5 bg-gradient-to-r from-cyan-500 to-blue-600 text-white font-bold rounded-xl hover:brightness-110 disabled:opacity-40 disabled:cursor-not-allowed transition-all active:scale-[0.98] shadow-lg shadow-cyan-500/20 flex items-center justify-center gap-2"
            >
              <span v-if="loading" class="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full"></span>
              <svg v-else class="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
                <path d="M8.691 2.188C3.891 2.188 0 5.476 0 9.53c0 2.212 1.17 4.203 3.002 5.55a.59.59 0 0 1 .213.665l-.39 1.48c-.019.07-.048.141-.048.213 0 .163.13.295.29.295a.326.326 0 0 0 .167-.054l1.903-1.114a.864.864 0 0 1 .717-.098 10.16 10.16 0 0 0 2.837.403c.276 0 .543-.027.811-.05-.857-2.578.157-4.972 1.932-6.446 1.703-1.415 3.882-1.98 5.853-1.838-.576-3.583-4.196-6.348-8.596-6.348zM5.785 5.991c.642 0 1.162.529 1.162 1.18a1.17 1.17 0 0 1-1.162 1.178A1.17 1.17 0 0 1 4.623 7.17c0-.651.52-1.18 1.162-1.18zm5.813 0c.642 0 1.162.529 1.162 1.18a1.17 1.17 0 0 1-1.162 1.178 1.17 1.17 0 0 1-1.162-1.178c0-.651.52-1.18 1.162-1.18zm5.34 2.867c-1.797-.052-3.746.512-5.28 1.786-1.72 1.428-2.687 3.72-1.78 6.22.942 2.453 3.666 4.229 6.884 4.229.826 0 1.622-.12 2.361-.336a.722.722 0 0 1 .598.082l1.584.926a.272.272 0 0 0 .14.047c.134 0 .24-.111.24-.247 0-.06-.023-.12-.038-.177l-.327-1.233a.495.495 0 0 1-.01-.153.489.489 0 0 1 .186-.396C23.157 18.353 24 16.769 24 15.042c0-3.39-3.407-6.184-6.938-6.184zm-2.74 3.12c.535 0 .969.44.969.982a.976.976 0 0 1-.969.983.976.976 0 0 1-.969-.983c0-.542.434-.983.97-.983zm4.844 0c.535 0 .969.44.969.982a.976.976 0 0 1-.97.983.976.976 0 0 1-.968-.983c0-.542.433-.983.969-.983z"/>
              </svg>
              {{ loading ? '正在创建订单...' : '微信支付' }}
            </button>

            <p class="text-center text-xs text-gray-600 mt-3 flex items-center justify-center gap-1">
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"></path></svg>
              支付系统安全加密 · 仅支持微信支付
            </p>
          </div>
        </div>

        <!-- 右：充值说明 -->
        <div class="space-y-4">
          <div class="bg-[#1a1d24]/80 border border-white/10 rounded-2xl p-5">
            <h3 class="text-sm font-bold text-white mb-3 flex items-center gap-2">
              <svg class="w-4 h-4 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
              充值说明
            </h3>
            <ul class="space-y-2 text-xs text-gray-400">
              <li class="flex items-start gap-2">
                <span class="text-cyan-400 mt-0.5">&#8226;</span>
                充值满 <span class="text-white font-medium">{{ config.bonus_min_amount }}元</span> 赠送 <span class="text-cyan-400 font-medium">{{ (config.bonus_rate * 100).toFixed(0) }}%</span> 余额
              </li>
              <li class="flex items-start gap-2">
                <span class="text-cyan-400 mt-0.5">&#8226;</span>
                单笔充值范围 ¥{{ config.min_recharge }} ~ ¥{{ config.max_recharge }}
              </li>
              <li class="flex items-start gap-2">
                <span class="text-cyan-400 mt-0.5">&#8226;</span>
                充值余额用于AI视频生成服务
              </li>
              <li class="flex items-start gap-2">
                <span class="text-cyan-400 mt-0.5">&#8226;</span>
                支付完成后余额自动到账
              </li>
            </ul>
          </div>

          <div class="bg-[#1a1d24]/80 border border-white/10 rounded-2xl p-5">
            <h3 class="text-sm font-bold text-white mb-3 flex items-center gap-2">
              <svg class="w-4 h-4 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v13m0-13V6a2 2 0 112 2h-2zm0 0V5.5A2.5 2.5 0 109.5 8H12zm-7 4h14M5 12a2 2 0 110-4h14a2 2 0 110 4M5 12v7a2 2 0 002 2h10a2 2 0 002-2v-7"></path></svg>
              更多优惠
            </h3>
            <p class="text-xs text-gray-400 mb-3">邀请好友注册，双方各得 ¥3 奖励！</p>
            <router-link to="/invite" class="text-xs text-cyan-400 hover:text-cyan-300 font-medium flex items-center gap-1">
              前往邀请页面
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path></svg>
            </router-link>
          </div>
        </div>
      </div>

      <!-- 交易记录 -->
      <div class="bg-[#1a1d24]/80 backdrop-blur-xl border border-white/10 rounded-2xl overflow-hidden">
        <button
          @click="showHistory = !showHistory"
          class="w-full px-6 py-4 flex items-center justify-between hover:bg-white/[0.02] transition-colors"
        >
          <h3 class="text-base font-bold text-white flex items-center gap-2">
            <svg class="w-5 h-5 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"></path></svg>
            交易记录
          </h3>
          <div class="flex items-center gap-2">
            <span class="text-xs text-gray-500">{{ transactions.length }} 条</span>
            <svg class="w-4 h-4 text-gray-500 transition-transform" :class="showHistory ? 'rotate-180' : ''" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
          </div>
        </button>

        <Transition name="expand">
          <div v-if="showHistory">
            <div v-if="!transactions.length" class="px-6 py-10 text-center text-gray-500 text-sm border-t border-white/5">
              暂无交易记录
            </div>
            <div v-else class="divide-y divide-white/5 border-t border-white/5 max-h-80 overflow-y-auto">
              <div v-for="tx in transactions" :key="tx.id" class="px-6 py-3.5 flex items-center justify-between">
                <div class="flex items-center gap-3">
                  <div class="w-8 h-8 rounded-lg flex items-center justify-center"
                    :class="tx.type === 'recharge' ? 'bg-green-500/10' : 'bg-orange-500/10'">
                    <svg v-if="tx.type === 'recharge'" class="w-4 h-4 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path></svg>
                    <svg v-else class="w-4 h-4 text-orange-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 12H4"></path></svg>
                  </div>
                  <div>
                    <p class="text-sm text-white font-medium">{{ tx.type === 'recharge' ? '充值' : tx.type === 'expense' ? '消费' : tx.type === 'refund' ? '退款' : tx.type }}</p>
                    <p class="text-xs text-gray-600">{{ relativeTime(tx.created_at) }}</p>
                  </div>
                </div>
                <div class="text-right">
                  <p class="text-sm font-bold" :class="tx.type === 'recharge' ? 'text-green-400' : tx.type === 'refund' ? 'text-blue-400' : 'text-orange-400'">
                    {{ tx.type === 'expense' ? '-' : '+' }}¥{{ tx.amount.toFixed(2) }}
                  </p>
                  <p v-if="tx.bonus > 0" class="text-[10px] text-cyan-400">+¥{{ tx.bonus.toFixed(2) }} 赠送</p>
                </div>
              </div>
            </div>
          </div>
        </Transition>
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

.expand-enter-active,
.expand-leave-active {
  transition: all 0.3s ease;
  overflow: hidden;
}
.expand-enter-from,
.expand-leave-to {
  opacity: 0;
  max-height: 0;
}
.expand-enter-to,
.expand-leave-from {
  max-height: 500px;
}
</style>
