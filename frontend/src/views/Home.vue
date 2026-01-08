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
    
    <!-- Navbar -->
    <nav class="flex justify-between items-center px-8 py-6 z-20 w-full max-w-7xl mx-auto relative">
      <div class="text-3xl font-extrabold tracking-tight flex items-center gap-2">
        <span class="text-white">大帝</span><span class="text-cyan-400">AI</span>
      </div>
      <div class="flex gap-4 items-center">
        <template v-if="isLoggedIn">
           <span class="text-gray-400 font-medium mr-2">你好, <span class="text-cyan-400">{{ user?.username || '创作者' }}</span></span>
           <router-link to="/dashboard" class="relative z-30 px-6 py-2.5 bg-white text-gray-900 rounded-full font-semibold hover:bg-gray-100 transition-all duration-300 shadow-lg">
             进入控制台
           </router-link>
        </template>
        <template v-else>
            <router-link to="/login" class="px-6 py-2 text-gray-400 hover:text-white font-medium transition-colors">登录</router-link>
            <router-link to="/login" class="relative z-30 px-6 py-2.5 bg-white text-gray-900 rounded-full font-semibold hover:bg-gray-100 transition-all duration-300 shadow-lg">
              开始制作
            </router-link>
        </template>
      </div>
    </nav>

    <!-- Main Content -->
    <main class="flex-grow flex flex-col items-center justify-center -mt-16 px-4 relative z-10">
      
      <!-- 标签 -->
      <div class="mb-6 flex items-center justify-center gap-4">
        <div class="px-4 py-1.5 rounded-full border border-cyan-500/30 bg-cyan-500/10 text-cyan-400 text-sm font-medium flex items-center gap-2">
            <span class="relative flex h-2 w-2">
            <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
            <span class="relative inline-flex rounded-full h-2 w-2 bg-cyan-500"></span>
            </span>
            AI 视频生成 · 支持中文
        </div>
        <div class="px-4 py-1.5 rounded-full border border-purple-500/30 bg-purple-500/10 text-purple-400 text-sm font-medium flex items-center gap-2">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
            搭载 Minimax 最新海螺模型
        </div>
      </div>
      
      <!-- Hero Text -->
      <h1 class="text-5xl md:text-7xl font-bold text-center mb-6 tracking-tight">
        <span class="text-white">想象.</span>
        <span class="text-white"> 输入.</span>
        <span class="bg-gradient-to-r from-cyan-400 via-purple-400 to-pink-400 bg-clip-text text-transparent"> 生成.</span>
      </h1>
      
      <p class="text-xl text-gray-400 mb-10 text-center max-w-2xl leading-relaxed">
        使用先进的 AI 技术，将你的创意转化为专业品质的视频
        <br>
        <span class="text-cyan-400 font-semibold">仅需 ¥0.99</span> / 次 · 无需专业知识
      </p>

      <!-- Prompt Bar -->
      <div class="w-full max-w-3xl relative group">
        <!-- 发光边框效果 -->
        <div class="absolute -inset-0.5 bg-gradient-to-r from-cyan-500 via-purple-500 to-pink-500 rounded-2xl opacity-30 blur group-hover:opacity-50 transition-opacity duration-500"></div>
        
        <div class="relative flex items-center bg-[#12121a] border border-white/10 rounded-2xl px-6 py-4 shadow-2xl">
          <div class="mr-4 p-2 rounded-lg bg-gradient-to-br from-cyan-500/20 to-purple-500/20">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
          </div>
          <input 
            v-model="prompt"
            @keyup.enter="handleStart"
            type="text" 
            placeholder="描述你想要的视频... 例如：赛博朋克风格的未来城市，霓虹灯闪烁" 
            class="flex-grow bg-transparent outline-none text-lg text-white placeholder-gray-500"
          >
          <button 
            @click="handleStart" 
            class="ml-4 px-6 py-2 bg-gradient-to-r from-cyan-500 to-purple-500 text-white rounded-xl font-medium hover:shadow-lg hover:shadow-cyan-500/25 transition-all duration-300 flex items-center gap-2"
          >
            生成
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </button>
        </div>
      </div>

      <!-- Feature Chips -->
      <div class="mt-10 flex flex-wrap justify-center gap-4">
        <div class="px-5 py-2.5 rounded-xl bg-white/5 border border-white/10 text-sm font-medium text-gray-300 flex items-center gap-2 hover:bg-white/10 hover:border-cyan-500/30 transition-all cursor-default backdrop-blur-sm">
            <span class="w-2 h-2 rounded-full bg-gradient-to-r from-orange-400 to-red-500"></span>
            充 ¥10 送 ¥1
        </div>
        <div class="px-5 py-2.5 rounded-xl bg-white/5 border border-white/10 text-sm font-medium text-gray-300 flex items-center gap-2 hover:bg-white/10 hover:border-purple-500/30 transition-all cursor-default backdrop-blur-sm">
            <span class="w-2 h-2 rounded-full bg-gradient-to-r from-yellow-400 to-orange-500"></span>
            充 ¥50 送 ¥5
        </div>
        <div class="px-5 py-2.5 rounded-xl bg-white/5 border border-white/10 text-sm font-medium text-gray-300 flex items-center gap-2 hover:bg-white/10 hover:border-pink-500/30 transition-all cursor-default backdrop-blur-sm">
            <span class="w-2 h-2 rounded-full bg-gradient-to-r from-cyan-400 to-blue-500"></span>
            1080p 影院级画质
        </div>
        <div class="px-5 py-2.5 rounded-xl bg-white/5 border border-white/10 text-sm font-medium text-gray-300 flex items-center gap-2 hover:bg-white/10 hover:border-green-500/30 transition-all cursor-default backdrop-blur-sm">
            <span class="w-2 h-2 rounded-full bg-gradient-to-r from-green-400 to-emerald-500"></span>
            秒级响应
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
