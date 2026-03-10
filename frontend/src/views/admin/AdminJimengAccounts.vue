<template>
  <div class="min-h-screen bg-gray-900 text-white">
    <!-- 页面头部 -->
    <div class="bg-gray-800 px-6 py-4 border-b border-gray-700">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="w-2 h-2 rounded-full bg-violet-400 shadow-[0_0_8px_rgba(167,139,250,0.8)]"></div>
          <h1 class="text-2xl font-bold text-white">即梦账号管理</h1>
          <span class="px-2 py-0.5 text-xs font-bold bg-violet-500/20 text-violet-400 border border-violet-500/30 rounded">Seedance</span>
        </div>
        <div class="text-sm text-gray-400">
          共 <span class="text-white font-bold">{{ stats.total }}</span> 个账号，
          <span class="text-green-400 font-bold">{{ stats.active }}</span> 个启用，
          <span class="text-blue-400 font-bold">{{ stats.logged_in }}</span> 个已登录
        </div>
      </div>
    </div>

    <div class="p-6 max-w-7xl mx-auto">
      <!-- 操作栏 -->
      <div class="flex items-center justify-between mb-6">
        <button
          @click="showAddModal = true"
          class="bg-violet-600 hover:bg-violet-700 text-white px-4 py-2 rounded-lg font-medium transition-colors flex items-center gap-2"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"/>
          </svg>
          添加账号
        </button>
        <button
          @click="loadAccounts"
          :disabled="loading"
          class="bg-gray-700 hover:bg-gray-600 text-white px-4 py-2 rounded-lg font-medium transition-colors flex items-center gap-2"
        >
          <svg class="w-4 h-4" :class="{ 'animate-spin': loading }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
          </svg>
          {{ loading ? '刷新中...' : '刷新' }}
        </button>
      </div>

      <!-- 账号列表 -->
      <div class="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
        <div class="p-4 border-b border-gray-700 flex items-center gap-2">
          <svg class="w-5 h-5 text-violet-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"/>
          </svg>
          <h3 class="text-lg font-semibold text-white">账号列表</h3>
        </div>

        <div v-if="accounts.length === 0" class="py-16 text-center text-gray-500">
          暂无即梦账号，点击「添加账号」开始
        </div>

        <div class="overflow-x-auto" v-else>
          <table class="w-full">
            <thead class="bg-gray-700/50">
              <tr>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">账号信息</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">状态</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">Cookie</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">优先级</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">操作</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-700">
              <tr v-for="account in accounts" :key="account.account_id" class="hover:bg-gray-700/30">
                <td class="px-6 py-4 whitespace-nowrap">
                  <div class="text-sm font-medium text-white">{{ account.display_name }}</div>
                  <div class="text-xs text-gray-500 mt-0.5">ID: {{ account.account_id }}</div>
                  <div class="text-xs text-gray-500">并发: {{ account.current_tasks }}/{{ account.max_concurrent }}</div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                  <div class="flex flex-col gap-1">
                    <span class="inline-flex px-2 py-1 text-xs font-semibold rounded-full"
                      :class="account.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'">
                      {{ account.is_active ? '已启用' : '已禁用' }}
                    </span>
                    <span class="inline-flex px-2 py-1 text-xs font-semibold rounded-full"
                      :class="account.is_logged_in ? 'bg-blue-100 text-blue-800' : 'bg-red-100 text-red-800'">
                      {{ account.is_logged_in ? '已登录' : '未登录' }}
                    </span>
                  </div>
                </td>
                <td class="px-6 py-4">
                  <div class="text-xs text-gray-400 font-mono max-w-[180px] truncate" :title="account.cookie">
                    {{ account.cookie ? account.cookie.substring(0, 30) + '...' : '未设置' }}
                  </div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                  <div class="flex items-center gap-1">
                    <span v-for="i in 10" :key="i"
                      class="w-2 h-2 rounded-full"
                      :class="i <= account.priority ? 'bg-violet-400' : 'bg-gray-600'">
                    </span>
                    <span class="text-sm text-gray-300 ml-1">{{ account.priority }}</span>
                  </div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                  <div class="flex items-center gap-2 flex-wrap">
                    <button
                      @click="openQrLoginModal(account)"
                      class="bg-blue-600 hover:bg-blue-700 text-white px-3 py-1 rounded text-xs transition-colors flex items-center gap-1"
                    >
                      <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v1m6 11h2m-6 0h-2v4m0-11v3m0 0h.01M12 12h4.01M16 20h4M4 12h4m12 0h.01M5 8h2a1 1 0 001-1V5a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1zm12 0h2a1 1 0 001-1V5a1 1 0 00-1-1h-2a1 1 0 00-1 1v2a1 1 0 001 1zM5 20h2a1 1 0 001-1v-2a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1z"/>
                      </svg>
                      扫码登录
                    </button>
                    <button
                      @click="openCookieModal(account)"
                      class="bg-violet-600 hover:bg-violet-700 text-white px-3 py-1 rounded text-xs transition-colors"
                    >
                      {{ account.is_logged_in ? '更新Cookie' : 'Cookie登录' }}
                    </button>
                    <button
                      @click="toggleActive(account)"
                      class="px-3 py-1 rounded text-xs transition-colors"
                      :class="account.is_active ? 'bg-yellow-600 hover:bg-yellow-700 text-white' : 'bg-green-600 hover:bg-green-700 text-white'"
                    >
                      {{ account.is_active ? '禁用' : '启用' }}
                    </button>
                    <button
                      v-if="account.is_logged_in"
                      @click="logoutAccount(account.account_id)"
                      class="bg-gray-600 hover:bg-gray-500 text-white px-3 py-1 rounded text-xs transition-colors"
                    >
                      登出
                    </button>
                    <button
                      @click="deleteAccount(account.account_id)"
                      class="bg-red-600 hover:bg-red-700 text-white px-3 py-1 rounded text-xs transition-colors"
                    >
                      删除
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Cookie登录说明 -->
      <div class="mt-4 p-4 bg-violet-500/10 border border-violet-500/20 rounded-xl text-sm text-gray-400">
        <p class="font-medium text-violet-400 mb-1">🍪 Cookie 登录说明</p>
        <p>即梦使用 Cookie 方式登录。在浏览器中登录即梦账号，打开开发者工具 → Network → 复制请求头中的 <code class="text-violet-300 bg-black/30 px-1 rounded">Cookie</code> 字段值粘贴到此处。</p>
      </div>
    </div>

    <!-- 添加账号弹窗 -->
    <div v-if="showAddModal" class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" @click.self="showAddModal = false">
      <div class="bg-gray-800 p-6 rounded-xl border border-gray-700 w-full max-w-md mx-4">
        <h3 class="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <span class="w-1.5 h-5 bg-violet-500 rounded-full"></span>
          添加即梦账号
        </h3>
        <form @submit.prevent="addAccount">
          <div class="space-y-4">
            <div>
              <label class="block text-sm font-medium text-gray-300 mb-1">账号ID <span class="text-red-400">*</span></label>
              <input v-model="newAccount.account_id" type="text" required placeholder="如：jimeng_main"
                class="w-full px-3 py-2 bg-gray-700 border border-gray-600 text-white rounded-lg focus:ring-violet-500 focus:border-violet-500">
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-300 mb-1">显示名称 <span class="text-red-400">*</span></label>
              <input v-model="newAccount.display_name" type="text" required placeholder="如：即梦主账号"
                class="w-full px-3 py-2 bg-gray-700 border border-gray-600 text-white rounded-lg focus:ring-violet-500 focus:border-violet-500">
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-300 mb-1">Cookie（可稍后填写）</label>
              <textarea v-model="newAccount.cookie" rows="3" placeholder="粘贴浏览器 Cookie 字符串..."
                class="w-full px-3 py-2 bg-gray-700 border border-gray-600 text-white rounded-lg focus:ring-violet-500 focus:border-violet-500 text-xs font-mono resize-none">
              </textarea>
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="block text-sm font-medium text-gray-300 mb-1">优先级 (1-10)</label>
                <input v-model.number="newAccount.priority" type="number" min="1" max="10"
                  class="w-full px-3 py-2 bg-gray-700 border border-gray-600 text-white rounded-lg focus:ring-violet-500 focus:border-violet-500">
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-300 mb-1">最大并发数</label>
                <input v-model.number="newAccount.max_concurrent" type="number" min="1" max="10"
                  class="w-full px-3 py-2 bg-gray-700 border border-gray-600 text-white rounded-lg focus:ring-violet-500 focus:border-violet-500">
              </div>
            </div>
          </div>
          <div class="flex justify-end gap-3 mt-6">
            <button type="button" @click="showAddModal = false"
              class="px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white rounded-lg transition-colors">取消</button>
            <button type="submit"
              class="px-4 py-2 bg-violet-600 hover:bg-violet-700 text-white rounded-lg transition-colors">添加</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Cookie登录弹窗 -->
    <div v-if="cookieModal.show" class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" @click.self="cookieModal.show = false">
      <div class="bg-gray-800 p-6 rounded-xl border border-gray-700 w-full max-w-lg mx-4">
        <h3 class="text-lg font-semibold text-white mb-1 flex items-center gap-2">
          <span class="w-1.5 h-5 bg-violet-500 rounded-full"></span>
          Cookie 登录
        </h3>
        <p class="text-sm text-gray-400 mb-4">账号：{{ cookieModal.displayName }}</p>

        <div class="mb-2 text-xs text-gray-400 bg-black/30 rounded-lg p-3 space-y-1">
          <p>1. 浏览器打开 <span class="text-violet-300">jimeng.jianying.com</span> 并登录</p>
          <p>2. 按 F12 → Network → 刷新页面 → 点击任意请求</p>
          <p>3. 在 Request Headers 中找到 <code class="text-violet-300">cookie</code> 字段，复制完整值</p>
        </div>

        <textarea
          v-model="cookieModal.cookie"
          rows="5"
          placeholder="粘贴完整 Cookie 字符串..."
          class="w-full px-3 py-2 bg-gray-700 border border-gray-600 text-white rounded-lg focus:ring-violet-500 focus:border-violet-500 text-xs font-mono resize-none mb-4"
        ></textarea>

        <div class="flex justify-end gap-3">
          <button @click="cookieModal.show = false"
            class="px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white rounded-lg transition-colors">取消</button>
          <button @click="saveCookie" :disabled="cookieModal.loading || !cookieModal.cookie.trim()"
            class="px-4 py-2 bg-violet-600 hover:bg-violet-700 disabled:opacity-50 text-white rounded-lg transition-colors flex items-center gap-2">
            <svg v-if="cookieModal.loading" class="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="m4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            {{ cookieModal.loading ? '保存中...' : '保存并登录' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 二维码登录弹窗 -->
    <div v-if="qrLoginModal.show" class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" @click.self="closeQrModal">
      <div class="bg-gray-800 p-6 rounded-xl border border-gray-700 w-full max-w-md mx-4">
        <h3 class="text-lg font-semibold text-white mb-1 flex items-center gap-2">
          <span class="w-1.5 h-5 bg-blue-500 rounded-full"></span>
          扫码登录
        </h3>
        <p class="text-sm text-gray-400 mb-4">账号：{{ qrLoginModal.displayName }}</p>

        <!-- 二维码显示区域 -->
        <div class="flex flex-col items-center">
          <!-- 加载中 -->
          <div v-if="qrLoginModal.status === 'loading'" class="w-48 h-48 bg-gray-700 rounded-lg flex items-center justify-center">
            <div class="text-center">
              <svg class="animate-spin h-8 w-8 text-blue-400 mx-auto mb-2" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              <p class="text-sm text-gray-400">正在生成二维码...</p>
            </div>
          </div>

          <!-- 二维码图片 -->
          <div v-else-if="qrLoginModal.qrBase64" class="relative">
            <img :src="'data:image/png;base64,' + qrLoginModal.qrBase64" 
                 class="w-48 h-48 rounded-lg border-2 border-blue-500/30"
                 alt="登录二维码" />
            <!-- 扫码成功遮罩 -->
            <div v-if="qrLoginModal.status === 'scanning'" 
                 class="absolute inset-0 bg-blue-500/20 rounded-lg flex items-center justify-center">
              <div class="text-center">
                <svg class="w-10 h-10 text-blue-400 mx-auto mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
                </svg>
                <p class="text-sm text-blue-300">已扫描，请在手机确认</p>
              </div>
            </div>
          </div>

          <!-- 状态提示 -->
          <div class="mt-4 text-center">
            <p v-if="qrLoginModal.status === 'pending'" class="text-sm text-gray-400">
              请使用 <span class="text-blue-400">抖音App</span> 扫描二维码
            </p>
            <p v-else-if="qrLoginModal.status === 'scanning'" class="text-sm text-blue-400">
              已扫描，请在手机上确认登录
            </p>
            <p v-else-if="qrLoginModal.status === 'success'" class="text-sm text-green-400 flex items-center justify-center gap-1">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
              </svg>
              登录成功！
            </p>
            <p v-else-if="qrLoginModal.status === 'timeout'" class="text-sm text-yellow-400">
              二维码已过期，请重新获取
            </p>
            <p v-else-if="qrLoginModal.status === 'failed'" class="text-sm text-red-400">
              {{ qrLoginModal.error || '登录失败，请重试' }}
            </p>
          </div>

          <!-- 倒计时 -->
          <div v-if="qrLoginModal.qrBase64 && ['pending', 'scanning'].includes(qrLoginModal.status)" 
               class="mt-2 text-xs text-gray-500">
            二维码有效期：{{ qrLoginModal.countdown }}秒
          </div>
        </div>

        <div class="flex justify-end gap-3 mt-6">
          <button @click="closeQrModal"
            class="px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white rounded-lg transition-colors">
            {{ qrLoginModal.status === 'success' ? '关闭' : '取消' }}
          </button>
          <button v-if="qrLoginModal.status === 'timeout' || qrLoginModal.status === 'failed'"
            @click="refreshQrCode"
            :disabled="qrLoginModal.loading"
            class="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg transition-colors flex items-center gap-2">
            <svg v-if="qrLoginModal.loading" class="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            刷新二维码
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import api from '../../api'

const loading = ref(false)
const accounts = ref([])
const showAddModal = ref(false)

const stats = computed(() => ({
  total: accounts.value.length,
  active: accounts.value.filter(a => a.is_active).length,
  logged_in: accounts.value.filter(a => a.is_logged_in).length,
}))

const newAccount = reactive({
  account_id: '',
  display_name: '',
  cookie: '',
  priority: 5,
  max_concurrent: 3,
})

const cookieModal = reactive({
  show: false,
  accountId: '',
  displayName: '',
  cookie: '',
  loading: false,
})

// 二维码登录相关
const qrLoginModal = reactive({
  show: false,
  accountId: '',
  displayName: '',
  qrBase64: '',
  status: 'loading', // loading, pending, scanning, success, timeout, failed
  error: '',
  loading: false,
  countdown: 180,
  pollTimer: null,
  countdownTimer: null,
})

const loadAccounts = async () => {
  loading.value = true
  try {
    const res = await api.get('/admin/jimeng-accounts/list')
    accounts.value = res.data.accounts || []
  } catch (e) {
    alert('加载失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    loading.value = false
  }
}

const addAccount = async () => {
  try {
    await api.post('/admin/jimeng-accounts/create', { ...newAccount })
    showAddModal.value = false
    Object.assign(newAccount, { account_id: '', display_name: '', cookie: '', priority: 5, max_concurrent: 3 })
    await loadAccounts()
    alert('账号添加成功')
  } catch (e) {
    alert('添加失败: ' + (e.response?.data?.detail || e.message))
  }
}

const toggleActive = async (account) => {
  try {
    await api.put(`/admin/jimeng-accounts/${account.account_id}`, { is_active: !account.is_active })
    await loadAccounts()
  } catch (e) {
    alert('操作失败: ' + (e.response?.data?.detail || e.message))
  }
}

const openCookieModal = (account) => {
  cookieModal.accountId = account.account_id
  cookieModal.displayName = account.display_name
  cookieModal.cookie = account.cookie || ''
  cookieModal.loading = false
  cookieModal.show = true
}

const saveCookie = async () => {
  if (!cookieModal.cookie.trim()) return
  cookieModal.loading = true
  try {
    await api.post(`/admin/jimeng-accounts/${cookieModal.accountId}/cookie-login`, {
      cookie: cookieModal.cookie.trim()
    })
    cookieModal.show = false
    await loadAccounts()
    alert('Cookie保存成功，账号已标记为已登录')
  } catch (e) {
    alert('保存失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    cookieModal.loading = false
  }
}

const logoutAccount = async (accountId) => {
  if (!confirm('确定登出该账号吗？')) return
  try {
    await api.post(`/admin/jimeng-accounts/${accountId}/logout`)
    await loadAccounts()
  } catch (e) {
    alert('登出失败: ' + (e.response?.data?.detail || e.message))
  }
}

const deleteAccount = async (accountId) => {
  if (!confirm('确定删除该账号吗？')) return
  try {
    await api.delete(`/admin/jimeng-accounts/${accountId}`)
    await loadAccounts()
    alert('账号已删除')
  } catch (e) {
    alert('删除失败: ' + (e.response?.data?.detail || e.message))
  }
}

// ===== 二维码登录功能 =====

const openQrLoginModal = async (account) => {
  qrLoginModal.accountId = account.account_id
  qrLoginModal.displayName = account.display_name
  qrLoginModal.qrBase64 = ''
  qrLoginModal.status = 'loading'
  qrLoginModal.error = ''
  qrLoginModal.loading = false
  qrLoginModal.countdown = 180
  qrLoginModal.show = true
  
  await startQrLogin()
}

const startQrLogin = async () => {
  qrLoginModal.status = 'loading'
  qrLoginModal.loading = true
  
  try {
    // 创建一个新的 axios 实例，设置更长的超时时间
    const axios = require('axios')
    const res = await axios({
      method: 'post',
      url: `/api/admin/jimeng-accounts/${qrLoginModal.accountId}/qr-login/start`,
      timeout: 0,  // 0 表示不超时
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('adminToken')}`
      }
    })
    if (res.data.qr_base64) {
      qrLoginModal.qrBase64 = res.data.qr_base64
      qrLoginModal.status = res.data.status || 'pending'
      startPolling()
      startCountdown()
    } else {
      qrLoginModal.status = 'failed'
      qrLoginModal.error = '获取二维码失败'
    }
  } catch (e) {
    qrLoginModal.status = 'failed'
    qrLoginModal.error = e.response?.data?.detail || e.message
  } finally {
    qrLoginModal.loading = false
  }
}

const startPolling = () => {
  stopPolling()
  qrLoginModal.pollTimer = setInterval(async () => {
    try {
      const res = await api.get(`/admin/jimeng-accounts/${qrLoginModal.accountId}/qr-login/status`)
      const status = res.data.status
      
      if (status === 'success') {
        qrLoginModal.status = 'success'
        stopPolling()
        stopCountdown()
        setTimeout(() => {
          closeQrModal()
          loadAccounts()
        }, 1500)
      } else if (status === 'failed') {
        qrLoginModal.status = 'failed'
        qrLoginModal.error = res.data.message || '登录失败'
        stopPolling()
        stopCountdown()
      } else if (status === 'timeout') {
        qrLoginModal.status = 'timeout'
        stopPolling()
        stopCountdown()
      } else if (status === 'scanning') {
        qrLoginModal.status = 'scanning'
      }
    } catch (e) {
      console.error('轮询状态失败:', e)
    }
  }, 2000)
}

const stopPolling = () => {
  if (qrLoginModal.pollTimer) {
    clearInterval(qrLoginModal.pollTimer)
    qrLoginModal.pollTimer = null
  }
}

const startCountdown = () => {
  stopCountdown()
  qrLoginModal.countdown = 180
  qrLoginModal.countdownTimer = setInterval(() => {
    qrLoginModal.countdown--
    if (qrLoginModal.countdown <= 0) {
      qrLoginModal.status = 'timeout'
      stopCountdown()
      stopPolling()
    }
  }, 1000)
}

const stopCountdown = () => {
  if (qrLoginModal.countdownTimer) {
    clearInterval(qrLoginModal.countdownTimer)
    qrLoginModal.countdownTimer = null
  }
}

const refreshQrCode = async () => {
  await startQrLogin()
}

const closeQrModal = () => {
  stopPolling()
  stopCountdown()
  qrLoginModal.show = false
}

onMounted(loadAccounts)
</script>
