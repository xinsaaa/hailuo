<template>
  <div class="space-y-6">
    <!-- Toast 通知 -->
    <div v-if="showToast" class="fixed top-4 right-4 z-50 px-4 py-3 rounded-xl shadow-lg text-sm font-medium transition-all"
      :class="toastType === 'success' ? 'bg-green-500/90 text-white' : toastType === 'error' ? 'bg-red-500/90 text-white' : 'bg-blue-500/90 text-white'">
      {{ toastMessage }}
    </div>

    <!-- 页面头部 -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-3">
        <div class="w-2 h-2 rounded-full shadow-[0_0_8px_rgba(59,130,246,0.8)]"
          :class="systemStatus.is_running ? 'bg-green-400 shadow-[0_0_8px_rgba(74,222,128,0.8)]' : 'bg-yellow-400 shadow-[0_0_8px_rgba(250,204,21,0.8)]'"></div>
        <h1 class="text-2xl font-bold text-white">多账号智能调度</h1>
        <span class="px-2 py-0.5 text-xs font-bold bg-blue-500/20 text-blue-400 border border-blue-500/30 rounded">
          {{ systemStatus.is_running ? '运行中' : '启动中' }}
        </span>
      </div>
      <div class="text-sm text-gray-400">
        共 <span class="text-white font-bold">{{ performance.total_accounts }}</span> 个账号，
        <span class="text-green-400 font-bold">{{ performance.active_accounts }}</span> 个活跃，
        <span class="text-blue-400 font-bold">{{ performance.available_slots }}</span> 个可用槽位
      </div>
    </div>

    <!-- 系统状态概览 -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div class="bg-gray-800 p-6 rounded-xl border border-gray-700">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-gray-400 text-sm">总账号数</p>
              <p class="text-2xl font-bold text-white">{{ performance.total_accounts }}</p>
            </div>
            <div class="w-12 h-12 bg-blue-500/20 rounded-lg flex items-center justify-center">
              <svg class="w-6 h-6 text-blue-400" fill="currentColor" viewBox="0 0 20 20">
                <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
              </svg>
            </div>
          </div>
        </div>

        <div class="bg-gray-800 p-6 rounded-xl border border-gray-700">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-gray-400 text-sm">活跃账号</p>
              <p class="text-2xl font-bold text-green-400">{{ performance.active_accounts }}</p>
            </div>
            <div class="w-12 h-12 bg-green-500/20 rounded-lg flex items-center justify-center">
              <svg class="w-6 h-6 text-green-400" fill="currentColor" viewBox="0 0 20 20">
                <path d="M10 12a2 2 0 100-4 2 2 0 000 4z"/>
                <path fill-rule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clip-rule="evenodd"/>
              </svg>
            </div>
          </div>
        </div>

        <div class="bg-gray-800 p-6 rounded-xl border border-gray-700">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-gray-400 text-sm">系统负载</p>
              <p class="text-2xl font-bold" :class="getLoadColor(performance.utilization)">
                {{ (performance.utilization * 100).toFixed(1) }}%
              </p>
            </div>
            <div class="w-12 h-12 bg-yellow-500/20 rounded-lg flex items-center justify-center">
              <svg class="w-6 h-6 text-yellow-400" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M3 4a1 1 0 011-1h12a1 1 0 011 1v2a1 1 0 01-1 1H4a1 1 0 01-1-1V4zm0 4a1 1 0 011-1h12a1 1 0 011 1v2a1 1 0 01-1 1H4a1 1 0 01-1-1V8zm0 4a1 1 0 011-1h12a1 1 0 011 1v2a1 1 0 01-1 1H4a1 1 0 01-1-1v-2z" clip-rule="evenodd"/>
              </svg>
            </div>
          </div>
        </div>

        <div class="bg-gray-800 p-6 rounded-xl border border-gray-700">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-gray-400 text-sm">可用槽位</p>
              <p class="text-2xl font-bold text-blue-400">{{ performance.available_slots }}</p>
            </div>
            <div class="w-12 h-12 bg-purple-500/20 rounded-lg flex items-center justify-center">
              <svg class="w-6 h-6 text-purple-400" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clip-rule="evenodd"/>
              </svg>
            </div>
          </div>
      </div>
    </div>

    <!-- 操作按钮栏 -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-3">
        <button
          @click="showAddModal = true"
          class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg font-medium transition-colors flex items-center gap-2"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"/>
          </svg>
          添加账号
        </button>
        <button
          @click="refreshAccounts"
          :disabled="loading"
          class="bg-gray-700 hover:bg-gray-600 text-white px-4 py-2 rounded-lg font-medium transition-colors flex items-center gap-2"
        >
          <svg class="w-4 h-4" :class="{ 'animate-spin': loading }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
          </svg>
          {{ loading ? '刷新中...' : '刷新状态' }}
        </button>
      </div>
      <div class="flex items-center gap-2">
        <span class="text-sm text-gray-400">性能等级:</span>
        <span class="px-3 py-1 rounded-full text-sm font-medium" :class="getPerformanceClass(performance.performance_level)">
          {{ performance.performance_level }}
        </span>
      </div>
    </div>

    <!-- 账号列表 -->
    <div class="bg-gray-800/50 rounded-2xl border border-gray-700/50 shadow-xl overflow-hidden">
      <div class="p-4 border-b border-gray-700 flex items-center gap-2">
        <svg class="w-5 h-5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"/>
        </svg>
        <h3 class="text-lg font-semibold text-white">账号管理</h3>
      </div>
        
        <div class="overflow-x-auto">
          <table class="w-full">
            <thead class="bg-gray-700/50">
              <tr>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">账号信息</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">状态</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">积分</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">负载情况</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">优先级</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">操作</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-700">
              <tr v-for="account in accounts" :key="account.account_id" class="hover:bg-gray-700/30">
                <td class="px-6 py-4 whitespace-nowrap">
                  <div>
                    <div class="text-sm font-medium text-white flex items-center gap-2">
                      {{ account.display_name }}
                      <span class="px-1.5 py-0.5 text-[10px] font-bold rounded"
                        :class="account.series === '3.1' ? 'bg-purple-500/20 text-purple-400 border border-purple-500/30' : 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30'">
                        {{ account.series || '2.3' }}系列
                      </span>
                    </div>
                    <div class="text-sm text-gray-400">{{ account.phone_number }}</div>
                    <div class="text-xs text-gray-500">ID: {{ account.account_id }}</div>
                  </div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                  <div class="flex flex-col space-y-1">
                    <span class="inline-flex px-2 py-1 text-xs font-semibold rounded-full" 
                      :class="account.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'">
                      {{ account.is_active ? '激活' : '禁用' }}
                    </span>
                    <span class="inline-flex px-2 py-1 text-xs font-semibold rounded-full"
                      :class="account.is_logged_in ? 'bg-blue-100 text-blue-800' : 'bg-red-100 text-red-800'">
                      {{ account.is_logged_in ? '已登录' : '未登录' }}
                    </span>
                  </div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                  <div class="flex items-center space-x-2">
                    <div class="flex items-center space-x-1">
                      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg" class="text-yellow-400">
                        <path d="M8.00048 1.82032C6.45773 1.81807 5.19485 2.38132 4.46364 3.58012C4.43766 3.62272 4.42779 3.67378 4.43462 3.72321C4.77643 6.19795 5.30049 8.145 5.40694 8.27814C4.92051 7.79389 4.28303 6.2985 3.68679 4.55829C3.66021 4.48072 3.59361 4.42262 3.51225 4.41238C2.63633 4.55829 1.57668 5.5607 1.25741 6.41925C-0.0504929 9.93425 4.9445 12.3503 4.9445 12.3503C4.9445 12.3503 5.47745 13.2418 6.06218 13.5395C6.44152 13.7327 6.98931 13.5734 7.32494 13.5395C8.01775 13.4697 7.91795 13.4697 8.61077 13.5395C8.94639 13.5734 9.51083 13.7193 9.87461 13.5395C10.475 13.2429 10.8305 12.3503 10.8305 12.3503C10.8305 12.3503 16.0386 9.93425 14.7306 6.41925C14.4114 5.5607 13.3517 4.55829 12.4758 4.41238C12.3944 4.42262 12.3279 4.48072 12.3013 4.55829C11.705 6.2985 11.0676 7.79389 10.5811 8.27814C10.6876 8.145 11.2116 6.19795 11.5534 3.72321C11.5603 3.67378 11.5504 3.62272 11.5244 3.58012C10.7932 2.38132 9.53872 1.82256 8.00048 1.82032Z" fill="currentColor"></path>
                      </svg>
                      <span class="text-sm font-medium text-white">
                        {{ account.credits >= 0 ? account.credits : '--' }}
                      </span>
                    </div>
                    <button 
                      v-if="account.is_logged_in"
                      @click="refreshCredits(account.account_id)"
                      class="text-blue-400 hover:text-blue-300 text-xs"
                      title="刷新积分"
                    >
                      🔄
                    </button>
                  </div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                  <div>
                    <div class="flex items-center">
                      <div class="flex-1 bg-gray-600 rounded-full h-2 mr-2">
                        <div class="bg-blue-500 h-2 rounded-full" 
                          :style="{ width: (account.utilization * 100) + '%' }"></div>
                      </div>
                      <span class="text-sm text-gray-300">{{ (account.utilization * 100).toFixed(1) }}%</span>
                    </div>
                    <div class="text-xs text-gray-400 mt-1">
                      {{ account.current_tasks }}/{{ account.max_concurrent }} 任务
                    </div>
                  </div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                  <div class="flex items-center space-x-1">
                    <span v-for="i in 10" :key="i" 
                      class="w-2 h-2 rounded-full"
                      :class="i <= account.priority ? 'bg-yellow-400' : 'bg-gray-600'"></span>
                    <span class="text-sm text-gray-300 ml-2">{{ account.priority }}</span>
                  </div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium">
                  <div class="flex items-center space-x-2">
                    <button 
                      @click="loginAccount(account.account_id)"
                      :disabled="account.is_logged_in"
                      class="bg-green-600 hover:bg-green-700 disabled:bg-gray-600 text-white px-3 py-1 rounded text-xs transition-colors"
                    >
                      {{ account.is_logged_in ? '已登录' : '登录' }}
                    </button>
                    <button 
                      @click="toggleAccount(account.account_id, !account.is_active)"
                      class="px-3 py-1 rounded text-xs transition-colors"
                      :class="account.is_active ? 'bg-yellow-600 hover:bg-yellow-700 text-white' : 'bg-green-600 hover:bg-green-700 text-white'"
                    >
                      {{ account.is_active ? '禁用' : '启用' }}
                    </button>
                    <button
                      @click="toggleSeries(account)"
                      class="px-3 py-1 rounded text-xs transition-colors"
                      :class="account.series === '3.1' ? 'bg-purple-600 hover:bg-purple-700 text-white' : 'bg-cyan-600 hover:bg-cyan-700 text-white'"
                    >
                      {{ account.series || '2.3' }}系列
                    </button>
                    <button
                      @click="editAccount(account)"
                      class="bg-blue-600 hover:bg-blue-700 text-white px-3 py-1 rounded text-xs transition-colors"
                    >
                      编辑
                    </button>
                    <button 
                      @click="deleteAccount(account.account_id)"
                      class="bg-red-600 hover:bg-red-700 text-white px-3 py-1 rounded text-xs transition-colors"
                    >
                      删除
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
    </div>

    <!-- 添加账号弹窗 -->
    <div v-if="showAddModal" class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" @click.self="closeAddModal">
      <div class="bg-gray-800 p-6 rounded-xl border border-gray-700 w-full max-w-md mx-4">
        <h3 class="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <span class="w-1.5 h-5 bg-blue-500 rounded-full"></span>
          添加海螺账号
          <span class="ml-auto text-xs text-gray-400">步骤 {{ addStep }}/2</span>
        </h3>

        <!-- 步骤1: 填写信息 + 发送验证码 -->
        <form v-if="addStep === 1" @submit.prevent="sendAddSms">
          <div class="space-y-4">
            <div>
              <label class="block text-sm font-medium text-gray-300 mb-2">账号ID</label>
              <input v-model="newAccount.account_id" type="text" required
                class="w-full px-3 py-2 bg-gray-700 border border-gray-600 text-white rounded-lg focus:ring-blue-500 focus:border-blue-500">
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-300 mb-2">手机号</label>
              <input v-model="newAccount.phone_number" type="tel" required
                class="w-full px-3 py-2 bg-gray-700 border border-gray-600 text-white rounded-lg focus:ring-blue-500 focus:border-blue-500">
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-300 mb-2">显示名称</label>
              <input v-model="newAccount.display_name" type="text" required
                class="w-full px-3 py-2 bg-gray-700 border border-gray-600 text-white rounded-lg focus:ring-blue-500 focus:border-blue-500">
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-300 mb-2">优先级 (1-10)</label>
              <input v-model.number="newAccount.priority" type="number" min="1" max="10" required
                class="w-full px-3 py-2 bg-gray-700 border border-gray-600 text-white rounded-lg focus:ring-blue-500 focus:border-blue-500">
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-300 mb-2">最大并发数</label>
              <input v-model.number="newAccount.max_concurrent" type="number" min="1" max="10" required
                class="w-full px-3 py-2 bg-gray-700 border border-gray-600 text-white rounded-lg focus:ring-blue-500 focus:border-blue-500">
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-300 mb-2">模型系列</label>
              <select v-model="newAccount.series"
                class="w-full px-3 py-2 bg-gray-700 border border-gray-600 text-white rounded-lg focus:ring-blue-500 focus:border-blue-500">
                <option value="2.3">2.3 系列</option>
                <option value="3.1">3.1 系列 (Pro)</option>
              </select>
            </div>
          </div>
          <div class="flex justify-end gap-3 mt-6">
            <button type="button" @click="closeAddModal"
              class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors">
              取消
            </button>
            <button type="submit" :disabled="addLoading"
              class="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg transition-colors">
              {{ addLoading ? '发送中...' : '发送验证码' }}
            </button>
          </div>
        </form>

        <!-- 步骤2: 输入验证码 -->
        <div v-else>
          <p class="text-sm text-gray-400 mb-4">验证码已发送至 <span class="text-white">{{ newAccount.phone_number }}</span>，请在下方输入。</p>
          <div class="space-y-4">
            <div>
              <label class="block text-sm font-medium text-gray-300 mb-2">验证码</label>
              <input v-model="addSmsCode" type="text" maxlength="6" placeholder="请输入6位验证码" autofocus
                class="w-full px-3 py-2 bg-gray-700 border border-gray-600 text-white rounded-lg focus:ring-blue-500 focus:border-blue-500">
            </div>
          </div>
          <div class="flex justify-between items-center mt-6">
            <button @click="addStep = 1" class="text-sm text-gray-400 hover:text-white transition-colors">重新发送</button>
            <div class="flex gap-3">
              <button @click="closeAddModal"
                class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors">
                取消
              </button>
              <button @click="confirmAddAccount" :disabled="addLoading || addSmsCode.length < 4"
                class="px-4 py-2 bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white rounded-lg transition-colors">
                {{ addLoading ? '登录中...' : '完成添加' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 验证码登录弹窗 -->
    <div v-if="verificationModal.show" class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" @click.self="closeVerificationModal">
      <div class="bg-gray-800 p-6 rounded-xl border border-gray-700 w-full max-w-md mx-4">
        <h3 class="text-lg font-semibold text-white mb-1 flex items-center gap-2">
          <span class="w-1.5 h-5 bg-blue-500 rounded-full"></span>
          {{ verificationModal.step === 'send' ? '发送验证码' : '验证码登录' }}
        </h3>
        <p class="text-sm text-gray-400 mb-4">账号：{{ verificationModal.accountName }}</p>

        <div v-if="verificationModal.step === 'send'" class="mb-4 text-sm text-gray-400 bg-black/30 rounded-lg p-3 space-y-1">
          <p>将向绑定手机发送验证码，请确认手机保持畅通</p>
        </div>

        <div v-else class="space-y-3 mb-4">
          <div>
            <label class="block text-sm font-medium text-gray-300 mb-1">验证码</label>
            <input
              v-model="verificationModal.code"
              type="text"
              placeholder="请输入6位验证码"
              maxlength="6"
              class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-blue-500"
              @keyup.enter="verifyAndLogin"
            />
          </div>
          <div class="flex items-center justify-between">
            <p class="text-gray-400 text-sm">请输入收到的短信验证码</p>
            <button
              @click="resendVerificationCode"
              :disabled="verificationModal.loading || resendCountdown > 0"
              class="text-blue-400 hover:text-blue-300 text-sm disabled:text-gray-500 disabled:cursor-not-allowed transition-colors"
            >
              {{ resendCountdown > 0 ? `${resendCountdown}s后重发` : '重新发送' }}
            </button>
          </div>
        </div>

        <div class="flex justify-end gap-3">
          <button
            type="button"
            @click="closeVerificationModal"
            :disabled="verificationModal.loading"
            class="px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white rounded-lg transition-colors disabled:opacity-50"
          >取消</button>

          <button
            v-if="verificationModal.step === 'send'"
            @click="sendVerificationCode"
            :disabled="verificationModal.loading"
            class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors disabled:opacity-50 flex items-center gap-2"
          >
            <svg v-if="verificationModal.loading" class="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="m4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            {{ verificationModal.loading ? '发送中...' : '发送验证码' }}
          </button>

          <button
            v-else
            @click="verifyAndLogin"
            :disabled="verificationModal.loading || !verificationModal.code.trim()"
            class="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg transition-colors disabled:opacity-50 flex items-center gap-2"
          >
            <svg v-if="verificationModal.loading" class="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="m4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            {{ verificationModal.loading ? '登录中...' : '确认登录' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import api from '../../api'

const loading = ref(false)
const showAddModal = ref(false)

// 系统状态
const systemStatus = reactive({
  is_running: false,
  active_tasks: 0
})

// 性能指标
const performance = reactive({
  total_accounts: 0,
  active_accounts: 0,
  logged_in_accounts: 0,
  total_capacity: 0,
  current_load: 0,
  utilization: 0,
  performance_level: '优秀',
  available_slots: 0,
  efficiency_score: 0
})

// 账号列表
const accounts = ref([])

// 新账号表单
const newAccount = reactive({
  account_id: '',
  phone_number: '',
  display_name: '',
  priority: 5,
  max_concurrent: 3,
  series: '2.3'
})
const addStep = ref(1)   // 1: 填信息, 2: 输验证码
const addLoading = ref(false)
const addSmsCode = ref('')

// 获取系统状态
const getSystemStatus = async () => {
  try {
    const response = await api.get('/admin/automation/status')
    Object.assign(systemStatus, response.data)

    const perfResponse = await api.get('/admin/accounts/performance')
    Object.assign(performance, perfResponse.data)
  } catch (error) {
    console.error('获取系统状态失败:', error)
  }
}

// 获取账号列表
const getAccounts = async () => {
  try {
    const response = await api.get('/admin/accounts')
    // 为每个账号初始化积分字段
    accounts.value = response.data.map(account => ({
      ...account,
      credits: -1 // -1 表示未获取
    }))
    
    // 为已登录的账号获取积分
    for (const account of accounts.value) {
      if (account.is_logged_in) {
        try {
          const creditsResponse = await api.get(`/admin/accounts/${account.account_id}/credits`)
          if (creditsResponse.data.success) {
            account.credits = creditsResponse.data.credits
          }
        } catch (error) {
          console.warn(`获取账号 ${account.account_id} 积分失败:`, error)
        }
      }
    }
  } catch (error) {
    console.error('获取账号列表失败:', error)
  }
}

// 刷新单个账号积分
const refreshCredits = async (accountId) => {
  try {
    const response = await api.get(`/admin/accounts/${accountId}/credits`)
    if (response.data.success) {
      // 更新账号积分
      const account = accounts.value.find(acc => acc.account_id === accountId)
      if (account) {
        account.credits = response.data.credits
      }
    }
  } catch (error) {
    console.error(`刷新账号 ${accountId} 积分失败:`, error)
    alert('刷新积分失败: ' + error.response?.data?.detail)
  }
}

// 刷新数据
const refreshAccounts = async () => {
  loading.value = true
  try {
    await Promise.all([getSystemStatus(), getAccounts()])
  } finally {
    loading.value = false
  }
}

// 系统状态说明：多账号管理系统现在自动启动，无需手动控制

// 重置添加账号弹窗
const resetAddModal = () => {
  showAddModal.value = false
  addStep.value = 1
  addLoading.value = false
  addSmsCode.value = ''
  Object.assign(newAccount, { account_id: '', phone_number: '', display_name: '', priority: 5, max_concurrent: 3, series: '2.3' })
}

const closeAddModal = resetAddModal

// 步骤1: 发送验证码
const sendAddSms = async () => {
  if (!newAccount.phone_number) return
  addLoading.value = true
  try {
    await api.post('/admin/accounts/sms/send', { phone_number: newAccount.phone_number })
    addStep.value = 2
  } catch (error) {
    alert('发送验证码失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    addLoading.value = false
  }
}

// 步骤2: 验证码登录并创建账号
const confirmAddAccount = async () => {
  if (addSmsCode.value.length < 4) return
  addLoading.value = true
  try {
    await api.post('/admin/accounts/sms/login', {
      ...newAccount,
      code: addSmsCode.value
    })
    await refreshAccounts()
    alert('账号添加成功')
    resetAddModal()
  } catch (error) {
    alert('添加失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    addLoading.value = false
  }
}

// 验证码登录状态
const verificationModal = reactive({
  show: false,
  accountId: '',
  accountName: '',
  code: '',
  loading: false,
  step: 'send' // 'send' | 'verify'
})

// 登录账号
const loginAccount = async (accountId) => {
  try {
    // 登录检查可能需要较长时间（页面导航+等待），设置60秒超时
    const response = await api.post(`/admin/accounts/${accountId}/login`, {}, { timeout: 60000 })
    
    if (response.data.success) {
      await refreshAccounts()
      alert('登录成功！')
      return
    }
  } catch (error) {
    console.error('登录检查失败（将弹出验证码登录）:', error)
  }
  
  // 无论什么原因失败，都弹出验证码登录窗口
  const account = accounts.value.find(acc => acc.account_id === accountId)
  verificationModal.accountId = accountId
  verificationModal.accountName = account?.display_name || accountId
  verificationModal.step = 'send'
  verificationModal.code = ''
  verificationModal.show = true
}

// 重发倒计时
const resendCountdown = ref(0)
let resendTimer = null

const startResendCountdown = () => {
  resendCountdown.value = 60
  if (resendTimer) clearInterval(resendTimer)
  resendTimer = setInterval(() => {
    resendCountdown.value--
    if (resendCountdown.value <= 0) {
      clearInterval(resendTimer)
      resendTimer = null
    }
  }, 1000)
}

// 发送验证码
const sendVerificationCode = async () => {
  verificationModal.loading = true
  try {
    const response = await api.post(`/admin/accounts/${verificationModal.accountId}/send-code`, {}, { timeout: 60000 })
    if (response.data.ok || response.data.success) {
      verificationModal.step = 'verify'
      startResendCountdown()
      alert('验证码已发送到绑定手机，请查收')
    } else {
      alert('发送验证码失败')
    }
  } catch (error) {
    alert('发送验证码失败: ' + (error.response?.data?.detail || error.message || '请重试'))
  } finally {
    verificationModal.loading = false
  }
}

// 重新发送验证码
const resendVerificationCode = async () => {
  verificationModal.loading = true
  try {
    const response = await api.post(`/admin/accounts/${verificationModal.accountId}/send-code`, {}, { timeout: 60000 })
    if (response.data.success) {
      startResendCountdown()
      alert('验证码已重新发送，请查收')
    } else {
      alert('重新发送失败')
    }
  } catch (error) {
    alert('重新发送失败: ' + (error.response?.data?.detail || error.message || '请重试'))
  } finally {
    verificationModal.loading = false
  }
}

// 验证码登录
const verifyAndLogin = async () => {
  if (!verificationModal.code.trim()) {
    alert('请输入验证码')
    return
  }
  
  verificationModal.loading = true
  try {
    const response = await api.post(`/admin/accounts/${verificationModal.accountId}/verify-code`, {
      verification_code: verificationModal.code
    }, { timeout: 60000 })
    
    if (response.data.ok || response.data.success) {
      verificationModal.show = false
      verificationModal.code = ''
      await refreshAccounts()
      alert('登录成功！')
    } else {
      alert('登录失败，请检查验证码是否正确')
    }
  } catch (error) {
    alert('验证码登录失败: ' + (error.response?.data?.detail || error.message || '请重试'))
  } finally {
    verificationModal.loading = false
  }
}

// 关闭验证码弹窗
const closeVerificationModal = () => {
  verificationModal.show = false
  verificationModal.code = ''
  verificationModal.step = 'send'
  resendCountdown.value = 0
  if (resendTimer) { clearInterval(resendTimer); resendTimer = null }
}

// 切换账号状态
const toggleAccount = async (accountId, isActive) => {
  try {
    await api.put(`/admin/accounts/${accountId}`, {
      is_active: isActive
    })
    await refreshAccounts()
  } catch (error) {
    alert('操作失败: ' + error.response?.data?.detail)
  }
}

// 切换账号系列
const toggleSeries = async (account) => {
  const newSeries = account.series === '3.1' ? '2.3' : '3.1'
  try {
    await api.put(`/admin/accounts/${account.account_id}`, { series: newSeries })
    await refreshAccounts()
  } catch (error) {
    alert('切换系列失败: ' + (error.response?.data?.detail || error.message))
  }
}

// 编辑账号（暂时使用简单弹窗）
const editAccount = (account) => {
  const newName = prompt('修改显示名称:', account.display_name)
  if (newName && newName !== account.display_name) {
    api.put(`/admin/accounts/${account.account_id}`, {
      display_name: newName
    }).then(() => {
      refreshAccounts()
    }).catch(error => {
      alert('修改失败: ' + (error.response?.data?.detail || error.message))
    })
  }
}

// 删除账号
const deleteAccount = async (accountId) => {
  if (!confirm('确定要删除这个账号吗？')) return
  
  try {
    await api.delete(`/admin/accounts/${accountId}`)
    await refreshAccounts()
    alert('账号删除成功')
  } catch (error) {
    alert('删除失败: ' + error.response?.data?.detail)
  }
}

// 工具函数
const getLoadColor = (utilization) => {
  if (utilization < 0.3) return 'text-green-400'
  if (utilization < 0.6) return 'text-yellow-400'
  if (utilization < 0.8) return 'text-orange-400'
  return 'text-red-400'
}

const getPerformanceClass = (level) => {
  const classes = {
    '优秀': 'bg-green-100 text-green-800',
    '良好': 'bg-blue-100 text-blue-800',
    '一般': 'bg-yellow-100 text-yellow-800',
    '繁忙': 'bg-red-100 text-red-800'
  }
  return classes[level] || 'bg-gray-100 text-gray-800'
}

// 定时刷新
let refreshInterval = null

onMounted(async () => {
  await refreshAccounts()
  // 每30秒自动刷新
  refreshInterval = setInterval(refreshAccounts, 30000)
})

onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
})
</script>
