import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
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

export const getGptimageModels = () => api.get('/gptimage/models')

export const getGptimageOrders = () => api.get('/gptimage/orders')

export const gptimageCreateOrder = async (data) => {
  const formData = new FormData()
  formData.append('prompt', data.prompt)
  formData.append('model', data.model)
  if (data.ratio) formData.append('ratio', data.ratio)
  if (data.quality) formData.append('quality', data.quality)
  if (data.count && data.count > 1) formData.append('count', data.count)
  if (data.ref_image) {
    formData.append('ref_image', data.ref_image)
  }
  return api.post('/gptimage/orders', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

export default api
