<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'
import { getPublicConfig, getAvailableModels } from '../api'

const prompt = ref('')
const router = useRouter()
const userStore = useUserStore()
const videoPrice23 = ref(0.99)
const modelsList = ref([])
const klingPrice = ref(0.99)
const hasKling = computed(() => modelsList.value.some(m => m.id?.includes('kling') && m.type !== 'lip_sync'))

const has23Series = computed(() => modelsList.value.some(m => m.id.includes('2_0') || m.id.includes('2_3') || m.id.includes('hailuo_1_0')))

const siteName = ref(localStorage.getItem('site_name') || '大帝AI')
const siteAnnouncement = ref('')
const isLoggedIn = computed(() => !!userStore.token)
const user = computed(() => userStore.user)

const bonusInfo = ref([])

const loadConfig = async () => {
    try {
        const config = await getPublicConfig()
        
        // 加载模型
        try {
            const modelsData = await getAvailableModels()
            if (modelsData && modelsData.models && modelsData.models.length > 0) {
                modelsList.value = modelsData.models
                const models23 = modelsData.models.filter(m => m.id.includes('2_0') || m.id.includes('2_3') || m.id.includes('hailuo_1_0'))
                if (models23.length > 0) {
                    videoPrice23.value = Math.min(...models23.map(m => m.price || 0.99))
                }
                const modelsKling = modelsData.models.filter(m => m.id === 'kling_3_0')
                if (modelsKling.length > 0) {
                    klingPrice.value = Math.min(...modelsKling.map(m => m.price || 0.99))
                }
            }
        } catch (e) {
            // 保持默认价格
        }
        
        // 生成赠送信息
        if (config.site_announcement) siteAnnouncement.value = config.site_announcement
        if (config.bonus_rate && config.bonus_min_amount) {
            const rate = config.bonus_rate
            const minAmount = config.bonus_min_amount
            
            // 根据赠送比例计算不同金额的赠送
            bonusInfo.value = [
                {
                    charge: minAmount,
                    bonus: minAmount * rate,
                    color: 'from-orange-400 to-red-500'
                },
                {
                    charge: 50,
                    bonus: 50 * rate,
                    color: 'from-yellow-400 to-orange-500'
                },
                {
                    charge: 100,
                    bonus: 100 * rate,
                    color: 'from-green-400 to-emerald-500'
                }
            ]
        }
    } catch (err) {
        console.error('获取配置失败', err)
    }
}

onMounted(() => {
  loadConfig()
})

const handleStart = () => {
  if (prompt.value) {
    router.push({ name: 'Dashboard', query: { prompt: prompt.value } })
  } else {
    router.push({ name: 'Dashboard' })
  }
}

// 处理不同模型系列的生成
const handleModelSeriesGenerate = (series) => {
  if (prompt.value) {
    router.push({ 
      name: 'Dashboard', 
      query: { 
        prompt: prompt.value, 
        series: series 
      } 
    })
  } else {
    router.push({ 
      name: 'Dashboard', 
      query: { 
        series: series 
      } 
    })
  }
}
</script>

<template>
  <div class="min-h-screen flex flex-col overflow-hidden relative selection:bg-cyan-500 selection:text-white">
    
    <!-- 右上角登录按钮 -->
    <nav class="absolute top-6 right-8 z-20">
      <div class="flex gap-4 items-center">
        <template v-if="isLoggedIn">
           <span class="text-gray-300 font-medium mr-2 text-shadow-sm">你好, <span class="text-cyan-400 font-bold">{{ user?.username || '创作者' }}</span></span>
           <router-link to="/invite" class="text-gray-300 hover:text-white font-medium transition-colors hover:drop-shadow-md mr-4">邀请</router-link>
           <router-link to="/dashboard" class="px-6 py-2.5 bg-white/90 text-gray-900 rounded-full font-bold hover:bg-white transition-all duration-300 shadow-lg hover:shadow-cyan-500/20 backdrop-blur-sm">
             进入控制台
           </router-link>
        </template>
        <template v-else>
            <router-link to="/login" class="px-6 py-2 text-gray-300 hover:text-white font-medium transition-colors hover:drop-shadow-md">登录</router-link>
            <router-link to="/login" class="px-6 py-2.5 bg-white/90 text-gray-900 rounded-full font-bold hover:bg-white transition-all duration-300 shadow-lg hover:shadow-cyan-500/20 backdrop-blur-sm">
              开始制作
            </router-link>
        </template>
      </div>
    </nav>

    <!-- Main Content -->
    <main class="flex-grow flex flex-col items-center justify-center px-4 relative z-10">
      
      <!-- 中央Logo -->
      <div class="text-center mb-12">
        <div class="text-5xl md:text-7xl font-extrabold tracking-tight mb-4 flex justify-center items-center gap-2">
          <span class="text-white drop-shadow-lg">{{ siteName }}</span>
        </div>
        <p class="text-xl text-gray-200 mb-2 font-light tracking-wide drop-shadow-md">想象 · 输入 · 生成</p>
        <p class="text-sm text-gray-400 font-medium">使用先进的 AI 技术，将你的创意转化为专业品质的视频</p>
      </div>

      <!-- 滚动公告 -->
      <div v-if="siteAnnouncement" class="w-full max-w-2xl mx-auto mb-8 overflow-hidden rounded-xl bg-amber-500/10 border border-amber-500/20 py-2 px-4">
        <div class="flex items-center gap-3">
          <span class="text-amber-400 text-base shrink-0">📢</span>
          <div class="overflow-hidden flex-1">
            <div class="animate-marquee whitespace-nowrap text-sm text-amber-200/90">{{ siteAnnouncement }}</div>
          </div>
        </div>
      </div>
      
      <!-- AI模型卡片网格 -->
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-8 w-full max-w-3xl">
        
        <!-- 海螺AI卡片 -->
        <div :class="['group relative', { 'opacity-60': !has23Series }]">
          <!-- 发光边框 - 优化为单色简约光晕 -->
          <div v-if="has23Series" class="absolute -inset-0.5 bg-gradient-to-b from-cyan-500/20 to-blue-500/5 rounded-3xl blur opacity-20 group-hover:opacity-60 transition-opacity duration-700"></div>
          
          <div class="relative bg-white/5 border border-white/5 border-t-white/20 rounded-2xl p-6 shadow-2xl h-full cursor-pointer transition-all duration-500 hover:scale-[1.02] hover:-translate-y-1 backdrop-blur-3xl hover:bg-white/10 hover:shadow-cyan-500/10">
            <!-- 顶部标签 -->
            <div class="flex justify-between items-center mb-4">
              <div class="px-2.5 py-1 rounded-full bg-gradient-to-r from-red-500 to-orange-500 text-white text-xs font-bold shadow-sm ring-1 ring-white/10">
                HOT
              </div>
              <div class="text-xl font-bold text-white drop-shadow-sm tracking-wide">
                ¥{{ videoPrice23 }}
              </div>
            </div>
            
            <!-- 模型名称 -->
            <h3 class="text-xl font-bold text-white mb-4 flex items-center gap-2">
              海螺 AI 2.3 <span class="text-[10px] text-cyan-400 font-normal px-1.5 py-0.5 border border-cyan-400/30 rounded tracking-wider uppercase">2.3系列</span>
              <div class="w-1.5 h-1.5 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,199,89,0.8)] animate-pulse"></div>
            </h3>
            
            <!-- 特性标签 -->
            <div class="space-y-2 mb-6">
              <div class="px-3 py-2 rounded-lg bg-black/20 text-gray-300 text-xs font-medium flex items-center gap-2 border border-white/5 group-hover:border-white/10 transition-colors">
                <svg class="w-3.5 h-3.5 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
                顶级生成效果
              </div>
              <div class="px-3 py-2 rounded-lg bg-black/20 text-gray-300 text-xs font-medium border border-white/5 group-hover:border-white/10 transition-colors">
                2.3系列：稳定、高效、全面升级
              </div>
            </div>
            
            <!-- 价格说明 -->
            <div class="text-center mb-6">
              <div class="text-sm font-medium text-gray-400">
                单次生成仅需 <span class="text-white font-bold mx-1">{{ videoPrice23 }}元</span>
              </div>
            </div>
            
            <!-- 生成按钮 -->
            <div>
              <button v-if="has23Series" @click.stop="handleModelSeriesGenerate('2.3')" class="w-full py-3.5 bg-white text-black hover:bg-gray-50 rounded-xl font-bold text-sm transition-all duration-300 shadow-lg hover:shadow-xl hover:scale-[1.02] active:scale-95">
                使用2.3系列生成
              </button>
              <button v-else class="w-full py-3.5 bg-gray-700 text-gray-500 rounded-xl font-bold text-sm cursor-not-allowed">
                暂未开放
              </button>
            </div>
          </div>
        </div>
        
        <!-- Seedance极速版 -->
        <div :class="['group relative', { 'opacity-60': !hasKling }]" @click="hasKling && router.push('/seedance')">
          <div v-if="hasKling" class="absolute -inset-0.5 bg-gradient-to-b from-violet-500/20 to-fuchsia-500/5 rounded-3xl blur opacity-20 group-hover:opacity-60 transition-opacity duration-700"></div>

          <div class="relative bg-white/5 border border-white/5 border-t-white/20 rounded-2xl p-6 shadow-2xl h-full cursor-pointer transition-all duration-500 hover:scale-[1.02] hover:-translate-y-1 backdrop-blur-3xl hover:bg-white/10 hover:shadow-violet-500/10">
            <div class="flex justify-between items-center mb-4">
              <div class="px-2.5 py-1 rounded-full bg-gradient-to-r from-violet-500 to-fuchsia-500 text-white text-xs font-bold shadow-sm ring-1 ring-white/10">
                HOT
              </div>
              <div class="text-xl font-bold text-white drop-shadow-sm tracking-wide">
                ¥{{ klingPrice }}
              </div>
            </div>

            <h3 class="text-xl font-bold text-white mb-4 flex items-center gap-2">
              Seedance 极速版 <span class="text-[10px] text-violet-400 font-normal px-1.5 py-0.5 border border-violet-400/30 rounded tracking-wider uppercase">Seedance 2.0</span>
              <div v-if="hasKling" class="w-1.5 h-1.5 rounded-full bg-violet-400 shadow-[0_0_8px_rgba(167,139,250,0.8)] animate-pulse"></div>
            </h3>

            <div class="space-y-2 mb-6">
              <div class="px-3 py-2 rounded-lg bg-black/20 text-gray-300 text-xs font-medium flex items-center gap-2 border border-white/5 group-hover:border-white/10 transition-colors">
                <svg class="w-3.5 h-3.5 text-violet-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
                字节跳动出品，极速生成
              </div>
              <div class="px-3 py-2 rounded-lg bg-black/20 text-gray-300 text-xs font-medium border border-white/5 group-hover:border-white/10 transition-colors">
                电影级画质，运动自然流畅
              </div>
            </div>

            <div class="text-center mb-6">
              <div class="text-sm font-medium text-gray-400">
                单次生成仅需 <span class="text-white font-bold mx-1">{{ klingPrice }}元</span>
              </div>
            </div>

            <div>
              <button v-if="hasKling" class="w-full py-3.5 bg-white text-black hover:bg-gray-50 rounded-xl font-bold text-sm transition-all duration-300 shadow-lg hover:shadow-xl hover:scale-[1.02] active:scale-95">
                使用 Seedance 生成
              </button>
              <button v-else class="w-full py-3.5 bg-gray-700 text-gray-500 rounded-xl font-bold text-sm cursor-not-allowed">
                暂未开放
              </button>
            </div>
          </div>
        </div>

        <!-- nanobanana pro 满血版 (暂时隐藏) -->
        
      </div>

      <!-- 服务特色 -->
      <div class="mt-8 flex justify-center">
        <div class="px-6 py-3 rounded-2xl bg-white/5 border border-white/10 text-sm font-medium text-gray-300 flex items-center gap-2 hover:bg-white/10 hover:border-green-500/30 transition-all cursor-default backdrop-blur-sm">
          <span class="w-3 h-3 rounded-full bg-gradient-to-r from-green-400 to-emerald-500"></span>
          秒级响应 · 极速生成
        </div>
      </div>

    </main>

    <!-- Footer -->
    <footer class="w-full text-center py-6 text-gray-600 text-sm z-10">
      © 2026 {{ siteName }} · 由先进 AI 技术驱动
    </footer>

  </div>
</template>

<style scoped>
/* 径向渐变 */
.bg-gradient-radial {
  background: radial-gradient(circle, var(--tw-gradient-from), var(--tw-gradient-via), var(--tw-gradient-to));
}
@keyframes marquee {
  0% { transform: translateX(100%); }
  100% { transform: translateX(-100%); }
}
.animate-marquee {
  animation: marquee 15s linear infinite;
}
</style>
