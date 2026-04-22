<script setup>
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getCurrentUser, getOrders, getPublicConfig } from '../api'
import { jimengCreateOrder, getJimengOrders, getJimengModels } from '../api/jimeng'

const route = useRoute()
const router = useRouter()
const siteName = ref(localStorage.getItem('site_name') || '大帝AI')
const siteAnnouncement = ref('')

const user = ref(null)
const orders = ref([])
const prompt = ref('')
const loading = ref(false)

const availableModels = ref([])
const selectedModel = ref(null)
const showModelSelector = ref(false)
const jimengEnabled = ref(true)

const videoMode = ref('text')
const firstFrameImage = ref(null)
const lastFrameImage = ref(null)
const firstFramePreview = ref(null)
const lastFramePreview = ref(null)

// 时长、比例选项
const durationOptions = [4, 5, 6, 7, 8, 9, 10, 11, 12]
const selectedDuration = ref(5)
const ratioOptions = ['21:9', '16:9', '4:3', '1:1', '3:4', '9:16']
const selectedRatio = ref('16:9')

const maxPromptLength = 500
const promptLength = computed(() => prompt.value.length)

const handleKeydown = (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    e.preventDefault()
    handleCreateOrder()
  }
}

const config = ref({
  bonus_rate: 0.2,
  bonus_min_amount: 10,
})

let ordersInterval = null
let pollCount = 0

const startOrdersPolling = () => {
  if (ordersInterval) return
  const poll = async () => {
    const hasProcessing = orders.value.some(o => 
      o.status === 'pending' || o.status === 'processing' || o.status === 'generating'
    )
    if (hasProcessing) {
      pollCount = 0
      try {
        orders.value = await getJimengOrders()
      } catch (err) { /* ignore */ }
    } else {
      pollCount++
    }
    const interval = hasProcessing ? 2000 : Math.min(3000 + pollCount * 2000, 10000)
    ordersInterval = setTimeout(poll, interval)
  }
  ordersInterval = setTimeout(poll, 2000)
}

const handleClickOutside = (event) => {
  if (showModelSelector.value && !event.target.closest('.model-selector')) {
    showModelSelector.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
  loadData()
  startOrdersPolling()
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
  if (ordersInterval) clearTimeout(ordersInterval)
})

const showToast = ref(false)
const toastMessage = ref('')
const toastType = ref('info')

const formattedBalance = computed(() => {
  return user.value ? user.value.balance.toFixed(2) : '0.00'
})

const isLowBalance = computed(() => {
  return user.value && user.value.balance < 5
})

const showNotification = (message, type = 'info') => {
  toastMessage.value = message
  toastType.value = type
  showToast.value = true
  setTimeout(() => { showToast.value = false }, 3000)
}

const loadData = async () => {
  try {
    const [userData, ordersData, configData, modelsData] = await Promise.all([
      getCurrentUser(),
      getJimengOrders().catch(() => []),
      getPublicConfig().catch(() => null),
      getJimengModels().catch(() => null),
    ])
    user.value = userData
    orders.value = ordersData || []
    if (configData) {
      config.value = configData
      if (configData.site_announcement) siteAnnouncement.value = configData.site_announcement
    }
    
    // 加载即梦模型列表
    if (modelsData && modelsData.models && modelsData.models.length > 0) {
      availableModels.value = modelsData.models
      jimengEnabled.value = true
      // 选择默认模型或第一个模型
      const defaultModel = modelsData.models.find(m => m.is_default) || modelsData.models[0]
      selectedModel.value = defaultModel
    } else {
      jimengEnabled.value = false
      // 如果没有模型，跳转到首页
      showNotification('即梦服务暂未开放', 'error')
      setTimeout(() => router.push('/'), 2000)
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

  if (videoMode.value === 'image' && !firstFrameImage.value) {
    showNotification('图生视频模式请上传首帧图片', 'error')
    return
  }

  // 计算实际价格（按秒计费优先）
  const pps = selectedModel.value?.price_per_second || 0
  const modelPrice = pps > 0 ? Math.round(pps * selectedDuration.value * 100) / 100 : (selectedModel.value?.price || 0.99)
  if (!user.value || user.value.balance < modelPrice) {
    showBalanceInsufficient(modelPrice)
    return
  }

  loading.value = true

  try {
    await jimengCreateOrder({
      prompt: prompt.value,
      model: selectedModel.value.name,
      duration: selectedDuration.value,
      ratio: selectedRatio.value,
      first_frame: videoMode.value === 'image' ? firstFrameImage.value : null,
      last_frame: videoMode.value === 'image' ? lastFrameImage.value : null,
    })
    showNotification('订单提交成功！AI 正在为您生成...', 'success')
    prompt.value = ''
    removeImage('first')
    removeImage('last')
    await loadData()
  } catch (err) {
    showNotification(err.friendlyMessage || err.response?.data?.detail || '创建订单失败', 'error')
  } finally {
    loading.value = false
  }
}

const selectModel = (model) => {
  selectedModel.value = model
  showModelSelector.value = false
}

const processFile = (file, type) => {
  if (!file) return
  if (!file.type.startsWith('image/')) {
    showNotification('请选择图片文件', 'error')
    return
  }
  if (file.size > 5 * 1024 * 1024) {
    showNotification('图片大小不能超过5MB', 'error')
    return
  }
  if (type === 'first') {
    firstFrameImage.value = file
    if (firstFramePreview.value) URL.revokeObjectURL(firstFramePreview.value)
    firstFramePreview.value = URL.createObjectURL(file)
  } else {
    lastFrameImage.value = file
    if (lastFramePreview.value) URL.revokeObjectURL(lastFramePreview.value)
    lastFramePreview.value = URL.createObjectURL(file)
  }
}

const handleImageUpload = (event, type) => {
  processFile(event.target.files[0], type)
}

const handleDrop = (event, type) => {
  event.preventDefault()
  const file = event.dataTransfer?.files?.[0]
  processFile(file, type)
}

const handlePaste = (event, type) => {
  const items = event.clipboardData?.items
  if (!items) return
  for (const item of items) {
    if (item.type.startsWith('image/')) {
      event.preventDefault()
      processFile(item.getAsFile(), type)
      return
    }
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

const showInsufficientModal = ref(false)
const insufficientPrice = ref(0)

const showBalanceInsufficient = (price) => {
  insufficientPrice.value = price
  showInsufficientModal.value = true
}

const retryOrder = async (order) => {
  prompt.value = order.prompt
  showNotification('已填入原始描述，请点击生成', 'info')
}

const formatUTCTime = (utcTimeStr) => {
  if (!utcTimeStr) return ''
  const date = new Date(utcTimeStr + 'Z')
  return date.toLocaleString()
}

const handleLogout = () => {
  localStorage.removeItem('token')
  router.push('/login')
}
</script>

<template>
  <div class="min-h-screen relative overflow-hidden flex flex-col">
    <Transition name="toast">
      <div v-if="showToast" class="fixed top-6 left-1/2 transform -translate-x-1/2 z-50">
        <div :class="{
            'bg-red-500/80 text-white border-red-500/50 shadow-red-900/50': toastType === 'error',
            'bg-green-500/80 text-white border-green-500/50 shadow-green-900/50': toastType === 'success',
            'bg-blue-500/80 text-white border-blue-500/50 shadow-blue-900/50': toastType === 'info'
        }" class="flex items-center gap-3 px-6 py-3 rounded-xl border shadow-lg backdrop-blur-xl">
          <span class="font-medium text-sm">{{ toastMessage }}</span>
        </div>
      </div>
    </Transition>
    
    <nav class="relative z-20 px-8 py-4 border-b border-white/10 bg-black/20 backdrop-blur-md">
      <div class="max-w-7xl mx-auto flex justify-between items-center">
        <div class="text-2xl font-extrabold cursor-pointer flex items-center gap-2" @click="router.push('/')">
          <span class="text-white drop-shadow-md">{{ siteName }}</span>
          <span class="text-xs px-2 py-0.5 bg-violet-500/20 text-violet-400 rounded border border-violet-500/30">即梦</span>
        </div>
        <div class="flex items-center gap-6">
          <router-link to="/nanobanana" class="text-sm text-gray-400 hover:text-white transition-colors">nanobanana pro</router-link>
          <router-link to="/tickets" class="flex items-center gap-1.5 px-3 py-1.5 text-sm text-amber-400/90 hover:text-amber-300 bg-amber-500/10 hover:bg-amber-500/15 border border-amber-500/20 hover:border-amber-500/30 rounded-lg transition-all">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"/>
            </svg>
            工单反馈
          </router-link>
          <router-link to="/invite" class="text-sm text-gray-400 hover:text-white transition-colors">邀请</router-link>

          <router-link to="/profile" class="flex items-center gap-1.5 px-3 py-1.5 text-sm text-cyan-400/90 hover:text-cyan-300 bg-cyan-500/10 hover:bg-cyan-500/15 border border-cyan-500/20 hover:border-cyan-500/30 rounded-lg transition-all">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/>
            </svg>
            我的
          </router-link>
          <button 
            @click="router.push('/recharge')"
            :class="isLowBalance ? 'from-red-500 to-orange-500 shadow-red-900/40' : 'from-violet-600 to-fuchsia-600 shadow-violet-900/40'"
            class="px-4 py-1.5 bg-gradient-to-r text-white text-xs font-bold rounded-lg hover:brightness-110 transition-all shadow-lg"
          >
            {{ isLowBalance ? '⚡ 充值' : '充值' }}
          </button>
          <button @click="handleLogout" class="text-sm text-gray-300 hover:text-white transition-colors hover:drop-shadow-sm">退出</button>
        </div>
      </div>
    </nav>
    
    <div v-if="siteAnnouncement" class="relative z-20 max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 mt-4">
      <div class="flex items-center gap-3 px-4 py-2.5 bg-amber-500/10 border border-amber-500/20 rounded-xl text-sm overflow-hidden">
        <span class="text-amber-400 text-base shrink-0">📢</span>
        <div class="overflow-hidden flex-1">
          <div class="animate-marquee whitespace-nowrap text-amber-200/90">{{ siteAnnouncement }}</div>
        </div>
      </div>
    </div>
    
    <div class="flex-grow max-w-5xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-10 relative z-10">
      <div class="space-y-8">
        
        <div class="relative">
          <div class="absolute -inset-1 rounded-3xl blur-2xl opacity-40 bg-gradient-to-br from-violet-500/20 to-fuchsia-500/20"></div>

          <div class="relative bg-white/5 backdrop-blur-3xl border border-white/10 border-t-white/20 rounded-3xl p-8 shadow-2xl">
            <div class="flex justify-between items-center mb-6">
              <div>
                <h2 class="text-xl font-bold text-white flex items-center gap-2">
                  <span class="w-1 h-6 rounded-full bg-violet-500"></span>
                  即梦 AI · Seedance
                </h2>
                <p class="text-xs text-gray-400 mt-1 ml-5">
                  字节跳动出品，高质量视频生成
                </p>
              </div>
              
              <div class="relative model-selector">
                <button
                  @click="showModelSelector = !showModelSelector"
                  class="flex items-center gap-2 px-4 py-2 bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl text-sm text-white transition-all hover:border-white/20 hover:shadow-lg hover:shadow-violet-500/10"
                >
                  <div class="flex items-center gap-2">
                    <div class="w-2 h-2 rounded-full bg-violet-400 shadow-[0_0_8px_rgba(167,139,250,0.8)]"></div>
                    <span class="font-medium tracking-wide">{{ selectedModel?.display_name || '选择模型' }}</span>
                  </div>
                  <svg class="w-4 h-4 text-gray-400 transition-transform duration-300" :class="{ 'rotate-180': showModelSelector }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
                  </svg>
                </button>

                <Transition name="dropdown">
                  <div v-if="showModelSelector" class="absolute top-full right-0 mt-3 w-72 bg-[#0f1115]/95 backdrop-blur-2xl border border-white/10 rounded-2xl shadow-2xl z-50 overflow-hidden ring-1 ring-white/5">
                    <div class="p-4 border-b border-white/5 bg-white/5">
                      <h3 class="text-sm font-bold text-white mb-1">选择生成模型</h3>
                      <p class="text-xs text-gray-400">即梦 Seedance 系列模型</p>
                    </div>
                    <div class="max-h-[320px] overflow-y-auto">
                      <div 
                        v-for="model in availableModels" 
                        :key="model.id"
                        @click="selectModel(model)"
                        class="p-3 hover:bg-white/5 cursor-pointer border-b border-white/5 last:border-b-0 transition-all group"
                        :class="{ 'bg-violet-500/10': selectedModel?.id === model.id }"
                      >
                        <div class="flex items-start justify-between">
                          <div class="flex-1">
                            <div class="flex items-center gap-2 mb-1">
                              <span class="font-bold text-white text-sm group-hover:text-violet-400 transition-colors">{{ model.display_name }}</span>
                              <span v-if="model.is_default" class="px-1.5 py-0.5 bg-green-500/20 text-green-400 text-[10px] font-bold rounded border border-green-500/30">
                                推荐
                              </span>
                            </div>
                            <p class="text-xs text-gray-400 mb-2">{{ model.description }}</p>
                            <span class="text-sm font-bold text-white">¥{{ model.price.toFixed(2) }}</span>
                          </div>
                          <div v-if="selectedModel?.id === model.id" class="ml-3 text-violet-400">
                            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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

            <div class="flex items-center gap-1 p-1 bg-black/30 rounded-xl border border-white/10 w-fit">
              <button
                @click="videoMode = 'text'"
                class="px-4 py-2 text-sm font-medium rounded-lg transition-all duration-200"
                :class="videoMode === 'text'
                  ? 'bg-gradient-to-r from-violet-500/80 to-fuchsia-500/80 text-white shadow-lg shadow-violet-900/30'
                  : 'text-gray-400 hover:text-white hover:bg-white/5'"
              >
                文生视频
              </button>
              <button
                @click="videoMode = 'image'"
                class="px-4 py-2 text-sm font-medium rounded-lg transition-all duration-200"
                :class="videoMode === 'image'
                  ? 'bg-gradient-to-r from-violet-500/80 to-fuchsia-500/80 text-white shadow-lg shadow-violet-900/30'
                  : 'text-gray-400 hover:text-white hover:bg-white/5'"
              >
                图生视频
              </button>
            </div>

            <!-- 时长、比例选择 -->
            <div class="flex flex-wrap items-center gap-4 mt-4">
              <!-- 时长选择 -->
              <div class="flex items-center gap-2">
                <span class="text-xs text-gray-400">时长</span>
                <div class="flex items-center gap-1 p-0.5 bg-black/30 rounded-lg border border-white/10">
                  <button
                    v-for="d in durationOptions"
                    :key="d"
                    @click="selectedDuration = d"
                    class="px-2.5 py-1 text-xs font-medium rounded-md transition-all duration-200"
                    :class="selectedDuration === d
                      ? 'bg-violet-500/80 text-white'
                      : 'text-gray-400 hover:text-white hover:bg-white/5'"
                  >
                    {{ d }}s
                  </button>
                </div>
              </div>

              <!-- 比例选择 -->
              <div class="flex items-center gap-2">
                <span class="text-xs text-gray-400">比例</span>
                <div class="flex items-center gap-1 p-0.5 bg-black/30 rounded-lg border border-white/10">
                  <button
                    v-for="r in ratioOptions"
                    :key="r"
                    @click="selectedRatio = r"
                    class="px-2.5 py-1 text-xs font-medium rounded-md transition-all duration-200"
                    :class="selectedRatio === r
                      ? 'bg-violet-500/80 text-white'
                      : 'text-gray-400 hover:text-white hover:bg-white/5'"
                  >
                    {{ r }}
                  </button>
                </div>
              </div>
            </div>

            <div class="relative group mt-6">
              <div class="absolute -inset-0.5 bg-gradient-to-r from-violet-500/20 to-fuchsia-500/20 rounded-2xl blur opacity-0 group-hover:opacity-100 transition duration-500"></div>
              <textarea 
                v-model="prompt"
                :maxlength="maxPromptLength"
                @keydown="handleKeydown"
                placeholder="请输入详细的画面描述... (例如: 一只可爱的小狗在草地上奔跑，阳光明媚)"
                class="relative w-full h-40 p-6 rounded-2xl bg-black/20 border border-white/10 text-white placeholder-gray-500 outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/20 transition-all resize-none text-lg shadow-inner backdrop-blur-sm"
              ></textarea>
              <div class="absolute bottom-4 right-4 flex items-center gap-3 pointer-events-none">
                <span class="text-xs px-2 py-1 rounded-lg bg-black/20 border border-white/5 backdrop-blur-md" :class="promptLength > maxPromptLength * 0.9 ? 'text-orange-400' : 'text-gray-500'">{{ promptLength }}/{{ maxPromptLength }}</span>
                <span class="text-xs text-gray-500 bg-black/20 px-2 py-1 rounded-lg border border-white/5 backdrop-blur-md hidden sm:inline-flex items-center gap-1">
                  <kbd class="px-1 py-0.5 bg-white/10 rounded text-[10px] font-mono">Ctrl</kbd>+<kbd class="px-1 py-0.5 bg-white/10 rounded text-[10px] font-mono">Enter</kbd> 发送
                </span>
              </div>
            </div>
            
            <div v-if="videoMode === 'image'" class="mt-6 grid grid-cols-2 gap-6">
              <div
                class="relative"
                @dragover.prevent
                @drop="(e) => handleDrop(e, 'first')"
                @paste="(e) => handlePaste(e, 'first')"
                tabindex="0"
              >
                <input
                  type="file"
                  accept="image/*"
                  @change="(e) => handleImageUpload(e, 'first')"
                  class="hidden"
                  id="jimeng-first-frame-input"
                />
                <label
                  for="jimeng-first-frame-input"
                  class="block cursor-pointer group"
                >
                  <div
                    v-if="!firstFramePreview"
                    class="h-28 border border-dashed border-white/20 rounded-2xl flex flex-col items-center justify-center gap-3 transition-all bg-white/[0.02] hover:bg-white/[0.05] hover:border-violet-500/30 hover:shadow-[0_0_20px_rgba(167,139,250,0.1)]"
                  >
                    <div class="p-3 bg-white/5 rounded-full group-hover:scale-110 transition-transform duration-300">
                      <svg class="w-6 h-6 text-gray-400 group-hover:text-violet-400 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                      </svg>
                    </div>
                    <span class="text-xs text-gray-400 font-medium group-hover:text-gray-300">拖拽/粘贴/点击上传首帧</span>
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

              <div
                class="relative"
                @dragover.prevent
                @drop="(e) => handleDrop(e, 'last')"
                @paste="(e) => handlePaste(e, 'last')"
                tabindex="0"
              >
                <input
                  type="file"
                  accept="image/*"
                  @change="(e) => handleImageUpload(e, 'last')"
                  class="hidden"
                  id="jimeng-last-frame-input"
                />
                <label
                  for="jimeng-last-frame-input"
                  class="block cursor-pointer group"
                >
                  <div
                    v-if="!lastFramePreview"
                    class="h-28 border border-dashed border-white/20 rounded-2xl flex flex-col items-center justify-center gap-3 transition-all bg-white/[0.02] hover:bg-white/[0.05] hover:border-fuchsia-500/30 hover:shadow-[0_0_20px_rgba(217,70,239,0.1)]"
                  >
                    <div class="p-3 bg-white/5 rounded-full group-hover:scale-110 transition-transform duration-300">
                      <svg class="w-6 h-6 text-gray-400 group-hover:text-fuchsia-400 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                      </svg>
                    </div>
                    <span class="text-xs text-gray-400 font-medium group-hover:text-gray-300">拖拽/粘贴/点击上传尾帧</span>
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
                <span class="font-medium">系统状态正常</span>
              </div>
              
              <div class="flex items-center gap-6">
                <div class="text-right">
                   <span class="text-xs text-gray-500 block">本次消耗</span>
                   <span class="text-lg font-bold text-white leading-none">¥{{ selectedModel?.price_per_second > 0 ? (selectedModel.price_per_second * selectedDuration).toFixed(2) : (selectedModel?.price ? selectedModel.price.toFixed(2) : '0.99') }}</span>
                </div>
                <button 
                  @click="handleCreateOrder"
                  :disabled="loading"
                  class="relative py-3 px-8 bg-gradient-to-r from-violet-500 to-fuchsia-600 hover:from-violet-400 hover:to-fuchsia-500 text-white rounded-xl font-bold transition-all duration-300 transform hover:scale-105 hover:shadow-[0_0_20px_rgba(167,139,250,0.4)] disabled:opacity-50 disabled:scale-100 disabled:hover:shadow-none flex items-center gap-2 overflow-hidden group"
                >
                  <div class="absolute inset-0 bg-white/20 translate-x-[-100%] group-hover:translate-x-[100%] transition-transform duration-1000"></div>
                  <span v-if="loading" class="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full"></span>
                  {{ loading ? '正在提交...' : '立即生成' }}
                </button>
              </div>
            </div>
          </div>
        </div>
        
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
                    <p class="text-xs text-gray-500 font-mono">{{ formatUTCTime(order.created_at) }}</p>
                    <div v-if="order.model_name" class="flex items-center gap-1.5 px-2 py-0.5 bg-white/5 rounded border border-white/5">
                      <div class="w-1.5 h-1.5 bg-violet-400 rounded-full shadow-[0_0_5px_rgba(167,139,250,0.8)]"></div>
                      <span class="text-xs text-gray-300">{{ order.model_name }}</span>
                    </div>
                    <template v-if="order.status === 'completed' && order.video_url">
                      <a
                        :href="order.video_url" target="_blank" rel="noopener noreferrer"
                        class="px-3 py-1 bg-violet-500/10 hover:bg-violet-500/20 text-violet-400 text-xs rounded-full border border-violet-500/20 hover:border-violet-500/40 transition-all flex items-center gap-1.5"
                      >
                        <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/>
                        </svg>
                        <span class="font-bold">查看视频</span>
                      </a>
                    </template>
                    <button v-if="order.status === 'failed'"
                      @click="retryOrder(order)"
                      class="px-3 py-1 bg-orange-500/10 hover:bg-orange-500/20 text-orange-400 text-xs rounded-full border border-orange-500/20 hover:border-orange-500/40 transition-all flex items-center gap-1.5">
                      <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
                      </svg>
                      <span class="font-bold">重试</span>
                    </button>
                  </div>
                </div>
                <div>
                  <span :class="`px-3 py-1.5 rounded-lg text-xs font-bold border flex items-center gap-1.5 ${statusMap[order.status]?.class || 'bg-gray-500/10 text-gray-400 border-gray-500/20'}`">
                    <span v-if="order.status === 'processing' || order.status === 'generating'" class="w-2 h-2 rounded-full border-2 border-current border-t-transparent animate-spin"></span>
                    {{ statusMap[order.status]?.text || order.status }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    
    <Transition name="toast">
      <div v-if="showInsufficientModal" class="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50" @click.self="showInsufficientModal = false">
        <div class="bg-[#0f1115]/95 border border-white/10 rounded-2xl p-8 max-w-sm w-full mx-4 shadow-2xl">
          <div class="text-center">
            <div class="w-16 h-16 bg-orange-500/10 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg class="w-8 h-8 text-orange-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
              </svg>
            </div>
            <h3 class="text-lg font-bold text-white mb-2">余额不足</h3>
            <p class="text-gray-400 text-sm mb-1">本次生成需要 <span class="text-white font-bold">¥{{ insufficientPrice.toFixed(2) }}</span></p>
            <p class="text-gray-500 text-sm mb-6">当前余额 <span class="text-orange-400 font-bold">¥{{ formattedBalance }}</span></p>
            <div class="flex gap-3">
              <button @click="showInsufficientModal = false" class="flex-1 py-2.5 bg-white/5 hover:bg-white/10 text-gray-300 rounded-xl text-sm font-medium border border-white/10 transition-all">取消</button>
              <button @click="showInsufficientModal = false; router.push('/recharge')" class="flex-1 py-2.5 bg-gradient-to-r from-violet-500 to-fuchsia-600 hover:from-violet-400 hover:to-fuchsia-500 text-white rounded-xl text-sm font-bold transition-all shadow-lg shadow-violet-900/30">去充值</button>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
@keyframes marquee {
  0% { transform: translateX(100%); }
  100% { transform: translateX(-100%); }
}
.animate-marquee {
  animation: marquee 15s linear infinite;
}
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
