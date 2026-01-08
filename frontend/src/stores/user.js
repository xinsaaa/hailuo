import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useUserStore = defineStore('user', () => {
    const user = ref(null)
    const token = ref(localStorage.getItem('token') || '')

    function login(userData, jwt) {
        user.value = userData
        token.value = jwt
        localStorage.setItem('token', jwt)
    }

    function logout() {
        user.value = null
        token.value = ''
        localStorage.removeItem('token')
    }

    return { user, token, login, logout }
})
