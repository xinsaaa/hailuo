<script setup>
import { ref, onMounted } from 'vue'
import { getAdminStats, getAutomationStatus, startAutomation } from '../../api'

const stats = ref(null)
const automation = ref(null)
const loading = ref(true)

const loadData = async () => {
    loading.value = true
    try {
        const [statsData, autoData] = await Promise.all([
            getAdminStats(),
            getAutomationStatus()
        ])
        stats.value = statsData
        automation.value = autoData
    } catch (err) {
        console.error(err)
    } finally {
        loading.value = false
    }
}

const handleStartAutomation = async () => {
    try {
        await startAutomation()
        await loadData()
    } catch (err) {
        alert('启动失败: ' + (err.response?.data?.detail || err.message))
    }
}

onMounted(loadData)
</script>

<template>
  <div v-if="loading" class="text-white">加载中...</div>
  <div v-else class="space-y-6">
    
    <!-- Automation Status -->
    <div class="bg-gradient-to-r from-gray-800 to-gray-800/50 p-6 rounded-2xl border border-gray-700/50 shadow-xl flex items-center justify-between relative overflow-hidden group">
        <div class="absolute inset-0 bg-gradient-to-r from-blue-500/5 to-purple-500/5 opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
        <div class="relative z-10">
            <h3 class="text-lg font-bold text-white flex items-center gap-2">
                <svg class="w-5 h-5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
                自动化服务状态
            </h3>
            <p class="text-sm text-gray-400 mt-1">负责处理视频生成队列的后台 Worker</p>
        </div>
        <div class="flex items-center gap-6 relative z-10">
            <div class="flex items-center gap-3 bg-gray-900/50 px-4 py-2 rounded-full border border-gray-700/50">
                <div class="w-2.5 h-2.5 rounded-full shadow-[0_0_10px_currentColor]" :class="automation?.status === 'running' ? 'bg-green-500 text-green-500' : 'bg-red-500 text-red-500'"></div>
                <span class="text-sm font-semibold tracking-wide" :class="automation?.status === 'running' ? 'text-green-400' : 'text-red-400'">
                    {{ automation?.status === 'running' ? 'RUNNING' : 'STOPPED' }}
                </span>
            </div>
            <button 
                v-if="automation?.status !== 'running'"
                @click="handleStartAutomation"
                class="px-5 py-2.5 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white rounded-xl text-sm font-semibold shadow-lg shadow-blue-600/20 transform hover:-translate-y-0.5 transition-all duration-200"
            >
                启动服务
            </button>
        </div>
    </div>

    <!-- Stats Grid -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
        <!-- Users -->
        <div class="bg-gray-800 p-6 rounded-2xl border border-gray-700/50 shadow-lg relative overflow-hidden">
            <div class="absolute right-0 top-0 w-32 h-32 bg-blue-500/5 rounded-full blur-3xl -mr-10 -mt-10"></div>
            <h4 class="text-gray-400 text-xs font-bold uppercase tracking-wider">总用户数</h4>
            <div class="mt-4 flex items-end justify-between">
                <div class="text-3xl font-bold text-white">{{ stats?.users.total }}</div>
                <div class="text-blue-500/20 p-2 rounded-lg">
                    <svg class="w-6 h-6 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"/></svg>
                </div>
            </div>
        </div>

        <!-- Orders Today -->
        <div class="bg-gray-800 p-6 rounded-2xl border border-gray-700/50 shadow-lg relative overflow-hidden">
             <div class="absolute right-0 top-0 w-32 h-32 bg-purple-500/5 rounded-full blur-3xl -mr-10 -mt-10"></div>
            <h4 class="text-gray-400 text-xs font-bold uppercase tracking-wider">今日订单</h4>
            <div class="mt-4 flex items-end justify-between">
                <div>
                     <div class="text-3xl font-bold text-white">{{ stats?.orders.today }}</div>
                     <div class="text-xs text-gray-500 mt-1">历史总量: {{ stats?.orders.total }}</div>
                </div>
                <div class="text-purple-500/20 p-2 rounded-lg">
                    <svg class="w-6 h-6 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>
                </div>
            </div>
        </div>

         <!-- Pending Orders -->
         <div class="bg-gray-800 p-6 rounded-2xl border border-gray-700/50 shadow-lg relative overflow-hidden">
            <div class="absolute right-0 top-0 w-32 h-32 bg-yellow-500/5 rounded-full blur-3xl -mr-10 -mt-10"></div>
            <h4 class="text-gray-400 text-xs font-bold uppercase tracking-wider">待处理队列</h4>
            <div class="mt-4 flex items-end justify-between">
                <div>
                    <div class="text-3xl font-bold text-yellow-500">{{ stats?.orders.pending }}</div>
                    <div class="text-xs text-gray-500 mt-1">已完成: {{ stats?.orders.completed }}</div>
                </div>
                <div class="text-yellow-500/20 p-2 rounded-lg">
                   <svg class="w-6 h-6 text-yellow-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
                </div>
            </div>
        </div>
    </div>

    <!-- Revenue Grid -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div class="bg-gray-800 p-6 rounded-2xl border border-gray-700/50 shadow-lg">
            <h4 class="text-gray-400 text-xs font-bold uppercase tracking-wider">今日充值</h4>
            <div class="mt-4 text-3xl font-bold text-green-400 font-mono">¥ {{ stats?.revenue.today_recharge.toFixed(2) }}</div>
        </div>
        <div class="bg-gray-800 p-6 rounded-2xl border border-gray-700/50 shadow-lg">
            <h4 class="text-gray-400 text-xs font-bold uppercase tracking-wider">资金总览 (充值 / 消耗)</h4>
             <div class="mt-4 flex items-baseline gap-4 font-mono">
                <span class="text-3xl font-bold text-white">¥ {{ stats?.revenue.total_recharge.toFixed(2) }}</span>
                <span class="text-lg text-gray-500">/ ¥ {{ stats?.revenue.total_expense.toFixed(2) }}</span>
            </div>
        </div>
    </div>
  </div>
</template>
