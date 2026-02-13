<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'
import { getPublicConfig, getAvailableModels } from '../api'

const prompt = ref('')
const router = useRouter()
const userStore = useUserStore()
const videoPrice23 = ref(0.99)
const videoPrice31 = ref(0.99)

const isLoggedIn = computed(() => !!userStore.token)
const user = computed(() => userStore.user)

// 鼠标跟随效果
const mouseX = ref(0)
const mouseY = ref(0)

const handleMouseMove = (e) => {
  mouseX.value = e.clientX
  mouseY.value = e.clientY
}

const bonusInfo = ref([])

const loadConfig = async () => {
    try {
        const config = await getPublicConfig()
        
        // 从模型API分别获取2.3和3.1系列最低价格
        try {
            const modelsData = await getAvailableModels()
            if (modelsData && modelsData.models && modelsData.models.length > 0) {
                const models23 = modelsData.models.filter(m => m.id.includes('2_0') || m.id.includes('2_3') || m.id.includes('hailuo_1_0'))
                const models31 = modelsData.models.filter(m => m.id.includes('3_1') || m.id.includes('beta_3'))
                if (models23.length > 0) {
                    videoPrice23.value = Math.min(...models23.map(m => m.price || 0.99))
                }
                if (models31.length > 0) {
                    videoPrice31.value = Math.min(...models31.map(m => m.price || 0.99))
                }
            }
        } catch (e) {
            // 保持默认价格
        }
        
        // 生成赠送信息
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
  window.addEventListener('mousemove', handleMouseMove)
  loadConfig()
})

onUnmounted(() => {
  window.removeEventListener('mousemove', handleMouseMove)
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
          <span class="text-white drop-shadow-lg">大帝</span><span class="text-cyan-400 drop-shadow-[0_0_15px_rgba(34,211,238,0.5)]">AI</span>
        </div>
        <p class="text-xl text-gray-200 mb-2 font-light tracking-wide drop-shadow-md">想象 · 输入 · 生成</p>
        <p class="text-sm text-gray-400 font-medium">使用先进的 AI 技术，将你的创意转化为专业品质的视频</p>
      </div>
      
      <!-- AI模型卡片网格 -->
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 w-full max-w-6xl">
        
        <!-- 海螺AI卡片 -->
        <div class="group relative md:col-start-2 lg:col-start-auto">
          <!-- 发光边框 - 优化为单色简约光晕 -->
          <div class="absolute -inset-0.5 bg-gradient-to-b from-cyan-500/20 to-blue-500/5 rounded-3xl blur opacity-20 group-hover:opacity-60 transition-opacity duration-700"></div>
          
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
              <button @click.stop="handleModelSeriesGenerate('2.3')" class="w-full py-3.5 bg-white text-black hover:bg-gray-50 rounded-xl font-bold text-sm transition-all duration-300 shadow-lg hover:shadow-xl hover:scale-[1.02] active:scale-95">
                使用2.3系列生成
              </button>
            </div>
          </div>
        </div>
        
        <!-- 海螺 AI 3.1模型 -->
        <div class="group relative hover:opacity-100 transition-all duration-500 md:col-start-2 md:row-start-2 lg:col-start-auto lg:row-start-auto">
          <div class="absolute -inset-0.5 bg-gradient-to-br from-purple-500/10 to-pink-500/10 rounded-3xl opacity-50 group-hover:opacity-100 transition-all"></div>
          
          <div class="relative bg-white/5 border border-white/5 border-t-white/10 rounded-2xl p-6 shadow-xl h-full backdrop-blur-3xl transition-all duration-500 hover:bg-white/10 hover:border-white/10 hover:-translate-y-1">
            <div class="flex justify-between items-center mb-4">
              <div class="px-2.5 py-1 rounded-full bg-gradient-to-r from-purple-500/80 to-pink-500/80 text-white text-xs font-bold shadow-sm ring-1 ring-white/10">
                NEW
              </div>
              <div class="text-xl font-bold text-white drop-shadow-sm tracking-wide">
                ¥{{ videoPrice31 }}
              </div>
            </div>
            
            <!-- 模型名称 -->
            <h3 class="text-xl font-bold text-white mb-4 flex items-center gap-2">
              海螺 AI 3.1 <span class="text-[10px] text-purple-400 font-normal px-1.5 py-0.5 border border-purple-400/30 rounded tracking-wider uppercase">3.1系列</span>
              <div class="w-1.5 h-1.5 rounded-full bg-purple-500 shadow-[0_0_8px_rgba(147,51,234,0.8)] animate-pulse"></div>
            </h3>
            
            <!-- 特性标签 -->
            <div class="space-y-2 mb-6">
              <div class="px-3 py-2 rounded-lg bg-black/20 text-gray-300 text-xs font-medium flex items-center gap-2 border border-white/5 group-hover:border-white/10 transition-colors">
                <svg class="w-3.5 h-3.5 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/></svg>
                音画同步技术
              </div>
              <div class="px-3 py-2 rounded-lg bg-black/20 text-gray-300 text-xs font-medium border border-white/5 group-hover:border-white/10 transition-colors">
                3.1系列：高精度控制，音画完美融合
              </div>
            </div>
            
            <!-- 价格说明 -->
            <div class="text-center mb-6">
              <div class="text-sm font-medium text-gray-400">
                单次生成仅需 <span class="text-white font-bold mx-1">{{ videoPrice31 }}元</span>
              </div>
            </div>
            
            <!-- 生成按钮 -->
            <div>
              <button @click.stop="handleModelSeriesGenerate('3.1')" class="w-full py-3.5 bg-white text-black hover:bg-gray-50 rounded-xl font-bold text-sm transition-all duration-300 shadow-lg hover:shadow-xl hover:scale-[1.02] active:scale-95">
                使用3.1系列生成
              </button>
            </div>
          </div>
        </div>
        
        <!-- Runway Gen 模型 -->
        <div class="group relative opacity-60 hover:opacity-100 transition-all duration-500 md:col-start-auto lg:col-start-auto">
          <div class="absolute -inset-0.5 bg-white/5 rounded-3xl opacity-0"></div>
          
          <div class="relative bg-white/5 border border-white/5 border-t-white/10 rounded-2xl p-6 shadow-xl h-full backdrop-blur-3xl transition-all duration-500 hover:bg-white/10 hover:border-white/10 hover:-translate-y-1">
            <div class="flex justify-between items-center mb-4">
              <div class="px-2.5 py-1 rounded-full bg-white/5 text-gray-400 text-xs font-bold border border-white/5">
                筹备中
              </div>
              <div class="text-3xl font-black text-gray-600">
                ¥?
              </div>
            </div>
            
            <h3 class="text-xl font-bold text-gray-500 mb-3 group-hover:text-gray-300 transition-colors">
              Runway Gen
            </h3>
            
            <div class="space-y-2 mb-4">
              <div class="px-3 py-1.5 rounded-lg border border-white/5 bg-black/20 text-gray-500 text-xs font-medium group-hover:text-gray-400">
                专业级质量
              </div>
              <div class="px-3 py-1.5 rounded-lg border border-white/5 bg-black/20 text-gray-500 text-xs font-medium group-hover:text-gray-400">
                电影级效果
              </div>
            </div>
            
            <div class="text-center mb-3">
              <div class="text-sm font-semibold text-gray-500 mb-1">
                敬请期待
              </div>
              <p class="text-xs text-gray-600">筹备中</p>
            </div>
            
            <button class="w-full py-2 bg-gray-700 text-gray-500 rounded-xl font-bold text-sm cursor-not-allowed">
              即将推出
            </button>
          </div>
        </div>
        
        <!-- Sora 模型 -->
        <div class="group relative opacity-60">
          <div class="absolute -inset-0.5 bg-gradient-to-r from-yellow-500 to-orange-600 rounded-2xl opacity-20 blur"></div>
          
          <div class="relative bg-[#12121a] border border-gray-700/50 rounded-2xl p-4 shadow-2xl h-full">
            <div class="flex justify-between items-center mb-3">
              <div class="px-2 py-1 rounded-full bg-gray-600 text-gray-400 text-xs font-bold">
                计划中
              </div>
              <div class="text-3xl font-black text-gray-600">
                ¥?
              </div>
            </div>
            
            <h3 class="text-xl font-bold text-gray-500 mb-3">
              Sora 模型
            </h3>
            
            <div class="space-y-2 mb-4">
              <div class="px-3 py-1.5 rounded-lg border border-gray-600/30 bg-gray-600/10 text-gray-500 text-xs font-medium">
                OpenAI Sora
              </div>
              <div class="px-3 py-1.5 rounded-lg border border-gray-600/30 bg-gray-600/10 text-gray-500 text-xs font-medium">
                长视频生成
              </div>
            </div>
            
            <div class="text-center mb-3">
              <div class="text-sm font-semibold text-gray-500 mb-1">
                敬请期待
              </div>
              <p class="text-xs text-gray-600">计划中</p>
            </div>
            
            <button class="w-full py-2 bg-gray-700 text-gray-500 rounded-xl font-bold text-sm cursor-not-allowed">
              即将推出
            </button>
          </div>
        </div>
        
        <!-- 可灵AI模型 -->
        <div class="group relative opacity-60">
          <div class="absolute -inset-0.5 bg-gradient-to-r from-blue-500 to-indigo-600 rounded-2xl opacity-20 blur"></div>
          
          <div class="relative bg-[#12121a] border border-gray-700/50 rounded-2xl p-4 shadow-2xl h-full">
            <div class="flex justify-between items-center mb-3">
              <div class="px-2 py-1 rounded-full bg-gray-600 text-gray-400 text-xs font-bold">
                评估中
              </div>
              <div class="text-3xl font-black text-gray-600">
                ¥?
              </div>
            </div>
            
            <h3 class="text-xl font-bold text-gray-500 mb-3">
              可灵 AI
            </h3>
            
            <div class="space-y-2 mb-4">
              <div class="px-3 py-1.5 rounded-lg border border-gray-600/30 bg-gray-600/10 text-gray-500 text-xs font-medium">
                快手技术
              </div>
              <div class="px-3 py-1.5 rounded-lg border border-gray-600/30 bg-gray-600/10 text-gray-500 text-xs font-medium">
                高性价比
              </div>
            </div>
            
            <div class="text-center mb-3">
              <div class="text-sm font-semibold text-gray-500 mb-1">
                敬请期待
              </div>
              <p class="text-xs text-gray-600">评估中</p>
            </div>
            
            <button class="w-full py-2 bg-gray-700 text-gray-500 rounded-xl font-bold text-sm cursor-not-allowed">
              即将推出
            </button>
          </div>
        </div>
        
        <!-- 文心一格模型 -->
        <div class="group relative opacity-60">
          <div class="absolute -inset-0.5 bg-gradient-to-r from-red-500 to-pink-600 rounded-2xl opacity-20 blur"></div>
          
          <div class="relative bg-[#12121a] border border-gray-700/50 rounded-2xl p-4 shadow-2xl h-full">
            <div class="flex justify-between items-center mb-3">
              <div class="px-2 py-1 rounded-full bg-gray-600 text-gray-400 text-xs font-bold">
                研究中
              </div>
              <div class="text-3xl font-black text-gray-600">
                ¥?
              </div>
            </div>
            
            <h3 class="text-xl font-bold text-gray-500 mb-3">
              文心一格
            </h3>
            
            <div class="space-y-2 mb-4">
              <div class="px-3 py-1.5 rounded-lg border border-gray-600/30 bg-gray-600/10 text-gray-500 text-xs font-medium">
                百度技术
              </div>
              <div class="px-3 py-1.5 rounded-lg border border-gray-600/30 bg-gray-600/10 text-gray-500 text-xs font-medium">
                本土化优势
              </div>
            </div>
            
            <div class="text-center mb-3">
              <div class="text-sm font-semibold text-gray-500 mb-1">
                敬请期待
              </div>
              <p class="text-xs text-gray-600">研究中</p>
            </div>
            
            <button class="w-full py-2 bg-gray-700 text-gray-500 rounded-xl font-bold text-sm cursor-not-allowed">
              即将推出
            </button>
          </div>
        </div>
        
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
      © 2026 大帝AI · 由先进 AI 技术驱动
    </footer>

  </div>
</template>

<style scoped>
/* 径向渐变 */
.bg-gradient-radial {
  background: radial-gradient(circle, var(--tw-gradient-from), var(--tw-gradient-via), var(--tw-gradient-to));
}
</style>
