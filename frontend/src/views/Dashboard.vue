<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getCurrentUser, createOrder, getOrders, getPublicConfig, getAvailableModels } from '../api'

const route = useRoute()
const router = useRouter()

// State
const user = ref(null)
const orders = ref([])
const prompt = ref(route.query.prompt || '')
const loading = ref(false)

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
  video_price: 0.99,
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
      availableModels.value = modelsData.models
      // 设置默认选中模型
      selectedModel.value = modelsData.models.find(m => m.is_default) || modelsData.models[0]
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
  
  if (!user.value || user.value.balance < config.value.video_price) {
    showNotification(`余额不足，需 ${config.value.video_price} 元`, 'error')
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

const handleLogout = () => {
  localStorage.removeItem('token')
  router.push('/login')
}
</script>

<template>
  <div class="min-h-screen bg-[#0a0a0f] relative overflow-hidden flex flex-col">
    
    <!-- 动态网格背景 -->
    <div class="absolute inset-0 bg-[linear-gradient(rgba(6,182,212,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(6,182,212,0.03)_1px,transparent_1px)] bg-[size:50px_50px]"></div>
    
    <!-- 鼠标跟随小球 -->
    <div 
      class="pointer-events-none fixed w-[600px] h-[600px] rounded-full bg-gradient-to-r from-cyan-500/20 to-purple-500/20 blur-[120px] transition-all duration-700 ease-out"
      :style="{ left: mouseX - 300 + 'px', top: mouseY - 300 + 'px' }"
    ></div>

    <!-- Toast Notification -->
    <Transition name="toast">
      <div v-if="showToast" class="fixed top-6 left-1/2 transform -translate-x-1/2 z-50">
        <div :class="{
            'bg-red-500/20 text-red-400 border-red-500/30': toastType === 'error',
            'bg-green-500/20 text-green-400 border-green-500/30': toastType === 'success',
            'bg-cyan-500/20 text-cyan-400 border-cyan-500/30': toastType === 'info'
        }" class="flex items-center gap-3 px-6 py-3 rounded-xl border backdrop-blur-xl">
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
    <nav class="relative z-20 px-8 py-4 border-b border-white/5">
      <div class="max-w-7xl mx-auto flex justify-between items-center">
        <div class="text-2xl font-extrabold cursor-pointer flex items-center gap-2" @click="router.push('/')">
          <span class="text-white">大帝</span><span class="text-cyan-400">AI</span>
        </div>
        <div class="flex items-center gap-6">
          <div class="flex items-center gap-3 bg-white/5 p-1 pr-4 rounded-xl border border-white/10">
             <button 
               @click="router.push('/recharge')"
               class="px-4 py-1.5 bg-gradient-to-r from-cyan-500 to-blue-500 text-white text-xs font-bold rounded-lg hover:opacity-90 transition-opacity shadow-lg shadow-cyan-500/20"
             >
               充值
             </button>
             <span class="text-sm text-gray-400">余额: <span class="font-bold text-white">¥{{ formattedBalance }}</span></span>
          </div>
          <button @click="handleLogout" class="text-sm text-gray-500 hover:text-white transition-colors">退出</button>
        </div>
      </div>
    </nav>
    
    <!-- Main Content -->
    <div class="flex-grow max-w-5xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-10 relative z-10">
      <div class="space-y-8">
        
        <!-- Generator -->
          <div class="relative">
            <div class="absolute -inset-0.5 bg-gradient-to-r from-cyan-500 via-purple-500 to-pink-500 rounded-2xl opacity-20 blur"></div>
            <div class="relative bg-[#12121a] border border-white/10 rounded-2xl p-8">
              <div class="flex justify-between items-center mb-6">
                <h2 class="text-xl font-bold text-white">开始创作</h2>
                <div class="flex items-center gap-3">
                  <!-- 模型选择器 -->
                  <div class="relative model-selector">
                    <button 
                      @click="showModelSelector = !showModelSelector"
                      class="flex items-center gap-2 px-4 py-2 bg-white/10 hover:bg-white/15 border border-white/20 rounded-lg text-sm text-white transition-all"
                    >
                      <div class="flex items-center gap-2">
                        <div class="w-2 h-2 bg-cyan-400 rounded-full"></div>
                        <span>{{ selectedModel?.display_name || '选择模型' }}</span>
                        <span v-if="selectedModel?.badge" class="px-2 py-0.5 bg-cyan-500/20 text-cyan-400 text-xs rounded border border-cyan-500/30">
                          {{ selectedModel.badge }}
                        </span>
                      </div>
                      <svg class="w-4 h-4 transition-transform" :class="{ 'rotate-180': showModelSelector }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
                      </svg>
                    </button>

                    <!-- 模型选择下拉菜单 -->
                    <Transition name="dropdown">
                      <div v-if="showModelSelector" class="absolute top-full right-0 mt-2 w-80 bg-[#12121a] border border-white/20 rounded-xl shadow-2xl z-50 overflow-hidden">
                        <div class="p-3 border-b border-white/10">
                          <h3 class="text-sm font-bold text-white mb-1">选择生成模型</h3>
                          <p class="text-xs text-gray-400">不同模型有不同的效果和价格</p>
                        </div>
                        <div class="max-h-60 overflow-y-auto">
                          <div 
                            v-for="model in availableModels" 
                            :key="model.id"
                            @click="selectModel(model)"
                            class="p-3 hover:bg-white/5 cursor-pointer border-b border-white/5 last:border-b-0 transition-all"
                            :class="{ 'bg-cyan-500/10': selectedModel?.id === model.id }"
                          >
                            <div class="flex items-start justify-between">
                              <div class="flex-1">
                                <div class="flex items-center gap-2 mb-1">
                                  <span class="font-medium text-white text-sm">{{ model.display_name }}</span>
                                  <span v-if="model.badge" class="px-2 py-0.5 bg-cyan-500/20 text-cyan-400 text-xs rounded border border-cyan-500/30">
                                    {{ model.badge }}
                                  </span>
                                  <span v-if="model.is_default" class="px-2 py-0.5 bg-green-500/20 text-green-400 text-xs rounded border border-green-500/30">
                                    推荐
                                  </span>
                                </div>
                                <p class="text-xs text-gray-400 mb-2">{{ model.description }}</p>
                                <div class="flex flex-wrap gap-1">
                                  <span 
                                    v-for="feature in model.features" 
                                    :key="feature"
                                    class="px-2 py-0.5 bg-white/10 text-gray-300 text-xs rounded"
                                  >
                                    {{ feature }}
                                  </span>
                                </div>
                              </div>
                              <div v-if="selectedModel?.id === model.id" class="ml-3 text-cyan-400">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
              
              <div class="relative">
                <textarea 
                  v-model="prompt"
                  placeholder="请输入详细的画面描述... (例如: 赛博朋克风格的雨夜街道，霓虹灯闪烁)"
                  class="w-full h-40 p-5 rounded-xl bg-white/5 border border-white/10 text-white placeholder-gray-500 outline-none focus:border-cyan-500/50 focus:ring-2 focus:ring-cyan-500/20 transition-all resize-none text-lg"
                ></textarea>
                <div class="absolute bottom-4 right-4 text-xs text-gray-600">
                  支持中文 · 自动优化提示词
                </div>
              </div>
              
              <!-- 首尾帧上传区域 -->
              <div class="mt-4 grid grid-cols-2 gap-4">
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
                    class="block cursor-pointer"
                  >
                    <div 
                      v-if="!firstFramePreview"
                      class="h-24 border-2 border-dashed border-white/20 hover:border-cyan-500/50 rounded-xl flex flex-col items-center justify-center gap-2 transition-all bg-white/5 hover:bg-white/10"
                    >
                      <svg class="w-6 h-6 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                      </svg>
                      <span class="text-xs text-gray-400">上传首帧（可选）</span>
                    </div>
                    <div v-else class="relative h-24 rounded-xl overflow-hidden group">
                      <img :src="firstFramePreview" class="w-full h-full object-cover" />
                      <div class="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                        <span class="text-white text-xs">点击更换</span>
                      </div>
                    </div>
                  </label>
                  <button 
                    v-if="firstFramePreview"
                    @click.stop="removeImage('first')"
                    class="absolute -top-2 -right-2 w-6 h-6 bg-red-500 text-white rounded-full flex items-center justify-center text-xs hover:bg-red-600 transition-colors z-10"
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
                  />
                  <label 
                    :for="'last-frame-input'"
                    class="block cursor-pointer"
                  >
                    <div 
                      v-if="!lastFramePreview"
                      class="h-24 border-2 border-dashed border-white/20 hover:border-purple-500/50 rounded-xl flex flex-col items-center justify-center gap-2 transition-all bg-white/5 hover:bg-white/10"
                    >
                      <svg class="w-6 h-6 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                      </svg>
                      <span class="text-xs text-gray-400">上传尾帧（可选）</span>
                    </div>
                    <div v-else class="relative h-24 rounded-xl overflow-hidden group">
                      <img :src="lastFramePreview" class="w-full h-full object-cover" />
                      <div class="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                        <span class="text-white text-xs">点击更换</span>
                      </div>
                    </div>
                  </label>
                  <button 
                    v-if="lastFramePreview"
                    @click.stop="removeImage('last')"
                    class="absolute -top-2 -right-2 w-6 h-6 bg-red-500 text-white rounded-full flex items-center justify-center text-xs hover:bg-red-600 transition-colors z-10"
                  >
                    ×
                  </button>
                </div>
              </div>
              
              <div class="flex justify-between items-center mt-6">
                <div class="flex items-center gap-2 text-sm text-gray-500">
                  <span class="relative flex h-2 w-2">
                    <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                    <span class="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
                  </span>
                  <span>预计耗时 2-5 分钟</span>
                </div>
                
                <div class="flex items-center gap-4">
                  <span class="text-sm font-medium text-gray-400">消耗: <span class="text-white">¥{{ config.video_price }}</span></span>
                  <button 
                    @click="handleCreateOrder"
                    :disabled="loading"
                    class="py-3 px-8 bg-white text-gray-900 rounded-xl font-semibold transition-all duration-300 hover:bg-gray-100 disabled:opacity-50 flex items-center gap-2 shadow-lg"
                  >
                    <span v-if="loading" class="animate-spin w-4 h-4 border-2 border-gray-900 border-t-transparent rounded-full"></span>
                    {{ loading ? '生成中...' : '立即生成' }}
                  </button>
                </div>
              </div>
            </div>
          </div>
          
          <!-- History -->
          <div>
            <h3 class="text-lg font-bold text-white mb-4 px-2">历史记录</h3>
            <div class="space-y-4">
              <div v-if="orders.length === 0" class="text-center py-12 bg-white/5 rounded-2xl border border-white/10 text-gray-500">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-12 w-12 mx-auto mb-3 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                </svg>
                <p>暂无生成记录</p>
              </div>

              <div 
                v-for="order in orders" 
                :key="order.id"
                class="group bg-white/5 hover:bg-white/10 border border-white/10 p-5 rounded-xl transition-all"
              >
                <div class="flex justify-between items-start">
                  <div class="flex-1 mr-4">
                    <p class="text-white font-medium line-clamp-2 leading-relaxed">{{ order.prompt }}</p>
                    <div class="flex items-center gap-3 mt-2">
                      <p class="text-xs text-gray-500">{{ new Date(order.created_at).toLocaleString() }}</p>
                      <div v-if="order.model_name" class="flex items-center gap-1">
                        <div class="w-1 h-1 bg-gray-600 rounded-full"></div>
                        <span class="text-xs text-purple-400">{{ order.model_name }}</span>
                      </div>
                      <a v-if="order.status === 'completed' && order.video_url" 
                         :href="order.video_url" 
                         target="_blank"
                         class="text-xs text-cyan-400 hover:text-cyan-300 font-medium flex items-center gap-1 transition-colors">
                         <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                           <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"/>
                           <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                         </svg>
                         查看视频
                      </a>
                    </div>
                  </div>
                  <div>
                    <span :class="`px-3 py-1 rounded-lg text-xs font-bold border ${statusMap[order.status]?.class || 'bg-gray-500/20 text-gray-400 border-gray-500/30'}`">
                      {{ statusMap[order.status]?.text || order.status }}
                    </span>
                  </div>
                </div>
                <!-- 进度条：仅在 processing 或 generating 状态显示 -->
                <div v-if="order.status === 'processing' || order.status === 'generating'" class="mt-4">
                  <div class="flex items-center justify-between mb-1.5">
                    <span class="text-xs text-gray-400">生成进度</span>
                    <span class="text-xs font-mono text-cyan-400">{{ order.progress || 0 }}%</span>
                  </div>
                  <div class="h-2 bg-gray-700 rounded-full overflow-hidden">
                    <div 
                      class="h-full bg-gradient-to-r from-cyan-500 to-purple-500 rounded-full transition-all duration-500"
                      :style="{ width: (order.progress || 0) + '%' }"
                    ></div>
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
