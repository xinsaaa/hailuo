<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'

const prompt = ref('')
const router = useRouter()
const userStore = useUserStore()

const isLoggedIn = computed(() => !!userStore.token)
const user = computed(() => userStore.user)

// 鼠标跟随效果
const mouseX = ref(0)
const mouseY = ref(0)

const handleMouseMove = (e) => {
  mouseX.value = e.clientX
  mouseY.value = e.clientY
}

onMounted(() => {
  window.addEventListener('mousemove', handleMouseMove)
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
</script>

<template>
  <div class="min-h-screen flex flex-col bg-[#0a0a0f] overflow-hidden relative selection:bg-cyan-500 selection:text-white">
    
    <!-- 动态网格背景 -->
    <div class="absolute inset-0 bg-[linear-gradient(rgba(6,182,212,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(6,182,212,0.03)_1px,transparent_1px)] bg-[size:50px_50px]"></div>
    
    <!-- 顶部渐变光晕 -->
    <div class="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px] bg-gradient-radial from-cyan-500/20 via-transparent to-transparent blur-3xl"></div>
    
    <!-- 鼠标跟随小球 -->
    <div 
      class="pointer-events-none fixed w-[500px] h-[500px] rounded-full bg-gradient-to-r from-cyan-500/30 to-purple-500/30 blur-[100px] transition-all duration-700 ease-out"
      :style="{ left: mouseX - 250 + 'px', top: mouseY - 250 + 'px' }"
    ></div>
    
    <!-- 装饰性浮动粒子 -->
    <div class="absolute top-20 left-[10%] w-2 h-2 bg-cyan-400 rounded-full animate-pulse opacity-60"></div>
    <div class="absolute top-40 right-[15%] w-1.5 h-1.5 bg-purple-400 rounded-full animate-ping opacity-40"></div>
    <div class="absolute bottom-32 left-[20%] w-1 h-1 bg-pink-400 rounded-full animate-pulse opacity-50"></div>
    <div class="absolute top-1/2 right-[8%] w-2 h-2 bg-yellow-400 rounded-full animate-ping opacity-30"></div>
    <div class="absolute bottom-1/4 right-[25%] w-1.5 h-1.5 bg-green-400 rounded-full animate-pulse opacity-40"></div>
    
    <!-- 右上角登录按钮 -->
    <nav class="absolute top-6 right-8 z-20">
      <div class="flex gap-4 items-center">
        <template v-if="isLoggedIn">
           <span class="text-gray-400 font-medium mr-2">你好, <span class="text-cyan-400">{{ user?.username || '创作者' }}</span></span>
           <router-link to="/dashboard" class="px-6 py-2.5 bg-white text-gray-900 rounded-full font-semibold hover:bg-gray-100 transition-all duration-300 shadow-lg">
             进入控制台
           </router-link>
        </template>
        <template v-else>
            <router-link to="/login" class="px-6 py-2 text-gray-400 hover:text-white font-medium transition-colors">登录</router-link>
            <router-link to="/login" class="px-6 py-2.5 bg-white text-gray-900 rounded-full font-semibold hover:bg-gray-100 transition-all duration-300 shadow-lg">
              开始制作
            </router-link>
        </template>
      </div>
    </nav>

    <!-- Main Content -->
    <main class="flex-grow flex flex-col items-center justify-center px-4 relative z-10">
      
      <!-- 中央Logo -->
      <div class="text-center mb-8">
        <div class="text-4xl md:text-6xl font-extrabold tracking-tight mb-3">
          <span class="text-white">大帝</span><span class="text-cyan-400">AI</span>
        </div>
        <p class="text-lg text-gray-400 mb-2">想象. 输入. 生成.</p>
        <p class="text-sm text-gray-500">使用先进的 AI 技术，将你的创意转化为专业品质的视频</p>
      </div>
      
      <!-- AI模型卡片网格 -->
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 w-full max-w-6xl">
        
        <!-- 海螺AI卡片 -->
        <div class="group relative">
          <!-- 发光边框 -->
          <div class="absolute -inset-0.5 bg-gradient-to-r from-cyan-500 via-purple-500 to-pink-500 rounded-2xl opacity-40 blur group-hover:opacity-60 transition-opacity duration-500"></div>
          
          <div class="relative bg-[#12121a] border border-white/20 rounded-2xl p-4 shadow-2xl h-full cursor-pointer transition-all duration-300 hover:scale-105" @click="handleStart">
            <!-- 顶部标签 -->
            <div class="flex justify-between items-center mb-3">
              <div class="px-2 py-1 rounded-full bg-gradient-to-r from-orange-500 to-red-500 text-white text-xs font-bold">
                最热门
              </div>
              <div class="text-2xl font-black text-transparent bg-gradient-to-r from-cyan-400 to-purple-400 bg-clip-text text-right">
                ¥0.99
              </div>
            </div>
            
            <!-- 模型名称 -->
            <h3 class="text-xl font-bold text-white mb-3 flex items-center gap-2">
              海螺 AI <span class="text-sm text-gray-400 font-normal">（官网正品）</span>
              <div class="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
            </h3>
            
            <!-- 特性标签 -->
            <div class="space-y-2 mb-5">
              <div class="px-3 py-1.5 rounded-lg border border-cyan-500/30 bg-cyan-500/10 text-cyan-400 text-xs font-medium flex items-center gap-1">
                <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
                最顶级 AI 模型
              </div>
              <div class="px-3 py-1.5 rounded-lg border border-purple-500/30 bg-purple-500/10 text-purple-400 text-xs font-medium">
                Minimax 海螺模型
              </div>
            </div>
            
            <!-- 价格说明 -->
            <div class="text-center mb-4">
              <div class="text-sm font-semibold text-gray-300 leading-relaxed">
                仅需<span class="text-yellow-400 text-lg font-bold">0.99元</span>即可生成一条视频
              </div>
            </div>
            
            <!-- 生成按钮 -->
            <div>
              <button class="w-full py-3 bg-gradient-to-r from-cyan-500 to-purple-500 text-white rounded-xl font-bold text-sm hover:shadow-lg hover:shadow-cyan-500/25 transition-all duration-300">
                立即生成视频
              </button>
            </div>
          </div>
        </div>
        
        <!-- GPT 视频模型 -->
        <div class="group relative opacity-60">
          <div class="absolute -inset-0.5 bg-gradient-to-r from-green-500 to-emerald-600 rounded-2xl opacity-20 blur"></div>
          
          <div class="relative bg-[#12121a] border border-gray-700/50 rounded-2xl p-4 shadow-2xl h-full">
            <div class="flex justify-between items-center mb-3">
              <div class="px-2 py-1 rounded-full bg-gray-600 text-gray-400 text-xs font-bold">
                即将推出
              </div>
              <div class="text-3xl font-black text-gray-600">
                ¥?
              </div>
            </div>
            
            <h3 class="text-xl font-bold text-gray-500 mb-3">
              GPT 视频
            </h3>
            
            <div class="space-y-2 mb-4">
              <div class="px-3 py-1.5 rounded-lg border border-gray-600/30 bg-gray-600/10 text-gray-500 text-xs font-medium">
                OpenAI 技术
              </div>
              <div class="px-3 py-1.5 rounded-lg border border-gray-600/30 bg-gray-600/10 text-gray-500 text-xs font-medium">
                更强理解能力
              </div>
            </div>
            
            <div class="text-center mb-3">
              <div class="text-sm font-semibold text-gray-500 mb-1">
                敬请期待
              </div>
              <p class="text-xs text-gray-600">开发中</p>
            </div>
            
            <button class="w-full py-2 bg-gray-700 text-gray-500 rounded-xl font-bold text-sm cursor-not-allowed">
              即将推出
            </button>
          </div>
        </div>
        
        <!-- Runway Gen 模型 -->
        <div class="group relative opacity-60">
          <div class="absolute -inset-0.5 bg-gradient-to-r from-purple-500 to-pink-600 rounded-2xl opacity-20 blur"></div>
          
          <div class="relative bg-[#12121a] border border-gray-700/50 rounded-2xl p-4 shadow-2xl h-full">
            <div class="flex justify-between items-center mb-3">
              <div class="px-2 py-1 rounded-full bg-gray-600 text-gray-400 text-xs font-bold">
                筹备中
              </div>
              <div class="text-3xl font-black text-gray-600">
                ¥?
              </div>
            </div>
            
            <h3 class="text-xl font-bold text-gray-500 mb-3">
              Runway Gen
            </h3>
            
            <div class="space-y-2 mb-4">
              <div class="px-3 py-1.5 rounded-lg border border-gray-600/30 bg-gray-600/10 text-gray-500 text-xs font-medium">
                专业级质量
              </div>
              <div class="px-3 py-1.5 rounded-lg border border-gray-600/30 bg-gray-600/10 text-gray-500 text-xs font-medium">
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

      <!-- 底部优惠信息 -->
      <div class="mt-8 flex flex-wrap justify-center gap-4">
        <div class="px-6 py-3 rounded-2xl bg-white/5 border border-white/10 text-sm font-medium text-gray-300 flex items-center gap-2 hover:bg-white/10 hover:border-cyan-500/30 transition-all cursor-default backdrop-blur-sm">
            <span class="w-3 h-3 rounded-full bg-gradient-to-r from-orange-400 to-red-500"></span>
            充值 ¥10 送 ¥2
        </div>
        <div class="px-6 py-3 rounded-2xl bg-white/5 border border-white/10 text-sm font-medium text-gray-300 flex items-center gap-2 hover:bg-white/10 hover:border-purple-500/30 transition-all cursor-default backdrop-blur-sm">
            <span class="w-3 h-3 rounded-full bg-gradient-to-r from-yellow-400 to-orange-500"></span>
            充值 ¥50 送 ¥10
        </div>
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
