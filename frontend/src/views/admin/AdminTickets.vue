<script setup>
import { ref, onMounted } from 'vue'
import { getAdminTickets, replyTicket, closeTicket } from '../../api'

const tickets = ref([])
const loading = ref(false)
const currentFilter = ref('')

// 回复弹窗
const showReplyModal = ref(false)
const replyingTicket = ref(null)
const replyContent = ref('')
const replying = ref(false)

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

// 加载工单
const loadTickets = async () => {
  loading.value = true
  try {
    const data = await getAdminTickets(1, 100, currentFilter.value)
    tickets.value = data.tickets || []
  } catch (err) {
    toast('加载工单失败', 'error')
  } finally {
    loading.value = false
  }
}

// 打开回复弹窗
const openReplyModal = (ticket) => {
  replyingTicket.value = ticket
  replyContent.value = ticket.admin_reply || ''
  showReplyModal.value = true
}

// 回复工单
const handleReply = async () => {
  if (!replyContent.value.trim()) {
    toast('请输入回复内容', 'error')
    return
  }
  
  replying.value = true
  try {
    await replyTicket(replyingTicket.value.id, replyContent.value)
    toast('回复成功', 'success')
    showReplyModal.value = false
    await loadTickets()
  } catch (err) {
    toast(err.response?.data?.detail || '回复失败', 'error')
  } finally {
    replying.value = false
  }
}

// 关闭工单
const handleClose = async (ticket) => {
  if (!confirm('确定要关闭此工单吗？')) return
  
  try {
    await closeTicket(ticket.id)
    toast('工单已关闭', 'success')
    await loadTickets()
  } catch (err) {
    toast(err.response?.data?.detail || '关闭失败', 'error')
  }
}

// 状态颜色和文本
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

onMounted(loadTickets)
</script>

<template>
  <div class="p-6">
    <!-- Toast -->
    <div v-if="showToast" 
         class="fixed top-4 right-4 z-50 px-4 py-3 rounded-lg shadow-lg"
         :class="toastType === 'success' ? 'bg-green-500' : toastType === 'error' ? 'bg-red-500' : 'bg-blue-500'">
      <p class="text-white font-medium">{{ toastMessage }}</p>
    </div>
    
    <!-- 头部 -->
    <div class="flex justify-between items-center mb-6">
      <h1 class="text-2xl font-bold text-gray-100 flex items-center gap-2">
        <span class="p-2 bg-purple-500/20 text-purple-400 rounded-lg">
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"></path>
          </svg>
        </span>
        工单管理
      </h1>
      
      <!-- 筛选 -->
      <div class="flex gap-2">
        <button 
          @click="currentFilter = ''; loadTickets()"
          :class="['px-3 py-1.5 rounded-lg text-sm transition-all', currentFilter === '' ? 'bg-purple-500 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600']"
        >全部</button>
        <button 
          @click="currentFilter = 'open'; loadTickets()"
          :class="['px-3 py-1.5 rounded-lg text-sm transition-all', currentFilter === 'open' ? 'bg-yellow-500 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600']"
        >待处理</button>
        <button 
          @click="currentFilter = 'replied'; loadTickets()"
          :class="['px-3 py-1.5 rounded-lg text-sm transition-all', currentFilter === 'replied' ? 'bg-green-500 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600']"
        >已回复</button>
        <button 
          @click="currentFilter = 'closed'; loadTickets()"
          :class="['px-3 py-1.5 rounded-lg text-sm transition-all', currentFilter === 'closed' ? 'bg-gray-500 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600']"
        >已关闭</button>
      </div>
    </div>
    
    <!-- 工单列表 -->
    <div class="bg-gray-800/50 backdrop-blur-xl border border-gray-700/50 rounded-2xl overflow-hidden">
      <div v-if="loading" class="py-20 text-center text-gray-400">加载中...</div>
      
      <div v-else-if="tickets.length === 0" class="py-20 text-center text-gray-500">暂无工单</div>
      
      <div v-else class="divide-y divide-gray-700/50">
        <div v-for="ticket in tickets" :key="ticket.id" class="p-5 hover:bg-gray-700/20 transition-colors">
          <div class="flex justify-between items-start mb-2">
            <div>
              <h3 class="text-white font-medium">{{ ticket.title }}</h3>
              <p class="text-sm text-gray-500">用户: {{ ticket.username }} · {{ new Date(ticket.created_at).toLocaleString() }}</p>
            </div>
            <span :class="[statusColor(ticket.status), 'px-2 py-1 text-xs rounded border']">
              {{ statusText(ticket.status) }}
            </span>
          </div>
          
          <p class="text-gray-400 text-sm mb-3">{{ ticket.content }}</p>
          
          <!-- 已有回复 -->
          <div v-if="ticket.admin_reply" class="bg-green-500/10 border border-green-500/20 rounded-lg p-3 mb-3">
            <p class="text-sm text-gray-300">
              <span class="font-medium text-green-400">已回复：</span>
              {{ ticket.admin_reply }}
            </p>
          </div>
          
          <!-- 操作按钮 -->
          <div class="flex gap-2" v-if="ticket.status !== 'closed'">
            <button 
              @click="openReplyModal(ticket)"
              class="px-3 py-1.5 bg-blue-500/20 text-blue-400 border border-blue-500/30 rounded-lg text-sm hover:bg-blue-500/30 transition-all"
            >
              {{ ticket.admin_reply ? '修改回复' : '回复' }}
            </button>
            <button 
              @click="handleClose(ticket)"
              class="px-3 py-1.5 bg-gray-500/20 text-gray-400 border border-gray-500/30 rounded-lg text-sm hover:bg-gray-500/30 transition-all"
            >
              关闭工单
            </button>
          </div>
        </div>
      </div>
    </div>
    
    <!-- 回复弹窗 -->
    <div v-if="showReplyModal" class="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div class="bg-gray-800 border border-gray-700 rounded-2xl w-full max-w-lg p-6">
        <h3 class="text-xl font-bold text-white mb-4">回复工单</h3>
        
        <div class="mb-4 p-3 bg-gray-700/50 rounded-lg">
          <p class="text-sm text-gray-400 mb-1">用户问题：</p>
          <p class="text-white">{{ replyingTicket?.content }}</p>
        </div>
        
        <textarea 
          v-model="replyContent"
          rows="4"
          placeholder="请输入回复内容..."
          class="w-full px-4 py-3 bg-gray-700/50 border border-gray-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 resize-none"
        ></textarea>
        
        <div class="flex justify-end gap-3 mt-4">
          <button 
            @click="showReplyModal = false"
            class="px-4 py-2 text-gray-400 hover:text-white transition-colors"
          >
            取消
          </button>
          <button 
            @click="handleReply"
            :disabled="replying"
            class="px-6 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 transition-all"
          >
            {{ replying ? '回复中...' : '发送回复' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
