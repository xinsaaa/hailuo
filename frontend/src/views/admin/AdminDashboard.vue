<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { getAdminStats, getAutomationStatus, startAutomation, stopAutomation, getAutomationLogs } from '../../api'

const stats = ref(null)
const automation = ref(null)
const logs = ref([])
const loading = ref(true)
const logsLoading = ref(false)
const actionLoading = ref(false)
let logsInterval = null

// Toast
const showToast = ref(false)
const toastMessage = ref('')
const toastType = ref('info')
const toast = (msg, type = 'info') => {
  toastMessage.value = msg
  toastType.value = type
  showToast.value = true
  setTimeout(() => { showToast.value = false }, 3000)
}

const safeFixed = (val, digits = 2) => (val ?? 0).toFixed(digits)

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

const loadLogs = async () => {
    logsLoading.value = true
    try {
        const data = await getAutomationLogs(50)
        logs.value = data.logs || []
    } catch (err) {
        console.error('加载日志失败', err)
    } finally {
        logsLoading.value = false
    }
}

const handleStartAutomation = async () => {
    actionLoading.value = true
    try {
        await startAutomation()
        toast('多账号自动化启动成功', 'success')
        await loadData()
        await loadLogs()
    } catch (err) {
        toast('启动失败: ' + (err.response?.data?.detail || err.message), 'error')
    } finally {
        actionLoading.value = false
    }
}

const handleStopAutomation = async () => {
    actionLoading.value = true
    try {
        await stopAutomation()
        toast('自动化已停止', 'success')
        await loadData()
    } catch (err) {
        toast('停止失败: ' + (err.response?.data?.detail || err.message), 'error')
    } finally {
        actionLoading.value = false
    }
}


const getLogColor = (level) => {
    switch (level) {
        case 'SUCCESS': return 'text-green-400'
        case 'ERROR': return 'text-red-400'
        case 'WARN': return 'text-yellow-400'
        default: return 'text-gray-300'
    }
}

const getLogBadgeColor = (level) => {
    switch (level) {
        case 'SUCCESS': return 'bg-green-500/20 text-green-400'
        case 'ERROR': return 'bg-red-500/20 text-red-400'
        case 'WARN': return 'bg-yellow-500/20 text-yellow-400'
        default: return 'bg-gray-500/20 text-gray-400'
    }
}

onMounted(() => {
    loadData()
    loadLogs()
    // 每5秒刷新日志
    logsInterval = setInterval(loadLogs, 5000)
})

onUnmounted(() => {
    if (logsInterval) clearInterval(logsInterval)
})
</script>

<template>
  <!-- Toast -->
  <Transition name="toast">
    <div v-if="showToast" class="fixed top-6 left-1/2 transform -translate-x-1/2 z-50">
      <div :class="toastType === 'error' ? 'bg-red-500/90' : 'bg-green-500/90'" class="px-6 py-3 rounded-xl text-white text-sm font-medium shadow-lg backdrop-blur-xl">{{ toastMessage }}</div>
    </div>
  </Transition>

  <div v-if="loading" class="text-white text-center py-20">加载中...</div>
  <div v-else class="space-y-6">
    
    <!-- Automation Status (V2 多账号) -->
    <div class="bg-gradient-to-r from-gray-800 to-gray-800/50 p-6 rounded-2xl border border-gray-700/50 shadow-xl relative overflow-hidden group">
        <div class="absolute inset-0 bg-gradient-to-r from-blue-500/5 to-purple-500/5 opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
        <div class="flex items-center justify-between relative z-10">
            <div>
                <h3 class="text-lg font-bold text-white flex items-center gap-2">
                    <svg class="w-5 h-5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
                    自动化服务状态
                    <span class="text-xs font-normal text-gray-500 bg-gray-700/50 px-2 py-0.5 rounded">V2 多账号</span>
                </h3>
                <p class="text-sm text-gray-400 mt-1">多账号并行处理视频生成队列</p>
                <div v-if="automation?.status === 'running'" class="flex items-center gap-4 mt-2 text-xs text-gray-400">
                    <span>账号: <span class="text-blue-400">{{ automation?.active_accounts ?? 0 }}/{{ automation?.total_accounts ?? 0 }}</span></span>
                    <span>任务: <span class="text-purple-400">{{ automation?.active_tasks ?? 0 }}</span></span>
                </div>
            </div>
            <div class="flex items-center gap-4">
                <div class="flex items-center gap-3 bg-gray-900/50 px-4 py-2 rounded-full border border-gray-700/50">
                    <div class="w-2.5 h-2.5 rounded-full shadow-[0_0_10px_currentColor]" :class="automation?.status === 'running' ? 'bg-green-500 text-green-500' : 'bg-red-500 text-red-500'"></div>
                    <span class="text-sm font-semibold tracking-wide" :class="automation?.status === 'running' ? 'text-green-400' : 'text-red-400'">
                        {{ automation?.status === 'running' ? 'RUNNING' : 'STOPPED' }}
                    </span>
                </div>
                <button
                    v-if="automation?.status !== 'running'"
                    @click="handleStartAutomation"
                    :disabled="actionLoading"
                    class="px-5 py-2.5 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 disabled:opacity-50 text-white rounded-xl text-sm font-semibold shadow-lg shadow-blue-600/20 transform hover:-translate-y-0.5 transition-all duration-200"
                >
                    {{ actionLoading ? '启动中...' : '启动服务' }}
                </button>
                <button
                    v-else
                    @click="handleStopAutomation"
                    :disabled="actionLoading"
                    class="px-5 py-2.5 bg-gradient-to-r from-red-600 to-rose-600 hover:from-red-500 hover:to-rose-500 disabled:opacity-50 text-white rounded-xl text-sm font-semibold shadow-lg shadow-red-600/20 transform hover:-translate-y-0.5 transition-all duration-200"
                >
                    {{ actionLoading ? '停止中...' : '停止服务' }}
                </button>
            </div>
        </div>
    </div>

    <!-- Stats Grid -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
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
            <div class="mt-2 text-xs text-blue-400/80 font-medium bg-blue-500/10 px-2 py-1 rounded inline-block">邀请注册: {{ stats?.users.invited }}</div>
        </div>

        <!-- Orders -->
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

        <!-- Revenue -->
        <div class="bg-gray-800 p-6 rounded-2xl border border-gray-700/50 shadow-lg relative overflow-hidden">
            <div class="absolute right-0 top-0 w-32 h-32 bg-green-500/5 rounded-full blur-3xl -mr-10 -mt-10"></div>
            <h4 class="text-gray-400 text-xs font-bold uppercase tracking-wider">今日充值</h4>
            <div class="mt-4 flex items-end justify-between">
                <div class="text-3xl font-bold text-green-400 font-mono">¥{{ safeFixed(stats?.revenue?.today_recharge) }}</div>
                <div class="p-3 bg-green-500/20 text-green-400 rounded-lg">
                   <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                </div>
            </div>
            <div class="mt-2 text-xs text-gray-500">总充值: ¥{{ safeFixed(stats?.revenue?.total_recharge) }}</div>
        </div>
        
        <!-- Invite Bonus -->
        <div class="bg-gray-800 p-6 rounded-2xl border border-gray-700/50 shadow-lg relative overflow-hidden">
            <div class="absolute right-0 top-0 w-32 h-32 bg-orange-500/5 rounded-full blur-3xl -mr-10 -mt-10"></div>
            <h4 class="text-gray-400 text-xs font-bold uppercase tracking-wider">已发邀请奖励</h4>
            <div class="mt-4 flex items-end justify-between">
                <div class="text-3xl font-bold text-orange-400 font-mono">¥{{ safeFixed(stats?.revenue?.total_invite_bonus) }}</div>
                <div class="p-3 bg-orange-500/20 text-orange-400 rounded-lg">
                   <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v13m0-13V6a2 2 0 112 2h-2zm0 0V5.5A2.5 2.5 0 109.5 8H12zm-7 4h14M5 12a2 2 0 110-4h14a2 2 0 110 4M5 12v7a2 2 0 002 2h10a2 2 0 002-2v-7"></path></svg>
                </div>
            </div>
        </div>
    </div>
    

    <!-- Logs Panel -->
    <div class="bg-gray-800 rounded-2xl border border-gray-700/50 shadow-xl overflow-hidden">
        <div class="px-6 py-4 border-b border-gray-700/50 bg-gray-900/50 flex items-center justify-between">
            <h3 class="text-lg font-bold text-white flex items-center gap-2">
                <svg class="w-5 h-5 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>
                运行日志
            </h3>
            <div class="flex items-center gap-3">
                <span v-if="logsLoading" class="text-xs text-gray-500">刷新中...</span>
                <button @click="loadLogs" class="text-xs text-blue-400 hover:text-blue-300 transition-colors">手动刷新</button>
            </div>
        </div>
        <div class="h-64 overflow-y-auto p-4 font-mono text-sm bg-gray-900/30 space-y-1">
            <div v-if="logs.length === 0" class="text-center text-gray-500 py-8">
                暂无日志，启动服务后将显示运行日志
            </div>
            <div 
                v-for="(log, index) in logs" 
                :key="index"
                class="flex items-start gap-3 py-1.5 px-2 hover:bg-gray-800/50 rounded"
            >
                <span class="text-gray-600 text-xs tabular-nums shrink-0">{{ log.time }}</span>
                <span 
                    class="text-xs px-1.5 py-0.5 rounded font-medium shrink-0"
                    :class="getLogBadgeColor(log.level)"
                >{{ log.level }}</span>
                <span :class="getLogColor(log.level)">{{ log.message }}</span>
            </div>
        </div>
    </div>
  </div>
</template>
