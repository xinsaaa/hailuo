<script setup>
import { ref, onMounted, computed } from 'vue'
import { getAdminModels, updateAdminModel } from '../../api'

const models = ref([])
const loading = ref(false)
const updating = ref(null)
const editingPrice = ref(null)
const editingPrice10s = ref(null)
const editingPPS = ref(null)
const tempPrice = ref('')
const tempPrice10s = ref('')
const tempPPS = ref('')
const platformFilter = ref('all')

// ============ 矩阵定价弹窗 ============
const showMatrixModal = ref(false)
const matrixModel = ref(null) // 当前编辑矩阵的模型
const matrixData = ref({})    // 编辑中的矩阵数据
const matrixSaving = ref(false)

// 矩阵定价的分辨率和时长配置（根据模型动态计算）
const defaultResolutions = ['720p', '1080p']
const defaultDurations = [5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]

const matrixResolutions = computed(() => {
  const m = matrixModel.value
  if (!m) return defaultResolutions
  if (m.model_id === 'seedance_2_0_fast') return ['480p', '720p']
  if (m.model_id === 'seedance_2_0') return ['480p', '720p', '1080p']
  return defaultResolutions
})
const matrixDurations = computed(() => {
  const m = matrixModel.value
  if (!m) return defaultDurations
  if (m.model_id?.startsWith('seedance')) return [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
  return defaultDurations
})
const matrixTiers = [
  { key: 'text', label: '文生视频', color: 'blue' },
  { key: 'single_image', label: '单图模式', color: 'orange' },
  { key: 'dual_image', label: '双图模式', color: 'purple' },
]
const activeTier = ref('text')

const openMatrixEditor = (model) => {
  matrixModel.value = model
  const existing = model.pricing_matrix || {}

  // 检测旧格式：顶层直接是 720p/1080p 而非 text/single_image/dual_image
  const isOldFormat = !existing.text && !existing.single_image && !existing.dual_image && (existing['720p'] || existing['1080p'])

  const data = {}
  for (const tier of matrixTiers) {
    // 旧格式：所有tier共用同一份旧数据；新格式：各tier独立
    const tierExisting = isOldFormat ? existing : (existing[tier.key] || {})
    data[tier.key] = {}
    for (const res of matrixResolutions.value) {
      data[tier.key][res] = { per_second: 0, ...(tierExisting[res] || {}) }
      for (const d of matrixDurations.value) {
        if (data[tier.key][res][String(d)] === undefined) data[tier.key][res][String(d)] = 0
      }
    }
  }
  matrixData.value = data
  activeTier.value = 'text'
  showMatrixModal.value = true
}

const closeMatrixEditor = () => {
  showMatrixModal.value = false
  matrixModel.value = null
}

// 从per_second批量填充：用每秒单价自动填当前tier+res所有时长
const fillFromPerSecond = (res) => {
  const tierData = matrixData.value[activeTier.value]
  const pps = parseFloat(tierData[res].per_second) || 0
  if (pps <= 0) return
  for (const d of matrixDurations.value) {
    tierData[res][String(d)] = Math.round(pps * d * 100) / 100
  }
}

// 复制720p到1080p（按比例）
const copyResolution = (fromRes, toRes, ratio = 1) => {
  const tierData = matrixData.value[activeTier.value]
  const src = tierData[fromRes]
  if (!src) return
  for (const key of Object.keys(src)) {
    tierData[toRes][key] = Math.round((parseFloat(src[key]) || 0) * ratio * 100) / 100
  }
}

// 复制当前tier到其他tier（按比例）
const copyTierTo = (toTierKey, ratio = 1) => {
  const src = matrixData.value[activeTier.value]
  if (!src) return
  for (const res of matrixResolutions.value) {
    for (const key of Object.keys(src[res])) {
      matrixData.value[toTierKey][res][key] = Math.round((parseFloat(src[res][key]) || 0) * ratio * 100) / 100
    }
  }
}

const saveMatrix = async () => {
  if (!matrixModel.value) return
  matrixSaving.value = true
  try {
    const cleanMatrix = {}
    for (const tier of matrixTiers) {
      cleanMatrix[tier.key] = {}
      for (const res of matrixResolutions.value) {
        cleanMatrix[tier.key][res] = {}
        const pps = parseFloat(matrixData.value[tier.key][res].per_second) || 0
        if (pps > 0) cleanMatrix[tier.key][res].per_second = pps
        for (const d of matrixDurations.value) {
          const val = parseFloat(matrixData.value[tier.key][res][String(d)]) || 0
          if (val > 0) cleanMatrix[tier.key][res][String(d)] = val
        }
      }
    }
    await updateAdminModel(matrixModel.value.id, { pricing_matrix: cleanMatrix })
    matrixModel.value.pricing_matrix = cleanMatrix
    closeMatrixEditor()
    await loadModels()
  } catch (err) {
    alert('保存矩阵定价失败: ' + (err.response?.data?.detail || err.message))
  } finally {
    matrixSaving.value = false
  }
}

// 矩阵是否有有效数据（兼容旧两层和新三层结构）
const hasMatrixData = (model) => {
  if (!model.pricing_matrix) return false
  const pm = model.pricing_matrix
  // 新三层结构
  for (const tierKey of ['text', 'single_image', 'dual_image']) {
    const tier = pm[tierKey]
    if (!tier) continue
    for (const res of Object.values(tier)) {
      if (typeof res !== 'object') continue
      for (const [k, v] of Object.entries(res)) {
        if (v > 0) return true
      }
    }
  }
  // 旧两层结构（720p/1080p直接在顶层）
  for (const resKey of ['720p', '1080p']) {
    const res = pm[resKey]
    if (!res || typeof res !== 'object') continue
    for (const [k, v] of Object.entries(res)) {
      if (v > 0) return true
    }
  }
  return false
}

// 获取模型当前生效的定价模式描述
const getPricingMode = (model) => {
  if (hasMatrixData(model)) return '矩阵定价'
  if (model.price_per_second > 0) return '按秒计费'
  return '固定价格'
}

// 按平台筛选后的模型列表
const filteredModels = computed(() => {
  if (platformFilter.value === 'all') return models.value
  return models.value.filter(m => m.platform === platformFilter.value)
})

const loadModels = async () => {
  loading.value = true
  try {
    const data = await getAdminModels()
    models.value = data.models || []
  } catch (err) {
    console.error('加载模型失败', err)
  } finally {
    loading.value = false
  }
}

const toggleEnabled = async (model) => {
  updating.value = model.id
  try {
    await updateAdminModel(model.id, { is_enabled: !model.is_enabled })
    model.is_enabled = !model.is_enabled
  } catch (err) {
    alert('更新失败: ' + (err.response?.data?.detail || err.message))
  } finally {
    updating.value = null
  }
}

const setDefault = async (model) => {
  if (model.is_default) return
  updating.value = model.id
  try {
    await updateAdminModel(model.id, { is_default: true })
    models.value.forEach(m => m.is_default = m.id === model.id)
  } catch (err) {
    alert('设置默认失败: ' + (err.response?.data?.detail || err.message))
  } finally {
    updating.value = null
  }
}

const startEditPrice = (model) => { editingPrice.value = model.id; tempPrice.value = model.price?.toString() || '0.99' }
const cancelEditPrice = () => { editingPrice.value = null; tempPrice.value = '' }
const savePrice = async (model) => {
  const v = parseFloat(tempPrice.value)
  if (isNaN(v) || v < 0) { alert('请输入有效的价格'); return }
  updating.value = model.id
  try {
    await updateAdminModel(model.id, { price: v })
    model.price = v; editingPrice.value = null; tempPrice.value = ''
    await loadModels()
  } catch (err) { alert('更新价格失败: ' + (err.response?.data?.detail || err.message)) }
  finally { updating.value = null }
}

const startEditPrice10s = (model) => { editingPrice10s.value = model.id; tempPrice10s.value = model.price_10s?.toString() || '0' }
const cancelEditPrice10s = () => { editingPrice10s.value = null; tempPrice10s.value = '' }
const savePrice10s = async (model) => {
  const v = parseFloat(tempPrice10s.value)
  if (isNaN(v) || v < 0) { alert('请输入有效的价格'); return }
  updating.value = model.id
  try {
    await updateAdminModel(model.id, { price_10s: v })
    model.price_10s = v; editingPrice10s.value = null; tempPrice10s.value = ''
    await loadModels()
  } catch (err) { alert('更新10s价格失败: ' + (err.response?.data?.detail || err.message)) }
  finally { updating.value = null }
}

const startEditPPS = (model) => { editingPPS.value = model.id; tempPPS.value = model.price_per_second?.toString() || '0' }
const cancelEditPPS = () => { editingPPS.value = null; tempPPS.value = '' }
const savePPS = async (model) => {
  const v = parseFloat(tempPPS.value)
  if (isNaN(v) || v < 0) { alert('请输入有效的每秒单价'); return }
  updating.value = model.id
  try {
    await updateAdminModel(model.id, { price_per_second: v })
    model.price_per_second = v; editingPPS.value = null; tempPPS.value = ''
    await loadModels()
  } catch (err) { alert('更新每秒单价失败: ' + (err.response?.data?.detail || err.message)) }
  finally { updating.value = null }
}

onMounted(() => {
  loadModels()
})
</script>

<template>
  <div class="p-6">
    <div class="flex justify-between items-center mb-6">
      <h1 class="text-2xl font-bold text-gray-100 flex items-center gap-2">
        <span class="p-2 bg-blue-500/20 text-blue-400 rounded-lg">
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.384-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"></path></svg>
        </span>
        模型管理
      </h1>
      <div class="flex items-center gap-3">
        <!-- 平台筛选 -->
        <div class="flex items-center gap-1 p-1 bg-gray-800 rounded-lg border border-gray-700">
          <button 
            @click="platformFilter = 'all'"
            :class="platformFilter === 'all' ? 'bg-blue-500 text-white' : 'text-gray-400 hover:text-white'"
            class="px-3 py-1.5 text-sm font-medium rounded-md transition-all"
          >
            全部
          </button>
          <button 
            @click="platformFilter = 'hailuo'"
            :class="platformFilter === 'hailuo' ? 'bg-blue-500 text-white' : 'text-gray-400 hover:text-white'"
            class="px-3 py-1.5 text-sm font-medium rounded-md transition-all"
          >
            海螺
          </button>
          <button 
            @click="platformFilter = 'jimeng'"
            :class="platformFilter === 'jimeng' ? 'bg-violet-500 text-white' : 'text-gray-400 hover:text-white'"
            class="px-3 py-1.5 text-sm font-medium rounded-md transition-all"
          >
            即梦
          </button>
          <button 
            @click="platformFilter = 'kling'"
            :class="platformFilter === 'kling' ? 'bg-orange-500 text-white' : 'text-gray-400 hover:text-white'"
            class="px-3 py-1.5 text-sm font-medium rounded-md transition-all"
          >
            可灵
          </button>
        </div>
        <button @click="loadModels" class="flex items-center gap-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-all active:scale-95">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>
          刷新列表
        </button>
      </div>
    </div>
    
    <!-- 模型列表 -->
    <div class="bg-gray-800/50 backdrop-blur-xl border border-gray-700/50 rounded-2xl overflow-hidden shadow-xl">
      <div class="overflow-x-auto">
        <table class="min-w-full divide-y divide-gray-700/50">
          <thead class="bg-gray-900/50">
            <tr>
              <th scope="col" class="px-6 py-4 text-left text-xs font-semibold text-gray-400 uppercase tracking-wider">排序</th>
              <th scope="col" class="px-6 py-4 text-left text-xs font-semibold text-gray-400 uppercase tracking-wider">模型信息</th>
              <th scope="col" class="px-6 py-4 text-left text-xs font-semibold text-gray-400 uppercase tracking-wider">价格</th>
              <th scope="col" class="px-6 py-4 text-left text-xs font-semibold text-gray-400 uppercase tracking-wider">功能特性</th>
              <th scope="col" class="px-6 py-4 text-left text-xs font-semibold text-gray-400 uppercase tracking-wider">上传支持</th>
              <th scope="col" class="px-6 py-4 text-left text-xs font-semibold text-gray-400 uppercase tracking-wider">状态</th>
              <th scope="col" class="px-6 py-4 text-right text-xs font-semibold text-gray-400 uppercase tracking-wider">操作</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-700/50">
            <tr v-if="loading">
              <td colspan="7" class="px-6 py-20 text-center">
                <div class="flex flex-col items-center justify-center text-gray-500">
                  <svg class="animate-spin h-8 w-8 text-blue-500 mb-3" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  加载数据中...
                </div>
              </td>
            </tr>
            <tr v-else-if="filteredModels.length === 0">
              <td colspan="7" class="px-6 py-20 text-center text-gray-500">
                暂无模型数据
              </td>
            </tr>
            <tr v-for="model in filteredModels" :key="model.id" class="group hover:bg-gray-700/30 transition-colors duration-150">
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-400 font-mono">
                #{{ model.sort_order }}
              </td>
              <td class="px-6 py-4">
                <div class="flex items-center">
                  <div>
                    <div class="flex items-center gap-2">
                      <span class="text-sm font-bold text-white tracking-wide">{{ model.display_name }}</span>
                      <span v-if="model.badge" class="px-1.5 py-0.5 text-[10px] uppercase font-bold tracking-wider bg-gradient-to-r from-pink-500 to-rose-500 text-white rounded">
                        {{ model.badge }}
                      </span>
                      <span v-if="model.is_default" class="px-1.5 py-0.5 text-[10px] uppercase font-bold tracking-wider bg-yellow-500/20 text-yellow-400 border border-yellow-500/30 rounded">
                        默认
                      </span>
                    </div>
                    <div class="text-xs text-gray-500 mt-0.5">{{ model.name }}</div>
                  </div>
                </div>
                <div class="text-xs text-gray-400 mt-1 max-w-xs truncate" :title="model.description">
                  {{ model.description }}
                </div>
              </td>
              <!-- 价格编辑 -->
              <td class="px-6 py-4">
                <!-- 固定价格（所有平台通用） -->
                <div v-if="editingPrice === model.id" class="flex items-center gap-2 mb-1">
                  <span class="text-xs text-gray-500 w-10">固定</span>
                  <input v-model="tempPrice" type="number" step="0.01" min="0" class="w-20 px-2 py-1 text-sm bg-gray-700 border border-gray-600 rounded text-white focus:border-blue-500 focus:outline-none" @keyup.enter="savePrice(model)" @keyup.esc="cancelEditPrice" />
                  <button @click="savePrice(model)" class="text-green-400 hover:text-green-300"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg></button>
                  <button @click="cancelEditPrice" class="text-red-400 hover:text-red-300"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg></button>
                </div>
                <div v-else class="flex items-center gap-2 mb-1">
                  <span class="text-xs text-gray-500 w-10">固定</span>
                  <span class="text-sm font-bold text-emerald-400">¥{{ model.price?.toFixed(2) || '0.99' }}</span>
                  <button @click="startEditPrice(model)" class="text-gray-400 hover:text-white opacity-0 group-hover:opacity-100 transition-opacity"><svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"></path></svg></button>
                </div>
                <!-- 10s价格（海螺） -->
                <template v-if="model.platform === 'hailuo'">
                  <div v-if="editingPrice10s === model.id" class="flex items-center gap-2 mb-1">
                    <span class="text-xs text-gray-500 w-10">10s</span>
                    <input v-model="tempPrice10s" type="number" step="0.01" min="0" class="w-20 px-2 py-1 text-sm bg-gray-700 border border-gray-600 rounded text-white focus:border-amber-500 focus:outline-none" @keyup.enter="savePrice10s(model)" @keyup.esc="cancelEditPrice10s" />
                    <button @click="savePrice10s(model)" class="text-green-400 hover:text-green-300"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg></button>
                    <button @click="cancelEditPrice10s" class="text-red-400 hover:text-red-300"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg></button>
                  </div>
                  <div v-else class="flex items-center gap-2 mb-1">
                    <span class="text-xs text-gray-500 w-10">10s</span>
                    <span class="text-sm font-bold text-amber-400">¥{{ model.price_10s?.toFixed(2) || '0.00' }}</span>
                    <button @click="startEditPrice10s(model)" class="text-gray-400 hover:text-white opacity-0 group-hover:opacity-100 transition-opacity"><svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"></path></svg></button>
                  </div>
                </template>
                <!-- 每秒单价（即梦） -->
                <template v-if="model.platform === 'jimeng'">
                  <div v-if="editingPPS === model.id" class="flex items-center gap-2">
                    <span class="text-xs text-gray-500 w-10">每秒</span>
                    <input v-model="tempPPS" type="number" step="0.01" min="0" class="w-20 px-2 py-1 text-sm bg-gray-700 border border-gray-600 rounded text-white focus:border-violet-500 focus:outline-none" @keyup.enter="savePPS(model)" @keyup.esc="cancelEditPPS" />
                    <button @click="savePPS(model)" class="text-green-400 hover:text-green-300"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg></button>
                    <button @click="cancelEditPPS" class="text-red-400 hover:text-red-300"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg></button>
                  </div>
                  <div v-else class="flex items-center gap-2">
                    <span class="text-xs text-gray-500 w-10">每秒</span>
                    <span class="text-sm font-bold text-violet-400">¥{{ model.price_per_second?.toFixed(2) || '0.00' }}/s</span>
                    <button @click="startEditPPS(model)" class="text-gray-400 hover:text-white opacity-0 group-hover:opacity-100 transition-opacity"><svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"></path></svg></button>
                  </div>
                </template>
                <!-- 矩阵定价按钮（可灵 & SeeDance） -->
                <template v-if="model.platform === 'kling' || model.model_id?.startsWith('seedance')">
                  <div class="flex items-center gap-2 mt-1">
                    <button @click="openMatrixEditor(model)" class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-all border" :class="hasMatrixData(model) ? 'bg-orange-500/10 text-orange-400 border-orange-500/30 hover:bg-orange-500/20' : 'bg-gray-700/50 text-gray-400 border-gray-600 hover:bg-gray-700 hover:text-white'">
                      <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 10h16M4 14h16M4 18h16"></path></svg>
                      {{ hasMatrixData(model) ? '编辑矩阵定价' : '设置矩阵定价' }}
                    </button>
                    <span class="text-[10px] px-1.5 py-0.5 rounded" :class="getPricingMode(model) === '矩阵定价' ? 'bg-orange-500/20 text-orange-400' : 'bg-gray-700 text-gray-500'">{{ getPricingMode(model) }}</span>
                  </div>
                </template>
              </td>
              <td class="px-6 py-4">
                <div class="flex flex-wrap gap-1.5">
                  <span v-for="f in model.features" :key="f" class="px-2 py-1 text-xs bg-gray-700/50 text-gray-300 border border-gray-600/50 rounded-md">
                    {{ f }}
                  </span>
                </div>
              </td>
              <td class="px-6 py-4 whitespace-nowrap">
                <div class="flex items-center gap-1.5">
                  <div class="w-2 h-2 rounded-full" :class="model.supports_last_frame ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]' : 'bg-gray-600'"></div>
                  <span class="text-sm" :class="model.supports_last_frame ? 'text-gray-200' : 'text-gray-500'">
                    {{ model.supports_last_frame ? '首尾帧支持' : '仅首帧' }}
                  </span>
                </div>
              </td>
              <td class="px-6 py-4 whitespace-nowrap">
                <span class="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border"
                      :class="model.is_enabled ? 'bg-green-500/10 text-green-400 border-green-500/20' : 'bg-red-500/10 text-red-400 border-red-500/20'">
                  {{ model.is_enabled ? '已启用' : '已禁用' }}
                </span>
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                <div class="flex items-center justify-end gap-2">
                  <button 
                    v-if="!model.is_default"
                    @click="setDefault(model)" 
                    :disabled="updating === model.id"
                    class="text-xs text-blue-400 hover:text-blue-300 hover:underline disabled:opacity-50 disabled:no-underline px-2 py-1"
                  >
                    设为默认
                  </button>
                  
                  <button 
                    @click="toggleEnabled(model)"
                    :disabled="updating === model.id"
                    :class="[
                      model.is_enabled 
                        ? 'bg-red-500/10 text-red-400 border-red-500/30 hover:bg-red-500/20' 
                        : 'bg-green-500/10 text-green-400 border-green-500/30 hover:bg-green-500/20',
                      'border px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200 disabled:opacity-50 flex items-center gap-1.5'
                    ]"
                  >
                    <span v-if="updating === model.id" class="animate-spin h-3 w-3 border-2 border-current border-t-transparent rounded-full"></span>
                    {{ model.is_enabled ? '禁用' : '启用' }}
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    
    <!-- 提示信息 -->
    <div class="mt-6 flex gap-4 p-4 bg-blue-900/20 border border-blue-500/20 rounded-xl">
      <div class="text-blue-400 mt-0.5">
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
      </div>
      <div class="text-sm text-blue-100/80 space-y-1">
        <p class="font-medium text-blue-200">配置说明</p>
        <p>• 禁用模型后，用户前端将无法看到该选项。</p>
        <p>• 默认模型将在用户未手动选择时自动应用。</p>
        <p>• <span class="text-blue-300 font-medium">可灵定价</span>：矩阵定价 &gt; 固定价格。矩阵定价分三档（文生视频/单图/双图），每档可为每个分辨率×时长组合单独设价。</p>
        <p>• <span class="text-blue-300 font-medium">海螺定价</span>：固定价格(6s) + 10s价格。</p>
        <p>• <span class="text-blue-300 font-medium">即梦定价</span>：每秒单价 &gt; 固定价格。</p>
      </div>
    </div>

    <!-- 矩阵定价编辑弹窗 -->
    <Teleport to="body">
      <Transition name="modal">
        <div v-if="showMatrixModal" class="fixed inset-0 z-[100] flex items-center justify-center">
          <div class="absolute inset-0 bg-black/60 backdrop-blur-sm" @click="closeMatrixEditor"></div>
          <div class="relative bg-[#1a1d23] border border-gray-700/50 rounded-2xl shadow-2xl w-[900px] max-h-[85vh] overflow-hidden">
            <!-- 弹窗头部 -->
            <div class="flex items-center justify-between px-6 py-4 border-b border-gray-700/50 bg-gray-900/50">
              <div>
                <h3 class="text-lg font-bold text-white flex items-center gap-2">
                  <span class="w-1 h-5 rounded-full bg-orange-500"></span>
                  矩阵定价 — {{ matrixModel?.display_name }}
                </h3>
                <p class="text-xs text-gray-400 mt-1">为每个分辨率×时长组合设置独立价格，0表示使用每秒单价计算</p>
              </div>
              <button @click="closeMatrixEditor" class="p-2 text-gray-400 hover:text-white hover:bg-white/10 rounded-lg transition-all">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
              </button>
            </div>

            <!-- 弹窗内容 -->
            <div class="p-6 overflow-y-auto max-h-[calc(85vh-140px)]">
              <!-- Tier Tab 切换 -->
              <div class="flex items-center gap-2 mb-5">
                <button
                  v-for="tier in matrixTiers" :key="tier.key"
                  @click="activeTier = tier.key"
                  class="px-4 py-2 text-sm font-medium rounded-lg transition-all border"
                  :class="activeTier === tier.key
                    ? (tier.color === 'blue' ? 'bg-blue-500/20 text-blue-400 border-blue-500/40' : tier.color === 'orange' ? 'bg-orange-500/20 text-orange-400 border-orange-500/40' : 'bg-purple-500/20 text-purple-400 border-purple-500/40')
                    : 'bg-gray-800 text-gray-400 border-gray-700 hover:text-white hover:bg-gray-700'"
                >{{ tier.label }}</button>
                <div class="flex-1"></div>
                <!-- 复制当前tab到其他tab -->
                <template v-for="tier in matrixTiers" :key="'copy-'+tier.key">
                  <button
                    v-if="tier.key !== activeTier"
                    @click="copyTierTo(tier.key, 1)"
                    class="px-2 py-1 text-[10px] bg-gray-700 text-gray-400 rounded hover:bg-gray-600 hover:text-white transition-all"
                  >复制到{{ tier.label }}</button>
                  <button
                    v-if="tier.key !== activeTier"
                    @click="copyTierTo(tier.key, 1.5)"
                    class="px-2 py-1 text-[10px] bg-gray-700 text-gray-400 rounded hover:bg-gray-600 hover:text-white transition-all"
                  >→{{ tier.label }}(1.5x)</button>
                </template>
              </div>

              <!-- 当前Tier的分辨率定价 -->
              <div v-for="res in matrixResolutions" :key="res" class="mb-6 last:mb-0">
                <div class="flex items-center justify-between mb-3">
                  <div class="flex items-center gap-3">
                    <span class="text-sm font-bold text-white px-3 py-1 rounded-lg" :class="res === '1080p' ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30' : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'">{{ res }}</span>
                    <div class="flex items-center gap-2">
                      <span class="text-xs text-gray-400">每秒单价</span>
                      <input
                        v-model.number="matrixData[activeTier][res].per_second"
                        type="number" step="0.01" min="0"
                        class="w-20 px-2 py-1 text-sm bg-gray-800 border border-gray-600 rounded text-orange-400 font-bold focus:border-orange-500 focus:outline-none text-center"
                        placeholder="0"
                      />
                      <span class="text-xs text-gray-500">元/秒</span>
                      <button @click="fillFromPerSecond(res)" class="px-2 py-1 text-[10px] bg-orange-500/10 text-orange-400 border border-orange-500/30 rounded hover:bg-orange-500/20 transition-all">
                        一键填充
                      </button>
                    </div>
                  </div>
                  <div class="flex items-center gap-2">
                    <template v-if="res === '1080p'">
                      <button @click="copyResolution('720p', '1080p', 1)" class="px-2 py-1 text-[10px] bg-gray-700 text-gray-300 rounded hover:bg-gray-600 transition-all">复制720p (1x)</button>
                      <button @click="copyResolution('720p', '1080p', 1.3)" class="px-2 py-1 text-[10px] bg-gray-700 text-gray-300 rounded hover:bg-gray-600 transition-all">复制720p (1.3x)</button>
                    </template>
                  </div>
                </div>

                <!-- 时长价格网格 -->
                <div class="grid gap-1" :style="{gridTemplateColumns: `repeat(${matrixDurations.length}, minmax(0, 1fr))`}">
                  <div v-for="d in matrixDurations" :key="d" class="flex flex-col items-center">
                    <span class="text-[10px] text-gray-500 mb-1 font-mono">{{ d }}s</span>
                    <input
                      v-model.number="matrixData[activeTier][res][String(d)]"
                      type="number" step="0.01" min="0"
                      class="w-full px-1 py-1.5 text-xs bg-gray-800 border rounded text-center font-mono focus:outline-none transition-colors"
                      :class="(matrixData[activeTier][res][String(d)] || 0) > 0 ? 'border-orange-500/40 text-orange-300 bg-orange-500/5' : 'border-gray-700 text-gray-500'"
                      placeholder="0"
                    />
                    <span v-if="matrixData[activeTier][res].per_second > 0 && !(matrixData[activeTier][res][String(d)] > 0)" class="text-[9px] text-gray-600 mt-0.5">
                      ≈{{ (matrixData[activeTier][res].per_second * d).toFixed(2) }}
                    </span>
                  </div>
                </div>
              </div>

              <!-- 预览表格 -->
              <div class="mt-6 p-4 bg-gray-900/50 rounded-xl border border-gray-700/30">
                <h4 class="text-xs font-bold text-gray-300 mb-2">当前「{{ matrixTiers.find(t => t.key === activeTier)?.label }}」价格预览</h4>
                <div class="overflow-x-auto">
                  <table class="w-full text-xs">
                    <thead>
                      <tr>
                        <th class="text-left text-gray-500 py-1 px-2">分辨率</th>
                        <th v-for="d in matrixDurations" :key="d" class="text-center text-gray-500 py-1 px-1 font-mono">{{ d }}s</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="res in matrixResolutions" :key="res" class="border-t border-gray-800">
                        <td class="py-1.5 px-2 font-bold" :class="res === '1080p' ? 'text-blue-400' : 'text-emerald-400'">{{ res }}</td>
                        <td v-for="d in matrixDurations" :key="d" class="text-center py-1.5 px-1 font-mono"
                            :class="(matrixData[activeTier][res][String(d)] || 0) > 0 ? 'text-orange-400 font-bold' : matrixData[activeTier][res].per_second > 0 ? 'text-gray-400' : 'text-gray-600'">
                          ¥{{ ((matrixData[activeTier][res][String(d)] || 0) > 0 ? matrixData[activeTier][res][String(d)] : (matrixData[activeTier][res].per_second > 0 ? (matrixData[activeTier][res].per_second * d) : 0)).toFixed(2) }}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <p class="text-[10px] text-gray-600 mt-2">橙色 = 精确定价，灰色 = 由每秒单价自动计算</p>
              </div>
            </div>

            <!-- 弹窗底部 -->
            <div class="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-700/50 bg-gray-900/30">
              <button @click="closeMatrixEditor" class="px-4 py-2 text-sm text-gray-400 hover:text-white bg-gray-800 hover:bg-gray-700 rounded-lg border border-gray-700 transition-all">
                取消
              </button>
              <button @click="saveMatrix" :disabled="matrixSaving" class="px-6 py-2 text-sm font-medium text-white bg-gradient-to-r from-orange-500 to-amber-500 hover:brightness-110 rounded-lg shadow-lg shadow-orange-900/30 transition-all disabled:opacity-50 flex items-center gap-2">
                <span v-if="matrixSaving" class="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full"></span>
                {{ matrixSaving ? '保存中...' : '保存矩阵定价' }}
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
.grid-cols-11 {
  grid-template-columns: repeat(11, minmax(0, 1fr));
}
.modal-enter-active, .modal-leave-active {
  transition: all 0.2s ease;
}
.modal-enter-from, .modal-leave-to {
  opacity: 0;
}
.modal-enter-from .relative, .modal-leave-to .relative {
  transform: scale(0.95);
}
</style>
