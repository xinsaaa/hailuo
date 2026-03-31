<template>
  <div class="space-y-6">
    <div
      v-if="showToast"
      class="fixed top-4 right-4 z-50 px-4 py-3 rounded-xl shadow-lg text-sm font-medium"
      :class="toastType === 'success' ? 'bg-green-500/90 text-white' : toastType === 'error' ? 'bg-red-500/90 text-white' : 'bg-blue-500/90 text-white'"
    >
      {{ toastMessage }}
    </div>

    <div class="flex items-center justify-between">
      <div class="flex items-center gap-3">
        <div class="w-2 h-2 rounded-full bg-orange-400 shadow-[0_0_8px_rgba(251,146,60,0.8)]"></div>
        <h1 class="text-2xl font-bold text-white">可灵账号管理</h1>
        <span class="px-2 py-0.5 text-xs font-bold bg-orange-500/20 text-orange-400 border border-orange-500/30 rounded">KlingAI</span>
      </div>
      <div class="text-sm text-gray-400">
        共 <span class="text-white font-bold">{{ stats.total }}</span> 个账号，
        <span class="text-green-400 font-bold">{{ stats.active }}</span> 个启用，
        <span class="text-blue-400 font-bold">{{ stats.loggedIn }}</span> 个已登录
      </div>
    </div>

    <div class="flex items-center gap-4">
      <button
        @click="showAddModal = true"
        class="flex items-center gap-2 px-4 py-2 bg-orange-600 hover:bg-orange-700 text-white rounded-lg text-sm font-medium transition-colors"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg>
        添加账号
      </button>
      <button
        @click="loadAccounts"
        class="flex items-center gap-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg text-sm font-medium transition-colors"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
        刷新
      </button>
    </div>

    <div class="bg-gray-800/50 border border-gray-700/50 rounded-xl overflow-hidden">
      <div v-if="accounts.length === 0" class="text-center py-16 text-gray-500">
        <svg class="w-12 h-12 mx-auto mb-3 opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0" />
        </svg>
        <p>暂无账号，点击“添加账号”创建</p>
      </div>

      <table v-else class="w-full text-sm">
        <thead class="bg-gray-900/50 border-b border-gray-700/50">
          <tr>
            <th class="text-left px-4 py-3 text-gray-400 font-medium">账号ID</th>
            <th class="text-left px-4 py-3 text-gray-400 font-medium">显示名称</th>
            <th class="text-left px-4 py-3 text-gray-400 font-medium">优先级</th>
            <th class="text-left px-4 py-3 text-gray-400 font-medium">并发数</th>
            <th class="text-left px-4 py-3 text-gray-400 font-medium">登录状态</th>
            <th class="text-left px-4 py-3 text-gray-400 font-medium">积分</th>
            <th class="text-left px-4 py-3 text-gray-400 font-medium">启用状态</th>
            <th class="text-left px-4 py-3 text-gray-400 font-medium">操作</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-700/30">
          <tr v-for="account in sortedAccounts" :key="account.account_id" class="hover:bg-gray-700/20 transition-colors">
            <td class="px-4 py-3 text-white font-mono text-xs">{{ account.account_id }}</td>
            <td class="px-4 py-3 text-gray-200">{{ account.display_name }}</td>
            <td class="px-4 py-3"><span class="px-2 py-0.5 bg-gray-700 text-gray-300 rounded text-xs">{{ account.priority }}</span></td>
            <td class="px-4 py-3 text-gray-300">{{ account.max_concurrent }}</td>
            <td class="px-4 py-3">
              <div class="flex flex-col gap-1">
                <span v-if="account.needs_relogin" class="px-2 py-0.5 bg-yellow-500/20 text-yellow-300 border border-yellow-500/30 rounded text-xs w-fit">需重登</span>
                <span v-else-if="account.is_logged_in" class="px-2 py-0.5 bg-green-500/20 text-green-400 border border-green-500/30 rounded text-xs w-fit">已登录</span>
                <span v-else class="px-2 py-0.5 bg-red-500/20 text-red-400 border border-red-500/30 rounded text-xs w-fit">未登录</span>
                <span v-if="account.refresh_paused" class="text-[11px] text-yellow-300">自动刷新已暂停，请扫码重登</span>
                <span v-else-if="account.next_refresh_retry_at && account.next_refresh_retry_at * 1000 > Date.now()" class="text-[11px] text-gray-400">下次自动重试：{{ formatRetryEta(account.next_refresh_retry_at) }}</span>
                <span v-if="account.monitor_message" class="text-[11px] text-gray-400">{{ account.monitor_message }}</span>
              </div>
            </td>
            <td class="px-4 py-3">
              <div class="flex items-center gap-2">
                <span v-if="accountPoints[account.account_id] !== undefined" class="text-orange-400 font-bold text-xs flex items-center gap-1">
                  <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm.31-8.86c-1.77-.45-2.34-.94-2.34-1.67 0-.84.79-1.43 2.1-1.43 1.38 0 1.9.66 1.94 1.64h1.71c-.05-1.34-.87-2.57-2.49-2.97V5H11.5v1.69c-1.51.32-2.72 1.3-2.72 2.81 0 1.79 1.49 2.69 3.66 3.21 1.95.46 2.34 1.15 2.34 1.87 0 .53-.39 1.39-2.1 1.39-1.6 0-2.23-.72-2.32-1.64H8.65c.09 1.58 1.26 2.46 2.85 2.78V19h1.72v-1.67c1.52-.29 2.72-1.16 2.72-2.74 0-2.22-1.88-2.98-3.63-3.45z"/></svg>
                  {{ accountPoints[account.account_id] }}
                </span>
                <span v-else class="text-gray-500 text-xs">--</span>
                <button v-if="account.is_logged_in" @click="fetchPoints(account.account_id)" :disabled="pointsLoading[account.account_id]" class="text-gray-500 hover:text-orange-400 transition-colors disabled:opacity-30">
                  <svg class="w-3.5 h-3.5" :class="{ 'animate-spin': pointsLoading[account.account_id] }" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
                </button>
              </div>
            </td>
            <td class="px-4 py-3">
              <span v-if="account.is_active" class="px-2 py-0.5 bg-blue-500/20 text-blue-400 border border-blue-500/30 rounded text-xs">启用</span>
              <span v-else class="px-2 py-0.5 bg-gray-500/20 text-gray-400 border border-gray-500/30 rounded text-xs">禁用</span>
            </td>
            <td class="px-4 py-3">
              <div class="flex items-center gap-2 flex-wrap">
                <button @click="openQrLogin(account)" class="bg-orange-600 hover:bg-orange-700 text-white px-3 py-1 rounded text-xs transition-colors">{{ account.is_logged_in ? '重新登录' : '扫码登录' }}</button>
                <button
                  @click="refreshToken(account)"
                  :disabled="refreshing[account.account_id] || account.refresh_paused"
                  class="bg-blue-600 hover:bg-blue-700 text-white px-3 py-1 rounded text-xs transition-colors disabled:opacity-50"
                >
                  {{ account.refresh_paused ? '已暂停自动刷新' : (refreshing[account.account_id] ? '刷新中...' : '刷新Token') }}
                </button>
                <button @click="checkLogin(account)" class="bg-gray-600 hover:bg-gray-500 text-white px-3 py-1 rounded text-xs transition-colors">验证</button>
                <button @click="toggleActive(account)" :class="account.is_active ? 'bg-yellow-600 hover:bg-yellow-700' : 'bg-green-600 hover:bg-green-700'" class="text-white px-3 py-1 rounded text-xs transition-colors">{{ account.is_active ? '禁用' : '启用' }}</button>
                <button @click="deleteAccount(account.account_id)" class="bg-red-600 hover:bg-red-700 text-white px-3 py-1 rounded text-xs transition-colors">删除</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="showAddModal" class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" @click.self="showAddModal = false">
      <div class="bg-gray-800 p-6 rounded-xl border border-gray-700 w-full max-w-md mx-4">
        <h3 class="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <span class="w-1.5 h-5 bg-orange-500 rounded-full"></span>添加可灵账号
        </h3>
        <form @submit.prevent="addAccount">
          <div class="space-y-4">
            <div>
              <label class="block text-sm font-medium text-gray-300 mb-1">账号ID <span class="text-red-400">*</span></label>
              <input v-model="newAccount.account_id" type="text" required placeholder="如：kling_main" class="w-full px-3 py-2 bg-gray-700 border border-gray-600 text-white rounded-lg">
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-300 mb-1">显示名称 <span class="text-red-400">*</span></label>
              <input v-model="newAccount.display_name" type="text" required placeholder="如：主号" class="w-full px-3 py-2 bg-gray-700 border border-gray-600 text-white rounded-lg">
            </div>
            <div class="grid grid-cols-2 gap-4">
              <div>
                <label class="block text-sm font-medium text-gray-300 mb-1">优先级</label>
                <input v-model.number="newAccount.priority" type="number" min="1" max="10" class="w-full px-3 py-2 bg-gray-700 border border-gray-600 text-white rounded-lg">
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-300 mb-1">最大并发数</label>
                <input v-model.number="newAccount.max_concurrent" type="number" min="1" max="10" class="w-full px-3 py-2 bg-gray-700 border border-gray-600 text-white rounded-lg">
              </div>
            </div>
          </div>
          <div class="flex gap-3 mt-6">
            <button type="submit" :disabled="addLoading" class="flex-1 py-2 bg-orange-600 hover:bg-orange-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors">{{ addLoading ? '添加中...' : '添加账号' }}</button>
            <button type="button" @click="showAddModal = false" class="flex-1 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg text-sm font-medium transition-colors">取消</button>
          </div>
        </form>
      </div>
    </div>

    <div v-if="qrModal.show" class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" @click.self="closeQrModal">
      <div class="bg-gray-800 p-6 rounded-xl border border-gray-700 w-full max-w-sm mx-4 text-center">
        <h3 class="text-lg font-semibold text-white mb-1">扫码登录可灵</h3>
        <p class="text-sm text-gray-400 mb-4">账号：{{ qrModal.accountId }}</p>
        <div v-if="qrModal.loading" class="py-12">
          <div class="w-8 h-8 border-2 border-orange-500 border-t-transparent rounded-full animate-spin mx-auto mb-3"></div>
          <p class="text-gray-400 text-sm">正在获取二维码...</p>
        </div>
        <div v-else-if="qrModal.status === 'pending' || qrModal.status === 'scanned'">
          <div class="bg-white p-3 rounded-lg inline-block mb-3">
            <img v-if="qrModal.qrBase64" :src="qrModal.qrBase64" class="w-48 h-48" alt="二维码" />
          </div>
          <p v-if="qrModal.status === 'pending'" class="text-gray-300 text-sm mb-1">请使用快手 APP 扫描二维码</p>
          <p v-if="qrModal.status === 'scanned'" class="text-orange-400 text-sm font-medium mb-1">已扫码，请在手机上确认登录</p>
          <p v-if="qrModal.countdown > 0" class="text-gray-500 text-xs">二维码将在 {{ qrModal.countdown }}s 后过期</p>
        </div>
        <div v-else-if="qrModal.status === 'done'" class="py-8">
          <div class="w-12 h-12 bg-green-500/20 rounded-full flex items-center justify-center mx-auto mb-3">
            <svg class="w-6 h-6 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>
          </div>
          <p class="text-green-400 font-medium">登录成功</p>
        </div>
        <div v-else-if="qrModal.status === 'timeout'" class="py-8">
          <p class="text-yellow-400 mb-4">二维码已过期</p>
          <button @click="refreshQr" class="px-4 py-2 bg-orange-600 hover:bg-orange-700 text-white rounded-lg text-sm transition-colors">重新获取</button>
        </div>
        <div v-else-if="qrModal.status === 'error'" class="py-8">
          <p class="text-red-400 mb-4">登录失败，请重试</p>
          <button @click="refreshQr" class="px-4 py-2 bg-orange-600 hover:bg-orange-700 text-white rounded-lg text-sm transition-colors">重试</button>
        </div>
        <button @click="closeQrModal" class="mt-4 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg text-sm transition-colors w-full">{{ qrModal.status === 'done' ? '完成' : '取消' }}</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import api from '../../api'

const accounts = ref([])
const showAddModal = ref(false)
const addLoading = ref(false)
const newAccount = ref({ account_id: '', display_name: '', priority: 5, max_concurrent: 3 })
const showToast = ref(false)
const toastMessage = ref('')
const toastType = ref('success')
let toastTimer = null
const qrModal = ref({ show: false, accountId: '', loading: false, status: 'none', qrBase64: '', countdown: 0 })
let pollTimer = null
let countdownTimer = null

const accountPoints = ref({})
const pointsLoading = ref({})
const refreshing = ref({})

const sortedAccounts = computed(() => {
  return [...accounts.value].sort((a, b) => {
    if (a.is_active === b.is_active) return (b.priority || 0) - (a.priority || 0)
    return a.is_active ? -1 : 1
  })
})

const stats = computed(() => ({
  total: accounts.value.length,
  active: accounts.value.filter(a => a.is_active).length,
  loggedIn: accounts.value.filter(a => a.is_logged_in).length,
}))

const showToastMessage = (msg, type = 'success') => {
  toastMessage.value = msg
  toastType.value = type
  showToast.value = true
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => {
    showToast.value = false
  }, 3000)
}

const formatRetryEta = (ts) => {
  const sec = Number(ts || 0)
  if (!sec) return '--'
  const targetMs = sec * 1000
  const deltaMs = targetMs - Date.now()
  if (deltaMs <= 0) return '即将重试'
  const mins = Math.ceil(deltaMs / 60000)
  if (mins < 60) return `${mins}分钟后`
  const hours = Math.floor(mins / 60)
  const leftMins = mins % 60
  return leftMins > 0 ? `${hours}小时${leftMins}分钟后` : `${hours}小时后`
}

const loadAccounts = async () => {
  try {
    const res = await api.get('/admin/kling-accounts')
    accounts.value = res.data.accounts
  } catch (e) {
    showToastMessage(e.response?.data?.detail || '加载失败', 'error')
  }
}

const addAccount = async () => {
  addLoading.value = true
  try {
    await api.post('/admin/kling-accounts', newAccount.value)
    showToastMessage('账号添加成功')
    showAddModal.value = false
    newAccount.value = { account_id: '', display_name: '', priority: 5, max_concurrent: 3 }
    loadAccounts()
  } catch (e) {
    showToastMessage(e.response?.data?.detail || '添加失败', 'error')
  } finally {
    addLoading.value = false
  }
}

const deleteAccount = async (accountId) => {
  if (!confirm('确定删除该账号吗？')) return
  try {
    await api.delete(`/admin/kling-accounts/${accountId}`)
    showToastMessage('账号已删除')
    loadAccounts()
  } catch (e) {
    showToastMessage(e.response?.data?.detail || '删除失败', 'error')
  }
}

const toggleActive = async (account) => {
  try {
    await api.patch(`/admin/kling-accounts/${account.account_id}`, { is_active: !account.is_active })
    showToastMessage(account.is_active ? '账号已禁用' : '账号已启用')
    loadAccounts()
  } catch (e) {
    showToastMessage(e.response?.data?.detail || '操作失败', 'error')
  }
}

const checkLogin = async (account) => {
  try {
    const res = await api.post(`/admin/kling-accounts/${account.account_id}/check-login`)
    showToastMessage(
      res.data.is_logged_in ? 'Cookie 有效，已登录' : 'Cookie 已失效，请重新扫码',
      res.data.is_logged_in ? 'success' : 'error'
    )
    loadAccounts()
  } catch (e) {
    showToastMessage(e.response?.data?.detail || '验证失败', 'error')
  }
}

const refreshToken = async (account) => {
  if (account.refresh_paused) {
    showToastMessage('该账号已暂停自动刷新，请扫码重登', 'error')
    return
  }
  refreshing.value[account.account_id] = true
  try {
    const res = await api.post(`/admin/kling-accounts/${account.account_id}/refresh-token`)
    showToastMessage(res.data.message || 'Token刷新成功')
    loadAccounts()
  } catch (e) {
    showToastMessage(e.response?.data?.detail || 'Token刷新失败', 'error')
    loadAccounts()
  } finally {
    refreshing.value[account.account_id] = false
  }
}

const fetchPoints = async (accountId) => {
  pointsLoading.value[accountId] = true
  try {
    const res = await api.get(`/admin/kling-accounts/${accountId}/points`)
    if (res.data.success) {
      accountPoints.value[accountId] = res.data.points.total
    }
  } catch (e) {
    accountPoints.value[accountId] = undefined
  } finally {
    pointsLoading.value[accountId] = false
  }
}

const fetchAllPoints = () => {
  accounts.value.forEach(a => {
    if (a.is_logged_in) fetchPoints(a.account_id)
  })
}

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

const stopCountdown = () => {
  if (countdownTimer) {
    clearInterval(countdownTimer)
    countdownTimer = null
  }
}

const startCountdown = (seconds) => {
  stopCountdown()
  qrModal.value.countdown = seconds
  countdownTimer = setInterval(() => {
    qrModal.value.countdown--
    if (qrModal.value.countdown <= 0) {
      stopCountdown()
      if (qrModal.value.status === 'pending') {
        qrModal.value.status = 'timeout'
        stopPolling()
      }
    }
  }, 1000)
}

const startPolling = (accountId) => {
  stopPolling()
  pollTimer = setInterval(async () => {
    try {
      const res = await api.get(`/admin/kling-accounts/${accountId}/qr-login/status`)
      const st = res.data.status
      if (st === 'scanned') {
        qrModal.value.status = 'scanned'
      } else if (st === 'done') {
        qrModal.value.status = 'done'
        stopPolling()
        stopCountdown()
        showToastMessage('登录成功')
        loadAccounts()
      } else if (st === 'error') {
        qrModal.value.status = 'error'
        stopPolling()
        stopCountdown()
      } else if (st === 'timeout') {
        qrModal.value.status = 'timeout'
        stopPolling()
        stopCountdown()
      }
    } catch (e) {
      // ignore
    }
  }, 2000)
}

const openQrLogin = async (account) => {
  qrModal.value = { show: true, accountId: account.account_id, loading: true, status: 'none', qrBase64: '', countdown: 0 }
  stopPolling()
  stopCountdown()
  try {
    const res = await api.post(`/admin/kling-accounts/${account.account_id}/qr-login/start`)
    if (res.data.success) {
      qrModal.value.qrBase64 = res.data.qr_base64
      qrModal.value.status = 'pending'
      qrModal.value.loading = false
      const expireSec = Math.max(Math.floor((res.data.expire_time - Date.now()) / 1000), 60)
      startCountdown(expireSec)
      startPolling(account.account_id)
    } else {
      qrModal.value.status = 'error'
      qrModal.value.loading = false
    }
  } catch (e) {
    qrModal.value.status = 'error'
    qrModal.value.loading = false
    showToastMessage(e.response?.data?.detail || '获取二维码失败', 'error')
  }
}

const refreshQr = () => {
  const accountId = qrModal.value.accountId
  const account = accounts.value.find(a => a.account_id === accountId)
  if (account) openQrLogin(account)
}

const closeQrModal = () => {
  stopPolling()
  stopCountdown()
  if (qrModal.value.status === 'pending' || qrModal.value.status === 'scanned') {
    api.post(`/admin/kling-accounts/${qrModal.value.accountId}/qr-login/cancel`).catch(() => {})
  }
  qrModal.value.show = false
}

onMounted(async () => {
  await loadAccounts()
  fetchAllPoints()
})

onUnmounted(() => {
  stopPolling()
  stopCountdown()
})
</script>
