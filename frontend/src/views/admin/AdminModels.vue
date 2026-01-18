<script setup>
import { ref, onMounted } from 'vue'
import { getAdminModels, updateAdminModel } from '../../api'

const models = ref([])
const loading = ref(false)
const updating = ref(null) // 正在更新的模型 ID

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

onMounted(() => {
  loadModels()
})
</script>

<template>
  <div class="p-6">
    <div class="flex justify-between items-center mb-6">
      <h1 class="text-2xl font-bold text-gray-900">模型管理</h1>
      <button @click="loadModels" class="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600">
        刷新
      </button>
    </div>
    
    <!-- 模型列表 -->
    <div class="bg-white rounded-xl shadow overflow-hidden">
      <table class="min-w-full divide-y divide-gray-200">
        <thead class="bg-gray-50">
          <tr>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">排序</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">模型名称</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">描述</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">功能</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">尾帧</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">状态</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">默认</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">操作</th>
          </tr>
        </thead>
        <tbody class="bg-white divide-y divide-gray-200">
          <tr v-if="loading">
            <td colspan="8" class="px-6 py-12 text-center text-gray-500">加载中...</td>
          </tr>
          <tr v-else-if="models.length === 0">
            <td colspan="8" class="px-6 py-12 text-center text-gray-500">暂无模型数据</td>
          </tr>
          <tr v-for="model in models" :key="model.id" class="hover:bg-gray-50">
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
              {{ model.sort_order }}
            </td>
            <td class="px-6 py-4 whitespace-nowrap">
              <div class="flex items-center gap-2">
                <span class="font-medium text-gray-900">{{ model.display_name }}</span>
                <span v-if="model.badge" class="px-2 py-0.5 text-xs bg-blue-100 text-blue-800 rounded">
                  {{ model.badge }}
                </span>
              </div>
              <div class="text-xs text-gray-400">{{ model.name }}</div>
            </td>
            <td class="px-6 py-4 text-sm text-gray-500 max-w-xs truncate">
              {{ model.description }}
            </td>
            <td class="px-6 py-4">
              <div class="flex flex-wrap gap-1">
                <span v-for="f in model.features" :key="f" class="px-2 py-0.5 text-xs bg-gray-100 text-gray-600 rounded">
                  {{ f }}
                </span>
              </div>
            </td>
            <td class="px-6 py-4 whitespace-nowrap">
              <span :class="model.supports_last_frame ? 'text-green-600' : 'text-gray-400'">
                {{ model.supports_last_frame ? '✓ 支持' : '✗ 不支持' }}
              </span>
            </td>
            <td class="px-6 py-4 whitespace-nowrap">
              <span :class="model.is_enabled ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'"
                    class="px-2 py-1 text-xs font-medium rounded-full">
                {{ model.is_enabled ? '已启用' : '已禁用' }}
              </span>
            </td>
            <td class="px-6 py-4 whitespace-nowrap">
              <span v-if="model.is_default" class="text-yellow-500">⭐ 默认</span>
              <button v-else @click="setDefault(model)" 
                      :disabled="updating === model.id"
                      class="text-sm text-blue-500 hover:text-blue-700 disabled:opacity-50">
                设为默认
              </button>
            </td>
            <td class="px-6 py-4 whitespace-nowrap">
              <button 
                @click="toggleEnabled(model)"
                :disabled="updating === model.id"
                :class="model.is_enabled ? 'bg-red-500 hover:bg-red-600' : 'bg-green-500 hover:bg-green-600'"
                class="px-3 py-1 text-white text-sm rounded disabled:opacity-50"
              >
                {{ updating === model.id ? '...' : (model.is_enabled ? '禁用' : '启用') }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    
    <!-- 提示信息 -->
    <div class="mt-4 p-4 bg-blue-50 rounded-lg text-sm text-blue-800">
      <p><strong>提示：</strong></p>
      <ul class="list-disc list-inside mt-1 space-y-1">
        <li>禁用的模型不会在用户端显示</li>
        <li>默认模型会在用户未选择时自动使用</li>
        <li>仅 海螺 2.0、Beta 3.1、Beta 3.1 Fast 支持首尾帧上传</li>
      </ul>
    </div>
  </div>
</template>
