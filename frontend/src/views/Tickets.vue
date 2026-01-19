<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getCurrentUser, getMyTickets, createTicket } from '../api'

const router = useRouter()
const user = ref(null)
const tickets = ref([])
const loading = ref(false)
const showCreateModal = ref(false)
const creating = ref(false)

// 新工单表单
const newTicket = ref({
  title: '',
  content: ''
})

// Toast
const showToast = ref(false)
const toastMessage = ref('')
const toastType = ref('info')

const toast = (message, type = 'info') => {
  toastMessage.value = message
  toastType.value = type
  showToast.value = true
  setTimeout(() => { showToast.value = false }, 3000)
}

// 加载用户信息和工单
const loadData = async () => {
  loading.value = true
  try {
    user.value = await getCurrentUser()
    const data = await getMyTickets()
    tickets.value = data.tickets || []
  } catch (err) {
    console.error('加载失败', err)
  } finally {
    loading.value = false
  }
}

// 创建工单
const handleCreate = async () => {
  if (!newTicket.value.title || !newTicket.value.content) {
    toast('请填写完整的工单信息', 'error')
    return
  }
  
  creating.value = true
  try {
    await createTicket(newTicket.value.title, newTicket.value.content)
    toast('工单提交成功！', 'success')
    showCreateModal.value = false
    newTicket.value = { title: '', content: '' }
    await loadData()
  } catch (err) {
    toast(err.response?.data?.detail || '提交失败', 'error')
  } finally {
    creating.value = false
  }
}

// 状态颜色
const statusColor = (status) => {
  const colors = {
    open: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
    replied: 'bg-green-500/20 text-green-400 border-green-500/30',
    closed: 'bg-gray-500/20 text-gray-400 border-gray-500/30'
  }
  return colors[status] || colors.open
}

const statusText = (status) => {
  const texts = { open: '待处理', replied: '已回复', closed: '已关闭' }
  return texts[status] || status
}

const handleLogout = () => {
  localStorage.removeItem('token')
  router.push('/login')
}

onMounted(loadData)
</script>

<template>
  <div class="min-h-screen relative bg-gray-900/95">
    <!-- Toast -->
    <div v-if="showToast" 
         class="fixed top-4 right-4 z-50 px-4 py-3 rounded-lg shadow-lg"
         :class="toastType === 'success' ? 'bg-green-500' : toastType === 'error' ? 'bg-red-500' : 'bg-blue-500'">
      <p class="text-white font-medium">{{ toastMessage }}</p>
    </div>
    
    <!-- 导航栏 -->
    <nav class="bg-gray-900/80 backdrop-blur-xl border-b border-gray-800">
      <div class="max-w-6xl mx-auto px-4 py-4 flex justify-between items-center">
        <h1 class="text-xl font-bold text-white">我的工单</h1>
        <div class="flex items-center gap-4">
          <router-link to="/dashboard" class="text-gray-400 hover:text-white text-sm">返回控制台</router-link>
          <span v-if="user" class="text-gray-400 text-sm">{{ user.username }}</span>
          <button @click="handleLogout" class="text-red-400 hover:text-red-300 text-sm">退出</button>
        </div>
      </div>
    </nav>
    
    <!-- 主内容 -->
    <div class="max-w-4xl mx-auto px-4 py-8">
      <!-- 头部操作栏 -->
      <div class="flex justify-between items-center mb-6">
        <h2 class="text-lg text-gray-200">工单列表</h2>
        <button 
          @click="showCreateModal = true"
          class="px-4 py-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-lg hover:opacity-90 transition-all"
        >
          + 新建工单
        </button>
      </div>
      
      <!-- 工单列表 -->
      <div v-if="loading" class="text-center py-20 text-gray-400">加载中...</div>
      
      <div v-else-if="tickets.length === 0" class="text-center py-20">
        <p class="text-gray-500 mb-4">暂无工单</p>
        <button @click="showCreateModal = true" class="text-purple-400 hover:underline">提交您的第一个工单</button>
      </div>
      
      <div v-else class="space-y-4">
        <div v-for="ticket in tickets" :key="ticket.id"
             class="bg-white/5 backdrop-blur-xl border border-white/10 rounded-xl p-5 hover:border-white/20 transition-all">
          <div class="flex justify-between items-start mb-3">
            <h3 class="text-white font-medium">{{ ticket.title }}</h3>
            <span :class="[statusColor(ticket.status), 'px-2 py-1 text-xs rounded border']">
              {{ statusText(ticket.status) }}
            </span>
          </div>
          <p class="text-gray-400 text-sm mb-3 line-clamp-2">{{ ticket.content }}</p>
          
          <!-- 管理员回复 -->
          <div v-if="ticket.admin_reply" class="bg-green-500/10 border border-green-500/20 rounded-lg p-3 mb-3">
            <p class="text-sm text-gray-300">
              <span class="font-medium text-green-400">管理员回复：</span>
              {{ ticket.admin_reply }}
            </p>
          </div>
          
          <div class="text-xs text-gray-500">
            提交于 {{ new Date(ticket.created_at).toLocaleString() }}
          </div>
        </div>
      </div>
    </div>
    
    <!-- 创建工单弹窗 -->
    <div v-if="showCreateModal" class="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div class="bg-gray-800 border border-gray-700 rounded-2xl w-full max-w-lg p-6">
        <h3 class="text-xl font-bold text-white mb-4">新建工单</h3>
        
        <div class="space-y-4">
          <div>
            <label class="block text-sm text-gray-400 mb-1">标题</label>
            <input 
              v-model="newTicket.title"
              type="text"
              placeholder="请简要描述您的问题"
              class="w-full px-4 py-3 bg-gray-700/50 border border-gray-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-purple-500"
            />
          </div>
          
          <div>
            <label class="block text-sm text-gray-400 mb-1">问题描述</label>
            <textarea 
              v-model="newTicket.content"
              rows="5"
              placeholder="请详细描述您遇到的问题..."
              class="w-full px-4 py-3 bg-gray-700/50 border border-gray-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-purple-500 resize-none"
            ></textarea>
          </div>
        </div>
        
        <div class="flex justify-end gap-3 mt-6">
          <button 
            @click="showCreateModal = false"
            class="px-4 py-2 text-gray-400 hover:text-white transition-colors"
          >
            取消
          </button>
          <button 
            @click="handleCreate"
            :disabled="creating"
            class="px-6 py-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-lg hover:opacity-90 disabled:opacity-50 transition-all"
          >
            {{ creating ? '提交中...' : '提交工单' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
