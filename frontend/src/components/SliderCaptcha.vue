<script setup>
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'

const props = defineProps({
  target: {
    type: Number,
    default: 50
  }
})

const emit = defineEmits(['success', 'fail'])

// 滑块状态
const sliderValue = ref(0)
const isDragging = ref(false)
const isVerified = ref(false)
const isFailed = ref(false)
const containerRef = ref(null)

// 目标位置（从 props 接收）
const targetPosition = ref(props.target)
const tolerance = 8 // 允许误差范围

// 监听 props 变化
watch(() => props.target, (newVal) => {
  targetPosition.value = newVal
  reset()
})

// 重置
const reset = () => {
  sliderValue.value = 0
  isVerified.value = false
  isFailed.value = false
}

// 设置目标位置（外部调用）
const setTarget = (target) => {
  targetPosition.value = target
  reset()
}

onMounted(() => {
  document.addEventListener('mousemove', onDrag)
  document.addEventListener('mouseup', endDrag)
  document.addEventListener('touchmove', onDrag)
  document.addEventListener('touchend', endDrag)
})

onUnmounted(() => {
  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', endDrag)
  document.removeEventListener('touchmove', onDrag)
  document.removeEventListener('touchend', endDrag)
})

// 滑块样式 - 拖动时无 transition
const sliderStyle = computed(() => {
  const leftPercent = Math.max(0, sliderValue.value - 6)
  return {
    left: `${leftPercent}%`,
    transition: isDragging.value ? 'none' : 'left 0.15s ease-out'
  }
})

const targetStyle = computed(() => ({
  left: `calc(${targetPosition.value}% - 20px)`
}))

const fillStyle = computed(() => ({
  width: sliderValue.value + '%',
  transition: isDragging.value ? 'none' : 'width 0.15s ease-out'
}))

// 开始拖动
const startDrag = (e) => {
  if (isVerified.value) return
  e.preventDefault()
  isDragging.value = true
  isFailed.value = false
}

// 拖动中
const onDrag = (e) => {
  if (!isDragging.value || !containerRef.value) return
  
  const rect = containerRef.value.getBoundingClientRect()
  const clientX = e.type.includes('touch') ? e.touches[0].clientX : e.clientX
  
  let percent = ((clientX - rect.left) / rect.width) * 100
  percent = Math.max(0, Math.min(100, percent))
  sliderValue.value = percent
}

// 结束拖动
const endDrag = () => {
  if (!isDragging.value) return
  isDragging.value = false
  
  const userPosition = sliderValue.value  // 保存用户实际滑动位置
  const diff = Math.abs(userPosition - targetPosition.value)
  
  if (diff <= tolerance) {
    isVerified.value = true
    sliderValue.value = targetPosition.value  // 视觉对齐到目标
    emit('success', userPosition)  // emit 用户实际位置，后端验证需要
  } else {
    isFailed.value = true
    emit('fail')
    setTimeout(() => {
      reset()
    }, 800)
  }
}

defineExpose({ reset, setTarget, isVerified })
</script>

<template>
  <div class="w-full">
    <div class="mb-2 text-xs text-gray-400">拖动滑块到缺口位置</div>
    
    <div 
      ref="containerRef"
      class="slider-container relative h-12 bg-white/5 rounded-xl border border-white/10 overflow-hidden select-none"
    >
      <!-- 目标缺口 -->
      <div 
        class="absolute top-1/2 -translate-y-1/2 w-10 h-10 rounded-lg border-2 border-dashed"
        :class="isVerified ? 'border-green-500 bg-green-500/20' : 'border-cyan-500/50 bg-cyan-500/10'"
        :style="targetStyle"
      >
        <div v-if="isVerified" class="flex items-center justify-center h-full text-green-400">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
          </svg>
        </div>
      </div>
      
      <!-- 已滑动区域 -->
      <div 
        class="absolute left-0 top-0 h-full"
        :class="isVerified ? 'bg-green-500/20' : isFailed ? 'bg-red-500/20' : 'bg-cyan-500/10'"
        :style="fillStyle"
      ></div>
      
      <!-- 滑块 -->
      <div 
        class="absolute top-1/2 -translate-y-1/2 w-12 h-10 rounded-lg flex items-center justify-center shadow-lg cursor-grab active:cursor-grabbing"
        :class="isVerified ? 'bg-green-500' : isFailed ? 'bg-red-500' : 'bg-white hover:bg-gray-100'"
        :style="sliderStyle"
        @mousedown="startDrag"
        @touchstart="startDrag"
      >
        <svg v-if="isVerified" class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
        </svg>
        <svg v-else-if="isFailed" class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
        </svg>
        <svg v-else class="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
        </svg>
      </div>
    </div>
    
    <div class="mt-2 text-xs text-center">
      <span v-if="isVerified" class="text-green-400">验证成功</span>
      <span v-else-if="isFailed" class="text-red-400">验证失败，请重试</span>
      <span v-else class="text-gray-500">向右拖动滑块</span>
    </div>
  </div>
</template>
