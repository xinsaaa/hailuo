<script setup>
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getCurrentUser, createOrder, getOrders, getPublicConfig, getAvailableModels } from '../api'

const route = useRoute()
const router = useRouter()

// State
const user = ref(null)
const orders = ref([])
const prompt = ref(route.query.prompt || '')
const loading = ref(false)

// 模型系列过滤
const modelSeries = ref(route.query.series || 'all') // '2.3', '3.1', 'all'

// 系列名称映射
const getSeriesDisplayName = (series) => {
  switch (series) {
    case '2.3': return '海螺AI 2.3系列'
    case '3.1': return '海螺AI 3.1系列'
    default: return '海螺AI 全系列'
  }
}

// 模型选择相关状态
const availableModels = ref([])
const selectedModel = ref(null)
const showModelSelector = ref(false)

// 首尾帧图片上传状态
const firstFrameImage = ref(null)
const lastFrameImage = ref(null)
const firstFramePreview = ref(null)
const lastFramePreview = ref(null)

// 系统配置（从 API 加载）
const config = ref({
  bonus_rate: 0.2,
  bonus_min_amount: 10,
  min_recharge: 0.01,
  max_recharge: 10000
})

// 鼠标跟随效果
const mouseX = ref(0)
const mouseY = ref(0)

const handleMouseMove = (e) => {
  mouseX.value = e.clientX
  mouseY.value = e.clientY
}

// 订单自动刷新
let ordersInterval = null

const startOrdersPolling = () => {
  if (ordersInterval) return
  ordersInterval = setInterval(async () => {
    // 检查是否有处理中的订单
    const hasProcessing = orders.value.some(o => 
      o.status === 'pending' || o.status === 'processing' || o.status === 'generating'
    )
    if (hasProcessing) {
      try {
        orders.value = await getOrders()
      } catch (err) {
        console.error('刷新订单失败', err)
      }
    }
  }, 1500) // 1.5秒刷新一次
}

// 点击外部关闭模型选择器
const handleClickOutside = (event) => {
  if (showModelSelector.value && !event.target.closest('.model-selector')) {
    showModelSelector.value = false
  }
}

// 监听路由参数变化
watch(() => route.query.series, (newSeries) => {
  modelSeries.value = newSeries || 'all'
  loadData() // 重新加载数据以应用新的过滤
})

onMounted(() => {
  window.addEventListener('mousemove', handleMouseMove)
  document.addEventListener('click', handleClickOutside)
  loadData()
  startOrdersPolling()
})

onUnmounted(() => {
  window.removeEventListener('mousemove', handleMouseMove)
  document.removeEventListener('click', handleClickOutside)
  if (ordersInterval) clearInterval(ordersInterval)
})

// Toast 状态
const showToast = ref(false)
const toastMessage = ref('')
const toastType = ref('info')

const formattedBalance = computed(() => {
  return user.value ? user.value.balance.toFixed(2) : '0.00'
})

const showNotification = (message, type = 'info') => {
  toastMessage.value = message
  toastType.value = type
  showToast.value = true
  setTimeout(() => { showToast.value = false }, 3000)
}

const loadData = async () => {
  try {
    // 并行加载用户、订单、配置和模型
    const [userData, ordersData, configData, modelsData] = await Promise.all([
      getCurrentUser(),
      getOrders(),
      getPublicConfig().catch(() => null),
      getAvailableModels().catch(() => null)
    ])
    user.value = userData
    orders.value = ordersData
    if (configData) {
      config.value = configData
    }
    if (modelsData && modelsData.models) {
      // 根据系列过滤模型
      let filteredModels = modelsData.models
      if (modelSeries.value === '2.3') {
        // 只显示2.3系列模型（包含2.0、2.3等）
        filteredModels = modelsData.models.filter(model => 
          model.model_id.includes('2_0') || 
          model.model_id.includes('2_3') || 
          model.model_id.includes('2.3') ||
          model.model_id.includes('hailuo_1_0') // 1.0系列归到2.3
        )
      } else if (modelSeries.value === '3.1') {
        // 只显示3.1系列模型
        filteredModels = modelsData.models.filter(model => 
          model.model_id.includes('3_1') || 
          model.model_id.includes('3.1') ||
          model.model_id.includes('beta_3_1') ||
          model.model_id.includes('hailuo_3_1')
        )
      }
      
      availableModels.value = filteredModels
      
      // 设置默认选中模型
      if (filteredModels.length > 0) {
        selectedModel.value = filteredModels.find(m => m.is_default) || filteredModels[0]
      }
    }
  } catch (err) {
    if (err.response?.status === 401) {
      router.push('/login')
    }
  }
}

const handleCreateOrder = async () => {
  if (!prompt.value.trim()) {
    showNotification('请输入视频描述', 'error')
    return
  }
  
  if (!selectedModel.value) {
    showNotification('请选择生成模型', 'error')
    return
  }
  
  const modelPrice = selectedModel.value?.price || 0.99
  if (!user.value || user.value.balance < modelPrice) {
    showNotification(`余额不足，需 ¥${modelPrice.toFixed(2)}`, 'error')
    return
  }
  
  loading.value = true
  
  try {
    await createOrder(prompt.value, selectedModel.value.name, firstFrameImage.value, lastFrameImage.value)
    showNotification('订单提交成功！AI 正在为您生成...', 'success')
    prompt.value = ''
    // 清理图片状态
    removeImage('first')
    removeImage('last')
    await loadData()
  } catch (err) {
    showNotification(err.response?.data?.detail || '创建订单失败', 'error')
  } finally {
    loading.value = false
  }
}

const selectModel = (model) => {
  selectedModel.value = model
  showModelSelector.value = false
}

// 图片上传处理函数
const handleImageUpload = (event, type) => {
  const file = event.target.files[0]
  if (!file) return
  
  // 检查文件类型
  if (!file.type.startsWith('image/')) {
    showNotification('请选择图片文件', 'error')
    return
  }
  
  // 检查文件大小 (5MB)
  if (file.size > 5 * 1024 * 1024) {
    showNotification('图片大小不能超过5MB', 'error')
    return
  }
  
  // 保存文件
  if (type === 'first') {
    firstFrameImage.value = file
    // 创建预览URL
    if (firstFramePreview.value) {
      URL.revokeObjectURL(firstFramePreview.value)
    }
    firstFramePreview.value = URL.createObjectURL(file)
  } else {
    lastFrameImage.value = file
    if (lastFramePreview.value) {
      URL.revokeObjectURL(lastFramePreview.value)
    }
    lastFramePreview.value = URL.createObjectURL(file)
  }
}

const removeImage = (type) => {
  if (type === 'first') {
    firstFrameImage.value = null
    if (firstFramePreview.value) {
      URL.revokeObjectURL(firstFramePreview.value)
      firstFramePreview.value = null
    }
  } else {
    lastFrameImage.value = null
    if (lastFramePreview.value) {
      URL.revokeObjectURL(lastFramePreview.value)
      lastFramePreview.value = null
    }
  }
}

const statusMap = {
  pending: { text: '排队中', class: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30' },
  processing: { text: '处理中', class: 'bg-blue-500/20 text-blue-400 border-blue-500/30' },
  generating: { text: '生成中', class: 'bg-purple-500/20 text-purple-400 border-purple-500/30' },
  completed: { text: '已完成', class: 'bg-green-500/20 text-green-400 border-green-500/30' },
  failed: { text: '失败', class: 'bg-red-500/20 text-red-400 border-red-500/30' },
}

const copyInviteCode = () => {
  if (!user.value || !user.value.invite_code) return
  const inviteLink = `${window.location.origin}/register?invite=${user.value.invite_code}`
  navigator.clipboard.writeText(inviteLink).then(() => {
    showNotification('邀请链接已复制！快去分享吧', 'success')
  }).catch(() => {
    showNotification('复制失败，请手动复制', 'error')
  })
}

const handleLogout = () => {
  localStorage.removeItem('token')
  router.push('/login')
}
</script>

<template>
  <div class="min-h-screen relative overflow-hidden flex flex-col">
    <!-- Toast Notification -->
    <Transition name="toast">
      <div v-if="showToast" class="fixed top-6 left-1/2 transform -translate-x-1/2 z-50">
        <div :class="{
            'bg-red-500/80 text-white border-red-500/50 shadow-red-900/50': toastType === 'error',
            'bg-green-500/80 text-white border-green-500/50 shadow-green-900/50': toastType === 'success',
            'bg-blue-500/80 text-white border-blue-500/50 shadow-blue-900/50': toastType === 'info'
        }" class="flex items-center gap-3 px-6 py-3 rounded-xl border shadow-lg backdrop-blur-xl">
          <svg v-if="toastType === 'error'" xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
          </svg>
          <svg v-else-if="toastType === 'success'" xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
          </svg>
          <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd" />
          </svg>
          <span class="font-medium text-sm">{{ toastMessage }}</span>
        </div>
      </div>
    </Transition>
    
    <!-- Navbar -->
    <nav class="relative z-20 px-8 py-4 border-b border-white/10 bg-black/20 backdrop-blur-md">
      <div class="max-w-7xl mx-auto flex justify-between items-center">
        <div class="text-2xl font-extrabold cursor-pointer flex items-center gap-2" @click="router.push('/')">
          <span class="text-white drop-shadow-md">大帝</span><span class="text-cyan-400 drop-shadow-md">AI</span>
        </div>
        <div class="flex items-center gap-6">
          <router-link to="/tickets" class="text-sm text-gray-400 hover:text-white transition-colors">工单</router-link>
          <router-link to="/invite" class="text-sm text-gray-400 hover:text-white transition-colors">邀请</router-link>

          <div class="flex items-center gap-3 bg-black/40 p-1 pr-4 rounded-xl border border-white/10 backdrop-blur-sm shadow-inner">
             <button 
               @click="router.push('/recharge')"
               class="px-4 py-1.5 bg-gradient-to-r from-cyan-600 to-blue-600 text-white text-xs font-bold rounded-lg hover:brightness-110 transition-all shadow-lg shadow-cyan-900/40"
             >
               充值
             </button>
             <span class="text-sm text-gray-300">余额: <span class="font-bold text-white text-shadow-sm">¥{{ formattedBalance }}</span></span>
          </div>
          <button @click="handleLogout" class="text-sm text-gray-300 hover:text-white transition-colors hover:drop-shadow-sm">退出</button>
        </div>
      </div>
    </nav>
    
    <!-- Main Content -->
    <div class="flex-grow max-w-5xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-10 relative z-10">
      <div class="space-y-8">
        
        <!-- Generator -->
          <div class="relative">
            <!-- Glow effect behind card -->
            <div class="absolute -inset-1 bg-gradient-to-br from-cyan-500/20 to-blue-500/20 rounded-3xl blur-2xl opacity-40"></div>
            
            <div class="relative bg-white/5 backdrop-blur-3xl border border-white/10 border-t-white/20 rounded-3xl p-8 shadow-2xl">
              <div class="flex justify-between items-center mb-6">
                <div>
                  <h2 class="text-xl font-bold text-white flex items-center gap-2">
                    <span class="w-1 h-6 bg-cyan-500 rounded-full" :class="modelSeries === '3.1' ? 'bg-purple-500' : 'bg-cyan-500'"></span>
                    {{ getSeriesDisplayName(modelSeries) }}
                  </h2>
                  <p v-if="modelSeries !== 'all'" class="text-xs text-gray-400 mt-1 ml-5">
                    专用模型选择器，仅显示{{ modelSeries }}系列模型
                  </p>
                </div>
                <div class="flex items-center gap-3">
                  <!-- 系列切换器 -->
                  <div class="flex bg-white/5 border border-white/10 rounded-xl p-1">
                    <button 
                      @click="router.push({ query: { ...route.query, series: '2.3' } })"
                      :class="[
                        'px-3 py-1.5 text-xs font-medium rounded-lg transition-all',
                        modelSeries === '2.3' 
                          ? 'bg-cyan-500/80 text-white shadow-sm' 
                          : 'text-gray-400 hover:text-white hover:bg-white/5'
                      ]"
                    >
                      2.3系列
                    </button>
                    <button 
                      @click="router.push({ query: { ...route.query, series: '3.1' } })"
                      :class="[
                        'px-3 py-1.5 text-xs font-medium rounded-lg transition-all',
                        modelSeries === '3.1' 
                          ? 'bg-purple-500/80 text-white shadow-sm' 
                          : 'text-gray-400 hover:text-white hover:bg-white/5'
                      ]"
                    >
                      3.1系列
                    </button>
                    <button 
                      @click="router.push({ query: { ...route.query, series: undefined } })"
                      :class="[
                        'px-3 py-1.5 text-xs font-medium rounded-lg transition-all',
                        modelSeries === 'all' 
                          ? 'bg-gray-500/80 text-white shadow-sm' 
                          : 'text-gray-400 hover:text-white hover:bg-white/5'
                      ]"
                    >
                      全部
                    </button>
                  </div>
                  
                  <!-- 模型选择器 -->
                  <div class="relative model-selector">
                    <button 
                      @click="showModelSelector = !showModelSelector"
                      :class="[
                        'flex items-center gap-2 px-4 py-2 bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl text-sm text-white transition-all hover:border-white/20 hover:shadow-lg',
                        modelSeries === '3.1' ? 'hover:shadow-purple-500/10' : 'hover:shadow-cyan-500/10'
                      ]"
                    >
                      <div class="flex items-center gap-2">
                        <div 
                          class="w-2 h-2 rounded-full" 
                          :class="modelSeries === '3.1' 
                            ? 'bg-purple-400 shadow-[0_0_8px_rgba(147,51,234,0.8)]' 
                            : 'bg-cyan-400 shadow-[0_0_8px_rgba(34,211,238,0.8)]'"
                        ></div>
                        <span class="font-medium tracking-wide">{{ selectedModel?.display_name || '选择模型' }}</span>
                        <span v-if="selectedModel?.badge" class="px-1.5 py-0.5 bg-gradient-to-r from-pink-500 to-rose-500 text-white text-[10px] font-bold rounded uppercase tracking-wider shadow-sm">
                          {{ selectedModel.badge }}
                        </span>
                      </div>
                      <svg class="w-4 h-4 text-gray-400 transition-transform duration-300" :class="{ 'rotate-180': showModelSelector }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
                      </svg>
                    </button>

                    <!-- 模型选择下拉菜单 -->
                    <Transition name="dropdown">
                      <div v-if="showModelSelector" class="absolute top-full right-0 mt-3 w-80 bg-[#0f1115]/95 backdrop-blur-2xl border border-white/10 rounded-2xl shadow-2xl z-50 overflow-hidden ring-1 ring-white/5">
                        <div class="p-4 border-b border-white/5 bg-white/5">
                          <h3 class="text-sm font-bold text-white mb-1">选择生成模型</h3>
                          <p class="text-xs text-gray-400">不同模型有不同的效果和消耗</p>
                        </div>
                        <div class="max-h-[320px] overflow-y-auto custom-scrollbar">
                          <div 
                            v-for="model in availableModels" 
                            :key="model.id"
                            @click="selectModel(model)"
                            class="p-3 hover:bg-white/5 cursor-pointer border-b border-white/5 last:border-b-0 transition-all group"
                            :class="{ 'bg-cyan-500/10': selectedModel?.id === model.id }"
                          >
                            <div class="flex items-start justify-between">
                              <div class="flex-1">
                                <div class="flex items-center gap-2 mb-1">
                                  <span class="font-bold text-white text-sm group-hover:text-cyan-400 transition-colors">{{ model.display_name }}</span>
                                  <span v-if="model.badge" class="px-1.5 py-0.5 bg-gradient-to-r from-pink-500 to-rose-500 text-white text-[10px] font-bold rounded shadow-sm">
                                    {{ model.badge }}
                                  </span>
                                  <span v-if="model.is_default" class="px-1.5 py-0.5 bg-green-500/20 text-green-400 text-[10px] font-bold rounded border border-green-500/30">
                                    推荐
                                  </span>
                                </div>
                                <p class="text-xs text-gray-400 mb-2 leading-relaxed">{{ model.description }}</p>
                                <div class="flex flex-wrap gap-1">
                                  <span 
                                    v-for="feature in model.features" 
                                    :key="feature"
                                    class="px-2 py-0.5 bg-white/5 text-gray-300 text-[10px] rounded border border-white/5"
                                  >
                                    {{ feature }}
                                  </span>
                                </div>
                              </div>
                              <div v-if="selectedModel?.id === model.id" class="ml-3 text-cyan-400">
                                <svg class="w-5 h-5 drop-shadow-[0_0_8px_rgba(34,211,238,0.5)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                                </svg>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </Transition>
                  </div>
                </div>
              </div>
              
              <div class="relative group">
                <div class="absolute -inset-0.5 bg-gradient-to-r from-cyan-500/20 to-purple-500/20 rounded-2xl blur opacity-0 group-hover:opacity-100 transition duration-500"></div>
                <textarea 
                  v-model="prompt"
                  placeholder="请输入详细的画面描述... (例如: 赛博朋克风格的雨夜街道，霓虹灯闪烁)"
                  class="relative w-full h-40 p-6 rounded-2xl bg-black/20 border border-white/10 text-white placeholder-gray-500 outline-none focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/20 transition-all resize-none text-lg shadow-inner backdrop-blur-sm"
                ></textarea>
                <div class="absolute bottom-4 right-4 text-xs text-gray-500 flex items-center gap-1 bg-black/20 px-2 py-1 rounded-lg border border-white/5 backdrop-blur-md pointer-events-none">
                  <svg class="w-3 h-3 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>
                  支持中文 · 自动优化
                </div>
              </div>
              
              <!-- 首尾帧上传区域 -->
              <div class="mt-6 grid grid-cols-2 gap-6">
                <!-- 首帧上传 -->
                <div class="relative">
                  <input 
                    type="file" 
                    accept="image/*" 
                    @change="(e) => handleImageUpload(e, 'first')"
                    class="hidden"
                    :id="'first-frame-input'"
                  />
                  <label 
                    :for="'first-frame-input'"
                    class="block cursor-pointer group"
                  >
                    <div 
                      v-if="!firstFramePreview"
                      class="h-28 border border-dashed border-white/20 rounded-2xl flex flex-col items-center justify-center gap-3 transition-all bg-white/[0.02] hover:bg-white/[0.05] hover:border-cyan-500/30 hover:shadow-[0_0_20px_rgba(6,182,212,0.1)]"
                    >
                      <div class="p-3 bg-white/5 rounded-full group-hover:scale-110 transition-transform duration-300">
                        <svg class="w-6 h-6 text-gray-400 group-hover:text-cyan-400 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                        </svg>
                      </div>
                      <span class="text-xs text-gray-400 font-medium group-hover:text-gray-300">上传首帧（可选）</span>
                    </div>
                    <div v-else class="relative h-28 rounded-2xl overflow-hidden group shadow-lg border border-white/10">
                      <img :src="firstFramePreview" class="w-full h-full object-cover transition-transform duration-700 group-hover:scale-105" />
                      <div class="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center backdrop-blur-sm">
                        <span class="text-white text-xs font-medium border border-white/20 px-3 py-1.5 rounded-full bg-white/10">点击更换</span>
                      </div>
                    </div>
                  </label>
                  <button 
                    v-if="firstFramePreview"
                    @click.stop="removeImage('first')"
                    class="absolute -top-2 -right-2 w-7 h-7 bg-red-500 text-white rounded-full flex items-center justify-center text-sm hover:bg-red-600 transition-all shadow-lg z-10 hover:scale-110"
                  >
                    ×
                  </button>
                </div>
                
                <!-- 尾帧上传 -->
                <div class="relative">
                  <input 
                    type="file" 
                    accept="image/*" 
                    @change="(e) => handleImageUpload(e, 'last')"
                    class="hidden"
                    :id="'last-frame-input'"
                    :disabled="!selectedModel?.supports_last_frame"
                  />
                  <label 
                    :for="'last-frame-input'"
                    class="block h-full"
                    :class="selectedModel?.supports_last_frame ? 'cursor-pointer group' : 'cursor-not-allowed opacity-60'"
                  >
                    <div 
                      v-if="!lastFramePreview"
                      class="h-28 border border-dashed rounded-2xl flex flex-col items-center justify-center gap-3 transition-all h-full"
                      :class="selectedModel?.supports_last_frame 
                        ? 'border-white/20 bg-white/[0.02] hover:bg-white/[0.05] hover:border-purple-500/30 hover:shadow-[0_0_20px_rgba(168,85,247,0.1)]' 
                        : 'border-white/5 bg-black/20'"
                    >
                      <div class="p-3 bg-white/5 rounded-full transition-transform duration-300" :class="{ 'group-hover:scale-110': selectedModel?.supports_last_frame }">
                        <svg class="w-6 h-6" :class="selectedModel?.supports_last_frame ? 'text-gray-400 group-hover:text-purple-400' : 'text-gray-600'" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                        </svg>
                      </div>
                      <span class="text-xs font-medium" :class="selectedModel?.supports_last_frame ? 'text-gray-400 group-hover:text-gray-300' : 'text-gray-600'">
                        {{ selectedModel?.supports_last_frame ? '上传尾帧（可选）' : '当前模型不支持尾帧' }}
                      </span>
                    </div>
                    <div v-else class="relative h-28 rounded-2xl overflow-hidden group shadow-lg border border-white/10">
                      <img :src="lastFramePreview" class="w-full h-full object-cover transition-transform duration-700 group-hover:scale-105" />
                      <div class="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center backdrop-blur-sm">
                        <span class="text-white text-xs font-medium border border-white/20 px-3 py-1.5 rounded-full bg-white/10">点击更换</span>
                      </div>
                    </div>
                  </label>
                  <button 
                    v-if="lastFramePreview"
                    @click.stop="removeImage('last')"
                    class="absolute -top-2 -right-2 w-7 h-7 bg-red-500 text-white rounded-full flex items-center justify-center text-sm hover:bg-red-600 transition-all shadow-lg z-10 hover:scale-110"
                  >
                    ×
                  </button>
                </div>
              </div>
              
              <div class="flex justify-between items-center mt-8 pt-6 border-t border-white/10">
                <div class="flex items-center gap-2 text-sm text-gray-400">
                  <span class="relative flex h-2.5 w-2.5">
                    <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                    <span class="relative inline-flex rounded-full h-2.5 w-2.5 bg-green-500"></span>
                  </span>
                  <span class="font-medium">系统状态正常 · 预计耗时 2-5 分钟</span>
                </div>
                
                <div class="flex items-center gap-6">
                  <div class="text-right">
                     <span class="text-xs text-gray-500 block">本次消耗</span>
                     <span class="text-lg font-bold text-white leading-none">¥{{ config.video_price }}</span>
                  </div>
                  <button 
                    @click="handleCreateOrder"
                    :disabled="loading"
                    class="relative py-3 px-8 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white rounded-xl font-bold transition-all duration-300 transform hover:scale-105 hover:shadow-[0_0_20px_rgba(6,182,212,0.4)] disabled:opacity-50 disabled:scale-100 disabled:hover:shadow-none flex items-center gap-2 overflow-hidden group"
                  >
                    <div class="absolute inset-0 bg-white/20 translate-x-[-100%] group-hover:translate-x-[100%] transition-transform duration-1000"></div>
                    <span v-if="loading" class="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full"></span>
                    {{ loading ? '正在提交...' : '立即生成' }}
                  </button>
                </div>
              </div>
            </div>
          </div>
          

          
          <!-- History -->
          <div>
            <h3 class="text-lg font-bold text-white mb-4 px-2 flex items-center gap-2">
              <svg class="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
              历史记录
            </h3>
            <div class="space-y-4">
              <div v-if="orders.length === 0" class="text-center py-16 bg-black/20 backdrop-blur-md rounded-3xl border border-white/5 text-gray-500">
                <div class="w-16 h-16 bg-white/5 rounded-full flex items-center justify-center mx-auto mb-4">
                   <svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8 opacity-40" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                     <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                   </svg>
                </div>
                <p>暂无生成记录，快去创作吧~</p>
              </div>

              <div 
                v-for="order in orders" 
                :key="order.id"
                class="group bg-white/5 hover:bg-white/10 border border-white/5 border-t-white/10 hover:border-white/20 p-6 rounded-2xl transition-all duration-300 backdrop-blur-3xl shadow-lg hover:shadow-xl hover:-translate-y-0.5"
              >
                <div class="flex justify-between items-start">
                  <div class="flex-1 mr-6">
                    <p class="text-gray-200 font-medium line-clamp-2 leading-relaxed text-sm">{{ order.prompt }}</p>
                    <div class="flex items-center gap-4 mt-3">
                      <p class="text-xs text-gray-500 font-mono">{{ new Date(order.created_at).toLocaleString() }}</p>
                      <div v-if="order.model_name" class="flex items-center gap-1.5 px-2 py-0.5 bg-white/5 rounded border border-white/5">
                        <div class="w-1.5 h-1.5 bg-purple-400 rounded-full shadow-[0_0_5px_rgba(192,132,252,0.8)]"></div>
                        <span class="text-xs text-gray-300">{{ order.model_name }}</span>
                      </div>
                      <a v-if="order.status === 'completed' && order.video_url" 
                         :href="order.video_url" 
                         target="_blank"
                         class="px-3 py-1 bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 text-xs rounded-full border border-cyan-500/20 hover:border-cyan-500/40 transition-all flex items-center gap-1.5 group/btn">
                         <svg class="w-3 h-3 transition-transform group-hover/btn:scale-110" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                           <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"/>
                           <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                         </svg>
                         <span class="font-bold">观看视频</span>
                      </a>
                    </div>
                  </div>
                  <div>
                    <span :class="`px-3 py-1.5 rounded-lg text-xs font-bold border flex items-center gap-1.5 ${statusMap[order.status]?.class || 'bg-gray-500/10 text-gray-400 border-gray-500/20'}`">
                      <span v-if="order.status === 'processing' || order.status === 'generating'" class="w-2 h-2 rounded-full border-2 border-current border-t-transparent animate-spin"></span>
                      {{ statusMap[order.status]?.text || order.status }}
                    </span>
                  </div>
                </div>
                <!-- 进度条 -->
                <div v-if="order.status === 'processing' || order.status === 'generating'" class="mt-4 bg-white/5 rounded-lg p-3 border border-white/5">
                  <div class="flex items-center justify-between mb-2">
                    <span class="text-xs text-gray-400 flex items-center gap-1">
                       <svg class="w-3 h-3 text-cyan-400 animate-spin" fill="none" viewBox="0 0 24 24">
                           <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                           <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                       </svg>
                       {{ order.progress === -1 ? '排队中，等待生成...' : 'AI 正在努力生成中...' }}
                    </span>
                    <span class="text-xs font-mono font-bold text-cyan-400">
                      {{ order.progress === -1 ? '准备中...' : (order.progress || 0) + '%' }}
                    </span>
                  </div>
                  <div class="h-1.5 bg-gray-700/50 rounded-full overflow-hidden">
                    <div 
                      class="h-full bg-gradient-to-r from-cyan-500 via-purple-500 to-pink-500 rounded-full transition-all duration-500 relative"
                      :style="{ width: order.progress === -1 ? '5%' : (order.progress || 0) + '%' }"
                    >
                       <div class="absolute inset-0 bg-white/20 animate-pulse"></div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          

      </div>
    </div>
  </div>
</template>

<style scoped>
.toast-enter-active,
.toast-leave-active {
  transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translate(-50%, -20px);
}

.dropdown-enter-active,
.dropdown-leave-active {
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  transform-origin: top right;
}

.dropdown-enter-from,
.dropdown-leave-to {
  opacity: 0;
  transform: scale(0.95) translateY(-10px);
}

.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
