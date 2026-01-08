<script setup>
import { ref, onMounted } from 'vue'
import { getBannedIps, unbanIp } from '../../api'
import api from '../../api'

const bannedIps = ref([])
const failStats = ref([])
const loading = ref(false)

const loadBans = async () => {
    loading.value = true
    try {
        const [banData, failData] = await Promise.all([
            getBannedIps(),
            api.get('/admin/security/fail-stats').then(r => r.data)
        ])
        bannedIps.value = banData.banned_ips
        failStats.value = failData.fail_stats
    } catch (err) {
        console.error(err)
    } finally {
        loading.value = false
    }
}

const handleUnban = async (ip) => {
    if (!confirm(`确定要解封 IP: ${ip} 吗？`)) return
    try {
        await unbanIp(ip)
        loadBans()
    } catch (err) {
        alert('解封失败')
    }
}

onMounted(loadBans)
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
        <h2 class="text-2xl font-bold text-white">安全中心</h2>
        <button @click="loadBans" class="text-blue-400 hover:text-blue-300 text-sm">刷新列表</button>
    </div>

    <!-- 被封禁的 IP -->
    <div class="bg-gray-800 rounded-2xl border border-gray-700/50 overflow-hidden shadow-xl">
        <div class="px-6 py-5 border-b border-gray-700/50 bg-gray-900/50 backdrop-blur-sm flex items-center justify-between">
            <div>
                <h3 class="text-lg font-bold text-white flex items-center gap-2">
                    <svg class="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" /></svg>
                    被封禁的 IP
                </h3>
                <p class="text-xs text-gray-500 mt-1 ml-7">因多次违规操作而被临时禁用的 IP 地址列表</p>
            </div>
            <span class="bg-red-500/10 text-red-400 px-3 py-1 rounded-full text-xs font-medium border border-red-500/20" v-if="bannedIps.length > 0">
                {{ bannedIps.length }} 个封禁中
            </span>
        </div>
        <div v-if="bannedIps.length === 0" class="p-12 text-center">
            <div class="w-16 h-16 bg-gray-700/50 rounded-full flex items-center justify-center mx-auto mb-4">
                <svg class="w-8 h-8 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
            </div>
            <h4 class="text-gray-300 font-medium">安全状况良好</h4>
            <p class="text-gray-500 text-sm mt-1">当前没有被封禁的 IP 地址</p>
        </div>
        <table v-else class="w-full text-left">
            <thead class="bg-gray-900/30 text-gray-400 text-xs font-semibold uppercase tracking-wider backdrop-blur-sm">
                <tr>
                    <th class="px-6 py-4">IP 地址</th>
                    <th class="px-6 py-4">解封时间</th>
                    <th class="px-6 py-4">剩余时间</th>
                    <th class="px-6 py-4 text-right">操作</th>
                </tr>
            </thead>
            <tbody class="divide-y divide-gray-700/50 text-gray-300 text-sm">
                <tr v-for="ban in bannedIps" :key="ban.ip" class="hover:bg-gray-700/30 transition-colors group">
                    <td class="px-6 py-4 font-mono text-white text-base">{{ ban.ip }}</td>
                    <td class="px-6 py-4 text-gray-400">{{ new Date(ban.expires_at).toLocaleString() }}</td>
                    <td class="px-6 py-4">
                        <div class="flex items-center gap-3">
                            <span class="text-red-400 font-bold tabular-nums">{{ Math.ceil(ban.remaining_seconds / 60) }}</span>
                            <span class="text-xs text-red-500/70">分钟</span>
                            <div class="h-1.5 w-24 bg-gray-700 rounded-full overflow-hidden">
                                <div class="h-full bg-red-500 rounded-full" style="width: 60%"></div> <!-- 可根据实际比例动态计算 -->
                            </div>
                        </div>
                    </td>
                    <td class="px-6 py-4 text-right">
                        <button 
                            @click="handleUnban(ban.ip)"
                            class="px-3 py-1.5 bg-red-500/10 hover:bg-red-500/20 text-red-400 hover:text-red-300 rounded-lg text-xs font-medium transition-all border border-transparent hover:border-red-500/30"
                        >
                            立即解封
                        </button>
                    </td>
                </tr>
            </tbody>
        </table>
    </div>

    <!-- 登录失败统计 -->
    <div class="bg-gray-800 rounded-2xl border border-gray-700/50 overflow-hidden shadow-lg mt-8">
        <div class="px-6 py-5 border-b border-gray-700/50 bg-gray-900/50 backdrop-blur-sm">
            <h3 class="text-lg font-bold text-white flex items-center gap-2">
                <svg class="w-5 h-5 text-yellow-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
                登录失败统计
            </h3>
            <p class="text-xs text-gray-500 mt-1 ml-7">监控异常登录尝试，达到 10 次失败后将自动封禁</p>
        </div>
        <div v-if="failStats.length === 0" class="p-8 text-center text-gray-500 text-sm">
            暂无异常登录记录
        </div>
        <table v-else class="w-full text-left">
            <thead class="bg-gray-900/30 text-gray-400 text-xs font-semibold uppercase tracking-wider backdrop-blur-sm">
                <tr>
                    <th class="px-6 py-4">IP 地址</th>
                    <th class="px-6 py-4">失败次数</th>
                    <th class="px-6 py-4">风险等级</th>
                    <th class="px-6 py-4">最后尝试时间</th>
                </tr>
            </thead>
            <tbody class="divide-y divide-gray-700/50 text-gray-300 text-sm">
                <tr v-for="stat in failStats" :key="stat.ip" class="hover:bg-gray-700/30 transition-colors">
                    <td class="px-6 py-4 font-mono text-gray-300">{{ stat.ip }}</td>
                    <td class="px-6 py-4 font-bold text-white">{{ stat.fail_count }}</td>
                    <td class="px-6 py-4">
                        <div class="flex items-center gap-2">
                            <div class="w-20 h-2 bg-gray-700 rounded-full overflow-hidden">
                                <div 
                                    class="h-full rounded-full transition-all duration-500"
                                    :class="stat.fail_count >= 7 ? 'bg-red-500' : stat.fail_count >= 4 ? 'bg-yellow-500' : 'bg-blue-500'"
                                    :style="`width: ${Math.min(100, stat.fail_count * 10)}%`"
                                ></div>
                            </div>
                            <span class="text-xs font-medium" :class="stat.fail_count >= 7 ? 'text-red-400' : stat.fail_count >= 4 ? 'text-yellow-400' : 'text-blue-400'">
                                {{ stat.fail_count >= 7 ? '高危' : stat.fail_count >= 4 ? '中等' : '低' }}
                            </span>
                        </div>
                    </td>
                    <td class="px-6 py-4 text-gray-500 text-xs">{{ stat.last_fail ? new Date(stat.last_fail).toLocaleString() : '-' }}</td>
                </tr>
            </tbody>
        </table>
    </div>
  </div>
</template>
