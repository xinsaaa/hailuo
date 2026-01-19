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

// 状态样式映射
const statusMap = {
  open: { text: '待处理', class: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30' },
  replied: { text: '已回复', class: 'bg-green-500/20 text-green-400 border-green-500/30' },
  closed: { text: '已关闭', class: 'bg-gray-500/20 text-gray-400 border-gray-500/30' }
}

const handleLogout = () => {
  localStorage.removeItem('token')
  router.push('/login')
}

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
      <div v-if="showToast" class="fixed top-6 left-1/2 transform -translate-x-1/2 z-50">
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
          <router-link to="/dashboard" class="flex items-center gap-2 text-sm text-gray-400 hover:text-white transition-colors group">
            <svg class="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"></path></svg>
            返回控制台
          </router-link>
          
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
          <p class="text-gray-400">查看历史记录或提交新问题</p>
        </div>
        <button 
          @click="showCreateModal = true"
          class="group relative px-6 py-3 bg-gradient-to-r from-purple-600 to-pink-600 text-white font-bold rounded-xl hover:shadow-[0_0_20px_rgba(168,85,247,0.4)] transition-all active:scale-95 flex items-center gap-2 overflow-hidden"
        >
          <div class="absolute inset-0 bg-white/20 translate-y-full group-hover:translate-y-0 transition-transform duration-300"></div>
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path></svg>
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
             class="group relative bg-[#1a1d24]/80 backdrop-blur-xl border border-white/10 rounded-2xl p-6 transition-all hover:border-white/20 hover:bg-[#1a1d24] hover:shadow-xl hover:-translate-y-1 overflow-hidden"
        >
          <!-- Status Indicator Stripe -->
          <div class="absolute left-0 top-0 bottom-0 w-1" :class="{
            'bg-yellow-500': ticket.status === 'open',
            'bg-green-500': ticket.status === 'replied',
            'bg-gray-600': ticket.status === 'closed'
          }"></div>

          <div class="ml-2">
            <div class="flex justify-between items-start mb-4">
              <div>
                <h3 class="text-lg font-bold text-white mb-1 group-hover:text-cyan-50 transition-colors">{{ ticket.title }}</h3>
                <p class="text-xs text-gray-500 font-mono">{{ new Date(ticket.created_at).toLocaleString() }}</p>
              </div>
              <span :class="`px-3 py-1 rounded-lg text-xs font-bold border flex items-center gap-1.5 ${statusMap[ticket.status].class}`">
                <span v-if="ticket.status === 'open'" class="w-1.5 h-1.5 rounded-full bg-current animate-pulse"></span>
                {{ statusMap[ticket.status].text }}
              </span>
            </div>
            
            <div class="bg-black/20 rounded-xl p-4 text-gray-300 text-sm leading-relaxed border border-white/5 mb-4">
               {{ ticket.content }}
            </div>
            
            <!-- Admin Reply Section -->
            <div v-if="ticket.admin_reply" class="relative mt-4 pl-4 before:absolute before:left-0 before:top-2 before:bottom-2 before:w-0.5 before:bg-gradient-to-b before:from-green-500 before:to-transparent">
              <div class="flex items-center gap-2 mb-2">
                <div class="w-5 h-5 rounded bg-green-500/20 flex items-center justify-center">
                  <svg class="w-3 h-3 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6"></path></svg>
                </div>
                <span class="text-sm font-bold text-green-400">管理员回复</span>
                <span class="text-xs text-gray-600" v-if="ticket.replied_at">{{ new Date(ticket.replied_at).toLocaleString() }}</span>
              </div>
              <p class="text-gray-300 text-sm leading-relaxed bg-green-500/5 p-3 rounded-lg border border-green-500/10">
                {{ ticket.admin_reply }}
              </p>
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
