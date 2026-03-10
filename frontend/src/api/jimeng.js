import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

api.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  response => response.data,
  error => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export const getJimengModels = () => api.get('/jimeng/models')

export const getJimengStatus = () => api.get('/jimeng/status')

export const getJimengOrders = () => api.get('/jimeng/orders')

export const jimengCreateOrder = async (data) => {
  const formData = new FormData()
  formData.append('prompt', data.prompt)
  formData.append('model', data.model)
  if (data.first_frame) {
    formData.append('first_frame', data.first_frame)
  }
  if (data.last_frame) {
    formData.append('last_frame', data.last_frame)
  }
  return api.post('/jimeng/orders', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

export default api
