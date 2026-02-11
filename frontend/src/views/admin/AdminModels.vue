<script setup>
import { ref, onMounted } from 'vue'
import { getAdminModels, updateAdminModel } from '../../api'

const models = ref([])
const loading = ref(false)
const updating = ref(null) // 正在更新的模型 ID
const editingPrice = ref(null) // 正在编辑价格的模型 ID
const tempPrice = ref('') // 临时价格输入

// 加载模型列表
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

// 切换启用状态
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

// 设置为默认模型
const setDefault = async (model) => {
  if (model.is_default) return
  updating.value = model.id
  try {
    await updateAdminModel(model.id, { is_default: true })
    // 更新本地状态
    models.value.forEach(m => m.is_default = m.id === model.id)
  } catch (err) {
    alert('设置默认失败: ' + (err.response?.data?.detail || err.message))
  } finally {
    updating.value = null
  }
}

// 开始编辑价格
const startEditPrice = (model) => {
  editingPrice.value = model.id
  tempPrice.value = model.price?.toString() || '0.99'
}

// 取消编辑价格
const cancelEditPrice = () => {
  editingPrice.value = null
  tempPrice.value = ''
}

// 保存价格
const savePrice = async (model) => {
  const newPrice = parseFloat(tempPrice.value)
  if (isNaN(newPrice) || newPrice < 0) {
    alert('请输入有效的价格')
    return
  }
  
  updating.value = model.id
  try {
    await updateAdminModel(model.id, { price: newPrice })
    // 更新本地状态
    model.price = newPrice
    editingPrice.value = null
    tempPrice.value = ''
    // 重新加载数据确保同步
    await loadModels()
  } catch (err) {
    alert('更新价格失败: ' + (err.response?.data?.detail || err.message))
  } finally {
    updating.value = null
  }
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
      <button @click="loadModels" class="flex items-center gap-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-all active:scale-95">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>
        刷新列表
      </button>
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
            <tr v-else-if="models.length === 0">
              <td colspan="7" class="px-6 py-20 text-center text-gray-500">
                暂无模型数据
              </td>
            </tr>
            <tr v-for="model in models" :key="model.id" class="group hover:bg-gray-700/30 transition-colors duration-150">
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
              <td class="px-6 py-4 whitespace-nowrap">
                <div v-if="editingPrice === model.id" class="flex items-center gap-2">
                  <input 
                    v-model="tempPrice"
                    type="number"
                    step="0.01"
                    min="0"
                    class="w-20 px-2 py-1 text-sm bg-gray-700 border border-gray-600 rounded text-white focus:border-blue-500 focus:outline-none"
                    @keyup.enter="savePrice(model)"
                    @keyup.esc="cancelEditPrice"
                  />
                  <button @click="savePrice(model)" class="text-green-400 hover:text-green-300" title="保存">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
                  </button>
                  <button @click="cancelEditPrice" class="text-red-400 hover:text-red-300" title="取消">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                  </button>
                </div>
                <div v-else class="flex items-center gap-2">
                  <span class="text-sm font-bold text-emerald-400">¥{{ model.price?.toFixed(2) || '0.99' }}</span>
                  <button @click="startEditPrice(model)" class="text-gray-400 hover:text-white opacity-0 group-hover:opacity-100 transition-opacity" title="编辑价格">
                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"></path></svg>
                  </button>
                </div>
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
        <p>• 尾帧上传功能由 "supports_last_frame" 字段控制，仅特定模型支持。</p>
      </div>
    </div>
  </div>
</template>
