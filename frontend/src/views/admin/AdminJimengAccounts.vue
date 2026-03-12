<template>
  <div class="space-y-6">
    <!-- Toast 通知 -->
    <div v-if="showToast" class="fixed top-4 right-4 z-50 px-4 py-3 rounded-xl shadow-lg text-sm font-medium transition-all"
      :class="toastType === 'success' ? 'bg-green-500/90 text-white' : toastType === 'error' ? 'bg-red-500/90 text-white' : 'bg-blue-500/90 text-white'">
      {{ toastMessage }}
    </div>

    <!-- 页面头部 -->
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

    <!-- 系统状态概览 -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      <div class="bg-gray-800 p-6 rounded-xl border border-gray-700">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-gray-400 text-sm">总账号数</p>
            <p class="text-2xl font-bold text-white">{{ stats.total }}</p>
          </div>
          <div class="w-12 h-12 bg-violet-500/20 rounded-lg flex items-center justify-center">
            <svg class="w-6 h-6 text-violet-400" fill="currentColor" viewBox="0 0 20 20">
              <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
            </svg>
          </div>
        </div>
      </div>

      <div class="bg-gray-800 p-6 rounded-xl border border-gray-700">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-gray-400 text-sm">启用账号</p>
            <p class="text-2xl font-bold text-green-400">{{ stats.active }}</p>
          </div>
          <div class="w-12 h-12 bg-green-500/20 rounded-lg flex items-center justify-center">
            <svg class="w-6 h-6 text-green-400" fill="currentColor" viewBox="0 0 20 20">
              <path d="M10 12a2 2 0 100-4 2 2 0 000 4z"/>
              <path fill-rule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clip-rule="evenodd"/>
            </svg>
          </div>
        </div>
      </div>

      <div class="bg-gray-800 p-6 rounded-xl border border-gray-700">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-gray-400 text-sm">已登录</p>
            <p class="text-2xl font-bold text-blue-400">{{ stats.logged_in }}</p>
          </div>
          <div class="w-12 h-12 bg-blue-500/20 rounded-lg flex items-center justify-center">
            <svg class="w-6 h-6 text-blue-400" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
            </svg>
          </div>
        </div>
      </div>

      <div class="bg-gray-800 p-6 rounded-xl border border-gray-700">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-gray-400 text-sm">未登录</p>
            <p class="text-2xl font-bold text-yellow-400">{{ stats.total - stats.logged_in }}</p>
          </div>
          <div class="w-12 h-12 bg-yellow-500/20 rounded-lg flex items-center justify-center">
            <svg class="w-6 h-6 text-yellow-400" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/>
            </svg>
          </div>
        </div>
      </div>
    </div>

    <!-- 操作按钮栏 -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-3">
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
                    Cookie登录
                  </button>
                  <button
                    @click="toggleActive(account)"
                    :class="account.is_active ? 'bg-yellow-600 hover:bg-yellow-700' : 'bg-green-600 hover:bg-green-700'"
                    class="text-white px-3 py-1 rounded text-xs transition-colors"
                  >
                    {{ account.is_active ? '禁用' : '启用' }}
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
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
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
          </div>

          <!-- 状态提示 -->
          <div class="mt-4 text-center">
            <p v-if="qrLoginModal.status === 'pending'" class="text-sm text-gray-400">
              请使用 <span class="text-blue-400">抖音App</span> 扫描二维码
            </p>
            <p v-else-if="qrLoginModal.status === 'success'" class="text-sm text-green-400 flex items-center justify-center gap-1">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
              </svg>
              登录成功！
            </p>
            <p v-else-if="qrLoginModal.status === 'timeout'" class="text-sm text-yellow-400">
              二维码已过期，请刷新
            </p>
            <p v-else-if="qrLoginModal.status === 'failed'" class="text-sm text-red-400">
              {{ qrLoginModal.error || '登录失败，请重试' }}
            </p>
          </div>

          <!-- 等待提示 -->
          <div v-if="qrLoginModal.qrBase64 && qrLoginModal.status === 'pending'"
               class="mt-2 text-xs text-gray-500">
            等待扫码中...
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
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import api from '../../api'

const router = useRouter()
const loading = ref(false)
const accounts = ref([])
const showAddModal = ref(false)
const showToast = ref(false)
const toastMessage = ref('')
const toastType = ref('success')

const stats = computed(() => {
  const total = accounts.value.length
  const active = accounts.value.filter(a => a.is_active).length
  const logged_in = accounts.value.filter(a => a.is_logged_in).length
  return { total, active, logged_in }
})

const newAccount = ref({
  account_id: '',
  display_name: '',
  cookie: '',
  priority: 5,
  max_concurrent: 1
})

const cookieModal = ref({
  show: false,
  accountId: '',
  displayName: '',
  cookie: '',
  loading: false
})

const qrLoginModal = ref({
  show: false,
  accountId: '',
  displayName: '',
  qrBase64: '',
  status: 'loading',
  error: '',
  loading: false,
  pollTimer: null,
  countdown: 180,
  countdownTimer: null
})

const loadAccounts = async () => {
  loading.value = true
  try {
    const res = await api.get('/admin/jimeng-accounts/list')
    accounts.value = res.data.accounts || []
  } catch (e) {
    console.error('加载账号失败', e)
    showToastMessage('加载账号失败', 'error')
  } finally {
    loading.value = false
  }
}

const showToastMessage = (message, type = 'success') => {
  toastMessage.value = message
  toastType.value = type
  showToast.value = true
  setTimeout(() => {
    showToast.value = false
  }, 3000)
}

const addAccount = async () => {
  try {
    await api.post('/admin/jimeng-accounts', newAccount.value)
    showToastMessage('账号添加成功')
    showAddModal.value = false
    newAccount.value = {
      account_id: '',
      display_name: '',
      cookie: '',
      priority: 5,
      max_concurrent: 1
    }
    loadAccounts()
  } catch (e) {
    console.error('添加账号失败', e)
    showToastMessage(e.response?.data?.detail || '添加账号失败', 'error')
  }
}

const openCookieModal = (account) => {
  cookieModal.value = {
    show: true,
    accountId: account.account_id,
    displayName: account.display_name,
    cookie: account.cookie || '',
    loading: false
  }
}

const saveCookie = async () => {
  cookieModal.value.loading = true
  try {
    await api.post(`/admin/jimeng-accounts/${cookieModal.value.accountId}/cookie-login`, {
      cookie: cookieModal.value.cookie
    })
    showToastMessage('Cookie 保存成功，账号已登录')
    cookieModal.value.show = false
    loadAccounts()
  } catch (e) {
    console.error('保存Cookie失败', e)
    showToastMessage(e.response?.data?.detail || '保存失败', 'error')
  } finally {
    cookieModal.value.loading = false
  }
}

const openQrLoginModal = async (account) => {
  qrLoginModal.value = {
    show: true,
    accountId: account.account_id,
    displayName: account.display_name,
    qrBase64: '',
    status: 'loading',
    error: '',
    loading: false,
    pollTimer: null,
    countdown: 180,
    countdownTimer: null
  }
  
  try {
    const res = await api.post(
      `/admin/jimeng-accounts/${account.account_id}/qr-login`,
      null,
      { timeout: 120000 }
    )
    qrLoginModal.value.qrBase64 = res.data.qr_base64
    qrLoginModal.value.status = 'pending'
    startPolling()
  } catch (e) {
    console.error('获取二维码失败', e)
    qrLoginModal.value.status = 'failed'
    qrLoginModal.value.error = e.response?.data?.detail || '获取二维码失败'
  }
}

const startPolling = () => {
  stopPolling()
  qrLoginModal.value.pollTimer = setInterval(async () => {
    try {
      const res = await api.get(`/admin/jimeng-accounts/${qrLoginModal.value.accountId}/qr-login/status`)
      const status = res.data.status
      
      if (status === 'success') {
        qrLoginModal.value.status = 'success'
        stopPolling()
        stopCountdown()
        setTimeout(() => {
          closeQrModal()
          loadAccounts()
        }, 1500)
      } else if (status === 'failed') {
        qrLoginModal.value.status = 'failed'
        qrLoginModal.value.error = res.data.message || '登录失败'
        stopPolling()
        stopCountdown()
      } else if (status === 'timeout') {
        qrLoginModal.value.status = 'timeout'
        stopPolling()
        stopCountdown()
      } else if (status === 'not_started') {
        console.log('Session not started, continuing polling...')
      } else if (status === 'pending') {
        qrLoginModal.value.status = 'pending'
      } else if (status === 'scanning') {
        qrLoginModal.value.status = 'scanning'
      }
    } catch (e) {
      console.error('轮询状态失败:', e)
    }
  }, 2000)
}

const stopPolling = () => {
  if (qrLoginModal.value.pollTimer) {
    clearInterval(qrLoginModal.value.pollTimer)
    qrLoginModal.value.pollTimer = null
  }
}

const startCountdown = () => {
}

const stopCountdown = () => {
}

const closeQrModal = () => {
  stopPolling()
  stopCountdown()
  qrLoginModal.value.show = false
}

const refreshQrCode = async () => {
  qrLoginModal.value.loading = true
  qrLoginModal.value.status = 'loading'
  try {
    const res = await api.post(
      `/admin/jimeng-accounts/${qrLoginModal.value.accountId}/qr-login`,
      null,
      { timeout: 120000 }
    )
    qrLoginModal.value.qrBase64 = res.data.qr_base64
    qrLoginModal.value.status = 'pending'
    startPolling()
  } catch (e) {
    console.error('刷新二维码失败', e)
    qrLoginModal.value.status = 'failed'
    qrLoginModal.value.error = e.response?.data?.detail || '刷新二维码失败'
  } finally {
    qrLoginModal.value.loading = false
  }
}

const toggleActive = async (account) => {
  try {
    await api.put(`/admin/jimeng-accounts/${account.account_id}/active`, {
      is_active: !account.is_active
    })
    showToastMessage(account.is_active ? '账号已禁用' : '账号已启用')
    loadAccounts()
  } catch (e) {
    console.error('切换状态失败', e)
    showToastMessage(e.response?.data?.detail || '操作失败', 'error')
  }
}

const deleteAccount = async (accountId) => {
  if (!confirm('确定删除该账号吗？')) return
  
  try {
    await api.delete(`/admin/jimeng-accounts/${accountId}`)
    showToastMessage('账号已删除')
    loadAccounts()
  } catch (e) {
    console.error('删除账号失败', e)
    showToastMessage(e.response?.data?.detail || '删除失败', 'error')
  }
}

onMounted(() => {
  loadAccounts()
})

onUnmounted(() => {
  stopPolling()
  stopCountdown()
})
</script>
