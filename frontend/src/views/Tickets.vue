<script setup>
import { ref, onMounted, nextTick, computed } from 'vue'
import { useRouter } from 'vue-router'
import { getCurrentUser, getMyTickets, createTicket, getTicketDetail, userReplyTicket, userCloseTicket } from '../api'

const router = useRouter()
const user = ref(null)
const tickets = ref([])
const loading = ref(false)
const showCreateModal = ref(false)
const creating = ref(false)

// 工单详情
const showDetailModal = ref(false)
const currentTicket = ref(null)
const messages = ref([])
const detailLoading = ref(false)
const replyContent = ref('')
const replying = ref(false)

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

// 查看工单详情
const openDetail = async (ticketId) => {
  detailLoading.value = true
  showDetailModal.value = true
  try {
    const data = await getTicketDetail(ticketId)
    currentTicket.value = data.ticket
    messages.value = data.messages || []
    await nextTick()
    scrollToBottom()
  } catch (err) {
    toast('加载详情失败', 'error')
    showDetailModal.value = false
  } finally {
    detailLoading.value = false
  }
}

// 滚动到底部
const scrollToBottom = () => {
  const container = document.getElementById('messages-container')
  if (container) {
    container.scrollTop = container.scrollHeight
  }
}

// 用户回复
const handleReply = async () => {
  if (!replyContent.value.trim()) {
    toast('请输入回复内容', 'error')
    return
  }
  
  replying.value = true
  try {
    await userReplyTicket(currentTicket.value.id, replyContent.value)
    replyContent.value = ''
    // 重新加载详情
    await openDetail(currentTicket.value.id)
    await loadData()
    toast('回复成功', 'success')
  } catch (err) {
    toast(err.response?.data?.detail || '回复失败', 'error')
  } finally {
    replying.value = false
  }
}

// 用户关闭工单
const handleCloseTicket = async () => {
  if (!confirm('确定要关闭此工单吗？关闭后将无法继续对话。')) return
  
  try {
    await userCloseTicket(currentTicket.value.id)
    toast('工单已关闭', 'success')
    showDetailModal.value = false
    await loadData()
  } catch (err) {
    toast(err.response?.data?.detail || '关闭失败', 'error')
  }
}

// 状态样式映射
const statusMap = {
  open: { text: '待处理', class: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30' },
  replied: { text: '已回复', class: 'bg-green-500/20 text-green-400 border-green-500/30' },
  closed: { text: '已关闭', class: 'bg-gray-500/20 text-gray-400 border-gray-500/30' }
}

const canReply = computed(() => currentTicket.value && currentTicket.value.status !== 'closed')

onMounted(loadData)
</script>

<template>
  <div class="min-h-screen relative overflow-hidden flex flex-col bg-[#0f1115]">
    <!-- Background Elements -->
    <div class="fixed inset-0 z-0">
       <div class="absolute top-0 left-1/4 w-96 h-96 bg-purple-900/20 rounded-full blur-[100px]"></div>
       <div class="absolute bottom-0 right-1/4 w-96 h-96 bg-cyan-900/20 rounded-full blur-[100px]"></div>
    </div>

    <!-- Toast -->
    <Transition name="toast">
      <div v-if="showToast" class="fixed top-6 left-1/2 transform -translate-x-1/2 z-[100]">
        <div :class="{
            'bg-red-500/80 text-white border-red-500/50 shadow-red-900/50': toastType === 'error',
            'bg-green-500/80 text-white border-green-500/50 shadow-green-900/50': toastType === 'success',
            'bg-blue-500/80 text-white border-blue-500/50 shadow-blue-900/50': toastType === 'info'
        }" class="flex items-center gap-3 px-6 py-3 rounded-xl border shadow-lg backdrop-blur-xl">
          <span class="font-medium text-sm">{{ toastMessage }}</span>
        </div>
      </div>
    </Transition>
    
    <!-- Navbar -->
    <nav class="relative z-20 px-8 py-4 border-b border-white/10 bg-black/20 backdrop-blur-md">
      <div class="max-w-7xl mx-auto flex justify-between items-center">
        <div class="text-2xl font-extrabold cursor-pointer flex items-center gap-2" @click="router.push('/dashboard')">
          <span class="text-white drop-shadow-md">大帝</span><span class="text-cyan-400 drop-shadow-md">AI</span>
          <span class="text-xs px-2 py-0.5 rounded bg-white/10 text-gray-400 border border-white/5 ml-2">工单系统</span>
        </div>
        <div class="flex items-center gap-6">
          <router-link to="/dashboard" class="text-sm text-gray-400 hover:text-white transition-colors">控制台</router-link>
          <router-link to="/invite" class="text-sm text-gray-400 hover:text-white transition-colors">邀请</router-link>
          
          <div class="h-6 w-px bg-white/10"></div>
          
          <div class="flex items-center gap-2">
            <div class="w-8 h-8 rounded-full bg-gradient-to-tr from-cyan-500 to-blue-500 flex items-center justify-center text-xs font-bold text-white shadow-lg">
              {{ user?.username?.charAt(0).toUpperCase() }}
            </div>
            <span v-if="user" class="text-sm text-gray-300 font-medium">{{ user.username }}</span>
          </div>
        </div>
      </div>
    </nav>
    
    <!-- Main Content -->
    <div class="flex-grow w-full max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-10 relative z-10">
      
      <!-- List Header -->
      <div class="flex justify-between items-end mb-8">
        <div>
          <h2 class="text-3xl font-bold text-white mb-2">我的工单</h2>
          <p class="text-gray-400">点击工单查看对话详情或继续回复</p>
        </div>
        <button 
          @click="showCreateModal = true"
          class="px-4 py-2 bg-white/10 hover:bg-white/20 text-white text-sm font-bold rounded-lg border border-white/5 hover:border-white/10 transition-all flex items-center gap-2 active:scale-95"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path></svg>
          <span>新建工单</span>
        </button>
      </div>
      
      <!-- Tickets Grid -->
      <div v-if="loading" class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div v-for="i in 4" :key="i" class="h-40 bg-white/5 rounded-2xl animate-pulse border border-white/5"></div>
      </div>
      
      <div v-else-if="tickets.length === 0" class="text-center py-24 bg-white/5 rounded-3xl border border-white/10 backdrop-blur-sm">
        <div class="w-20 h-20 bg-white/5 rounded-full flex items-center justify-center mx-auto mb-6">
           <svg class="w-10 h-10 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"></path></svg>
        </div>
        <h3 class="text-xl font-bold text-white mb-2">暂无工单记录</h3>
        <p class="text-gray-400 mb-8">遇到问题？您可以随时提交工单联系我们</p>
        <button @click="showCreateModal = true" class="text-cyan-400 hover:text-cyan-300 font-medium underline underline-offset-4">立即提交</button>
      </div>
      
      <div v-else class="grid grid-cols-1 gap-4">
        <div v-for="ticket in tickets" :key="ticket.id"
             @click="openDetail(ticket.id)"
             class="group relative bg-[#1a1d24]/80 backdrop-blur-xl border border-white/10 rounded-2xl p-6 transition-all hover:border-white/20 hover:bg-[#1a1d24] hover:shadow-xl cursor-pointer overflow-hidden"
        >
          <!-- Status Indicator Stripe -->
          <div class="absolute left-0 top-0 bottom-0 w-1" :class="{
            'bg-yellow-500': ticket.status === 'open',
            'bg-green-500': ticket.status === 'replied',
            'bg-gray-600': ticket.status === 'closed'
          }"></div>

          <div class="ml-2 flex justify-between items-center">
            <div>
              <h3 class="text-lg font-bold text-white mb-1 group-hover:text-cyan-50 transition-colors">{{ ticket.title }}</h3>
              <p class="text-xs text-gray-500 font-mono">{{ new Date(ticket.created_at).toLocaleString() }}</p>
            </div>
            <div class="flex items-center gap-3">
              <span :class="`px-3 py-1 rounded-lg text-xs font-bold border flex items-center gap-1.5 ${statusMap[ticket.status].class}`">
                <span v-if="ticket.status === 'open'" class="w-1.5 h-1.5 rounded-full bg-current animate-pulse"></span>
                {{ statusMap[ticket.status].text }}
              </span>
              <svg class="w-5 h-5 text-gray-600 group-hover:text-cyan-400 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path></svg>
            </div>
          </div>
        </div>
      </div>
    </div>
    
    <!-- Create Modal -->
    <Transition name="modal">
      <div v-if="showCreateModal" class="fixed inset-0 z-50 flex items-center justify-center p-4">
        <!-- Backdrop -->
        <div class="absolute inset-0 bg-black/80 backdrop-blur-sm" @click="showCreateModal = false"></div>
        
        <!-- Modal Content -->
        <div class="relative bg-[#151921] border border-white/10 rounded-2xl w-full max-w-lg shadow-2xl overflow-hidden transform transition-all">
          <div class="p-6 border-b border-white/10 bg-white/5">
            <h3 class="text-xl font-bold text-white">新建工单</h3>
            <p class="text-sm text-gray-400 mt-1">请详细描述您遇到的问题，我们会尽快回复</p>
            <button @click="showCreateModal = false" class="absolute top-4 right-4 text-gray-500 hover:text-white transition-colors">
              <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
            </button>
          </div>
          
          <div class="p-6 space-y-5">
            <div>
              <label class="block text-sm font-medium text-gray-300 mb-2">标题</label>
              <input 
                v-model="newTicket.title"
                type="text"
                placeholder="例如：生成视频失败..."
                class="w-full px-4 py-3 bg-black/30 border border-white/10 rounded-xl text-white placeholder-gray-600 focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/20 focus:outline-none transition-all"
              />
            </div>
            
            <div>
              <label class="block text-sm font-medium text-gray-300 mb-2">问题描述</label>
              <textarea 
                v-model="newTicket.content"
                rows="5"
                placeholder="请提供尽可能多的细节..."
                class="w-full px-4 py-3 bg-black/30 border border-white/10 rounded-xl text-white placeholder-gray-600 focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/20 focus:outline-none transition-all resize-none"
              ></textarea>
            </div>
          </div>
          
          <div class="p-6 border-t border-white/10 flex justify-end gap-3 bg-black/20">
            <button 
              @click="showCreateModal = false"
              class="px-5 py-2.5 text-gray-400 hover:text-white font-medium transition-colors hover:bg-white/5 rounded-lg"
            >
              取消
            </button>
            <button 
              @click="handleCreate"
              :disabled="creating"
              class="px-6 py-2.5 bg-gradient-to-r from-purple-600 to-pink-600 text-white font-bold rounded-lg hover:shadow-lg hover:shadow-purple-500/20 disabled:opacity-50 disabled:cursor-not-allowed transition-all active:scale-95"
            >
              {{ creating ? '提交中...' : '确认提交' }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
    
    <!-- Detail Modal (Chat View) -->
    <Transition name="modal">
      <div v-if="showDetailModal" class="fixed inset-0 z-50 flex items-center justify-center p-4">
        <!-- Backdrop -->
        <div class="absolute inset-0 bg-black/80 backdrop-blur-sm" @click="showDetailModal = false"></div>
        
        <!-- Modal Content -->
        <div class="relative bg-[#151921] border border-white/10 rounded-2xl w-full max-w-2xl h-[80vh] shadow-2xl overflow-hidden flex flex-col">
          <!-- Header -->
          <div class="p-4 border-b border-white/10 bg-white/5 flex items-center justify-between shrink-0">
            <div v-if="currentTicket">
              <h3 class="text-lg font-bold text-white">{{ currentTicket.title }}</h3>
              <p class="text-xs text-gray-500">{{ new Date(currentTicket.created_at).toLocaleString() }}</p>
            </div>
            <div class="flex items-center gap-3">
              <span v-if="currentTicket" :class="`px-3 py-1 rounded-lg text-xs font-bold border ${statusMap[currentTicket.status].class}`">
                {{ statusMap[currentTicket.status].text }}
              </span>
              <button v-if="canReply" @click="handleCloseTicket" class="text-xs text-gray-500 hover:text-red-400 transition-colors">关闭工单</button>
              <button @click="showDetailModal = false" class="text-gray-500 hover:text-white transition-colors">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
              </button>
            </div>
          </div>
          
          <!-- Messages Area -->
          <div id="messages-container" class="flex-grow overflow-y-auto p-4 space-y-4">
            <div v-if="detailLoading" class="text-center text-gray-500 py-10">加载中...</div>
            
            <template v-else>
              <!-- 初始消息（工单内容） -->
              <div class="flex justify-end">
                <div class="max-w-[80%] bg-cyan-600/20 text-white p-4 rounded-2xl rounded-br-md border border-cyan-500/20">
                  <p class="text-sm leading-relaxed whitespace-pre-wrap">{{ currentTicket?.content }}</p>
                  <p class="text-xs text-cyan-400/60 mt-2 text-right">{{ currentTicket ? new Date(currentTicket.created_at).toLocaleTimeString() : '' }}</p>
                </div>
              </div>
              
              <!-- 对话消息 -->
              <div v-for="msg in messages" :key="msg.id" 
                   :class="msg.sender_type === 'user' ? 'flex justify-end' : 'flex justify-start'">
                <div :class="[
                  'max-w-[80%] p-4 rounded-2xl border',
                  msg.sender_type === 'user' 
                    ? 'bg-cyan-600/20 text-white border-cyan-500/20 rounded-br-md' 
                    : 'bg-green-600/20 text-white border-green-500/20 rounded-bl-md'
                ]">
                  <div v-if="msg.sender_type === 'admin'" class="flex items-center gap-2 mb-2">
                    <div class="w-5 h-5 rounded-full bg-green-500/30 flex items-center justify-center">
                      <svg class="w-3 h-3 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5.121 17.804A13.937 13.937 0 0112 16c2.5 0 4.847.655 6.879 1.804M15 10a3 3 0 11-6 0 3 3 0 016 0zm6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                    </div>
                    <span class="text-xs font-bold text-green-400">管理员</span>
                  </div>
                  <p class="text-sm leading-relaxed whitespace-pre-wrap">{{ msg.content }}</p>
                  <p :class="[
                    'text-xs mt-2',
                    msg.sender_type === 'user' ? 'text-cyan-400/60 text-right' : 'text-green-400/60'
                  ]">{{ new Date(msg.created_at).toLocaleTimeString() }}</p>
                </div>
              </div>
              
              <!-- 兼容旧数据: 如果没有 messages 但有 admin_reply -->
              <div v-if="messages.length === 0 && currentTicket?.admin_reply" class="flex justify-start">
                <div class="max-w-[80%] bg-green-600/20 text-white p-4 rounded-2xl rounded-bl-md border border-green-500/20">
                  <div class="flex items-center gap-2 mb-2">
                    <div class="w-5 h-5 rounded-full bg-green-500/30 flex items-center justify-center">
                      <svg class="w-3 h-3 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5.121 17.804A13.937 13.937 0 0112 16c2.5 0 4.847.655 6.879 1.804M15 10a3 3 0 11-6 0 3 3 0 016 0zm6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                    </div>
                    <span class="text-xs font-bold text-green-400">管理员</span>
                  </div>
                  <p class="text-sm leading-relaxed whitespace-pre-wrap">{{ currentTicket.admin_reply }}</p>
                  <p class="text-xs text-green-400/60 mt-2">{{ currentTicket.replied_at ? new Date(currentTicket.replied_at).toLocaleTimeString() : '' }}</p>
                </div>
              </div>
              
              <!-- 工单已关闭提示 -->
              <div v-if="currentTicket?.status === 'closed'" class="text-center text-gray-500 text-sm py-4">
                --- 工单已关闭 ---
              </div>
            </template>
          </div>
          
          <!-- Reply Input -->
          <div v-if="canReply" class="p-4 border-t border-white/10 bg-black/20 shrink-0">
            <div class="flex gap-3">
              <textarea 
                v-model="replyContent"
                rows="2"
                placeholder="输入您的回复..."
                class="flex-grow px-4 py-3 bg-black/30 border border-white/10 rounded-xl text-white placeholder-gray-600 focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/20 focus:outline-none transition-all resize-none"
                @keydown.ctrl.enter="handleReply"
              ></textarea>
              <button 
                @click="handleReply"
                :disabled="replying || !replyContent.trim()"
                class="px-6 py-3 bg-gradient-to-r from-cyan-600 to-blue-600 text-white font-bold rounded-xl hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed transition-all active:scale-95 shrink-0"
              >
                {{ replying ? '发送中...' : '发送' }}
              </button>
            </div>
            <p class="text-xs text-gray-600 mt-2">Ctrl + Enter 快速发送</p>
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
  transform: translate(-50%, -20px);
}

.modal-enter-active,
.modal-leave-active {
  transition: all 0.3s ease;
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
  transform: scale(0.95);
}
</style>
