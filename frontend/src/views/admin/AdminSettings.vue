<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <h2 class="text-2xl font-bold text-white">系统设置</h2>
      <button
        @click="saveAllSettings"
        :disabled="!hasChanges || saving"
        class="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white rounded-lg transition-colors flex items-center gap-2"
      >
        <svg v-if="saving" class="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="m4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        {{ saving ? '保存中...' : '保存设置' }}
      </button>
    </div>

    <div v-if="loading" class="flex items-center justify-center py-20">
      <svg class="animate-spin h-8 w-8 text-blue-500" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="m4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
      </svg>
    </div>

    <div v-else class="space-y-6">
      <!-- 站点设置 -->
      <SettingsSection title="站点设置" icon="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6">
        <SettingsItem
          v-for="item in getByCategory('site')"
          :key="item.key"
          :item="item"
          v-model="editedValues[item.key]"
          :original="originalValues[item.key]"
        />
      </SettingsSection>

      <!-- 充值设置 -->
      <SettingsSection title="充值设置" icon="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z">
        <SettingsItem
          v-for="item in getByCategory('recharge')"
          :key="item.key"
          :item="item"
          v-model="editedValues[item.key]"
          :original="originalValues[item.key]"
        />
      </SettingsSection>

      <!-- 用户设置 -->
      <SettingsSection title="用户设置" icon="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z">
        <SettingsItem
          v-for="item in getByCategory('user')"
          :key="item.key"
          :item="item"
          v-model="editedValues[item.key]"
          :original="originalValues[item.key]"
        />
      </SettingsSection>

      <!-- 自动化设置 -->
      <SettingsSection title="自动化设置" icon="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z">
        <SettingsItem
          v-for="item in getByCategory('automation')"
          :key="item.key"
          :item="item"
          v-model="editedValues[item.key]"
          :original="originalValues[item.key]"
        />
      </SettingsSection>

      <!-- 安全设置 -->
      <SettingsSection title="安全设置" icon="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z">
        <SettingsItem
          v-for="item in getByCategory('security')"
          :key="item.key"
          :item="item"
          v-model="editedValues[item.key]"
          :original="originalValues[item.key]"
        />
      </SettingsSection>

      <!-- 存储管理 -->
      <div class="bg-slate-800/60 rounded-xl border border-slate-700/50 overflow-hidden">
        <div class="px-6 py-4 border-b border-slate-700/50 flex items-center gap-3">
          <svg class="w-5 h-5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" />
          </svg>
          <h3 class="text-lg font-semibold text-white">存储管理</h3>
        </div>
        <div class="p-6">
          <div v-if="storageStats" class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
            <div class="bg-slate-700/40 rounded-lg p-4">
              <p class="text-sm text-gray-400">上传图片</p>
              <p class="text-xl font-bold text-white mt-1">{{ storageStats.images_count || 0 }} 个</p>
              <p class="text-sm text-gray-500">{{ formatSize(storageStats.images_size || 0) }}</p>
            </div>
            <div class="bg-slate-700/40 rounded-lg p-4">
              <p class="text-sm text-gray-400">订单数据</p>
              <p class="text-xl font-bold text-white mt-1">{{ storageStats.orders_count || 0 }} 条</p>
            </div>
            <div class="bg-slate-700/40 rounded-lg p-4">
              <p class="text-sm text-gray-400">总占用空间</p>
              <p class="text-xl font-bold text-white mt-1">{{ formatSize(storageStats.total_size || 0) }}</p>
            </div>
          </div>
          <div class="flex gap-3">
            <button
              @click="loadStorageStats"
              :disabled="storageLoading"
              class="px-4 py-2 bg-slate-600 hover:bg-slate-500 text-white rounded-lg transition-colors text-sm disabled:opacity-50"
            >
              {{ storageLoading ? '加载中...' : '刷新统计' }}
            </button>
            <button
              @click="runCleanup"
              :disabled="cleanupRunning"
              class="px-4 py-2 bg-red-600/80 hover:bg-red-600 text-white rounded-lg transition-colors text-sm disabled:opacity-50"
            >
              {{ cleanupRunning ? '清理中...' : '手动清理' }}
            </button>
          </div>
        </div>
      </div>

      <!-- 修改密码 -->
      <div class="bg-slate-800/60 rounded-xl border border-slate-700/50 overflow-hidden">
        <div class="px-6 py-4 border-b border-slate-700/50 flex items-center gap-3">
          <svg class="w-5 h-5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
          </svg>
          <h3 class="text-lg font-semibold text-white">修改管理员密码</h3>
        </div>
        <div class="p-6 space-y-4">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-gray-300 mb-1">新密码</label>
              <input
                v-model="newPassword"
                type="password"
                placeholder="请输入新密码"
                class="w-full px-3 py-2 bg-slate-700/60 border border-slate-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-300 mb-1">确认密码</label>
              <input
                v-model="confirmPassword"
                type="password"
                placeholder="请再次输入新密码"
                class="w-full px-3 py-2 bg-slate-700/60 border border-slate-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>
          <button
            @click="changePassword"
            :disabled="!newPassword || !confirmPassword || changingPwd"
            class="px-4 py-2 bg-amber-600 hover:bg-amber-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white rounded-lg transition-colors text-sm"
          >
            {{ changingPwd ? '修改中...' : '修改密码' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 保存成功提示 -->
    <div
      v-if="showSaveSuccess"
      class="fixed bottom-6 right-6 bg-green-600 text-white px-5 py-3 rounded-lg shadow-xl flex items-center gap-2 z-50 animate-slide-up"
    >
      <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
      </svg>
      设置已保存
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, h } from 'vue'
import api from '../../api'

// ============ 子组件定义 ============

const SettingsSection = (props, { slots }) => {
  return h('div', { class: 'bg-slate-800/60 rounded-xl border border-slate-700/50 overflow-hidden' }, [
    h('div', { class: 'px-6 py-4 border-b border-slate-700/50 flex items-center gap-3' }, [
      h('svg', { class: 'w-5 h-5 text-blue-400', fill: 'none', stroke: 'currentColor', viewBox: '0 0 24 24', innerHTML: `<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="${props.icon}" />` }),
      h('h3', { class: 'text-lg font-semibold text-white' }, props.title)
    ]),
    h('div', { class: 'p-6 space-y-4' }, slots.default?.())
  ])
}
SettingsSection.props = ['title', 'icon']

const SettingsItem = (props, { emit }) => {
  const item = props.item
  const isChanged = JSON.stringify(props.modelValue) !== JSON.stringify(props.original)

  const inputEl = (() => {
    if (item.type === 'boolean') {
      return h('div', { class: 'flex items-center gap-3' }, [
        h('button', {
          class: [
            'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
            props.modelValue ? 'bg-blue-600' : 'bg-slate-600'
          ],
          onClick: () => emit('update:modelValue', !props.modelValue)
        }, [
          h('span', {
            class: [
              'inline-block h-4 w-4 transform rounded-full bg-white transition-transform',
              props.modelValue ? 'translate-x-6' : 'translate-x-1'
            ]
          })
        ]),
        h('span', { class: 'text-sm text-gray-400' }, props.modelValue ? '开启' : '关闭')
      ])
    } else if (item.type === 'number') {
      return h('input', {
        type: 'number',
        value: props.modelValue,
        step: item.key.includes('rate') ? '0.01' : '1',
        class: 'w-full max-w-xs px-3 py-2 bg-slate-700/60 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-blue-500',
        onInput: (e) => emit('update:modelValue', parseFloat(e.target.value) || 0)
      })
    } else {
      return h(item.key.includes('announcement') ? 'textarea' : 'input', {
        type: 'text',
        value: props.modelValue,
        rows: item.key.includes('announcement') ? 3 : undefined,
        class: 'w-full max-w-md px-3 py-2 bg-slate-700/60 border border-slate-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-blue-500',
        onInput: (e) => emit('update:modelValue', e.target.value)
      })
    }
  })()

  return h('div', {
    class: [
      'flex flex-col md:flex-row md:items-center justify-between gap-2 py-3',
      isChanged ? 'bg-blue-900/10 -mx-3 px-3 rounded-lg border border-blue-500/20' : ''
    ]
  }, [
    h('div', { class: 'flex-1' }, [
      h('div', { class: 'flex items-center gap-2' }, [
        h('label', { class: 'text-sm font-medium text-gray-200' }, item.description),
        isChanged
          ? h('span', { class: 'text-xs bg-blue-500/20 text-blue-300 px-1.5 py-0.5 rounded' }, '已修改')
          : null
      ]),
      h('p', { class: 'text-xs text-gray-500 mt-0.5' }, `配置项: ${item.key}`)
    ]),
    h('div', { class: 'md:w-64' }, [inputEl])
  ])
}
SettingsItem.props = ['item', 'modelValue', 'original']
SettingsItem.emits = ['update:modelValue']

// ============ 状态 ============

const loading = ref(true)
const saving = ref(false)
const showSaveSuccess = ref(false)
const configs = ref({})
const originalValues = reactive({})
const editedValues = reactive({})

const newPassword = ref('')
const confirmPassword = ref('')
const changingPwd = ref(false)

const storageStats = ref(null)
const storageLoading = ref(false)
const cleanupRunning = ref(false)

const hasChanges = computed(() => {
  for (const key in editedValues) {
    if (JSON.stringify(editedValues[key]) !== JSON.stringify(originalValues[key])) {
      return true
    }
  }
  return false
})

// ============ 方法 ============

function getByCategory(category) {
  return Object.entries(configs.value)
    .filter(([, v]) => v.category === category)
    .map(([key, v]) => ({ key, ...v }))
}

async function loadSettings() {
  loading.value = true
  try {
    const res = await api.get('/admin/config')
    configs.value = res.data.configs
    for (const [key, item] of Object.entries(res.data.configs)) {
      originalValues[key] = item.value
      editedValues[key] = item.value
    }
  } catch (e) {
    console.error('加载配置失败:', e)
  } finally {
    loading.value = false
  }
}

async function saveAllSettings() {
  saving.value = true
  try {
    const changedKeys = Object.keys(editedValues).filter(
      key => JSON.stringify(editedValues[key]) !== JSON.stringify(originalValues[key])
    )

    for (const key of changedKeys) {
      await api.patch('/admin/config', { key, value: editedValues[key] })
      originalValues[key] = editedValues[key]
    }

    showSaveSuccess.value = true
    setTimeout(() => { showSaveSuccess.value = false }, 2000)
  } catch (e) {
    alert('保存失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    saving.value = false
  }
}

async function loadStorageStats() {
  storageLoading.value = true
  try {
    const res = await api.get('/admin/storage/stats')
    storageStats.value = res.data.data || res.data
  } catch (e) {
    console.error('加载存储统计失败:', e)
  } finally {
    storageLoading.value = false
  }
}

async function runCleanup() {
  if (!confirm('确定要执行手动清理吗？这将删除过期的临时文件。')) return
  cleanupRunning.value = true
  try {
    await api.post('/admin/storage/cleanup')
    alert('清理完成')
    loadStorageStats()
  } catch (e) {
    alert('清理失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    cleanupRunning.value = false
  }
}

async function changePassword() {
  if (newPassword.value !== confirmPassword.value) {
    alert('两次输入的密码不一致')
    return
  }
  if (newPassword.value.length < 6) {
    alert('密码长度不能少于6位')
    return
  }
  changingPwd.value = true
  try {
    await api.post('/admin/change-password', { new_password: newPassword.value })
    alert('密码修改成功，请重新登录')
    newPassword.value = ''
    confirmPassword.value = ''
    localStorage.removeItem('adminToken')
    window.location.href = '/admin/login'
  } catch (e) {
    alert('修改失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    changingPwd.value = false
  }
}

function formatSize(bytes) {
  if (!bytes || bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  while (bytes >= 1024 && i < units.length - 1) { bytes /= 1024; i++ }
  return `${bytes.toFixed(1)} ${units[i]}`
}

// ============ 初始化 ============

onMounted(() => {
  loadSettings()
  loadStorageStats()
})
</script>

<style scoped>
.animate-slide-up {
  animation: slideUp 0.3s ease-out;
}
@keyframes slideUp {
  from { transform: translateY(20px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}
</style>
