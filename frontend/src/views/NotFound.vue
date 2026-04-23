<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const countdown = ref(5)
let timer = null

onMounted(() => {
  timer = setInterval(() => {
    countdown.value--
    if (countdown.value <= 0) {
      clearInterval(timer)
      router.push('/')
    }
  }, 1000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})

const goHome = () => {
  if (timer) clearInterval(timer)
  router.push('/')
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center relative overflow-hidden">
    <div class="relative z-10 text-center px-6">
      <div class="text-[120px] font-extrabold leading-none tracking-tighter bg-gradient-to-b from-white/80 to-white/10 bg-clip-text text-transparent select-none">
        404
      </div>
      <h2 class="text-2xl font-bold text-white mt-4 mb-2">页面不存在</h2>
      <p class="text-gray-400 mb-8 text-sm">你访问的页面可能已被移除或地址有误</p>
      <div class="flex flex-col items-center gap-4">
        <button
          @click="goHome"
          class="px-8 py-3 bg-white text-black rounded-xl font-bold text-sm hover:bg-gray-100 transition-all duration-300 shadow-lg hover:shadow-xl hover:scale-105 active:scale-95"
        >
          返回首页
        </button>
        <span class="text-xs text-gray-500">{{ countdown }} 秒后自动返回首页</span>
      </div>
    </div>
    <div class="fixed inset-0 z-0">
      <div class="absolute inset-0 bg-[radial-gradient(ellipse_80%_80%_at_50%_-20%,rgba(99,102,241,0.15),transparent)]"></div>
    </div>
  </div>
</template>
