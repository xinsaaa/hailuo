import axios from 'axios'

// Create axios instance
const api = axios.create({
    baseURL: 'http://localhost:8000/api',
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

// ============ Security API ============

export const getCaptcha = async () => {
    const response = await api.get('/captcha')
    return response.data
}

export const getSecurityStatus = async () => {
    const response = await api.get('/security/status')
    return response.data
}

// ============ Auth API ============

export const register = async (username, password, captchaData, position) => {
    const response = await api.post('/register', {
        username,
        password,
        captcha_challenge: captchaData.challenge,
        captcha_puzzle: captchaData.puzzle,
        captcha_cipher: captchaData.cipher,
        captcha_nonce: captchaData.nonce,
        captcha_proof: captchaData.proof,
        captcha_position: position
    })
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

export const createOrder = async (prompt) => {
    const response = await api.post('/orders/create', { prompt })
    return response.data
}

export const getOrders = async () => {
    const response = await api.get('/orders')
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

export const getBannedIps = async () => {
    const response = await api.get('/admin/security/banned-ips')
    return response.data
}

export const unbanIp = async (ip) => {
    const response = await api.delete('/admin/security/unban', { params: { ip } })
    return response.data
}

export default api
