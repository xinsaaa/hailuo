<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { adminLogin } from '../../api'

const router = useRouter()
const username = ref('')
const password = ref('')
const loading = ref(false)
const errorMessage = ref('')

const handleLogin = async () => {
  if (!username.value || !password.value) {
    errorMessage.value = '请输入用户名和密码'
    return
  }

  loading.value = true
  errorMessage.value = ''

  try {
    const result = await adminLogin(username.value, password.value)
    localStorage.setItem('adminToken', result.access_token)
    router.push('/admin/dashboard')
  } catch (err) {
    errorMessage.value = err.response?.data?.detail || '登录失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-gray-900 text-white font-sans">
    <div class="relative w-full max-w-md p-8 bg-gray-800 rounded-xl shadow-2xl border border-gray-700">
      <div class="mb-8 text-center">
        <h1 class="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-indigo-500">
          管理后台
        </h1>
        <p class="text-gray-400 mt-2 text-sm">Administrator Access</p>
      </div>

      <form @submit.prevent="handleLogin" class="space-y-6">
        <div>
          <label class="block text-sm font-medium text-gray-400 mb-2">用户名</label>
          <input 
            v-model="username" 
            type="text" 
            class="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all text-white placeholder-gray-500"
            placeholder="admin"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-400 mb-2">密码</label>
          <input 
            v-model="password" 
            type="password" 
            class="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all text-white placeholder-gray-500"
            placeholder="••••••••"
          />
        </div>

        <div v-if="errorMessage" class="text-red-400 text-sm text-center bg-red-900/20 py-2 rounded">
          {{ errorMessage }}
        </div>

        <button 
          type="submit" 
          :disabled="loading"
          class="w-full py-3 bg-gradient-to-r from-blue-500 to-indigo-600 hover:from-blue-600 hover:to-indigo-700 text-white font-semibold rounded-lg shadow-lg transform transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <span v-if="loading">登录中...</span>
          <span v-else>立即登录</span>
        </button>
      </form>
    </div>
  </div>
</template>
