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

// 状态样式
const statusMap = {
  open: { text: '待处理', class: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' },
  replied: { text: '已回复', class: 'bg-green-500/10 text-green-400 border-green-500/20' },
  closed: { text: '已关闭', class: 'bg-gray-500/10 text-gray-400 border-gray-500/20' }
}

onMounted(loadTickets)
</script>

<template>
  <div class="space-y-6">
    <!-- Toast -->
    <Transition name="toast">
      <div v-if="showToast" class="fixed top-6 right-6 z-50">
        <div :class="{
            'bg-red-500/90 text-white shadow-red-500/20': toastType === 'error',
            'bg-green-500/90 text-white shadow-green-500/20': toastType === 'success',
            'bg-blue-500/90 text-white shadow-blue-500/20': toastType === 'info'
        }" class="flex items-center gap-3 px-4 py-3 rounded-xl shadow-lg backdrop-blur-md transition-all transform hover:scale-105">
          <span class="font-medium text-sm">{{ toastMessage }}</span>
        </div>
      </div>
    </Transition>
    
    <!-- 头部 -->
    <div class="flex flex-col md:flex-row justify-between items-center gap-4 bg-white/5 p-6 rounded-2xl border border-white/5 backdrop-blur-sm">
      <div class="flex items-center gap-4">
        <div class="p-3 bg-gradient-to-br from-purple-500/20 to-blue-500/20 rounded-xl border border-white/10">
          <svg class="w-6 h-6 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"></path>
          </svg>
        </div>
        <div>
          <h1 class="text-xl font-bold text-white">工单管理</h1>
          <p class="text-sm text-gray-400">处理用户提交的问题反馈</p>
        </div>
      </div>
      
      <!-- 筛选 -->
      <div class="flex p-1 bg-black/40 rounded-xl border border-white/5">
        <button 
          v-for="filter in [
            { id: '', label: '全部' },
            { id: 'open', label: '待处理' },
            { id: 'replied', label: '已回复' },
            { id: 'closed', label: '已关闭' }
          ]"
          :key="filter.id"
          @click="currentFilter = filter.id; loadTickets()"
          class="px-4 py-1.5 rounded-lg text-sm font-medium transition-all"
          :class="currentFilter === filter.id ? 'bg-white/10 text-white shadow-sm' : 'text-gray-400 hover:text-gray-200'"
        >
          {{ filter.label }}
        </button>
      </div>
    </div>
    
    <!-- 工单列表 -->
    <div class="bg-black/20 backdrop-blur-xl border border-white/5 rounded-2xl overflow-hidden shadow-xl">
      <div v-if="loading" class="p-12">
        <div class="flex flex-col items-center justify-center gap-3">
          <div class="w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full animate-spin"></div>
          <p class="text-gray-500 text-sm">加载数据中...</p>
        </div>
      </div>
      
      <div v-else-if="tickets.length === 0" class="p-20 text-center">
        <div class="w-16 h-16 bg-white/5 rounded-full flex items-center justify-center mx-auto mb-4">
          <svg class="w-8 h-8 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"></path></svg>
        </div>
        <p class="text-gray-500">暂无相关工单</p>
      </div>
      
      <div v-else class="divide-y divide-white/5">
        <div v-for="ticket in tickets" :key="ticket.id" class="p-6 hover:bg-white/[0.02] transition-colors group">
          <div class="flex flex-col md:flex-row md:items-start justify-between gap-4 mb-4">
            <div class="flex-1">
              <div class="flex items-center gap-3 mb-2">
                <h3 class="text-lg font-bold text-gray-200">{{ ticket.title }}</h3>
                <span :class="`px-2.5 py-0.5 rounded text-xs font-bold border ${statusMap[ticket.status].class}`">
                  {{ statusMap[ticket.status].text }}
                </span>
              </div>
              
              <div class="flex items-center gap-4 text-xs text-gray-500 mb-4">
                <span class="flex items-center gap-1.5">
                  <div class="w-5 h-5 rounded-full bg-gradient-to-tr from-cyan-900 to-blue-900 flex items-center justify-center text-[10px] text-cyan-200 font-bold border border-white/5">
                    {{ ticket.username?.charAt(0).toUpperCase() }}
                  </div>
                  {{ ticket.username }}
                </span>
                <span class="w-1 h-1 bg-gray-700 rounded-full"></span>
                <span>{{ new Date(ticket.created_at).toLocaleString() }}</span>
              </div>
              
              <div class="bg-black/30 rounded-xl p-4 text-gray-300 text-sm leading-relaxed border border-white/5 max-w-3xl">
                 {{ ticket.content }}
              </div>
            </div>
            
            <div class="flex items-center gap-2 opacity-80 group-hover:opacity-100 transition-opacity">
               <button 
                 @click="handleClose(ticket)"
                 v-if="ticket.status !== 'closed'"
                 class="px-3 py-1.5 text-gray-500 hover:text-red-400 hover:bg-red-500/10 rounded-lg text-sm transition-all"
               >
                 关闭
               </button>
               <button 
                 @click="openReplyModal(ticket)"
                 v-if="ticket.status !== 'closed'"
                 class="px-4 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm shadow-lg shadow-blue-500/20 transition-all font-medium"
               >
                 {{ ticket.admin_reply ? '修改回复' : '回复' }}
               </button>
               <span v-else class="text-sm text-gray-500 italic px-4 py-1.5">已归档</span>
            </div>
          </div>
          
          <!-- 已有回复 -->
          <div v-if="ticket.admin_reply" class="bg-gradient-to-r from-green-500/5 to-transparent border-l-2 border-green-500/50 pl-4 py-2 ml-1">
            <div class="flex items-center gap-2 mb-1">
              <span class="text-xs font-bold text-green-400 uppercase tracking-wider">Admin Reply</span>
              <span class="text-[10px] text-gray-600" v-if="ticket.replied_at">{{ new Date(ticket.replied_at).toLocaleString() }}</span>
            </div>
            <p class="text-sm text-gray-400">
              {{ ticket.admin_reply }}
            </p>
          </div>
        </div>
      </div>
    </div>
    
    <!-- 回复弹窗 -->
    <Transition name="modal">
      <div v-if="showReplyModal" class="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div class="absolute inset-0 bg-black/80 backdrop-blur-sm" @click="showReplyModal = false"></div>
        
        <div class="relative bg-[#151921] border border-white/10 rounded-2xl w-full max-w-lg shadow-2xl overflow-hidden transform transition-all">
          <div class="p-6 border-b border-white/10 bg-white/5">
            <h3 class="text-xl font-bold text-white">回复工单</h3>
            <p class="text-sm text-gray-400 mt-1">回复用户将通过系统通知告知对方</p>
          </div>
          
          <div class="p-6">
            <div class="mb-4 p-4 bg-black/40 rounded-xl border border-white/5">
              <p class="text-xs text-gray-500 mb-2 uppercase tracking-wider font-bold">用户问题</p>
              <p class="text-gray-300 text-sm leading-relaxed">{{ replyingTicket?.content }}</p>
            </div>
            
            <div>
              <label class="text-xs text-gray-500 mb-2 block uppercase tracking-wider font-bold">回复内容</label>
              <textarea 
                v-model="replyContent"
                rows="6"
                placeholder="请输入详细的回复内容..."
                class="w-full px-4 py-3 bg-black/30 border border-white/10 rounded-xl text-white placeholder-gray-600 focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20 focus:outline-none transition-all resize-none"
              ></textarea>
            </div>
          </div>
          
          <div class="p-6 border-t border-white/10 flex justify-end gap-3 bg-black/20">
            <button 
              @click="showReplyModal = false"
              class="px-5 py-2.5 text-gray-400 hover:text-white font-medium transition-colors hover:bg-white/5 rounded-lg"
            >
              取消
            </button>
            <button 
              @click="handleReply"
              :disabled="replying"
              class="px-6 py-2.5 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-lg shadow-lg shadow-blue-500/20 disabled:opacity-50 transition-all active:scale-95"
            >
              {{ replying ? '发送中...' : '发送回复' }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
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
  transform: translate(0, -20px);
}

.modal-enter-active,
.modal-leave-active {
  transition: all 0.2s ease-out;
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
  transform: scale(0.95);
}
</style>
