<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { getAdminTickets, replyTicket, closeTicket, getAdminTicketDetail } from '../../api'

const allTickets = ref([])
const loading = ref(false)
const currentFilter = ref('')
const searchQuery = ref('')

// 回复弹窗/详情
const showReplyModal = ref(false)
const currentTicket = ref(null)
const messages = ref([])
const detailLoading = ref(false)
const replyContent = ref('')
const replying = ref(false)

// 快捷回复
const showQuickReplies = ref(false)
const quickReplies = [
  '您好，您的问题我们已收到，正在处理中，请稍候。',
  '您好，该问题已修复，请刷新页面重试。',
  '您好，请提供更多详细信息（如截图、操作步骤），以便我们排查。',
  '您好，该功能暂不支持，我们已记录需求，后续会考虑添加。',
  '您好，您的余额已手动调整，请刷新查看。如有疑问请继续反馈。',
]

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

// 统计
const stats = computed(() => {
  const all = allTickets.value
  return {
    total: all.length,
    open: all.filter(t => t.status === 'open').length,
    replied: all.filter(t => t.status === 'replied').length,
    closed: all.filter(t => t.status === 'closed').length,
  }
})

// 筛选+搜索+智能排序
const filteredTickets = computed(() => {
  let list = allTickets.value

  // 状态筛选
  if (currentFilter.value) {
    list = list.filter(t => t.status === currentFilter.value)
  }

  // 搜索
  if (searchQuery.value.trim()) {
    const q = searchQuery.value.toLowerCase()
    list = list.filter(t =>
      t.title.toLowerCase().includes(q) ||
      t.content.toLowerCase().includes(q) ||
      (t.username && t.username.toLowerCase().includes(q))
    )
  }

  // 智能排序: open最前, replied其次, closed最后; 同状态按时间倒序
  const statusOrder = { open: 0, replied: 1, closed: 2 }
  return [...list].sort((a, b) => {
    const sa = statusOrder[a.status] ?? 9
    const sb = statusOrder[b.status] ?? 9
    if (sa !== sb) return sa - sb
    return new Date(b.updated_at || b.created_at) - new Date(a.updated_at || a.created_at)
  })
})

// 相对时间
const relativeTime = (dateStr) => {
  if (!dateStr) return ''
  const now = Date.now()
  const diff = now - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return '刚刚'
  if (mins < 60) return `${mins}分钟前`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}小时前`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days}天前`
  return new Date(dateStr).toLocaleDateString()
}

// 加载工单
const loadTickets = async () => {
  loading.value = true
  try {
    const data = await getAdminTickets(1, 200, '')
    allTickets.value = data.tickets || []
  } catch (err) {
    toast('加载工单失败', 'error')
  } finally {
    loading.value = false
  }
}

// 自动刷新 (30秒)
let refreshTimer = null
onMounted(() => {
  loadTickets()
  refreshTimer = setInterval(loadTickets, 30000)
})
onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})

// 打开详情/回复窗口
const openReplyModal = async (ticket) => {
  currentTicket.value = ticket
  showReplyModal.value = true
  detailLoading.value = true
  showQuickReplies.value = false
  try {
    const data = await getAdminTicketDetail(ticket.id)
    currentTicket.value = data.ticket
    messages.value = data.messages || []
    await nextTick()
    scrollToBottom()
  } catch (err) {
    toast('加载详情失败', 'error')
  } finally {
    detailLoading.value = false
  }
}

const scrollToBottom = () => {
  const container = document.getElementById('admin-messages-container')
  if (container) container.scrollTop = container.scrollHeight
}

// 回复工单
const handleReply = async () => {
  if (!replyContent.value.trim()) {
    toast('请输入回复内容', 'error')
    return
  }
  replying.value = true
  try {
    await replyTicket(currentTicket.value.id, replyContent.value)
    toast('回复成功', 'success')
    replyContent.value = ''
    showQuickReplies.value = false
    await openReplyModal(currentTicket.value)
    await loadTickets()
  } catch (err) {
    toast(err.response?.data?.detail || '回复失败', 'error')
  } finally {
    replying.value = false
  }
}

// 快捷回复
const useQuickReply = (text) => {
  replyContent.value = text
  showQuickReplies.value = false
}

// 关闭工单
const handleClose = async (ticketId) => {
  if (!confirm('确定要关闭此工单吗？')) return
  try {
    await closeTicket(ticketId)
    toast('工单已关闭', 'success')
    showReplyModal.value = false
    await loadTickets()
  } catch (err) {
    toast(err.response?.data?.detail || '关闭失败', 'error')
  }
}

// 状态样式
const statusMap = {
  open: { text: '待处理', class: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20', dot: 'bg-yellow-400' },
  replied: { text: '已回复', class: 'bg-green-500/10 text-green-400 border-green-500/20', dot: 'bg-green-400' },
  closed: { text: '已关闭', class: 'bg-gray-500/10 text-gray-400 border-gray-500/20', dot: 'bg-gray-500' }
}
</script>

<template>
  <div class="space-y-6">
    <!-- Toast -->
    <Transition name="toast">
      <div v-if="showToast" class="fixed top-6 right-6 z-[100]">
        <div :class="{
            'bg-red-500/90 text-white shadow-red-500/20': toastType === 'error',
            'bg-green-500/90 text-white shadow-green-500/20': toastType === 'success',
            'bg-blue-500/90 text-white shadow-blue-500/20': toastType === 'info'
        }" class="flex items-center gap-3 px-4 py-3 rounded-xl shadow-lg backdrop-blur-md">
          <span class="font-medium text-sm">{{ toastMessage }}</span>
        </div>
      </div>
    </Transition>
    
    <!-- 统计栏 -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
      <div class="bg-slate-800/60 rounded-xl border border-slate-700/50 p-4 flex items-center gap-3">
        <div class="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center">
          <svg class="w-5 h-5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"></path></svg>
        </div>
        <div>
          <p class="text-2xl font-bold text-white">{{ stats.total }}</p>
          <p class="text-xs text-gray-400">全部工单</p>
        </div>
      </div>
      <div class="bg-slate-800/60 rounded-xl border border-slate-700/50 p-4 flex items-center gap-3 cursor-pointer hover:border-yellow-500/30 transition-colors" @click="currentFilter = 'open'">
        <div class="w-10 h-10 rounded-lg bg-yellow-500/10 flex items-center justify-center">
          <span class="relative flex h-3 w-3">
            <span v-if="stats.open > 0" class="animate-ping absolute inline-flex h-full w-full rounded-full bg-yellow-400 opacity-75"></span>
            <span class="relative inline-flex rounded-full h-3 w-3 bg-yellow-400"></span>
          </span>
        </div>
        <div>
          <p class="text-2xl font-bold text-yellow-400">{{ stats.open }}</p>
          <p class="text-xs text-gray-400">待处理</p>
        </div>
      </div>
      <div class="bg-slate-800/60 rounded-xl border border-slate-700/50 p-4 flex items-center gap-3 cursor-pointer hover:border-green-500/30 transition-colors" @click="currentFilter = 'replied'">
        <div class="w-10 h-10 rounded-lg bg-green-500/10 flex items-center justify-center">
          <svg class="w-5 h-5 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
        </div>
        <div>
          <p class="text-2xl font-bold text-green-400">{{ stats.replied }}</p>
          <p class="text-xs text-gray-400">已回复</p>
        </div>
      </div>
      <div class="bg-slate-800/60 rounded-xl border border-slate-700/50 p-4 flex items-center gap-3 cursor-pointer hover:border-gray-500/30 transition-colors" @click="currentFilter = 'closed'">
        <div class="w-10 h-10 rounded-lg bg-gray-500/10 flex items-center justify-center">
          <svg class="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
        </div>
        <div>
          <p class="text-2xl font-bold text-gray-400">{{ stats.closed }}</p>
          <p class="text-xs text-gray-400">已关闭</p>
        </div>
      </div>
    </div>

    <!-- 搜索 + 筛选 -->
    <div class="flex flex-col md:flex-row justify-between items-center gap-4">
      <!-- 搜索框 -->
      <div class="relative w-full md:w-80">
        <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
        <input
          v-model="searchQuery"
          type="text"
          placeholder="搜索标题、内容或用户名..."
          class="w-full pl-10 pr-4 py-2.5 bg-slate-800/60 border border-slate-700/50 rounded-xl text-white text-sm placeholder-gray-500 focus:outline-none focus:border-blue-500/50"
        />
      </div>
      
      <!-- 筛选按钮 -->
      <div class="flex p-1 bg-black/40 rounded-xl border border-white/5">
        <button 
          v-for="filter in [
            { id: '', label: '全部' },
            { id: 'open', label: '待处理' },
            { id: 'replied', label: '已回复' },
            { id: 'closed', label: '已关闭' }
          ]"
          :key="filter.id"
          @click="currentFilter = filter.id"
          class="px-4 py-1.5 rounded-lg text-sm font-medium transition-all"
          :class="currentFilter === filter.id ? 'bg-white/10 text-white shadow-sm' : 'text-gray-400 hover:text-gray-200'"
        >
          {{ filter.label }}
        </button>
      </div>
    </div>
    
    <!-- 工单列表 -->
    <div class="bg-black/20 backdrop-blur-xl border border-white/5 rounded-2xl overflow-hidden shadow-xl">
      <div v-if="loading && allTickets.length === 0" class="p-12">
        <div class="flex flex-col items-center justify-center gap-3">
          <div class="w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full animate-spin"></div>
          <p class="text-gray-500 text-sm">加载数据中...</p>
        </div>
      </div>
      
      <div v-else-if="filteredTickets.length === 0" class="p-20 text-center">
        <div class="w-16 h-16 bg-white/5 rounded-full flex items-center justify-center mx-auto mb-4">
          <svg class="w-8 h-8 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"></path></svg>
        </div>
        <p class="text-gray-500">{{ searchQuery ? '未搜索到匹配工单' : '暂无相关工单' }}</p>
      </div>
      
      <div v-else class="divide-y divide-white/5">
        <div 
          v-for="ticket in filteredTickets" :key="ticket.id" 
          class="p-5 hover:bg-white/[0.03] transition-colors cursor-pointer group"
          @click="openReplyModal(ticket)"
        >
          <div class="flex items-center gap-4">
            <!-- 状态指示条 -->
            <div class="w-1 h-12 rounded-full shrink-0" :class="statusMap[ticket.status].dot"></div>
            
            <!-- 内容 -->
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 mb-1">
                <h3 class="text-base font-bold text-gray-200 truncate">{{ ticket.title }}</h3>
                <span :class="`px-2 py-0.5 rounded text-[10px] font-bold border shrink-0 ${statusMap[ticket.status].class}`">
                  {{ statusMap[ticket.status].text }}
                </span>
              </div>
              <p class="text-gray-500 text-sm truncate">{{ ticket.content }}</p>
            </div>
            
            <!-- 用户 + 时间 -->
            <div class="text-right shrink-0 hidden md:block">
              <div class="flex items-center gap-1.5 justify-end mb-1">
                <div class="w-5 h-5 rounded-full bg-gradient-to-tr from-cyan-900 to-blue-900 flex items-center justify-center text-[10px] text-cyan-200 font-bold">
                  {{ ticket.username?.charAt(0).toUpperCase() }}
                </div>
                <span class="text-xs text-gray-400">{{ ticket.username }}</span>
              </div>
              <span class="text-xs text-gray-600">{{ relativeTime(ticket.updated_at || ticket.created_at) }}</span>
            </div>
            
            <!-- 箭头 -->
            <svg class="w-4 h-4 text-gray-600 group-hover:text-gray-400 transition-colors shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path></svg>
          </div>
        </div>
      </div>
    </div>
    
    <!-- 详情/回复弹窗 -->
    <Transition name="modal">
      <div v-if="showReplyModal" class="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div class="absolute inset-0 bg-black/80 backdrop-blur-sm" @click="showReplyModal = false"></div>
        
        <div class="relative bg-[#151921] border border-white/10 rounded-2xl w-full max-w-2xl h-[80vh] shadow-2xl overflow-hidden flex flex-col transform transition-all">
          <!-- Header -->
          <div class="p-4 border-b border-white/10 bg-white/5 flex items-center justify-between shrink-0">
            <div v-if="currentTicket">
              <h3 class="text-lg font-bold text-white flex items-center gap-2">
                {{ currentTicket.title }}
                <span :class="`px-2 py-0.5 rounded text-[10px] ${statusMap[currentTicket.status].class}`">{{ statusMap[currentTicket.status].text }}</span>
              </h3>
              <p class="text-xs text-gray-400 flex items-center gap-2 mt-1">
                <span class="text-cyan-400">{{ currentTicket.username }}</span>
                <span class="w-1 h-1 bg-gray-600 rounded-full"></span>
                {{ relativeTime(currentTicket.created_at) }}
              </p>
            </div>
            <div class="flex items-center gap-3">
              <button 
                 v-if="currentTicket && currentTicket.status !== 'closed'"
                 @click="handleClose(currentTicket.id)"
                 class="px-3 py-1 bg-red-500/10 hover:bg-red-500/20 text-red-400 text-xs rounded border border-red-500/20 transition-colors"
              >
                关闭工单
              </button>
              <button @click="showReplyModal = false" class="text-gray-500 hover:text-white transition-colors">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
              </button>
            </div>
          </div>
          
          <!-- Chat Area -->
          <div id="admin-messages-container" class="flex-grow overflow-y-auto p-4 space-y-4 bg-black/20">
             <div v-if="detailLoading" class="text-center text-gray-500 py-10">加载消息中...</div>
             
             <template v-else>
               <!-- 用户初始提问 -->
                <div class="flex justify-start">
                  <div class="max-w-[85%]">
                     <div class="flex items-center gap-2 mb-1 pl-1">
                        <span class="text-xs font-bold text-cyan-400">{{ currentTicket.username }}</span>
                        <span class="text-[10px] text-gray-600">{{ relativeTime(currentTicket.created_at) }}</span>
                     </div>
                     <div class="bg-cyan-900/20 text-gray-200 p-4 rounded-2xl rounded-tl-sm border border-cyan-500/10">
                        <p class="text-sm leading-relaxed whitespace-pre-wrap">{{ currentTicket.content }}</p>
                     </div>
                  </div>
                </div>

                <!-- 对话流 -->
                <div v-for="msg in messages" :key="msg.id" 
                   :class="msg.sender_type === 'admin' ? 'flex justify-end' : 'flex justify-start'">
                   <div class="max-w-[85%]">
                      <div class="flex items-center gap-2 mb-1 px-1" :class="msg.sender_type === 'admin' ? 'justify-end' : 'justify-start'">
                        <span class="text-xs font-bold" :class="msg.sender_type === 'admin' ? 'text-green-400' : 'text-cyan-400'">
                           {{ msg.sender_type === 'admin' ? '管理员' : currentTicket.username }}
                        </span>
                        <span class="text-[10px] text-gray-600">{{ relativeTime(msg.created_at) }}</span>
                     </div>
                     <div :class="[
                       'p-4 rounded-2xl border',
                       msg.sender_type === 'admin' 
                         ? 'bg-green-600/20 text-white border-green-500/20 rounded-tr-sm' 
                         : 'bg-cyan-900/20 text-gray-200 border-cyan-500/10 rounded-tl-sm'
                     ]">
                       <p class="text-sm leading-relaxed whitespace-pre-wrap">{{ msg.content }}</p>
                     </div>
                   </div>
                </div>
                
                <!-- 兼容旧数据 (admin_reply) -->
                <div v-if="messages.length === 0 && currentTicket.admin_reply" class="flex justify-end">
                   <div class="max-w-[85%]">
                      <div class="flex items-center gap-2 mb-1 justify-end pr-1">
                        <span class="text-xs font-bold text-green-400">管理员</span>
                     </div>
                     <div class="bg-green-600/20 text-white p-4 rounded-2xl rounded-tr-sm border border-green-500/20">
                        <p class="text-sm leading-relaxed whitespace-pre-wrap">{{ currentTicket.admin_reply }}</p>
                     </div>
                   </div>
                </div>
             </template>
          </div>
          
          <!-- Reply Input -->
          <div v-if="currentTicket && currentTicket.status !== 'closed'" class="border-t border-white/10 bg-black/30 shrink-0">
             <!-- 快捷回复 -->
             <Transition name="quick">
               <div v-if="showQuickReplies" class="px-4 pt-3 pb-1 space-y-1.5 border-b border-white/5 max-h-40 overflow-y-auto">
                 <button 
                   v-for="(qr, idx) in quickReplies" :key="idx"
                   @click="useQuickReply(qr)"
                   class="block w-full text-left px-3 py-2 bg-blue-500/5 hover:bg-blue-500/10 text-gray-300 hover:text-white text-xs rounded-lg border border-blue-500/10 transition-colors truncate"
                 >{{ qr }}</button>
               </div>
             </Transition>
             
             <div class="p-4">
               <div class="flex gap-3">
                 <div class="flex-grow relative">
                   <textarea 
                     v-model="replyContent"
                     rows="3"
                     placeholder="输入回复内容..."
                     class="w-full px-4 py-3 bg-black/40 border border-white/10 rounded-xl text-white placeholder-gray-600 focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20 focus:outline-none transition-all resize-none"
                     @keydown.ctrl.enter="handleReply"
                   ></textarea>
                 </div>
                 <div class="flex flex-col gap-2 shrink-0">
                   <button 
                     @click="handleReply"
                     :disabled="replying || !replyContent.trim()"
                     class="px-5 py-2 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-xl shadow-lg shadow-blue-500/20 disabled:opacity-50 disabled:cursor-not-allowed transition-all active:scale-95 flex-1 w-20"
                   >
                     <span v-if="!replying">发送</span>
                     <span v-else class="text-xs">...</span>
                   </button>
                   <button 
                     @click="showQuickReplies = !showQuickReplies"
                     class="px-2 py-1.5 bg-slate-700/60 hover:bg-slate-600/60 text-gray-400 hover:text-white text-[10px] rounded-lg transition-colors w-20"
                     :class="showQuickReplies ? 'bg-blue-600/20 text-blue-400' : ''"
                   >
                     快捷回复
                   </button>
                 </div>
               </div>
               <p class="text-xs text-gray-600 mt-1.5 text-right">Ctrl + Enter 发送</p>
             </div>
          </div>
          <div v-else class="p-4 bg-gray-900/50 text-center text-gray-500 text-sm border-t border-white/5">
             该工单已关闭，无法回复
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

.quick-enter-active,
.quick-leave-active {
  transition: all 0.2s ease;
}
.quick-enter-from,
.quick-leave-to {
  opacity: 0;
  max-height: 0;
}
</style>
