<template>
  <div class="space-y-6">
    <div v-if="showToast" class="fixed top-4 right-4 z-50 px-4 py-3 rounded-xl shadow-lg text-sm font-medium"
      :class="toastType === 'success' ? 'bg-green-500/90 text-white' : toastType === 'error' ? 'bg-red-500/90 text-white' : 'bg-blue-500/90 text-white'">
      {{ toastMessage }}
    </div>
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-3">
        <div class="w-2 h-2 rounded-full bg-cyan-400 shadow-[0_0_8px_rgba(34,211,238,0.8)]"></div>
        <h1 class="text-2xl font-bold text-white">海螺账号管理</h1>
        <span class="px-2 py-0.5 text-xs font-bold bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 rounded">HailuoAI</span>
      </div>
      <div class="text-sm text-gray-400">
        共 <span class="text-white font-bold">{{ stats.total }}</span> 个账号，
        <span class="text-green-400 font-bold">{{ stats.active }}</span> 个启用，
        <span class="text-blue-400 font-bold">{{ stats.loggedIn }}</span> 个已登录
      </div>
    </div>
    <div class="flex items-center gap-4">
      <button @click="showAddModal = true" class="flex items-center gap-2 px-4 py-2 bg-cyan-600 hover:bg-cyan-700 text-white rounded-lg text-sm font-medium transition-colors">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg>
        添加账号
      </button>
      <button @click="loadAccounts" class="flex items-center gap-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg text-sm font-medium transition-colors">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
        刷新
      </button>
    </div>
    <div class="bg-gray-800/50 border border-gray-700/50 rounded-xl overflow-hidden">
      <div v-if="accounts.length === 0" class="text-center py-16 text-gray-500">
        <svg class="w-12 h-12 mx-auto mb-3 opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0" />
        </svg>
        <p>暂无账号，点击「添加账号」创建</p>
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
              <span v-if="account.is_logged_in" class="px-2 py-0.5 bg-green-500/20 text-green-400 border border-green-500/30 rounded text-xs">已登录</span>
              <span v-else class="px-2 py-0.5 bg-red-500/20 text-red-400 border border-red-500/30 rounded text-xs">未登录</span>
            </td>
            <td class="px-4 py-3">
              <div class="flex items-center gap-2">
                <span v-if="accountPoints[account.account_id] !== undefined" class="text-cyan-400 font-bold text-xs flex items-center gap-1">
                  <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm.31-8.86c-1.77-.45-2.34-.94-2.34-1.67 0-.84.79-1.43 2.1-1.43 1.38 0 1.9.66 1.94 1.64h1.71c-.05-1.34-.87-2.57-2.49-2.97V5H11.5v1.69c-1.51.32-2.72 1.3-2.72 2.81 0 1.79 1.49 2.69 3.66 3.21 1.95.46 2.34 1.15 2.34 1.87 0 .53-.39 1.39-2.1 1.39-1.6 0-2.23-.72-2.32-1.64H8.65c.09 1.58 1.26 2.46 2.85 2.78V19h1.72v-1.67c1.52-.29 2.72-1.16 2.72-2.74 0-2.22-1.88-2.98-3.63-3.45z"/></svg>
                  {{ accountPoints[account.account_id] }}
                </span>
                <span v-else class="text-gray-500 text-xs">--</span>
                <button v-if="account.is_logged_in" @click="fetchPoints(account.account_id)" :disabled="pointsLoading[account.account_id]" class="text-gray-500 hover:text-cyan-400 transition-colors disabled:opacity-30">
                  <svg class="w-3.5 h-3.5" :class="{'animate-spin': pointsLoading[account.account_id]}" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
                </button>
              </div>
            </td>
            <td class="px-4 py-3">
              <span v-if="account.is_active" class="px-2 py-0.5 bg-blue-500/20 text-blue-400 border border-blue-500/30 rounded text-xs">启用</span>
              <span v-else class="px-2 py-0.5 bg-gray-500/20 text-gray-400 border border-gray-500/30 rounded text-xs">禁用</span>
            </td>
            <td class="px-4 py-3">
              <div class="flex items-center gap-2 flex-wrap">
                <button @click="openCookieModal(account)" class="bg-cyan-600 hover:bg-cyan-700 text-white px-3 py-1 rounded text-xs transition-colors">Cookie登录</button>
                <button @click="openSmsModal(account)" class="bg-blue-600 hover:bg-blue-700 text-white px-3 py-1 rounded text-xs transition-colors">短信登录</button>
                <button @click="checkLogin(account)" class="bg-gray-600 hover:bg-gray-500 text-white px-3 py-1 rounded text-xs transition-colors">验证</button>
                <button @click="toggleActive(account)" :class="account.is_active ? 'bg-yellow-600 hover:bg-yellow-700' : 'bg-green-600 hover:bg-green-700'" class="text-white px-3 py-1 rounded text-xs transition-colors">{{ account.is_active ? '禁用' : '启用' }}</button>
                <button @click="deleteAccount(account.account_id)" class="bg-red-600 hover:bg-red-700 text-white px-3 py-1 rounded text-xs transition-colors">删除</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 添加账号弹窗 -->
    <div v-if="showAddModal" class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" @click.self="showAddModal = false">
      <div class="bg-gray-800 p-6 rounded-xl border border-gray-700 w-full max-w-md mx-4">
        <h3 class="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <span class="w-1.5 h-5 bg-cyan-500 rounded-full"></span>添加海螺账号
        </h3>
        <form @submit.prevent="addAccount">
          <div class="space-y-4">
            <div>
              <label class="block text-sm font-medium text-gray-300 mb-1">账号ID <span class="text-red-400">*</span></label>
              <input v-model="newAccount.account_id" type="text" required placeholder="如：hailuo_main" class="w-full px-3 py-2 bg-gray-700 border border-gray-600 text-white rounded-lg">
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
            <button type="submit" :disabled="addLoading" class="flex-1 py-2 bg-cyan-600 hover:bg-cyan-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors">{{ addLoading ? '添加中...' : '添加账号' }}</button>
            <button type="button" @click="showAddModal = false" class="flex-1 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg text-sm font-medium transition-colors">取消</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Cookie登录弹窗 -->
    <div v-if="cookieModal.show" class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" @click.self="cookieModal.show = false">
      <div class="bg-gray-800 p-6 rounded-xl border border-gray-700 w-full max-w-lg mx-4">
        <h3 class="text-lg font-semibold text-white mb-1">Cookie 登录</h3>
        <p class="text-sm text-gray-400 mb-4">账号：{{ cookieModal.accountId }}</p>
        <div class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-300 mb-1">Cookie <span class="text-red-400">*</span></label>
            <textarea v-model="cookieModal.cookie" rows="4" placeholder="从浏览器开发者工具复制完整 Cookie" class="w-full px-3 py-2 bg-gray-700 border border-gray-600 text-white rounded-lg text-xs font-mono"></textarea>
          </div>
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-gray-300 mb-1">UUID <span class="text-gray-500">(可选)</span></label>
              <input v-model="cookieModal.uuid" type="text" placeholder="自动生成" class="w-full px-3 py-2 bg-gray-700 border border-gray-600 text-white rounded-lg text-xs font-mono">
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-300 mb-1">Device ID <span class="text-gray-500">(可选)</span></label>
              <input v-model="cookieModal.device_id" type="text" placeholder="自动生成" class="w-full px-3 py-2 bg-gray-700 border border-gray-600 text-white rounded-lg text-xs font-mono">
            </div>
          </div>
        </div>
        <div class="flex gap-3 mt-6">
          <button @click="submitCookieLogin" :disabled="cookieModal.loading" class="flex-1 py-2 bg-cyan-600 hover:bg-cyan-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors">{{ cookieModal.loading ? '验证中...' : '登录' }}</button>
          <button @click="cookieModal.show = false" class="flex-1 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg text-sm font-medium transition-colors">取消</button>
        </div>
      </div>
    </div>

    <!-- 短信登录弹窗 -->
    <div v-if="smsModal.show" class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" @click.self="smsModal.show = false">
      <div class="bg-gray-800 p-6 rounded-xl border border-gray-700 w-full max-w-sm mx-4 text-center">
        <h3 class="text-lg font-semibold text-white mb-1">短信验证码登录</h3>
        <p class="text-sm text-gray-400 mb-4">账号：{{ smsModal.accountId }}</p>
        
        <!-- 步骤1：输入手机号 -->
        <div v-if="smsModal.step === 'phone'" class="space-y-4">
          <input v-model="smsModal.phone" type="tel" placeholder="请输入手机号" class="w-full px-3 py-2 bg-gray-700 border border-gray-600 text-white rounded-lg text-center text-lg tracking-widest">
          <button @click="sendSmsCode" :disabled="smsModal.loading" class="w-full py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors">{{ smsModal.loading ? '发送中...' : '发送验证码' }}</button>
        </div>
        
        <!-- 步骤2：输入验证码 -->
        <div v-if="smsModal.step === 'code'" class="space-y-4">
          <p class="text-gray-300 text-sm">验证码已发送到 {{ smsModal.phone }}</p>
          <input v-model="smsModal.code" type="text" maxlength="6" placeholder="请输入验证码" class="w-full px-3 py-2 bg-gray-700 border border-gray-600 text-white rounded-lg text-center text-2xl tracking-[0.5em] font-mono">
          <button @click="verifySmsCode" :disabled="smsModal.loading || smsModal.code.length < 4" class="w-full py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors">{{ smsModal.loading ? '登录中...' : '确认登录' }}</button>
          <button @click="smsModal.step = 'phone'" class="text-gray-400 hover:text-white text-xs transition-colors">重新发送</button>
        </div>
        
        <!-- 步骤3：成功 -->
        <div v-if="smsModal.step === 'done'" class="py-4">
          <div class="w-12 h-12 bg-green-500/20 rounded-full flex items-center justify-center mx-auto mb-3">
            <svg class="w-6 h-6 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>
          </div>
          <p class="text-green-400 font-medium">{{ smsModal.username ? `${smsModal.username} 登录成功！` : '登录成功！' }}</p>
        </div>
        
        <button @click="smsModal.show = false" class="mt-4 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg text-sm transition-colors w-full">{{ smsModal.step === 'done' ? '完成' : '取消' }}</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '../../api'

const accounts = ref([])
const showAddModal = ref(false)
const addLoading = ref(false)
const newAccount = ref({ account_id: '', display_name: '', priority: 5, max_concurrent: 3 })
const showToast = ref(false)
const toastMessage = ref('')
const toastType = ref('success')
let toastTimer = null

const accountPoints = ref({})
const pointsLoading = ref({})

const cookieModal = ref({ show: false, accountId: '', cookie: '', uuid: '', device_id: '', loading: false })
const smsModal = ref({ show: false, accountId: '', phone: '', code: '', step: 'phone', loading: false, username: '' })

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
  toastTimer = setTimeout(() => { showToast.value = false }, 3000)
}

const loadAccounts = async () => {
  try {
    const res = await api.get('/admin/hailuo-accounts')
    accounts.value = res.data.accounts
  } catch (e) {
    showToastMessage(e.response?.data?.detail || '加载失败', 'error')
  }
}

const addAccount = async () => {
  addLoading.value = true
  try {
    await api.post('/admin/hailuo-accounts', newAccount.value)
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
    await api.delete(`/admin/hailuo-accounts/${accountId}`)
    showToastMessage('账号已删除')
    loadAccounts()
  } catch (e) {
    showToastMessage(e.response?.data?.detail || '删除失败', 'error')
  }
}

const toggleActive = async (account) => {
  try {
    await api.patch(`/admin/hailuo-accounts/${account.account_id}`, { is_active: !account.is_active })
    showToastMessage(account.is_active ? '账号已禁用' : '账号已启用')
    loadAccounts()
  } catch (e) {
    showToastMessage(e.response?.data?.detail || '操作失败', 'error')
  }
}

const checkLogin = async (account) => {
  try {
    const res = await api.post(`/admin/hailuo-accounts/${account.account_id}/check-login`)
    showToastMessage(
      res.data.is_logged_in ? 'Cookie 有效，已登录' : 'Cookie 已失效，请重新登录',
      res.data.is_logged_in ? 'success' : 'error'
    )
    loadAccounts()
  } catch (e) {
    showToastMessage(e.response?.data?.detail || '验证失败', 'error')
  }
}

const fetchPoints = async (accountId) => {
  pointsLoading.value[accountId] = true
  try {
    const res = await api.get(`/admin/hailuo-accounts/${accountId}/points`)
    if (res.data.success) {
      accountPoints.value[accountId] = res.data.points.total
    }
  } catch (e) {
    accountPoints.value[accountId] = undefined
    showToastMessage(e.response?.data?.detail || '查询积分失败', 'error')
  } finally {
    pointsLoading.value[accountId] = false
  }
}

const fetchAllPoints = () => {
  accounts.value.forEach(a => {
    if (a.is_logged_in) fetchPoints(a.account_id)
  })
}

// Cookie 登录
const openCookieModal = (account) => {
  cookieModal.value = { show: true, accountId: account.account_id, cookie: '', uuid: '', device_id: '', loading: false }
}

const submitCookieLogin = async () => {
  if (!cookieModal.value.cookie.trim()) {
    showToastMessage('请输入 Cookie', 'error')
    return
  }
  cookieModal.value.loading = true
  try {
    const body = { cookie: cookieModal.value.cookie.trim() }
    if (cookieModal.value.uuid.trim()) body.uuid = cookieModal.value.uuid.trim()
    if (cookieModal.value.device_id.trim()) body.device_id = cookieModal.value.device_id.trim()
    await api.post(`/admin/hailuo-accounts/${cookieModal.value.accountId}/cookie-login`, body)
    showToastMessage('Cookie 登录成功')
    cookieModal.value.show = false
    loadAccounts()
    fetchAllPoints()
  } catch (e) {
    showToastMessage(e.response?.data?.detail || 'Cookie 登录失败', 'error')
  } finally {
    cookieModal.value.loading = false
  }
}

// 短信登录
const openSmsModal = (account) => {
  smsModal.value = { show: true, accountId: account.account_id, phone: '', code: '', step: 'phone', loading: false, username: '' }
}

const sendSmsCode = async () => {
  if (!smsModal.value.phone.trim()) {
    showToastMessage('请输入手机号', 'error')
    return
  }
  smsModal.value.loading = true
  try {
    await api.post(`/admin/hailuo-accounts/${smsModal.value.accountId}/sms/send`, { phone: smsModal.value.phone.trim() })
    showToastMessage('验证码已发送')
    smsModal.value.step = 'code'
  } catch (e) {
    showToastMessage(e.response?.data?.detail || '发送失败', 'error')
  } finally {
    smsModal.value.loading = false
  }
}

const verifySmsCode = async () => {
  smsModal.value.loading = true
  try {
    const res = await api.post(`/admin/hailuo-accounts/${smsModal.value.accountId}/sms/verify`, { code: smsModal.value.code.trim() })
    smsModal.value.username = res.data.username || ''
    smsModal.value.step = 'done'
    showToastMessage('登录成功')
    loadAccounts()
    fetchAllPoints()
  } catch (e) {
    showToastMessage(e.response?.data?.detail || '验证失败', 'error')
  } finally {
    smsModal.value.loading = false
  }
}

onMounted(async () => {
  await loadAccounts()
  fetchAllPoints()
})
</script>
