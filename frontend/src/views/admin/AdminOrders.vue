<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import { getAdminOrders, updateOrder } from '../../api'

const orders = ref([])
const total = ref(0)
const page = ref(1)
const statusFilter = ref('')
const loading = ref(false)
const showModal = ref(false)
const editingOrder = ref(null)
const editForm = ref({ status: '', video_url: '' })

const loadOrders = async (p = 1) => {
    loading.value = true
    try {
        const data = await getAdminOrders(p, 20, statusFilter.value)
        orders.value = data.orders
        total.value = data.total
        page.value = data.page
    } catch (err) {
        console.error(err)
    } finally {
        loading.value = false
    }
}

watch(statusFilter, () => {
    page.value = 1
    loadOrders(1)
})

const openEditModal = (order) => {
    editingOrder.value = order
    editForm.value = { 
        status: order.status, 
        video_url: order.video_url || '' 
    }
    showModal.value = true
}

const handleUpdate = async () => {
    try {
        await updateOrder(editingOrder.value.id, editForm.value)
        showModal.value = false
        loadOrders(page.value)
    } catch (err) {
        alert('更新失败')
    }
}

const statusColors = {
    pending: 'bg-yellow-500/10 text-yellow-500',
    processing: 'bg-blue-500/10 text-blue-500',
    generating: 'bg-purple-500/10 text-purple-500',
    completed: 'bg-green-500/10 text-green-500',
    failed: 'bg-red-500/10 text-red-500',
}

const totalPages = computed(() => Math.ceil(total.value / 20))

onMounted(() => loadOrders())
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
        <h2 class="text-2xl font-bold text-white">订单管理</h2>
        
        <select 
            v-model="statusFilter"
            class="px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white outline-none focus:border-blue-500"
        >
            <option value="">全部状态</option>
            <option value="pending">待处理</option>
            <option value="processing">处理中</option>
            <option value="generating">生成中</option>
            <option value="completed">已完成</option>
            <option value="failed">失败</option>
        </select>
    </div>

    <!-- Table -->
    <div class="bg-gray-800 rounded-2xl border border-gray-700/50 overflow-hidden shadow-xl">
        <table class="w-full text-left">
            <thead class="bg-gray-900/50 text-gray-400 text-xs font-semibold uppercase tracking-wider backdrop-blur-sm">
                <tr>
                    <th class="px-6 py-5">ID</th>
                    <th class="px-6 py-5">Prompt</th>
                    <th class="px-6 py-5">状态</th>
                    <th class="px-6 py-5">视频链接</th>
                    <th class="px-6 py-5">创建时间</th>
                    <th class="px-6 py-5 text-right">操作</th>
                </tr>
            </thead>
            <tbody class="divide-y divide-gray-700/50 text-gray-300 text-sm">
                <tr v-for="order in orders" :key="order.id" class="hover:bg-gray-700/30 transition-colors group">
                    <td class="px-6 py-4 font-mono text-gray-500 group-hover:text-blue-400 transition-colors">#{{ order.id }}</td>
                    <td class="px-6 py-4">
                        <div class="max-w-md truncate text-gray-300 font-medium" :title="order.prompt">
                            {{ order.prompt }}
                        </div>
                    </td>
                    <td class="px-6 py-4">
                        <span 
                            class="px-2.5 py-1 text-xs rounded-full font-semibold tracking-wide border" 
                            :class="{
                                'bg-yellow-500/10 text-yellow-400 border-yellow-500/20': order.status === 'pending',
                                'bg-blue-500/10 text-blue-400 border-blue-500/20': order.status === 'processing',
                                'bg-purple-500/10 text-purple-400 border-purple-500/20': order.status === 'generating',
                                'bg-green-500/10 text-green-400 border-green-500/20': order.status === 'completed',
                                'bg-red-500/10 text-red-400 border-red-500/20': order.status === 'failed'
                            }"
                        >
                            {{ order.status.toUpperCase() }}
                        </span>
                    </td>
                    <td class="px-6 py-4 text-sm">
                        <a 
                            v-if="order.video_url" 
                            :href="order.video_url" 
                            target="_blank"
                            class="inline-flex items-center gap-1.5 px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded-lg text-blue-400 hover:text-blue-300 transition-colors text-xs font-medium"
                        >
                            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
                            查看视频
                        </a>
                        <span v-else class="text-gray-600 text-xs italic">尚未生成</span>
                    </td>
                    <td class="px-6 py-4 text-gray-500">{{ new Date(order.created_at).toLocaleString() }}</td>
                    <td class="px-6 py-4 text-right">
                        <button 
                            @click="openEditModal(order)"
                            class="px-3 py-1.5 rounded-lg text-blue-400 hover:text-white hover:bg-blue-600/20 text-xs font-medium transition-all duration-200 border border-transparent hover:border-blue-500/30"
                        >
                            编辑
                        </button>
                    </td>
                </tr>
            </tbody>
        </table>
        
        <!-- Pagination -->
        <div class="p-4 border-t border-gray-700/50 flex items-center justify-between text-sm text-gray-400 bg-gray-900/20">
            <div>共 {{ total }} 个订单</div>
            <div class="flex gap-2">
                 <button 
                    :disabled="page <= 1"
                    @click="loadOrders(page - 1)"
                    class="px-3 py-1 rounded-lg hover:bg-gray-700 disabled:opacity-50 disabled:hover:bg-transparent transition-colors"
                >上一页</button>
                <span class="bg-gray-800 px-3 py-1 rounded-lg border border-gray-700 font-mono">{{ page }} / {{ totalPages }}</span>
                <button 
                    :disabled="page >= totalPages"
                    @click="loadOrders(page + 1)"
                    class="px-3 py-1 rounded-lg hover:bg-gray-700 disabled:opacity-50 disabled:hover:bg-transparent transition-colors"
                >下一页</button>
            </div>
        </div>
    </div>

    <!-- Edit Modal -->
    <div v-if="showModal" class="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 z-50 transition-all duration-300">
        <div class="bg-gray-800 p-8 rounded-2xl w-full max-w-lg border border-gray-700 shadow-2xl transform transition-all scale-100">
            <h3 class="text-xl font-bold text-white mb-6 flex items-center gap-2">
                <svg class="w-6 h-6 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" /></svg>
                编辑订单 <span class="text-gray-500 font-mono text-lg ml-2">#{{ editingOrder.id }}</span>
            </h3>
            
            <div class="space-y-6">
                <div>
                    <label class="block text-sm text-gray-400 mb-2 font-medium">订单状态</label>
                    <select 
                        v-model="editForm.status"
                        class="w-full px-4 py-3 bg-gray-700/50 border border-gray-600 rounded-xl text-white outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all appearance-none"
                    >
                        <option value="pending">PENDING (等待中)</option>
                        <option value="processing">PROCESSING (处理中)</option>
                        <option value="generating">GENERATING (生成中)</option>
                        <option value="completed">COMPLETED (已完成)</option>
                        <option value="failed">FAILED (失败)</option>
                    </select>
                </div>
                <div>
                    <label class="block text-sm text-gray-400 mb-2 font-medium">视频链接</label>
                    <div class="relative">
                        <span class="absolute left-3 top-3.5 text-gray-500"><svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" /></svg></span>
                        <input 
                            v-model="editForm.video_url"
                            type="text" 
                            placeholder="https://example.com/video.mp4"
                            class="w-full pl-10 pr-4 py-3 bg-gray-700/50 border border-gray-600 rounded-xl text-white outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all placeholder-gray-600"
                        />
                    </div>
                </div>
            </div>

            <div class="flex justify-end gap-3 mt-8">
                <button @click="showModal = false" class="px-5 py-2.5 text-gray-400 hover:text-white transition-colors">取消</button>
                <button @click="handleUpdate" class="px-5 py-2.5 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white rounded-xl shadow-lg shadow-blue-900/20 font-medium transition-all transform active:scale-95">
                    保存修改
                </button>
            </div>
        </div>
    </div>
  </div>
</template>
