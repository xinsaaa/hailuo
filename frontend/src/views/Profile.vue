<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { getCurrentUser, getTransactions, getOrders, getInviteStats, getPublicConfig } from '../api'

const router = useRouter()
const siteName = ref(localStorage.getItem('site_name') || '大帝AI')

const user = ref(null)
const transactions = ref([])
const summary = ref({ total_recharge: 0, total_expense: 0, balance: 0 })
const orders = ref([])
const inviteStats = ref(null)
const loading = ref(true)

const formattedBalance = computed(() => user.value ? user.value.balance.toFixed(2) : '0.00')
const isLowBalance = computed(() => user.value && user.value.balance < 5)

const activeTab = ref('transactions')

const formatTime = (utcStr) => {
  if (!utcStr) return ''
  const date = new Date(utcStr + (utcStr.endsWith('Z') ? '' : 'Z'))
  return date.toLocaleString()
}

const orderStats = computed(() => {
  const total = orders.value.length
  const completed = orders.value.filter(o => o.status === 'completed').length
  const failed = orders.value.filter(o => o.status === 'failed').length
  const processing = orders.value.filter(o => ['pending', 'processing', 'generating'].includes(o.status)).length
  return { total, completed, failed, processing }
})

const loadData = async () => {
  loading.value = true
  try {
    const [userData, txData, ordersData, inviteData] = await Promise.all([
      getCurrentUser(),
      getTransactions(),
      getOrders(),
      getInviteStats().catch(() => null)
    ])
    user.value = userData
    transactions.value = txData.transactions || []
    summary.value = txData.summary || { total_recharge: 0, total_expense: 0, balance: 0 }
    orders.value = ordersData || []
    inviteStats.value = inviteData
  } catch (err) {
    if (err.response?.status === 401) router.push('/login')
  } finally {
    loading.value = false
  }
}

const handleLogout = () => {
  localStorage.removeItem('token')
  router.push('/login')
}

const copyInviteLink = () => {
  if (!user.value?.invite_code) return
  const link = `${window.location.origin}/login?invite=${user.value.invite_code}`
  navigator.clipboard.writeText(link).then(() => {
    showToastMsg('邀请链接已复制', 'success')
  }).catch(() => {
    showToastMsg('复制失败', 'error')
  })
}

const showToast = ref(false)
const toastMessage = ref('')
const toastType = ref('info')
const showToastMsg = (msg, type = 'info') => {
  toastMessage.value = msg
  toastType.value = type
  showToast.value = true
  setTimeout(() => { showToast.value = false }, 3000)
}

onMounted(() => {
  loadData()
})
</script>

<template>
  <div class="min-h-screen relative overflow-hidden flex flex-col bg-[#0a0b0e]">
    <!-- Toast -->
    <Transition name="toast">
      <div v-if="showToast" class="fixed top-6 left-1/2 transform -translate-x-1/2 z-50">
        <div :class="{
          'bg-red-500/80 text-white border-red-500/50': toastType === 'error',
          'bg-green-500/80 text-white border-green-500/50': toastType === 'success',
          'bg-blue-500/80 text-white border-blue-500/50': toastType === 'info'
        }" class="flex items-center gap-3 px-6 py-3 rounded-xl border shadow-lg backdrop-blur-xl">
          <span class="font-medium text-sm">{{ toastMessage }}</span>
        </div>
      </div>
    </Transition>

    <!-- Navbar -->
    <nav class="relative z-20 px-8 py-4 border-b border-white/10 bg-black/20 backdrop-blur-md">
      <div class="max-w-7xl mx-auto flex justify-between items-center">
        <div class="text-2xl font-extrabold cursor-pointer flex items-center gap-2" @click="router.push('/')">
          <span class="text-white drop-shadow-md">{{ siteName }}</span>
        </div>
        <div class="flex items-center gap-6">
          <router-link to="/dashboard" class="text-sm text-gray-400 hover:text-white transition-colors">海螺AI</router-link>
          <router-link to="/kling" class="text-sm text-gray-400 hover:text-white transition-colors">可灵AI</router-link>
          <router-link to="/tickets" class="flex items-center gap-1.5 px-3 py-1.5 text-sm text-amber-400/90 hover:text-amber-300 bg-amber-500/10 hover:bg-amber-500/15 border border-amber-500/20 hover:border-amber-500/30 rounded-lg transition-all">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"/>
            </svg>
            工单
          </router-link>
          <button 
            @click="router.push('/recharge')"
            class="px-4 py-1.5 bg-gradient-to-r from-cyan-600 to-blue-600 shadow-cyan-900/40 text-white text-xs font-bold rounded-lg hover:brightness-110 transition-all shadow-lg"
          >
            充值
          </button>
          <button @click="handleLogout" class="text-sm text-gray-300 hover:text-white transition-colors">退出</button>
        </div>
      </div>
    </nav>

    <!-- Loading -->
    <div v-if="loading" class="flex-grow flex items-center justify-center">
      <div class="w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin"></div>
    </div>

    <!-- Main Content -->
    <div v-else class="flex-grow max-w-5xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-10 relative z-10">
      <div class="space-y-8">

        <!-- 用户信息卡片 -->
        <div class="relative">
          <div class="absolute -inset-1 rounded-3xl blur-2xl opacity-40 bg-gradient-to-br from-cyan-500/20 to-blue-500/20"></div>
          <div class="relative bg-white/5 backdrop-blur-3xl border border-white/10 border-t-white/20 rounded-3xl p-8 shadow-2xl">
            <div class="flex items-start justify-between">
              <!-- 左侧用户信息 -->
              <div class="flex items-center gap-6">
                <div class="w-20 h-20 rounded-2xl bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-900/30">
                  <span class="text-3xl font-bold text-white">{{ user?.username?.[0]?.toUpperCase() || 'U' }}</span>
                </div>
                <div>
                  <h1 class="text-2xl font-bold text-white mb-1">{{ user?.username }}</h1>
                  <p class="text-sm text-gray-400 mb-2">{{ user?.email || '未绑定邮箱' }}</p>
                  <p class="text-xs text-gray-500">注册时间: {{ formatTime(user?.created_at) }}</p>
                </div>
              </div>
              <!-- 右侧余额 -->
              <div class="text-right">
                <p class="text-xs text-gray-500 mb-1">账户余额</p>
                <p class="text-4xl font-extrabold mb-3" :class="isLowBalance ? 'text-red-400' : 'text-white'">
                  <span class="text-lg text-gray-400 mr-1">¥</span>{{ formattedBalance }}
                </p>
                <button
                  @click="router.push('/recharge')"
                  :class="isLowBalance ? 'from-red-500 to-orange-500' : 'from-cyan-500 to-blue-600'"
                  class="px-6 py-2 bg-gradient-to-r text-white text-sm font-bold rounded-xl hover:brightness-110 transition-all shadow-lg"
                >
                  {{ isLowBalance ? '余额不足，去充值' : '去充值' }}
                </button>
              </div>
            </div>

            <!-- 统计卡片 -->
            <div class="grid grid-cols-4 gap-4 mt-8 pt-6 border-t border-white/10">
              <div class="bg-black/20 rounded-2xl p-4 border border-white/5">
                <p class="text-xs text-gray-500 mb-1">累计充值</p>
                <p class="text-xl font-bold text-emerald-400">¥{{ summary.total_recharge.toFixed(2) }}</p>
              </div>
              <div class="bg-black/20 rounded-2xl p-4 border border-white/5">
                <p class="text-xs text-gray-500 mb-1">累计消费</p>
                <p class="text-xl font-bold text-orange-400">¥{{ summary.total_expense.toFixed(2) }}</p>
              </div>
              <div class="bg-black/20 rounded-2xl p-4 border border-white/5">
                <p class="text-xs text-gray-500 mb-1">生成视频</p>
                <p class="text-xl font-bold text-cyan-400">{{ orderStats.completed }} <span class="text-xs text-gray-500 font-normal">/ {{ orderStats.total }}</span></p>
              </div>
              <div class="bg-black/20 rounded-2xl p-4 border border-white/5">
                <p class="text-xs text-gray-500 mb-1">邀请好友</p>
                <p class="text-xl font-bold text-purple-400">{{ inviteStats?.total_invited || 0 }}</p>
              </div>
            </div>
          </div>
        </div>

        <!-- Tab 切换 -->
        <div class="flex items-center gap-1 p-1 bg-white/5 border border-white/10 rounded-xl w-fit">
          <button
            @click="activeTab = 'transactions'"
            class="px-5 py-2 text-sm font-medium rounded-lg transition-all duration-200"
            :class="activeTab === 'transactions'
              ? 'bg-gradient-to-r from-cyan-500/80 to-blue-500/80 text-white shadow-lg shadow-cyan-900/30'
              : 'text-gray-400 hover:text-white hover:bg-white/5'"
          >
            消费记录
          </button>
          <button
            @click="activeTab = 'orders'"
            class="px-5 py-2 text-sm font-medium rounded-lg transition-all duration-200"
            :class="activeTab === 'orders'
              ? 'bg-gradient-to-r from-purple-500/80 to-pink-500/80 text-white shadow-lg shadow-purple-900/30'
              : 'text-gray-400 hover:text-white hover:bg-white/5'"
          >
            订单记录
          </button>
          <button
            @click="activeTab = 'invite'"
            class="px-5 py-2 text-sm font-medium rounded-lg transition-all duration-200"
            :class="activeTab === 'invite'
              ? 'bg-gradient-to-r from-amber-500/80 to-orange-500/80 text-white shadow-lg shadow-amber-900/30'
              : 'text-gray-400 hover:text-white hover:bg-white/5'"
          >
            邀请记录
          </button>
        </div>

        <!-- 消费记录 -->
        <div v-if="activeTab === 'transactions'" class="relative">
          <div class="absolute -inset-1 rounded-3xl blur-2xl opacity-20 bg-gradient-to-br from-cyan-500/20 to-blue-500/20"></div>
          <div class="relative bg-white/5 backdrop-blur-3xl border border-white/10 border-t-white/20 rounded-3xl shadow-2xl overflow-hidden">
            <div class="p-6 pb-4 border-b border-white/5">
              <h3 class="text-lg font-bold text-white flex items-center gap-2">
                <svg class="w-5 h-5 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/>
                </svg>
                消费记录
              </h3>
            </div>
            <div v-if="transactions.length === 0" class="text-center py-16 text-gray-500">
              <svg class="w-12 h-12 mx-auto mb-3 opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/>
              </svg>
              <p>暂无交易记录</p>
            </div>
            <div v-else class="divide-y divide-white/5">
              <div v-for="tx in transactions" :key="tx.id" class="flex items-center justify-between px-6 py-4 hover:bg-white/[0.03] transition-colors">
                <div class="flex items-center gap-4">
                  <div class="w-10 h-10 rounded-xl flex items-center justify-center" :class="{
                    'bg-emerald-500/10 border border-emerald-500/20': tx.type === 'recharge',
                    'bg-orange-500/10 border border-orange-500/20': tx.type === 'expense',
                    'bg-blue-500/10 border border-blue-500/20': tx.type === 'refund',
                    'bg-purple-500/10 border border-purple-500/20': tx.type === 'invite_reward'
                  }">
                    <svg v-if="tx.type === 'recharge'" class="w-5 h-5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
                    </svg>
                    <svg v-else-if="tx.type === 'expense'" class="w-5 h-5 text-orange-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 12H4"/>
                    </svg>
                    <svg v-else-if="tx.type === 'refund'" class="w-5 h-5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6"/>
                    </svg>
                    <svg v-else class="w-5 h-5 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                    </svg>
                  </div>
                  <div>
                    <p class="text-sm font-medium text-white">
                      {{ tx.type === 'recharge' ? '充值' : tx.type === 'expense' ? '消费' : tx.type === 'refund' ? '退款' : tx.type === 'invite_reward' ? '邀请奖励' : tx.type }}
                    </p>
                    <p class="text-xs text-gray-500">{{ formatTime(tx.created_at) }}</p>
                  </div>
                </div>
                <div class="text-right">
                  <p class="text-sm font-bold" :class="{
                    'text-emerald-400': tx.type === 'recharge' || tx.type === 'refund' || tx.type === 'invite_reward',
                    'text-orange-400': tx.type === 'expense'
                  }">
                    {{ tx.type === 'expense' ? '-' : '+' }}¥{{ Math.abs(tx.amount).toFixed(2) }}
                  </p>
                  <p v-if="tx.bonus > 0" class="text-[10px] text-emerald-400/70">+¥{{ tx.bonus.toFixed(2) }} 赠送</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 订单记录 -->
        <div v-if="activeTab === 'orders'" class="relative">
          <div class="absolute -inset-1 rounded-3xl blur-2xl opacity-20 bg-gradient-to-br from-purple-500/20 to-pink-500/20"></div>
          <div class="relative bg-white/5 backdrop-blur-3xl border border-white/10 border-t-white/20 rounded-3xl shadow-2xl overflow-hidden">
            <div class="p-6 pb-4 border-b border-white/5">
              <h3 class="text-lg font-bold text-white flex items-center gap-2">
                <svg class="w-5 h-5 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"/>
                </svg>
                订单记录
                <span class="text-xs text-gray-500 font-normal ml-2">共 {{ orders.length }} 条</span>
              </h3>
            </div>
            <div v-if="orders.length === 0" class="text-center py-16 text-gray-500">
              <p>暂无订单记录</p>
            </div>
            <div v-else class="divide-y divide-white/5">
              <div v-for="order in orders" :key="order.id" class="px-6 py-4 hover:bg-white/[0.03] transition-colors">
                <div class="flex items-center justify-between">
                  <div class="flex-1 mr-4">
                    <p class="text-sm text-gray-200 line-clamp-1">{{ order.prompt }}</p>
                    <div class="flex items-center gap-3 mt-1.5">
                      <span class="text-xs text-gray-500">{{ formatTime(order.created_at) }}</span>
                      <span v-if="order.model_name" class="text-[10px] px-1.5 py-0.5 bg-white/5 text-gray-400 rounded border border-white/5">{{ order.model_name }}</span>
                      <span class="text-[10px] px-1.5 py-0.5 bg-white/5 text-gray-400 rounded border border-white/5">{{ order.resolution || '768p' }} · {{ order.duration || '6s' }}</span>
                    </div>
                  </div>
                  <div class="flex items-center gap-3">
                    <span class="text-sm font-bold text-orange-400">¥{{ order.cost?.toFixed(2) || '0.00' }}</span>
                    <span class="px-2.5 py-1 rounded-lg text-[10px] font-bold border" :class="{
                      'bg-yellow-500/20 text-yellow-400 border-yellow-500/30': order.status === 'pending',
                      'bg-blue-500/20 text-blue-400 border-blue-500/30': order.status === 'processing',
                      'bg-purple-500/20 text-purple-400 border-purple-500/30': order.status === 'generating',
                      'bg-green-500/20 text-green-400 border-green-500/30': order.status === 'completed',
                      'bg-red-500/20 text-red-400 border-red-500/30': order.status === 'failed',
                    }">
                      {{ order.status === 'pending' ? '排队中' : order.status === 'processing' ? '处理中' : order.status === 'generating' ? '生成中' : order.status === 'completed' ? '已完成' : order.status === 'failed' ? '失败' : order.status }}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 邀请记录 -->
        <div v-if="activeTab === 'invite'" class="relative">
          <div class="absolute -inset-1 rounded-3xl blur-2xl opacity-20 bg-gradient-to-br from-amber-500/20 to-orange-500/20"></div>
          <div class="relative bg-white/5 backdrop-blur-3xl border border-white/10 border-t-white/20 rounded-3xl shadow-2xl overflow-hidden">
            <div class="p-6 border-b border-white/5">
              <div class="flex items-center justify-between">
                <h3 class="text-lg font-bold text-white flex items-center gap-2">
                  <svg class="w-5 h-5 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"/>
                  </svg>
                  邀请好友
                </h3>
                <button @click="copyInviteLink" class="flex items-center gap-1.5 px-4 py-2 text-sm bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 border border-amber-500/20 hover:border-amber-500/40 rounded-xl transition-all">
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3"/>
                  </svg>
                  复制邀请链接
                </button>
              </div>
              <!-- 邀请统计 -->
              <div class="grid grid-cols-3 gap-4 mt-6">
                <div class="bg-black/20 rounded-xl p-4 border border-white/5 text-center">
                  <p class="text-xs text-gray-500 mb-1">邀请人数</p>
                  <p class="text-2xl font-bold text-amber-400">{{ inviteStats?.total_invited || 0 }}</p>
                </div>
                <div class="bg-black/20 rounded-xl p-4 border border-white/5 text-center">
                  <p class="text-xs text-gray-500 mb-1">邀请奖励</p>
                  <p class="text-2xl font-bold text-emerald-400">¥{{ (inviteStats?.total_earnings || 0).toFixed(2) }}</p>
                </div>
                <div class="bg-black/20 rounded-xl p-4 border border-white/5 text-center">
                  <p class="text-xs text-gray-500 mb-1">每人奖励</p>
                  <p class="text-2xl font-bold text-purple-400">¥{{ (inviteStats?.invite_reward || 0).toFixed(2) }}</p>
                </div>
              </div>
            </div>
            <!-- 邀请列表 -->
            <div v-if="!inviteStats?.invite_list?.length" class="text-center py-12 text-gray-500">
              <p>暂无邀请记录，快分享邀请链接给好友吧</p>
            </div>
            <div v-else class="divide-y divide-white/5">
              <div v-for="(inv, idx) in inviteStats.invite_list" :key="idx" class="flex items-center justify-between px-6 py-3.5 hover:bg-white/[0.03] transition-colors">
                <div class="flex items-center gap-3">
                  <div class="w-8 h-8 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center">
                    <span class="text-xs font-bold text-amber-400">{{ idx + 1 }}</span>
                  </div>
                  <span class="text-sm text-gray-300">{{ inv.username }}</span>
                </div>
                <span class="text-xs text-gray-500">{{ formatTime(inv.created_at) }}</span>
              </div>
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
.line-clamp-1 {
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
