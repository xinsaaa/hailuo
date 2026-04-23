<script setup>
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  getCurrentUser,
  createOrder,
  getOrders,
  getPublicConfig,
  getAvailableModels,
  klingPreUpload,
  klingLipSyncSpeakers,
  klingLipSyncSubmit,
  klingLipSyncStatus,
} from '../api'

const router = useRouter()
const siteName = ref(localStorage.getItem('site_name') || '大帝AI')

// State
const user = ref(null)
const orders = ref([])
const prompt = ref('')
const loading = ref(false)

// Model selection
const availableModels = ref([])
const lipSyncModels = ref([])
const selectedModel = ref(null)
const showModelSelector = ref(false)

// Video mode: text-to-video / image-to-video
const videoMode = ref('image')

// Image mode: single / dual
const imageMode = ref('single') // 'single' or 'dual'

// Clear last frame when switching back to single-image mode
watch(imageMode, (val) => {
  if (val === 'single') {
    lastFrameImage.value = null
    lastFrameCdnUrl.value = null
    uploadingLast.value = false
    if (lastFramePreview.value) {
      URL.revokeObjectURL(lastFramePreview.value)
      lastFramePreview.value = null
    }
  }
})

// Duration
const duration = ref('5s')
const durationSlider = ref(5)

// Resolution
const resolution = ref('1080p')

// Quantity
const quantity = ref(1)

// First frame
const firstFrameImage = ref(null)
const firstFramePreview = ref(null)

// Last frame
const lastFrameImage = ref(null)
const lastFramePreview = ref(null)

// Kling CDN pre-upload state
const firstFrameCdnUrl = ref(null)
const lastFrameCdnUrl = ref(null)
const uploadingFirst = ref(false)
const uploadingLast = ref(false)

// Watermark option
const removeWatermark = ref(true)

// Aspect ratio
const aspectRatio = ref('16:9')
const aspectRatioOptions = [
  { label: '16:9', icon: '▭', desc: '横屏' },
  { label: '9:16', icon: '▯', desc: '竖屏' },
  { label: '1:1', icon: '□', desc: '方形' },
]

// Resolve model-specific UI options
const modelConfig = computed(() => {
  const name = selectedModel.value?.name || ''
  if (name.includes('3.0')) return { resolutions: ['720p', '1080p'], durationMode: 'slider', durationMin: 5, durationMax: 15, quantities: [1, 2, 3, 4] }
  if (name.includes('2.6')) return { resolutions: ['720p', '1080p'], durationMode: 'buttons', durationOptions: ['5s', '10s'], quantities: [1, 2, 3, 4] }
  if (name.includes('2.5')) return { resolutions: ['720p', '1080p'], durationMode: 'buttons', durationOptions: ['5s', '10s'], quantities: [1, 2, 3, 4] }
  return { resolutions: ['720p', '1080p'], durationMode: 'buttons', durationOptions: ['5s', '10s'], quantities: [1, 2, 3, 4] }
})

// Keep values within the selected model's supported range
watch(() => selectedModel.value, () => {
  const cfg = modelConfig.value
  if (!cfg.resolutions.includes(resolution.value)) resolution.value = cfg.resolutions[0]
  if (cfg.durationMode === 'slider') {
    durationSlider.value = Math.max(cfg.durationMin, Math.min(cfg.durationMax, durationSlider.value))
    duration.value = durationSlider.value + 's'
  } else {
    if (!cfg.durationOptions.includes(duration.value)) duration.value = cfg.durationOptions[0]
  }
  if (!cfg.quantities.includes(quantity.value)) quantity.value = 1
})

// Sync slider to duration text
watch(durationSlider, (val) => { duration.value = val + 's' })

// prompt字数限制
const maxPromptLength = 500
const promptLength = computed(() => prompt.value.length)

// Ctrl+Enter submit shortcut
const handleKeydown = (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    e.preventDefault()
    handleCreateOrder()
  }
}

// Unit price depends on mode / resolution / duration
const unitPrice = computed(() => {
  const m = selectedModel.value
  if (!m) return 1.49
  const seconds = parseInt(duration.value) || 5

  // Priority 1: pricing_matrix
  if (m.pricing_matrix) {
    let tierKey = 'single_image'
    if (videoMode.value === 'text') tierKey = 'text'
    else if (imageMode.value === 'dual') tierKey = 'dual_image'

    const tier = m.pricing_matrix[tierKey]
    if (tier) {
      const resPrices = tier[resolution.value]
      if (resPrices) {
        const exact = resPrices[String(seconds)]
        if (exact && exact > 0) return Math.round(exact * 100) / 100
        const pps = resPrices.per_second
        if (pps && pps > 0) return Math.round(pps * seconds * 100) / 100
      }
    }
  }

  // Priority 2: price_per_second
  if (m.price_per_second) {
    return Math.round(m.price_per_second * seconds * 100) / 100
  }

  // Priority 3: price_10s
  if (duration.value === '10s' && m.price_10s) return m.price_10s

  // Fallback: fixed price
  return m.price || 1.49
})
// Total price
const currentPrice = computed(() => unitPrice.value * quantity.value)

// Auto polling
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
        const [userData, ordersData] = await Promise.all([
          getCurrentUser().catch(() => user.value),
          getOrders()
        ])
        user.value = userData
        orders.value = ordersData.filter(o =>
          o.model_name && (o.model_name.startsWith('Kling') || o.model_name.startsWith('可灵'))
        )
      } catch (err) { /* ignore */ }
    } else {
      pollCount++
    }
    const interval = hasProcessing ? 2000 : Math.min(3000 + pollCount * 2000, 10000)
    ordersInterval = setTimeout(poll, interval)
  }
  ordersInterval = setTimeout(poll, 2000)
}

// Close model selector when clicking outside
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
  if (lipSyncStatusTimer) clearTimeout(lipSyncStatusTimer)
})

// Toast
const showToast = ref(false)
const toastMessage = ref('')
const toastType = ref('info')

// Video player dialog
const showVideoPlayer = ref(false)
const currentVideoUrl = ref('')
const showLipSyncModal = ref(false)
const lipSyncOrder = ref(null)
const lipSyncText = ref('')
const lipSyncSpeakerId = ref('chat1_female_new-3')
const lipSyncSpeakers = ref([])
const lipSyncSubmitting = ref(false)
const lipSyncPolling = ref(false)
const lipSyncTaskId = ref('')
let lipSyncStatusTimer = null

const playVideo = (url) => {
  currentVideoUrl.value = url
  showVideoPlayer.value = true
}

const getDownloadFilename = (order, idx) => {
  let name = (order.prompt || '').replace(/\[#ORD\d+\]/g, '').trim()
  name = name.replace(/[\\/:*?"<>|]/g, '').substring(0, 20).trim()
  if (!name) name = '视频'
  const suffix = idx !== undefined ? `_${idx + 1}` : ''
  return `${name}_${order.id}${suffix}.mp4`
}

const getVideoUrls = (order) => {
  if (order.video_urls) {
    try {
      const urls = JSON.parse(order.video_urls)
      if (Array.isArray(urls) && urls.length > 0) return urls
    } catch (e) {}
  }
  return order.video_url ? [order.video_url] : []
}

const canLipSync = (order) => {
  const urls = getVideoUrls(order)
  const isKling = !!order?.model_name && (order.model_name.startsWith('Kling') || order.model_name.startsWith('可灵'))
  return order?.status === 'completed' && urls.length > 0 && isKling && !!order?.task_id
}

const openLipSync = (order) => {
  if (!canLipSync(order)) {
    showNotification('请先选择一个已完成的视频', 'error')
    return
  }
  lipSyncOrder.value = order
  lipSyncText.value = (order.prompt || '').replace(/\[#ORD\d+\]/g, '').trim()
  lipSyncTaskId.value = ''
  showLipSyncModal.value = true
}

const closeLipSyncModal = () => {
  showLipSyncModal.value = false
  lipSyncTaskId.value = ''
  lipSyncSubmitting.value = false
  lipSyncPolling.value = false
  if (lipSyncStatusTimer) {
    clearTimeout(lipSyncStatusTimer)
    lipSyncStatusTimer = null
  }
}

const selectedLipSyncModel = computed(() => lipSyncModels.value[0] || null)

const lipSyncPriceHint = computed(() => {
  const model = selectedLipSyncModel.value
  if (!model) return ''
  if (model.price_per_second) return `按秒计费：¥${Number(model.price_per_second).toFixed(2)}/秒`
  if (model.price_10s) return `10秒价格：¥${Number(model.price_10s).toFixed(2)}`
  if (model.price) return `基础价格：¥${Number(model.price).toFixed(2)}`
  return ''
})

const pollLipSyncTask = async (taskId) => {
  if (!taskId) return
  lipSyncPolling.value = true
  try {
    const result = await klingLipSyncStatus(taskId)
    if (result.done && result.video_url) {
      lipSyncPolling.value = false
      lipSyncTaskId.value = ''
      showNotification('对口型已完成，记录已刷新', 'success')
      await loadData()
      closeLipSyncModal()
      playVideo(getVideoUrl(result.video_url))
      return
    }
    if (result.failed) {
      lipSyncPolling.value = false
      lipSyncTaskId.value = ''
      showNotification(result.message || '对口型生成失败', 'error')
      return
    }
    lipSyncStatusTimer = setTimeout(() => pollLipSyncTask(taskId), 5000)
  } catch (err) {
    lipSyncPolling.value = false
    lipSyncTaskId.value = ''
    showNotification(err.response?.data?.detail || '查询对口型状态失败', 'error')
  }
}

const submitLipSync = async () => {
  if (!lipSyncOrder.value || !canLipSync(lipSyncOrder.value)) {
    showNotification('请先选择一个已完成的视频', 'error')
    return
  }
  if (!lipSyncText.value.trim()) {
    showNotification('请输入配音文案', 'error')
    return
  }
  if (!lipSyncSpeakerId.value) {
    showNotification('请选择音色', 'error')
    return
  }

  lipSyncSubmitting.value = true
  try {
    const result = await klingLipSyncSubmit({
      order_id: lipSyncOrder.value.id,
      model_name: selectedLipSyncModel.value?.name || 'Kling Lip Sync',
      tts_text: lipSyncText.value.trim(),
      tts_speaker_id: lipSyncSpeakerId.value,
      tts_speed: '1',
      tts_emotion: '',
      audio_start_time: 0,
      audio_end_time: 0,
      face_start_time: 0,
      face_end_time: 0,
      include_original_audio: false,
    })
    lipSyncTaskId.value = result.task_id || ''
    showNotification(`对口型任务已提交${result.cost ? `，扣费 ¥${Number(result.cost).toFixed(2)}` : ''}`, 'success')
    await loadData()
    if (lipSyncTaskId.value) {
      pollLipSyncTask(lipSyncTaskId.value)
    }
  } catch (err) {
    showNotification(err.response?.data?.detail || '对口型提交失败', 'error')
  } finally {
    lipSyncSubmitting.value = false
  }
}
const getVideoUrl = (url) => {
  const token = localStorage.getItem('token')
  if (!token || !url) return url
  const sep = url.includes('?') ? '&' : '?'
  return `${url}${sep}token=${token}`
}

const closeVideoPlayer = () => {
  showVideoPlayer.value = false
  currentVideoUrl.value = ''
}

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
    const [userData, ordersData, modelsData] = await Promise.all([
      getCurrentUser(),
      getOrders(),
      getAvailableModels().catch(() => null)
    ])
    user.value = userData
    // Only keep Kling-related orders
    orders.value = ordersData.filter(o =>
      o.model_name && (o.model_name.startsWith('Kling') || o.model_name.startsWith('可灵'))
    )
    if (modelsData && modelsData.models) {
      // Only keep Kling 3.0 (Seedance 2.0)
      const klingModels = modelsData.models.filter(model =>
        (model.platform === 'kling' || model.id?.includes('kling') || model.name?.startsWith('Kling')) &&
        model.type !== 'lip_sync' &&
        model.id === 'kling_3_0'
      )
      lipSyncModels.value = modelsData.models.filter(model =>
        (model.platform === 'kling' || model.id?.includes('kling') || model.name?.startsWith('Kling')) &&
        model.type === 'lip_sync'
      )
      // Rename display names: 可灵 -> Seedance, 3.0 -> 2.0
      klingModels.forEach(m => {
        if (m.display_name) {
          m.display_name = m.display_name.replace(/可灵/g, 'Seedance').replace(/3\.0/g, '2.0')
        }
        if (m.description) {
          m.description = m.description.replace(/可灵/g, 'Seedance').replace(/3\.0/g, '2.0')
        }
      })
      availableModels.value = klingModels
      if (klingModels.length > 0 && !selectedModel.value) {
        selectedModel.value = klingModels[0]
      }
    }
    if (lipSyncSpeakers.value.length === 0) {
      const speakerData = await klingLipSyncSpeakers().catch(() => null)
      if (speakerData?.speakers?.length) {
        lipSyncSpeakers.value = speakerData.speakers
        if (!lipSyncSpeakerId.value) lipSyncSpeakerId.value = speakerData.speakers[0].speaker_id
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
  if (videoMode.value === 'image' && !firstFrameImage.value && !firstFrameCdnUrl.value) {
    showNotification('图生视频模式请上传首帧图片', 'error')
    return
  }
  if (videoMode.value === 'image' && imageMode.value === 'dual' && !lastFrameImage.value && !lastFrameCdnUrl.value) {
    showNotification('双图模式请上传尾帧图片', 'error')
    return
  }

  const modelPrice = currentPrice.value
  if (!user.value || user.value.balance < modelPrice) {
    showInsufficientModal.value = true
    insufficientPrice.value = modelPrice
    return
  }

  loading.value = true
  let videoType = 'text_to_video'
  if (videoMode.value === 'image') {
    videoType = imageMode.value === 'dual' ? 'dual_image_to_video' : 'image_to_video'
  }

  try {
    const opts = { aspectRatio: aspectRatio.value, removeWatermark: removeWatermark.value }
    if (firstFrameCdnUrl.value) opts.firstFrameCdnUrl = firstFrameCdnUrl.value
    if (lastFrameCdnUrl.value) opts.lastFrameCdnUrl = lastFrameCdnUrl.value

    await createOrder(
      prompt.value,
      selectedModel.value.name,
      videoMode.value === 'image' && !firstFrameCdnUrl.value ? firstFrameImage.value : null,
      videoMode.value === 'image' && !lastFrameCdnUrl.value ? lastFrameImage.value : null,
      videoType,
      resolution.value,
      duration.value,
      quantity.value,
      opts
    )
    showNotification('订单提交成功，Seedance 正在为您生成...', 'success')
    prompt.value = ''
    firstFrameCdnUrl.value = null
    lastFrameCdnUrl.value = null
    removeImage('all')
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

// Image upload
const processFile = async (file, type = 'first') => {
  if (!file) return
  if (!file.type.startsWith('image/')) {
    showNotification('请选择图片文件', 'error')
    return
  }
  if (file.size > 5 * 1024 * 1024) {
    showNotification('图片大小不能超过 5MB', 'error')
    return
  }

  if (type === 'first') {
    firstFrameImage.value = file
    if (firstFramePreview.value) URL.revokeObjectURL(firstFramePreview.value)
    firstFramePreview.value = URL.createObjectURL(file)
    firstFrameCdnUrl.value = null
    uploadingFirst.value = true
    try {
      const res = await klingPreUpload(file, 'first')
      if (res.cdn_url) {
        firstFrameCdnUrl.value = res.cdn_url
        showNotification('图片已预上传到 CDN', 'success')
      }
    } catch (e) {
      const msg = e.response?.data?.detail || e.message || '未知错误'
      console.warn('预上传失败', msg, e)
      showNotification(`预上传失败：${msg}，提交时将重新上传`, 'warning')
    } finally {
      uploadingFirst.value = false
    }
  } else {
    lastFrameImage.value = file
    if (lastFramePreview.value) URL.revokeObjectURL(lastFramePreview.value)
    lastFramePreview.value = URL.createObjectURL(file)
    lastFrameCdnUrl.value = null
    uploadingLast.value = true
    try {
      const res = await klingPreUpload(file, 'last')
      if (res.cdn_url) {
        lastFrameCdnUrl.value = res.cdn_url
        showNotification('尾帧图片已预上传', 'success')
      }
    } catch (e) {
      const msg = e.response?.data?.detail || e.message || '未知错误'
      console.warn('尾帧预上传失败', msg, e)
      showNotification(`尾帧预上传失败：${msg}`, 'warning')
    } finally {
      uploadingLast.value = false
    }
  }
}

const handleImageUpload = (event) => { processFile(event.target.files[0]) }
const handleDrop = (event) => { event.preventDefault(); processFile(event.dataTransfer?.files?.[0]) }
const handlePaste = (event) => {
  const items = event.clipboardData?.items
  if (!items) return
  for (const item of items) {
    if (item.type.startsWith('image/')) {
      event.preventDefault()
      processFile(item.getAsFile())
      return
    }
  }
}

const processLastFrameFile = (file) => { processFile(file, 'last') }
const handleLastFrameUpload = (event) => { processLastFrameFile(event.target.files[0]) }
const handleLastFrameDrop = (event) => { event.preventDefault(); processLastFrameFile(event.dataTransfer?.files?.[0]) }

const removeImage = (type = 'first') => {
  if (type === 'first' || type === 'all') {
    firstFrameImage.value = null
    firstFrameCdnUrl.value = null
    uploadingFirst.value = false
    if (firstFramePreview.value) {
      URL.revokeObjectURL(firstFramePreview.value)
      firstFramePreview.value = null
    }
  }
  if (type === 'last' || type === 'all') {
    lastFrameImage.value = null
    lastFrameCdnUrl.value = null
    uploadingLast.value = false
    if (lastFramePreview.value) {
      URL.revokeObjectURL(lastFramePreview.value)
      lastFramePreview.value = null
    }
  }
}

const statusMap = {
  pending: { text: '排队中', class: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30' },
  processing: { text: '处理中', class: 'bg-blue-500/20 text-blue-400 border-blue-500/30' },
  generating: { text: '生成中', class: 'bg-orange-500/20 text-orange-400 border-orange-500/30' },
  completed: { text: '已完成', class: 'bg-green-500/20 text-green-400 border-green-500/30' },
  failed: { text: '失败', class: 'bg-red-500/20 text-red-400 border-red-500/30' },
}

const getOrderFailureMessage = (order) => {
  return order?.status === 'failed'
    ? (order?.status_message || '生成失败，请稍后重试')
    : ''
}

// Insufficient balance dialog
const showInsufficientModal = ref(false)
const insufficientPrice = ref(0)

// Retry
const retryOrder = (order) => {
  prompt.value = order.prompt
  showNotification('已填入原始描述，请点击生成', 'info')
}

// Format UTC time
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
    <!-- Toast -->
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
        <div class="flex items-center gap-4">
          <div class="text-2xl font-extrabold cursor-pointer flex items-center gap-2" @click="router.push('/')">
            <span class="text-white drop-shadow-md">{{ siteName }}</span>
          </div>
          <div class="flex items-center gap-1 px-3 py-1 bg-violet-500/10 border border-violet-500/20 rounded-lg">
            <svg class="w-4 h-4 text-violet-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            <span class="text-xs font-bold text-violet-400 tracking-wide">Seedance 极速版</span>
          </div>
        </div>
        <div class="flex items-center gap-6">
          <router-link to="/dashboard" class="text-sm text-gray-400 hover:text-white transition-colors">海螺AI</router-link>
          <router-link to="/nanobanana" class="text-sm text-gray-400 hover:text-white transition-colors">nanobanana pro</router-link>
          <router-link to="/tickets" class="flex items-center gap-1.5 px-3 py-1.5 text-sm text-amber-400/90 hover:text-amber-300 bg-amber-500/10 hover:bg-amber-500/15 border border-amber-500/20 hover:border-amber-500/30 rounded-lg transition-all">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"/>
            </svg>
            工单反馈
          </router-link>
          <router-link to="/profile" class="flex items-center gap-1.5 px-3 py-1.5 text-sm text-cyan-400/90 hover:text-cyan-300 bg-cyan-500/10 hover:bg-cyan-500/15 border border-cyan-500/20 hover:border-cyan-500/30 rounded-lg transition-all">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/>
            </svg>
            我的
          </router-link>
          <button 
            @click="router.push('/recharge')"
            :class="isLowBalance ? 'from-red-500 to-orange-500 shadow-red-900/40' : 'from-orange-600 to-amber-600 shadow-orange-900/40'"
            class="px-4 py-1.5 bg-gradient-to-r text-white text-xs font-bold rounded-lg hover:brightness-110 transition-all shadow-lg"
          >
            {{ isLowBalance ? '⚡ 充值' : '充值' }}
          </button>
          <button @click="handleLogout" class="text-sm text-gray-300 hover:text-white transition-colors hover:drop-shadow-sm">退出</button>
        </div>
      </div>
    </nav>

    <!-- Main Content -->
    <div class="flex-grow max-w-5xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-10 relative z-10">
      <div class="space-y-8">

        <!-- Generator Card -->
        <div class="relative">
          <div class="absolute -inset-1 rounded-3xl blur-2xl opacity-40 bg-gradient-to-br from-orange-500/20 to-amber-500/20"></div>

          <div class="relative bg-white/5 backdrop-blur-3xl border border-white/10 border-t-white/20 rounded-3xl p-8 shadow-2xl">
            <div class="flex justify-between items-center mb-6">
              <div>
                <h2 class="text-xl font-bold text-white flex items-center gap-2">
                  <span class="w-1 h-6 rounded-full bg-orange-500"></span>
                  Seedance 极速版 视频生成
                </h2>
                <p class="text-xs text-gray-400 mt-1 ml-5">
                  字节跳动出品，极速生成，电影级画质
                  <a href="https://docs.qingque.cn/d/home/eZQCqDGoymg61UKgMckSB2oMh?identityId=1oEGKOVUffX" target="_blank" class="ml-2 text-orange-400 hover:text-orange-300 transition-colors inline-flex items-center gap-1">
                    <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" /></svg>
                    使用教程
                  </a>
                </p>
              </div>

              <!-- Model selector -->
              <div class="relative model-selector">
                <button
                  @click="showModelSelector = !showModelSelector"
                  class="flex items-center gap-2 px-4 py-2 bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl text-sm text-white transition-all hover:border-orange-500/30 hover:shadow-lg hover:shadow-orange-500/10"
                >
                  <div class="flex items-center gap-2">
                    <div class="w-2 h-2 rounded-full bg-orange-400 shadow-[0_0_8px_rgba(251,146,60,0.8)]"></div>
                    <span class="font-medium tracking-wide">{{ selectedModel?.display_name || '选择模型' }}</span>
                    <span v-if="selectedModel?.badge" class="px-1.5 py-0.5 bg-gradient-to-r from-orange-500 to-amber-500 text-white text-[10px] font-bold rounded uppercase tracking-wider shadow-sm">
                      {{ selectedModel.badge }}
                    </span>
                  </div>
                  <svg class="w-4 h-4 text-gray-400 transition-transform duration-300" :class="{ 'rotate-180': showModelSelector }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
                  </svg>
                </button>

                <Transition name="dropdown">
                  <div v-if="showModelSelector" class="absolute top-full right-0 mt-3 w-80 bg-[#0f1115]/95 backdrop-blur-2xl border border-white/10 rounded-2xl shadow-2xl z-50 overflow-hidden ring-1 ring-white/5">
                    <div class="p-4 border-b border-white/5 bg-white/5">
                      <h3 class="text-sm font-bold text-white mb-1">选择 Seedance 模型</h3>
                      <p class="text-xs text-gray-400">不同版本有不同的画质和速度</p>
                    </div>
                    <div class="max-h-[320px] overflow-y-auto custom-scrollbar">
                      <div
                        v-for="model in availableModels"
                        :key="model.id"
                        @click="selectModel(model)"
                        class="p-3 hover:bg-white/5 cursor-pointer border-b border-white/5 last:border-b-0 transition-all group"
                        :class="{ 'bg-orange-500/10': selectedModel?.id === model.id }"
                      >
                        <div class="flex items-start justify-between">
                          <div class="flex-1">
                            <div class="flex items-center gap-2 mb-1">
                              <span class="font-bold text-white text-sm group-hover:text-orange-400 transition-colors">{{ model.display_name }}</span>
                              <span v-if="model.badge" class="px-1.5 py-0.5 bg-gradient-to-r from-orange-500 to-amber-500 text-white text-[10px] font-bold rounded shadow-sm">
                                {{ model.badge }}
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
                          <div class="ml-3 flex flex-col items-end gap-1">
                            <span class="text-orange-400 font-bold text-sm">¥{{ model.price }}</span>
                            <div v-if="selectedModel?.id === model.id" class="text-orange-400">
                              <svg class="w-5 h-5 drop-shadow-[0_0_8px_rgba(251,146,60,0.5)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                              </svg>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </Transition>
              </div>
            </div>

            <!-- Video mode switch -->
            <div class="flex items-center gap-4 mb-4">
              <div class="flex items-center gap-1 p-1 bg-black/30 rounded-xl border border-white/10 w-fit">
                <button
                  @click="videoMode = 'text'"
                  class="px-4 py-2 text-sm font-medium rounded-lg transition-all duration-200"
                  :class="videoMode === 'text'
                    ? 'bg-gradient-to-r from-orange-500/80 to-amber-500/80 text-white shadow-lg shadow-orange-900/30'
                    : 'text-gray-400 hover:text-white hover:bg-white/5'"
                >
                  文生视频
                </button>
                <button
                  @click="videoMode = 'image'"
                  class="px-4 py-2 text-sm font-medium rounded-lg transition-all duration-200"
                  :class="videoMode === 'image'
                    ? 'bg-gradient-to-r from-amber-500/80 to-yellow-500/80 text-white shadow-lg shadow-amber-900/30'
                    : 'text-gray-400 hover:text-white hover:bg-white/5'"
                >
                  图生视频
                </button>
              </div>

              <!-- Duration -->
              <div class="flex items-center gap-2">
                <span class="text-gray-400 text-sm">时长</span>
                <!-- Slider mode -->
                <div v-if="modelConfig.durationMode === 'slider'" class="flex items-center gap-2 flex-1">
                  <input
                    type="range"
                    :min="modelConfig.durationMin"
                    :max="modelConfig.durationMax"
                    v-model.number="durationSlider"
                    class="flex-1 h-1.5 bg-white/10 rounded-full appearance-none cursor-pointer accent-orange-500 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-gradient-to-r [&::-webkit-slider-thumb]:from-orange-500 [&::-webkit-slider-thumb]:to-amber-500 [&::-webkit-slider-thumb]:shadow-lg [&::-webkit-slider-thumb]:shadow-orange-900/40"
                  />
                  <span class="text-white text-sm font-bold min-w-[36px] text-center bg-black/30 px-2 py-1 rounded-lg border border-white/10">{{ durationSlider }}s</span>
                </div>
                <!-- Button mode -->
                <div v-else class="flex items-center gap-1 p-1 bg-black/30 rounded-xl border border-white/10">
                  <button
                    v-for="d in modelConfig.durationOptions"
                    :key="d"
                    @click="duration = d"
                    class="px-3 py-1.5 text-sm font-medium rounded-lg transition-all duration-200"
                    :class="duration === d
                      ? 'bg-gradient-to-r from-orange-500/80 to-amber-500/80 text-white shadow-lg shadow-orange-900/30'
                      : 'text-gray-400 hover:text-white hover:bg-white/5'"
                  >{{ d.replace('s', '秒') }}</button>
                </div>
              </div>

              <!-- Resolution -->
              <div class="flex items-center gap-2">
                <span class="text-gray-400 text-sm">画质</span>
                <div class="flex items-center gap-1 p-1 bg-black/30 rounded-xl border border-white/10">
                  <button
                    v-for="res in modelConfig.resolutions"
                    :key="res"
                    @click="resolution = res"
                    class="px-3 py-1.5 text-sm font-medium rounded-lg transition-all duration-200"
                    :class="resolution === res
                      ? 'bg-gradient-to-r from-orange-500/80 to-amber-500/80 text-white shadow-lg shadow-orange-900/30'
                      : 'text-gray-400 hover:text-white hover:bg-white/5'"
                  >{{ res }}</button>
                </div>
              </div>

              <!-- Aspect ratio -->
              <div class="flex items-center gap-2">
                <span class="text-gray-400 text-sm">比例</span>
                <div class="flex items-center gap-1 p-1 bg-black/30 rounded-xl border border-white/10">
                  <button
                    v-for="ar in aspectRatioOptions"
                    :key="ar.label"
                    @click="aspectRatio = ar.label"
                    class="px-3 py-1.5 text-sm font-medium rounded-lg transition-all duration-200 flex items-center gap-1"
                    :class="aspectRatio === ar.label
                      ? 'bg-gradient-to-r from-orange-500/80 to-amber-500/80 text-white shadow-lg shadow-orange-900/30'
                      : 'text-gray-400 hover:text-white hover:bg-white/5'"
                  >
                    <span class="text-[10px]">{{ ar.icon }}</span>
                    {{ ar.desc }}
                  </button>
                </div>
              </div>

              <!-- Quantity -->
              <div class="flex items-center gap-2">
                <span class="text-gray-400 text-sm">数量</span>
                <div class="flex items-center gap-1 p-1 bg-black/30 rounded-xl border border-white/10">
                  <button
                    v-for="q in modelConfig.quantities"
                    :key="q"
                    @click="quantity = q"
                    class="px-3 py-1.5 text-sm font-medium rounded-lg transition-all duration-200"
                    :class="quantity === q
                      ? 'bg-gradient-to-r from-orange-500/80 to-amber-500/80 text-white shadow-lg shadow-orange-900/30'
                      : 'text-gray-400 hover:text-white hover:bg-white/5'"
                  >{{ q }}</button>
                </div>
              </div>

            </div>

            <!-- Prompt -->
            <div class="relative group">
              <div class="absolute -inset-0.5 bg-gradient-to-r from-orange-500/20 to-amber-500/20 rounded-2xl blur opacity-0 group-hover:opacity-100 transition duration-500"></div>
              <textarea
                v-model="prompt"
                :maxlength="maxPromptLength"
                @keydown="handleKeydown"
                placeholder="请输入详细的画面描述...（例如：一只猫在阳光下打盹睡觉，毛发随风轻摆）"
                class="relative w-full h-36 p-6 rounded-2xl bg-black/20 border border-white/10 text-white placeholder-gray-500 outline-none focus:border-orange-500/50 focus:ring-1 focus:ring-orange-500/20 transition-all resize-none text-lg shadow-inner backdrop-blur-sm"
              ></textarea>
              <div class="absolute bottom-4 right-4 flex items-center gap-3 pointer-events-none">
                <span class="text-xs px-2 py-1 rounded-lg bg-black/20 border border-white/5 backdrop-blur-md" :class="promptLength > maxPromptLength * 0.9 ? 'text-orange-400' : 'text-gray-500'">{{ promptLength }}/{{ maxPromptLength }}</span>
                <span class="text-xs text-gray-500 bg-black/20 px-2 py-1 rounded-lg border border-white/5 backdrop-blur-md hidden sm:inline-flex items-center gap-1">
                  <kbd class="px-1 py-0.5 bg-white/10 rounded text-[10px] font-mono">Ctrl</kbd>+<kbd class="px-1 py-0.5 bg-white/10 rounded text-[10px] font-mono">Enter</kbd> 发送
                </span>
              </div>
            </div>

            <!-- Image upload -->
            <div v-if="videoMode === 'image'" class="mt-6">
              <!-- Single / dual image mode -->
              <div class="flex items-center gap-3 mb-4">
                <span class="text-xs font-medium text-gray-400">图片模式</span>
                <div class="flex items-center gap-1 p-1 bg-black/30 rounded-xl border border-white/10">
                  <button
                    @click="imageMode = 'single'"
                    class="px-4 py-1.5 text-sm font-medium rounded-lg transition-all duration-200"
                    :class="imageMode === 'single'
                      ? 'bg-gradient-to-r from-orange-500/80 to-amber-500/80 text-white shadow-lg shadow-orange-900/30'
                      : 'text-gray-400 hover:text-white hover:bg-white/5'"
                  >
                    单图模式
                  </button>
                  <button
                    @click="imageMode = 'dual'"
                    class="px-4 py-1.5 text-sm font-medium rounded-lg transition-all duration-200"
                    :class="imageMode === 'dual'
                      ? 'bg-gradient-to-r from-amber-500/80 to-yellow-500/80 text-white shadow-lg shadow-amber-900/30'
                      : 'text-gray-400 hover:text-white hover:bg-white/5'"
                  >
                    双图模式
                  </button>
                </div>
                <span class="text-[10px] text-gray-500">{{ imageMode === 'single' ? '仅上传首帧，AI 自动生成运动' : '上传首帧和尾帧，AI 生成过渡动画' }}</span>
              </div>

              <div :class="imageMode === 'dual' ? 'grid grid-cols-2 gap-4' : ''">
              <!-- First frame -->
              <div>
                <div class="flex items-center gap-2 mb-2">
                  <span class="text-xs font-medium text-gray-300">首帧图片</span>
                  <span class="text-[10px] text-orange-400 bg-orange-500/10 px-1.5 py-0.5 rounded border border-orange-500/20">必传</span>
                </div>
                <div
                  class="relative"
                  @dragover.prevent
                  @drop="handleDrop"
                  @paste="handlePaste"
                  tabindex="0"
                >
                  <input type="file" accept="image/*" @change="handleImageUpload" class="hidden" id="kling-first-frame" />
                  <label for="kling-first-frame" class="block cursor-pointer group">
                    <div
                      v-if="!firstFramePreview"
                      class="h-28 border border-dashed border-white/20 rounded-2xl flex flex-col items-center justify-center gap-2 transition-all bg-white/[0.02] hover:bg-white/[0.05] hover:border-orange-500/30 hover:shadow-[0_0_20px_rgba(251,146,60,0.1)]"
                    >
                      <div class="p-2.5 bg-white/5 rounded-full group-hover:scale-110 transition-transform duration-300">
                        <svg class="w-5 h-5 text-gray-400 group-hover:text-orange-400 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                        </svg>
                      </div>
                      <span class="text-xs text-gray-400 font-medium group-hover:text-gray-300">拖拽 / 粘贴 / 点击上传</span>
                    </div>
                    <div v-else class="relative h-28 rounded-2xl overflow-hidden group shadow-lg border border-white/10">
                      <img :src="firstFramePreview" class="w-full h-full object-cover transition-transform duration-700 group-hover:scale-105" />
                      <div class="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center backdrop-blur-sm">
                        <span class="text-white text-xs font-medium border border-white/20 px-3 py-1.5 rounded-full bg-white/10">点击更换</span>
                      </div>
                      <div v-if="uploadingFirst" class="absolute bottom-1 right-1 w-5 h-5 bg-black/70 rounded-full flex items-center justify-center">
                        <svg class="w-3 h-3 text-orange-400 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
                      </div>
                      <div v-else-if="firstFrameCdnUrl" class="absolute bottom-1 right-1 w-5 h-5 bg-green-500/80 rounded-full flex items-center justify-center" title="已预上传到 CDN">
                        <svg class="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"/></svg>
                      </div>
                    </div>
                  </label>
                  <button
                    v-if="firstFramePreview"
                    @click.stop="removeImage('first')"
                    class="absolute -top-2 -right-2 w-6 h-6 bg-red-500 text-white rounded-full flex items-center justify-center text-xs hover:bg-red-600 transition-all shadow-lg z-10 hover:scale-110"
                  >×</button>
                </div>
              </div>

              <!-- Last frame -->
              <div v-if="imageMode === 'dual'">
                <div class="flex items-center gap-2 mb-2">
                  <span class="text-xs font-medium text-gray-300">尾帧图片</span>
                  <span class="text-[10px] text-orange-400 bg-orange-500/10 px-1.5 py-0.5 rounded border border-orange-500/20">必传</span>
                </div>
                <div
                  class="relative"
                  @dragover.prevent
                  @drop="handleLastFrameDrop"
                  tabindex="0"
                >
                  <input type="file" accept="image/*" @change="handleLastFrameUpload" class="hidden" id="kling-last-frame" />
                  <label for="kling-last-frame" class="block cursor-pointer group">
                    <div
                      v-if="!lastFramePreview"
                      class="h-28 border border-dashed border-white/10 rounded-2xl flex flex-col items-center justify-center gap-2 transition-all bg-white/[0.01] hover:bg-white/[0.04] hover:border-amber-500/20"
                    >
                      <div class="p-2.5 bg-white/5 rounded-full group-hover:scale-110 transition-transform duration-300">
                        <svg class="w-5 h-5 text-gray-500 group-hover:text-amber-400 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                        </svg>
                      </div>
                      <span class="text-xs text-gray-500 font-medium group-hover:text-gray-400">点击上传尾帧（必传）</span>
                    </div>
                    <div v-else class="relative h-28 rounded-2xl overflow-hidden group shadow-lg border border-white/10">
                      <img :src="lastFramePreview" class="w-full h-full object-cover transition-transform duration-700 group-hover:scale-105" />
                      <div class="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center backdrop-blur-sm">
                        <span class="text-white text-xs font-medium border border-white/20 px-3 py-1.5 rounded-full bg-white/10">点击更换</span>
                      </div>
                      <div v-if="uploadingLast" class="absolute bottom-1 right-1 w-5 h-5 bg-black/70 rounded-full flex items-center justify-center">
                        <svg class="w-3 h-3 text-orange-400 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
                      </div>
                      <div v-else-if="lastFrameCdnUrl" class="absolute bottom-1 right-1 w-5 h-5 bg-green-500/80 rounded-full flex items-center justify-center" title="已预上传到 CDN">
                        <svg class="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"/></svg>
                      </div>
                    </div>
                  </label>
                  <button
                    v-if="lastFramePreview"
                    @click.stop="removeImage('last')"
                    class="absolute -top-2 -right-2 w-6 h-6 bg-red-500 text-white rounded-full flex items-center justify-center text-xs hover:bg-red-600 transition-all shadow-lg z-10 hover:scale-110"
                  >×</button>
                </div>
              </div>
              </div>
            </div>

            <!-- Footer action bar -->
            <div class="flex justify-between items-center mt-8 pt-6 border-t border-white/10">
              <div class="flex items-center gap-4">
                <div class="flex items-center gap-2 text-sm text-gray-400">
                  <span class="relative flex h-2.5 w-2.5">
                    <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-orange-400 opacity-75"></span>
                    <span class="relative inline-flex rounded-full h-2.5 w-2.5 bg-orange-500"></span>
                  </span>
                  <span class="font-medium">Seedance 极速版</span>
                </div>
                <div class="flex items-center gap-1 p-0.5 bg-black/30 rounded-lg border border-white/10">
                  <button
                    @click="removeWatermark = true"
                    class="px-2 py-1 text-xs font-medium rounded-md transition-all duration-200"
                    :class="removeWatermark
                      ? 'bg-orange-500/80 text-white'
                      : 'text-gray-500 hover:text-gray-300'"
                  >去水印</button>
                  <button
                    @click="removeWatermark = false"
                    class="px-2 py-1 text-xs font-medium rounded-md transition-all duration-200"
                    :class="!removeWatermark
                      ? 'bg-gray-500/80 text-white'
                      : 'text-gray-500 hover:text-gray-300'"
                  >保留水印</button>
                </div>
              </div>

              <div class="flex items-center gap-6">
                <div class="text-right">
                  <span class="text-xs text-gray-500 block">
                    {{ videoMode === 'text' ? '文生视频' : (imageMode === 'dual' ? '双图模式' : '单图模式') }}
                    · 单价 ¥{{ unitPrice.toFixed(2) }}{{ quantity > 1 ? ' × ' + quantity : '' }}
                  </span>
                  <span class="text-lg font-bold text-white leading-none">¥{{ currentPrice.toFixed(2) }}</span>
                </div>
                <button
                  @click="handleCreateOrder"
                  :disabled="loading"
                  class="relative py-3 px-8 bg-gradient-to-r from-orange-500 to-amber-600 hover:from-orange-400 hover:to-amber-500 text-white rounded-xl font-bold transition-all duration-300 transform hover:scale-105 hover:shadow-[0_0_20px_rgba(251,146,60,0.4)] disabled:opacity-50 disabled:scale-100 disabled:hover:shadow-none flex items-center gap-2 overflow-hidden group"
                >
                  <div class="absolute inset-0 bg-white/20 translate-x-[-100%] group-hover:translate-x-[100%] transition-transform duration-1000"></div>
                  <span v-if="loading" class="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full"></span>
                  {{ loading ? '正在提交...' : '立即生成' }}
                </button>
              </div>
              <p class="text-center text-xs text-gray-500 mt-3">全部为官网正版算力，品质保障</p>
            </div>
          </div>
        </div>

        <!-- History -->
        <div>
          <h3 class="text-lg font-bold text-white mb-4 px-2 flex items-center gap-2">
            <svg class="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
            Seedance 生成记录
          </h3>
          <div class="space-y-4">
            <div v-if="orders.length === 0" class="text-center py-16 bg-black/20 backdrop-blur-md rounded-3xl border border-white/5 text-gray-500">
              <div class="w-16 h-16 bg-white/5 rounded-full flex items-center justify-center mx-auto mb-4">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8 opacity-40" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7 4v16M17 4v16M3 8h4m10 0h4M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z" />
                </svg>
              </div>
              <p>暂无 Seedance 生成记录，快去创作吧~</p>
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
                    <div v-if="order.model_name" class="flex items-center gap-1.5 px-2 py-0.5 bg-orange-500/10 rounded border border-orange-500/20">
                      <div class="w-1.5 h-1.5 bg-orange-400 rounded-full shadow-[0_0_5px_rgba(251,146,60,0.8)]"></div>
                      <span class="text-xs text-orange-300">{{ order.model_name }}</span>
                    </div>
                    <!-- Video actions -->
                    <template v-if="order.status === 'completed' && order.video_url">
                      <button
                        v-if="canLipSync(order)"
                        @click="openLipSync(order)"
                        class="px-3 py-1 bg-violet-500/10 hover:bg-violet-500/20 text-violet-400 text-xs rounded-full border border-violet-500/20 hover:border-violet-500/40 transition-all flex items-center gap-1.5"
                      >
                        <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 9l10.5-3-3 10.5-2.5-4-4 2.5L9 9z" />
                        </svg>
                        <span class="font-bold">对口型</span>
                      </button>
                      <template v-for="(url, idx) in getVideoUrls(order)" :key="idx">
                        <button v-if="url.startsWith('/videos/')"
                          @click="playVideo(getVideoUrl(url))"
                          class="px-3 py-1 bg-orange-500/10 hover:bg-orange-500/20 text-orange-400 text-xs rounded-full border border-orange-500/20 hover:border-orange-500/40 transition-all flex items-center gap-1.5 group/btn">
                          <svg class="w-3 h-3 transition-transform group-hover/btn:scale-110" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"/>
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                          </svg>
                          <span class="font-bold">{{ getVideoUrls(order).length > 1 ? `播放${idx+1}` : '播放' }}</span>
                        </button>
                        <a v-if="url.startsWith('/videos/')"
                          :href="getVideoUrl(url)" :download="getDownloadFilename(order, idx)"
                          class="px-3 py-1 bg-green-500/10 hover:bg-green-500/20 text-green-400 text-xs rounded-full border border-green-500/20 hover:border-green-500/40 transition-all flex items-center gap-1.5 group/btn">
                          <svg class="w-3 h-3 transition-transform group-hover/btn:scale-110" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
                          </svg>
                          <span class="font-bold">{{ getVideoUrls(order).length > 1 ? `下载${idx+1}` : '下载' }}</span>
                        </a>
                        <a v-if="!url.startsWith('/videos/')"
                          :href="url" target="_blank"
                          class="px-3 py-1 bg-orange-500/10 hover:bg-orange-500/20 text-orange-400 text-xs rounded-full border border-orange-500/20 hover:border-orange-500/40 transition-all flex items-center gap-1.5 group/btn">
                          <svg class="w-3 h-3 transition-transform group-hover/btn:scale-110" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"/>
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                          </svg>
                          <span class="font-bold">{{ getVideoUrls(order).length > 1 ? `观看${idx+1}` : '观看视频' }}</span>
                        </a>
                      </template>
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
              <!-- Generating hint -->
              <div v-if="order.status === 'processing' || order.status === 'generating'" class="mt-4 bg-white/5 rounded-lg p-3 border border-white/5">
                <div class="flex items-center gap-2">
                  <svg class="w-4 h-4 text-orange-400 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  <span class="text-sm text-gray-400">Seedance 正在生成中...</span>
                </div>
              </div>
                <div v-if="order.status === 'failed' && getOrderFailureMessage(order)" class="mt-4 bg-red-500/10 rounded-lg p-3 border border-red-500/20">
                  <div class="flex items-start gap-2">
                    <svg class="w-4 h-4 text-red-400 mt-0.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                    </svg>
                    <span class="text-sm text-red-300 leading-relaxed">{{ getOrderFailureMessage(order) }}</span>
                  </div>
                </div>
            </div>

            <div v-if="orders.length > 0" class="mt-6 text-center">
              <router-link to="/tickets" class="inline-flex items-center gap-2 px-4 py-2 text-sm text-gray-400 hover:text-amber-400 bg-white/5 hover:bg-amber-500/10 border border-white/10 hover:border-amber-500/20 rounded-xl transition-all">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                </svg>
                遇到问题？提交工单反馈
              </router-link>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Lip sync dialog -->
    <Transition name="toast">
      <div v-if="showLipSyncModal" class="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4" @click.self="closeLipSyncModal">
        <div class="w-full max-w-2xl bg-[#0f1115]/95 border border-white/10 rounded-3xl shadow-2xl overflow-hidden">
          <div class="flex items-center justify-between px-6 py-5 border-b border-white/10 bg-white/5">
            <div>
              <h3 class="text-lg font-bold text-white">Seedance 对口型</h3>
              <p class="text-xs text-gray-400 mt-1">仅支持 Seedance 历史记录里已完成的视频</p>
            </div>
            <button @click="closeLipSyncModal" class="w-9 h-9 rounded-full bg-white/5 hover:bg-white/10 text-gray-300 hover:text-white transition-all">×</button>
          </div>

          <div class="p-6 space-y-5">
            <div class="rounded-2xl border border-white/10 bg-white/5 p-4">
              <div class="flex items-center justify-between gap-4">
                <div class="min-w-0">
                  <p class="text-xs text-gray-500 mb-1">源视频</p>
                  <p class="text-sm text-white line-clamp-2">{{ lipSyncOrder?.prompt }}</p>
                </div>
                <button
                  v-if="lipSyncOrder?.video_url"
                  @click="playVideo(getVideoUrl(lipSyncOrder.video_url))"
                  class="shrink-0 px-3 py-1.5 text-xs rounded-lg bg-orange-500/10 text-orange-300 border border-orange-500/20 hover:bg-orange-500/20 transition-all"
                >预览视频</button>
              </div>
            </div>

            <div class="grid md:grid-cols-2 gap-4">
              <div>
                <label class="block text-sm text-gray-300 mb-2">音色</label>
                <select v-model="lipSyncSpeakerId" class="w-full px-4 py-3 rounded-2xl bg-black/30 border border-white/10 text-white outline-none focus:border-violet-500/40">
                  <option v-for="speaker in lipSyncSpeakers" :key="speaker.speaker_id" :value="speaker.speaker_id">
                    {{ speaker.name }}
                  </option>
                </select>
              </div>
              <div class="rounded-2xl border border-violet-500/20 bg-violet-500/10 p-4">
                <p class="text-sm font-medium text-violet-200">{{ selectedLipSyncModel?.display_name || '对口型模型' }}</p>
                <p class="text-xs text-violet-100/80 mt-2">{{ lipSyncPriceHint || '价格由管理员在模型管理中配置' }}</p>
              </div>
            </div>

            <div>
              <label class="block text-sm text-gray-300 mb-2">配音文案</label>
              <textarea
                v-model="lipSyncText"
                rows="6"
                maxlength="1000"
                placeholder="请输入要生成配音的文本"
                class="w-full px-4 py-3 rounded-2xl bg-black/30 border border-white/10 text-white placeholder:text-gray-500 outline-none focus:border-violet-500/40 resize-none"
              />
              <div class="flex items-center justify-between mt-2 text-xs text-gray-500">
                <span>情感默认留空，语速固定 1.0</span>
                <span>{{ lipSyncText.length }}/1000</span>
              </div>
            </div>

            <div v-if="lipSyncTaskId || lipSyncPolling" class="rounded-2xl border border-amber-500/20 bg-amber-500/10 p-4 text-sm text-amber-100">
              <div class="flex items-center gap-2">
                <span class="w-4 h-4 rounded-full border-2 border-current border-t-transparent animate-spin"></span>
                <span>任务已提交，正在轮询 Seedance 结果{{ lipSyncTaskId ? `（任务ID: ${lipSyncTaskId}）` : '' }}</span>
              </div>
            </div>
          </div>

          <div class="px-6 py-5 border-t border-white/10 bg-white/5 flex items-center justify-between gap-4">
            <p class="text-xs text-gray-500">提交后会自动扣费并开始生成，完成后会刷新历史记录。</p>
            <div class="flex items-center gap-3">
              <button @click="closeLipSyncModal" class="px-4 py-2 rounded-xl border border-white/10 text-gray-300 hover:text-white hover:bg-white/5 transition-all">取消</button>
              <button
                @click="submitLipSync"
                :disabled="lipSyncSubmitting || lipSyncPolling"
                class="px-5 py-2.5 rounded-xl bg-gradient-to-r from-violet-500 to-fuchsia-500 text-white font-semibold disabled:opacity-50 transition-all"
              >
                <span v-if="lipSyncSubmitting">提交中...</span>
                <span v-else-if="lipSyncPolling">生成中...</span>
                <span v-else>开始对口型</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </Transition>

    <!-- Insufficient balance dialog -->
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
              <button @click="showInsufficientModal = false; router.push('/recharge')" class="flex-1 py-2.5 bg-gradient-to-r from-orange-500 to-amber-600 hover:from-orange-400 hover:to-amber-500 text-white rounded-xl text-sm font-bold transition-all shadow-lg shadow-orange-900/30">去充值</button>
            </div>
          </div>
        </div>
      </div>
    </Transition>

    <!-- Video player dialog -->
    <Transition name="modal">
      <div v-if="showVideoPlayer" class="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm" @click.self="closeVideoPlayer">
        <div class="relative w-full max-w-3xl mx-4">
          <button @click="closeVideoPlayer" class="absolute -top-10 right-0 text-white/70 hover:text-white transition-colors text-sm flex items-center gap-1">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
            </svg>
            关闭
          </button>
          <video :src="currentVideoUrl" controls autoplay class="w-full rounded-xl shadow-2xl" style="max-height: 80vh;"></video>
        </div>
      </div>
    </Transition>
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
