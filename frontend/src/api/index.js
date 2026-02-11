import axios from 'axios'

// 根据当前环境自动选择 API 地址
const getBaseURL = () => {
    // 如果有环境变量则使用
    if (import.meta.env.VITE_API_URL) {
        return import.meta.env.VITE_API_URL
    }
    // 如果访问的不是 localhost，说明是远程访问，使用当前域名
    if (window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
        return `${window.location.protocol}//${window.location.hostname}:8000/api`
    }
    // 本地开发：localhost
    return 'http://localhost:8000/api'
}

// Create axios instance
const api = axios.create({
    baseURL: getBaseURL(),
    timeout: 10000,
    headers: {
        'Content-Type': 'application/json',
    }
})

// Request interceptor: Add Token
api.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem('token')
        const adminToken = localStorage.getItem('adminToken')

        // Check if request is for admin
        if (config.url.startsWith('/admin')) {
            if (adminToken) {
                config.headers.Authorization = `Bearer ${adminToken}`
            }
        } else {
            if (token) {
                config.headers.Authorization = `Bearer ${token}`
            }
        }
        return config
    },
    (error) => {
        return Promise.reject(error)
    }
)

// Response interceptor
api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401) {
            const isLoginPage = window.location.pathname === '/login'
            const isAdminLoginPage = window.location.pathname === '/admin/login'

            if (error.config.url.startsWith('/admin')) {
                if (!isAdminLoginPage) {
                    localStorage.removeItem('adminToken')
                    window.location.href = '/admin/login'
                }
            } else {
                if (!isLoginPage) {
                    localStorage.removeItem('token')
                    window.location.href = '/login'
                }
            }
        }
        return Promise.reject(error)
    }
)

// ============ Config API ============
// Moved to end of file to match export order

// ============ Security API ============

export const getCaptcha = async () => {
    const response = await api.get('/captcha')
    return response.data
}

export const getSecurityStatus = async () => {
    const response = await api.get('/security/status')
    return response.data
}

export const checkRisk = async (fingerprint) => {
    const response = await api.get('/risk/check', { params: { device_fingerprint: fingerprint } })
    return response.data
}

// ============ Email API ============

export const sendEmailCode = async (email, purpose = 'register') => {
    const response = await api.post('/send-email-code', { email, purpose })
    return response.data
}

export const forgotPassword = async (email, emailCode, newPassword) => {
    const response = await api.post('/forgot-password', { email, email_code: emailCode, new_password: newPassword })
    return response.data
}

// ============ Auth API ============

export const register = async (username, email, emailCode, password, captchaData, position, deviceFingerprint = null, inviteCode = null) => {
    const payload = {
        username,
        email,
        email_code: emailCode,
        password,
        captcha_challenge: captchaData.challenge,
        captcha_puzzle: captchaData.puzzle,
        captcha_cipher: captchaData.cipher,
        captcha_nonce: captchaData.nonce,
        captcha_proof: captchaData.proof,
        captcha_position: position
    }

    // 添加设备指纹（防止同设备多次注册）
    if (deviceFingerprint) {
        payload.device_fingerprint = deviceFingerprint
    }

    // 添加邀请码（如果有）
    if (inviteCode) {
        payload.invite_code = inviteCode
    }

    const response = await api.post('/register', payload)
    return response.data
}

export const login = async (username, password, captchaData = null, position = null) => {
    const payload = { username, password }

    if (captchaData) {
        payload.captcha_challenge = captchaData.challenge
        payload.captcha_puzzle = captchaData.puzzle
        payload.captcha_cipher = captchaData.cipher
        payload.captcha_nonce = captchaData.nonce
        payload.captcha_proof = captchaData.proof
        payload.captcha_position = position
    }

    const response = await api.post('/login', payload)
    return response.data
}

export const getCurrentUser = async () => {
    const response = await api.get('/users/me')
    return response.data
}

// ============ User API ============

export const recharge = async (amount) => {
    const response = await api.post('/recharge', { amount })
    return response.data
}

// ============ Payment API ============

export const createPayment = async (amount) => {
    const response = await api.post('/pay/create', { amount })
    return response.data
}

export const getPaymentStatus = async (outTradeNo) => {
    const response = await api.get(`/pay/status/${outTradeNo}`)
    return response.data
}

export const confirmPayment = async (params) => {
    const response = await api.get('/pay/confirm', { params })
    return response.data
}

export const createOrder = async (prompt, model_name, firstFrameImage, lastFrameImage) => {
    const formData = new FormData();
    formData.append('prompt', prompt);
    formData.append('model_name', model_name || "Hailuo 2.3");

    if (firstFrameImage) {
        formData.append('first_frame_image', firstFrameImage);
    }
    if (lastFrameImage) {
        formData.append('last_frame_image', lastFrameImage);
    }

    const { data } = await api.post('/orders/create', formData, {
        headers: {
            'Content-Type': 'multipart/form-data'
        }
    });
    return data;
};

export const getOrders = async () => {
    const response = await api.get('/orders')
    return response.data
}

export const getAvailableModels = async () => {
    const response = await api.get('/models')
    return response.data
}

// ============ Admin API ============

export const adminLogin = async (username, password) => {
    const response = await api.post('/admin/login', { username, password })
    return response.data
}

export const getAdminStats = async () => {
    const response = await api.get('/admin/stats')
    return response.data
}

export const getAdminUsers = async (page = 1, limit = 20) => {
    const response = await api.get('/admin/users', { params: { page, limit } })
    return response.data
}

export const updateUserBalance = async (userId, balance) => {
    const response = await api.patch(`/admin/users/${userId}`, { balance })
    return response.data
}

export const getAdminOrders = async (page = 1, limit = 20, status = '') => {
    const params = { page, limit }
    if (status) params.status = status
    const response = await api.get('/admin/orders', { params })
    return response.data
}

export const updateOrder = async (orderId, data) => {
    const response = await api.patch(`/admin/orders/${orderId}`, data)
    return response.data
}

export const getAutomationStatus = async () => {
    const response = await api.get('/admin/automation/status')
    return response.data
}

export const startAutomation = async () => {
    const response = await api.post('/admin/automation/start')
    return response.data
}

export const stopAutomation = async () => {
    const response = await api.post('/admin/automation/stop')
    return response.data
}

export const getAutomationLogs = async (limit = 50) => {
    const response = await api.get('/admin/automation/logs', { params: { limit } })
    return response.data
}

export const getBannedIps = async () => {
    const response = await api.get('/admin/security/banned-ips')
    return response.data
}

export const unbanIp = async (ip) => {
    const response = await api.delete('/admin/security/unban', { params: { ip } })
    return response.data
}

// ============ Admin Model Management API ============

export const getAdminModels = async () => {
    const response = await api.get('/admin/models')
    return response.data
}

export const updateAdminModel = async (modelId, data) => {
    const response = await api.put(`/admin/models/${modelId}`, data)
    return response.data
}

export const updateModelsOrder = async (modelOrders) => {
    const response = await api.put('/admin/models/batch/order', { model_orders: modelOrders })
    return response.data
}

// ============ Ticket API (User) ============

export const createTicket = async (title, content) => {
    const response = await api.post('/tickets/create', { title, content })
    return response.data
}

export const getMyTickets = async () => {
    const response = await api.get('/tickets')
    return response.data
}

export const getTicketDetail = async (ticketId) => {
    const response = await api.get(`/tickets/${ticketId}`)
    return response.data
}

export const userReplyTicket = async (ticketId, reply) => {
    const response = await api.post(`/tickets/${ticketId}/reply`, { reply })
    return response.data
}

export const userCloseTicket = async (ticketId) => {
    const response = await api.post(`/tickets/${ticketId}/close`)
    return response.data
}

// ============ Admin Ticket API ============

export const getAdminTickets = async (page = 1, limit = 20, status = '') => {
    const params = { page, limit }
    if (status) params.status = status
    const response = await api.get('/admin/tickets', { params })
    return response.data
}

export const getAdminTicketDetail = async (ticketId) => {
    const response = await api.get(`/admin/tickets/${ticketId}`)
    return response.data
}

export const replyTicket = async (ticketId, reply) => {
    const response = await api.post(`/admin/tickets/${ticketId}/reply`, { reply })
    return response.data
}

export const closeTicket = async (ticketId) => {
    const response = await api.post(`/admin/tickets/${ticketId}/close`)
    return response.data
}

export const getPublicConfig = async () => {
    const response = await api.get('/config')
    return response.data
}

export const getAllConfig = async () => {
    const response = await api.get('/admin/config')
    return response.data
}

export const updateConfig = async (key, value) => {
    const response = await api.patch('/admin/config', { key, value })
    return response.data
}

export default api

