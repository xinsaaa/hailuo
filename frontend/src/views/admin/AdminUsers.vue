<script setup>
import { ref, onMounted, computed } from 'vue'
import { getAdminUsers, updateUserBalance } from '../../api'

const users = ref([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const showModal = ref(false)
const editingUser = ref(null)
const newBalance = ref(0)

const loadUsers = async (p = 1) => {
    loading.value = true
    try {
        const data = await getAdminUsers(p)
        users.value = data.users
        total.value = data.total
        page.value = data.page
    } catch (err) {
        console.error(err)
    } finally {
        loading.value = false
    }
}

const openEditModal = (user) => {
    editingUser.value = user
    newBalance.value = user.balance
    showModal.value = true
}

const handleUpdateBalance = async () => {
    try {
        await updateUserBalance(editingUser.value.id, newBalance.value)
        showModal.value = false
        loadUsers(page.value)
    } catch (err) {
        alert('更新失败')
    }
}

const totalPages = computed(() => Math.ceil(total.value / 20))

onMounted(() => loadUsers())
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
        <h2 class="text-2xl font-bold text-white">用户管理</h2>
    </div>

    <!-- Table -->
    <div class="bg-gray-800 rounded-2xl border border-gray-700/50 overflow-hidden shadow-xl">
        <table class="w-full text-left">
            <thead class="bg-gray-900/50 text-gray-400 text-xs font-semibold uppercase tracking-wider backdrop-blur-sm">
                <tr>
                    <th class="px-6 py-5">ID</th>
                    <th class="px-6 py-5">用户名</th>
                    <th class="px-6 py-5">余额 (¥)</th>
                    <th class="px-6 py-5">邀请码</th>
                    <th class="px-6 py-5">邀请人ID</th>
                    <th class="px-6 py-5">注册时间</th>
                    <th class="px-6 py-5 text-right">操作</th>
                </tr>
            </thead>
            <tbody class="divide-y divide-gray-700/50 text-gray-300 text-sm">
                <tr v-for="user in users" :key="user.id" class="hover:bg-gray-700/30 transition-colors group">
                    <td class="px-6 py-4 font-mono text-gray-500 group-hover:text-blue-400 transition-colors">#{{ user.id }}</td>
                    <td class="px-6 py-4 font-medium text-white flex items-center gap-3">
                        <div class="w-8 h-8 rounded-full bg-gradient-to-tr from-gray-700 to-gray-600 flex items-center justify-center text-xs font-bold text-gray-300">
                            {{ user.username.charAt(0).toUpperCase() }}
                        </div>
                        {{ user.username }}
                    </td>
                    <td class="px-6 py-4 font-mono text-green-400 font-medium">{{ user.balance.toFixed(2) }}</td>
                    <td class="px-6 py-4 font-mono text-gray-400">{{ user.invite_code || '-' }}</td>
                    <td class="px-6 py-4 text-gray-400">{{ user.invited_by ? '#' + user.invited_by : '-' }}</td>
                    <td class="px-6 py-4 text-gray-500">{{ new Date(user.created_at).toLocaleString() }}</td>
                    <td class="px-6 py-4 text-right">
                        <button 
                            @click="openEditModal(user)"
                            class="px-3 py-1.5 rounded-lg text-blue-400 hover:text-white hover:bg-blue-600/20 text-xs font-medium transition-all duration-200 border border-transparent hover:border-blue-500/30"
                        >
                            修改余额
                        </button>
                    </td>
                </tr>
            </tbody>
        </table>
        
        <!-- Pagination -->
        <div class="p-4 border-t border-gray-700/50 flex items-center justify-between text-sm text-gray-400 bg-gray-900/20">
            <div>共 {{ total }} 个用户</div>
            <div class="flex gap-2">
                <button 
                    :disabled="page <= 1"
                    @click="loadUsers(page - 1)"
                    class="px-3 py-1 rounded-lg hover:bg-gray-700 disabled:opacity-50 disabled:hover:bg-transparent transition-colors"
                >上一页</button>
                <span class="bg-gray-800 px-3 py-1 rounded-lg border border-gray-700 font-mono">{{ page }} / {{ totalPages }}</span>
                <button 
                    :disabled="page >= totalPages"
                    @click="loadUsers(page + 1)"
                    class="px-3 py-1 rounded-lg hover:bg-gray-700 disabled:opacity-50 disabled:hover:bg-transparent transition-colors"
                >下一页</button>
            </div>
        </div>
    </div>

    <!-- Edit Modal -->
    <div v-if="showModal" class="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 z-50 transition-all duration-300">
        <div class="bg-gray-800 p-8 rounded-2xl w-full max-w-sm border border-gray-700 shadow-2xl transform transition-all scale-100">
            <h3 class="text-xl font-bold text-white mb-6 flex items-center gap-2">
                <svg class="w-6 h-6 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                修改余额
            </h3>
            
            <div class="space-y-6">
                <div class="p-4 bg-gray-900/50 rounded-xl border border-gray-700/50">
                    <div class="text-sm text-gray-400 mb-1">用户</div>
                    <div class="text-white font-medium">{{ editingUser.username }}</div>
                    <div class="text-sm text-gray-400 mt-3 mb-1">当前余额</div>
                    <div class="text-2xl font-bold text-green-400 font-mono">¥ {{ editingUser.balance.toFixed(2) }}</div>
                </div>

                <div>
                    <label class="block text-sm text-gray-400 mb-2 font-medium">设置新余额</label>
                    <div class="relative">
                        <span class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">¥</span>
                        <input 
                            v-model.number="newBalance"
                            type="number" 
                            step="0.01"
                            class="w-full pl-8 pr-4 py-3 bg-gray-700/50 border border-gray-600 rounded-xl text-white outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all"
                            placeholder="0.00"
                        />
                    </div>
                </div>
            </div>

            <div class="flex justify-end gap-3 mt-8">
                <button @click="showModal = false" class="px-5 py-2.5 text-gray-400 hover:text-white transition-colors">取消</button>
                <button @click="handleUpdateBalance" class="px-5 py-2.5 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white rounded-xl shadow-lg shadow-blue-900/20 font-medium transition-all transform active:scale-95">
                    保存修改
                </button>
            </div>
        </div>
    </div>
  </div>
</template>
