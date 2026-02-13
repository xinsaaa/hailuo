<template>
  <div class="min-h-screen bg-gray-900 text-white">
    <!-- 页面头部 -->
    <div class="bg-gray-800 px-6 py-4 border-b border-gray-700">
      <div class="flex items-center justify-between">
        <h1 class="text-2xl font-bold text-white">多账号智能调度系统</h1>
        <div class="flex items-center space-x-4">
          <div class="flex items-center space-x-2">
            <div class="w-3 h-3 rounded-full" :class="systemStatus.is_running ? 'bg-green-400' : 'bg-yellow-400'"></div>
            <span class="text-sm">{{ systemStatus.is_running ? '系统运行中' : '系统启动中...' }}</span>
          </div>
          <div class="px-4 py-2 bg-gray-700 text-gray-300 rounded-lg text-sm">
            自动管理系统
          </div>
        </div>
      </div>
    </div>

    <div class="p-6 max-w-7xl mx-auto">
      <!-- 系统状态概览 -->
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div class="bg-gray-800 p-6 rounded-xl border border-gray-700">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-gray-400 text-sm">总账号数</p>
              <p class="text-2xl font-bold text-white">{{ performance.total_accounts }}</p>
            </div>
            <div class="w-12 h-12 bg-blue-500/20 rounded-lg flex items-center justify-center">
              <svg class="w-6 h-6 text-blue-400" fill="currentColor" viewBox="0 0 20 20">
                <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
              </svg>
            </div>
          </div>
        </div>

        <div class="bg-gray-800 p-6 rounded-xl border border-gray-700">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-gray-400 text-sm">活跃账号</p>
              <p class="text-2xl font-bold text-green-400">{{ performance.active_accounts }}</p>
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
              <p class="text-gray-400 text-sm">系统负载</p>
              <p class="text-2xl font-bold" :class="getLoadColor(performance.utilization)">
                {{ (performance.utilization * 100).toFixed(1) }}%
              </p>
            </div>
            <div class="w-12 h-12 bg-yellow-500/20 rounded-lg flex items-center justify-center">
              <svg class="w-6 h-6 text-yellow-400" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M3 4a1 1 0 011-1h12a1 1 0 011 1v2a1 1 0 01-1 1H4a1 1 0 01-1-1V4zm0 4a1 1 0 011-1h12a1 1 0 011 1v2a1 1 0 01-1 1H4a1 1 0 01-1-1V8zm0 4a1 1 0 011-1h12a1 1 0 011 1v2a1 1 0 01-1 1H4a1 1 0 01-1-1v-2z" clip-rule="evenodd"/>
              </svg>
            </div>
          </div>
        </div>

        <div class="bg-gray-800 p-6 rounded-xl border border-gray-700">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-gray-400 text-sm">可用槽位</p>
              <p class="text-2xl font-bold text-blue-400">{{ performance.available_slots }}</p>
            </div>
            <div class="w-12 h-12 bg-purple-500/20 rounded-lg flex items-center justify-center">
              <svg class="w-6 h-6 text-purple-400" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clip-rule="evenodd"/>
              </svg>
            </div>
          </div>
        </div>
      </div>

      <!-- 操作按钮栏 -->
      <div class="flex items-center justify-between mb-6">
        <div class="flex items-center space-x-4">
          <button 
            @click="showAddModal = true"
            class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg font-medium transition-colors flex items-center"
          >
            <svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"/>
            </svg>
            添加账号
          </button>
          <button 
            @click="refreshAccounts"
            :disabled="loading"
            class="bg-gray-700 hover:bg-gray-600 text-white px-4 py-2 rounded-lg font-medium transition-colors flex items-center"
          >
            <svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
            </svg>
            {{ loading ? '刷新中...' : '刷新状态' }}
          </button>
        </div>
        <div class="flex items-center space-x-2">
          <span class="text-sm text-gray-400">性能等级:</span>
          <span class="px-3 py-1 rounded-full text-sm font-medium" :class="getPerformanceClass(performance.performance_level)">
            {{ performance.performance_level }}
          </span>
        </div>
      </div>

      <!-- 账号列表 -->
      <div class="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
        <div class="p-4 border-b border-gray-700">
          <h3 class="text-lg font-semibold text-white">账号管理</h3>
        </div>
        
        <div class="overflow-x-auto">
          <table class="w-full">
            <thead class="bg-gray-700/50">
              <tr>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">账号信息</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">状态</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">负载情况</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">优先级</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">操作</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-700">
              <tr v-for="account in accounts" :key="account.account_id" class="hover:bg-gray-700/30">
                <td class="px-6 py-4 whitespace-nowrap">
                  <div>
                    <div class="text-sm font-medium text-white">{{ account.display_name }}</div>
                    <div class="text-sm text-gray-400">{{ account.phone_number }}</div>
                    <div class="text-xs text-gray-500">ID: {{ account.account_id }}</div>
                  </div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                  <div class="flex flex-col space-y-1">
                    <span class="inline-flex px-2 py-1 text-xs font-semibold rounded-full" 
                      :class="account.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'">
                      {{ account.is_active ? '激活' : '禁用' }}
                    </span>
                    <span class="inline-flex px-2 py-1 text-xs font-semibold rounded-full"
                      :class="account.is_logged_in ? 'bg-blue-100 text-blue-800' : 'bg-red-100 text-red-800'">
                      {{ account.is_logged_in ? '已登录' : '未登录' }}
                    </span>
                  </div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                  <div>
                    <div class="flex items-center">
                      <div class="flex-1 bg-gray-600 rounded-full h-2 mr-2">
                        <div class="bg-blue-500 h-2 rounded-full" 
                          :style="{ width: (account.utilization * 100) + '%' }"></div>
                      </div>
                      <span class="text-sm text-gray-300">{{ (account.utilization * 100).toFixed(1) }}%</span>
                    </div>
                    <div class="text-xs text-gray-400 mt-1">
                      {{ account.current_tasks }}/{{ account.max_concurrent }} 任务
                    </div>
                  </div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                  <div class="flex items-center space-x-1">
                    <span v-for="i in 10" :key="i" 
                      class="w-2 h-2 rounded-full"
                      :class="i <= account.priority ? 'bg-yellow-400' : 'bg-gray-600'"></span>
                    <span class="text-sm text-gray-300 ml-2">{{ account.priority }}</span>
                  </div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium">
                  <div class="flex items-center space-x-2">
                    <button 
                      @click="loginAccount(account.account_id)"
                      :disabled="account.is_logged_in"
                      class="bg-green-600 hover:bg-green-700 disabled:bg-gray-600 text-white px-3 py-1 rounded text-xs transition-colors"
                    >
                      {{ account.is_logged_in ? '已登录' : '登录' }}
                    </button>
                    <button 
                      @click="toggleAccount(account.account_id, !account.is_active)"
                      class="px-3 py-1 rounded text-xs transition-colors"
                      :class="account.is_active ? 'bg-yellow-600 hover:bg-yellow-700 text-white' : 'bg-green-600 hover:bg-green-700 text-white'"
                    >
                      {{ account.is_active ? '禁用' : '启用' }}
                    </button>
                    <button 
                      @click="editAccount(account)"
                      class="bg-blue-600 hover:bg-blue-700 text-white px-3 py-1 rounded text-xs transition-colors"
                    >
                      编辑
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
    </div>

    <!-- 添加账号弹窗 -->
    <div v-if="showAddModal" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div class="bg-gray-800 p-6 rounded-xl border border-gray-700 w-full max-w-md">
        <h3 class="text-lg font-semibold text-white mb-4">添加新账号</h3>
        <form @submit.prevent="addAccount">
          <div class="space-y-4">
            <div>
              <label class="block text-sm font-medium text-gray-300 mb-2">账号ID</label>
              <input v-model="newAccount.account_id" type="text" required
                class="w-full px-3 py-2 bg-gray-700 border border-gray-600 text-white rounded-lg focus:ring-blue-500 focus:border-blue-500">
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-300 mb-2">手机号</label>
              <input v-model="newAccount.phone_number" type="tel" required
                class="w-full px-3 py-2 bg-gray-700 border border-gray-600 text-white rounded-lg focus:ring-blue-500 focus:border-blue-500">
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-300 mb-2">显示名称</label>
              <input v-model="newAccount.display_name" type="text" required
                class="w-full px-3 py-2 bg-gray-700 border border-gray-600 text-white rounded-lg focus:ring-blue-500 focus:border-blue-500">
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-300 mb-2">优先级 (1-10)</label>
              <input v-model.number="newAccount.priority" type="number" min="1" max="10" required
                class="w-full px-3 py-2 bg-gray-700 border border-gray-600 text-white rounded-lg focus:ring-blue-500 focus:border-blue-500">
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-300 mb-2">最大并发数</label>
              <input v-model.number="newAccount.max_concurrent" type="number" min="1" max="10" required
                class="w-full px-3 py-2 bg-gray-700 border border-gray-600 text-white rounded-lg focus:ring-blue-500 focus:border-blue-500">
            </div>
          </div>
          <div class="flex justify-end space-x-3 mt-6">
            <button type="button" @click="showAddModal = false"
              class="px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white rounded-lg transition-colors">
              取消
            </button>
            <button type="submit"
              class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors">
              添加
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>

  <!-- 验证码登录弹窗 -->
  <div v-if="verificationModal.show" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
    <div class="bg-slate-800 rounded-xl p-6 w-full max-w-md mx-4">
      <h3 class="text-xl font-bold text-white mb-4">
        {{ verificationModal.step === 'send' ? '发送验证码' : '验证码登录' }}
      </h3>
      
      <div class="mb-4">
        <p class="text-gray-300 mb-2">账号：{{ verificationModal.accountName }}</p>
        
        <div v-if="verificationModal.step === 'send'" class="text-gray-400 text-sm">
          <p>将向绑定手机发送验证码</p>
          <p>请确认手机号正确并保持畅通</p>
        </div>
        
        <div v-else class="space-y-3">
          <div>
            <label class="block text-sm font-medium text-gray-300 mb-1">
              验证码
            </label>
            <input
              v-model="verificationModal.code"
              type="text"
              placeholder="请输入6位验证码"
              maxlength="6"
              class="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-blue-500"
              @keyup.enter="verifyAndLogin"
            />
          </div>
          <p class="text-gray-400 text-sm">
            请输入收到的短信验证码
          </p>
        </div>
      </div>
      
      <div class="flex justify-end space-x-3">
        <button
          type="button"
          @click="closeVerificationModal"
          :disabled="verificationModal.loading"
          class="px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white rounded-lg transition-colors disabled:opacity-50"
        >
          取消
        </button>
        
        <button
          v-if="verificationModal.step === 'send'"
          @click="sendVerificationCode"
          :disabled="verificationModal.loading"
          class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors disabled:opacity-50 flex items-center"
        >
          <svg v-if="verificationModal.loading" class="animate-spin h-4 w-4 mr-2" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="m4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          {{ verificationModal.loading ? '发送中...' : '发送验证码' }}
        </button>
        
        <button
          v-else
          @click="verifyAndLogin"
          :disabled="verificationModal.loading || !verificationModal.code.trim()"
          class="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg transition-colors disabled:opacity-50 flex items-center"
        >
          <svg v-if="verificationModal.loading" class="animate-spin h-4 w-4 mr-2" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="m4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          {{ verificationModal.loading ? '登录中...' : '确认登录' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import api from '../../api'

const loading = ref(false)
const showAddModal = ref(false)

// 系统状态
const systemStatus = reactive({
  is_running: false,
  active_tasks: 0
})

// 性能指标
const performance = reactive({
  total_accounts: 0,
  active_accounts: 0,
  logged_in_accounts: 0,
  total_capacity: 0,
  current_load: 0,
  utilization: 0,
  performance_level: '优秀',
  available_slots: 0,
  efficiency_score: 0
})

// 账号列表
const accounts = ref([])

// 新账号表单
const newAccount = reactive({
  account_id: '',
  phone_number: '',
  display_name: '',
  priority: 5,
  max_concurrent: 3
})

// 获取系统状态
const getSystemStatus = async () => {
  try {
    const response = await api.get('/admin/accounts/status')
    Object.assign(systemStatus, response.data)
    
    const perfResponse = await api.get('/admin/accounts/performance')
    Object.assign(performance, perfResponse.data)
  } catch (error) {
    console.error('获取系统状态失败:', error)
  }
}

// 获取账号列表
const getAccounts = async () => {
  try {
    const response = await api.get('/admin/accounts/list')
    accounts.value = response.data.accounts
  } catch (error) {
    console.error('获取账号列表失败:', error)
  }
}

// 刷新数据
const refreshAccounts = async () => {
  loading.value = true
  try {
    await Promise.all([getSystemStatus(), getAccounts()])
  } finally {
    loading.value = false
  }
}

// 系统状态说明：多账号管理系统现在自动启动，无需手动控制

// 添加账号
const addAccount = async () => {
  try {
    await api.post('/admin/accounts/create', newAccount)
    showAddModal.value = false
    Object.assign(newAccount, {
      account_id: '',
      phone_number: '',
      display_name: '',
      priority: 5,
      max_concurrent: 3
    })
    await refreshAccounts()
    alert('账号添加成功')
  } catch (error) {
    alert('添加失败: ' + error.response?.data?.detail)
  }
}

// 验证码登录状态
const verificationModal = reactive({
  show: false,
  accountId: '',
  accountName: '',
  code: '',
  loading: false,
  step: 'send' // 'send' | 'verify'
})

// 登录账号
const loginAccount = async (accountId) => {
  try {
    const response = await api.post(`/admin/accounts/${accountId}/login`)
    
    if (response.data.success) {
      await refreshAccounts()
      alert('登录成功！')
    } else if (response.data.require_code) {
      // 需要验证码登录
      const account = accounts.value.find(acc => acc.account_id === accountId)
      verificationModal.accountId = accountId
      verificationModal.accountName = account?.display_name || accountId
      verificationModal.step = 'send'
      verificationModal.show = true
    }
  } catch (error) {
    alert('登录失败: ' + error.response?.data?.detail)
  }
}

// 发送验证码
const sendVerificationCode = async () => {
  verificationModal.loading = true
  try {
    const response = await api.post(`/admin/accounts/${verificationModal.accountId}/send-code`)
    if (response.data.success) {
      verificationModal.step = 'verify'
      alert('验证码已发送到绑定手机，请查收')
    } else {
      alert('发送验证码失败')
    }
  } catch (error) {
    alert('发送验证码失败: ' + error.response?.data?.detail)
  } finally {
    verificationModal.loading = false
  }
}

// 验证码登录
const verifyAndLogin = async () => {
  if (!verificationModal.code.trim()) {
    alert('请输入验证码')
    return
  }
  
  verificationModal.loading = true
  try {
    const response = await api.post(`/admin/accounts/${verificationModal.accountId}/verify-code`, {
      verification_code: verificationModal.code
    })
    
    if (response.data.success) {
      verificationModal.show = false
      verificationModal.code = ''
      await refreshAccounts()
      alert('登录成功！')
    } else {
      alert('登录失败，请检查验证码是否正确')
    }
  } catch (error) {
    alert('验证码登录失败: ' + error.response?.data?.detail)
  } finally {
    verificationModal.loading = false
  }
}

// 关闭验证码弹窗
const closeVerificationModal = () => {
  verificationModal.show = false
  verificationModal.code = ''
  verificationModal.step = 'send'
}

// 切换账号状态
const toggleAccount = async (accountId, isActive) => {
  try {
    await api.put(`/admin/accounts/${accountId}`, {
      is_active: isActive
    })
    await refreshAccounts()
  } catch (error) {
    alert('操作失败: ' + error.response?.data?.detail)
  }
}

// 删除账号
const deleteAccount = async (accountId) => {
  if (!confirm('确定要删除这个账号吗？')) return
  
  try {
    await api.delete(`/admin/accounts/${accountId}`)
    await refreshAccounts()
    alert('账号删除成功')
  } catch (error) {
    alert('删除失败: ' + error.response?.data?.detail)
  }
}

// 工具函数
const getLoadColor = (utilization) => {
  if (utilization < 0.3) return 'text-green-400'
  if (utilization < 0.6) return 'text-yellow-400'
  if (utilization < 0.8) return 'text-orange-400'
  return 'text-red-400'
}

const getPerformanceClass = (level) => {
  const classes = {
    '优秀': 'bg-green-100 text-green-800',
    '良好': 'bg-blue-100 text-blue-800',
    '一般': 'bg-yellow-100 text-yellow-800',
    '繁忙': 'bg-red-100 text-red-800'
  }
  return classes[level] || 'bg-gray-100 text-gray-800'
}

// 定时刷新
let refreshInterval = null

onMounted(async () => {
  await refreshAccounts()
  // 每30秒自动刷新
  refreshInterval = setInterval(refreshAccounts, 30000)
})

onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
})
</script>
