import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'

// Admin Views
import AdminLogin from '../views/admin/AdminLogin.vue'
import AdminLayout from '../views/admin/AdminLayout.vue'
import AdminDashboard from '../views/admin/AdminDashboard.vue'
import AdminUsers from '../views/admin/AdminUsers.vue'
import AdminOrders from '../views/admin/AdminOrders.vue'
import AdminSecurity from '../views/admin/AdminSecurity.vue'
import AdminModels from '../views/admin/AdminModels.vue'
import AdminMultiAccounts from '../views/admin/AdminMultiAccounts.vue'

const routes = [
    {
        path: '/',
        name: 'Home',
        component: Home
    },
    {
        path: '/login',
        name: 'Login',
        component: () => import('../views/Login.vue')
    },
    {
        path: '/forgot-password',
        name: 'ForgotPassword',
        component: () => import('../views/ForgotPassword.vue')
    },
    {
        path: '/dashboard',
        name: 'Dashboard',
        component: () => import('../views/Dashboard.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/recharge',
        name: 'Recharge',
        component: () => import('../views/Recharge.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/tickets',
        name: 'Tickets',
        component: () => import('../views/Tickets.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/invite',
        name: 'Invite',
        component: () => import('../views/Invite.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/risk-test',
        name: 'RiskTest',
        component: () => import('../views/RiskTest.vue')
    },

    // Admin Routes
    {
        path: '/admin/login',
        name: 'AdminLogin',
        component: AdminLogin
    },
    {
        path: '/admin',
        component: AdminLayout,
        meta: { requiresAdmin: true },
        children: [
            {
                path: 'dashboard',
                name: '概览',
                component: AdminDashboard
            },
            {
                path: 'users',
                name: '用户管理',
                component: AdminUsers
            },
            {
                path: 'orders',
                name: '订单管理',
                component: AdminOrders
            },
            {
                path: 'tickets',
                name: '工单管理',
                component: () => import('../views/admin/AdminTickets.vue')
            },
            {
                path: 'security',
                name: '安全中心',
                component: AdminSecurity
            },
            {
                path: 'models',
                name: '模型管理',
                component: AdminModels
            },
            {
                path: 'multi-accounts',
                name: '多账号管理',
                component: AdminMultiAccounts
            },
            {
                path: '',
                redirect: '/admin/dashboard'
            }
        ]
    },
    // 开发调试路由
    {
        path: '/dev',
        children: [
            {
                path: 'codes',
                name: 'DevCodes',
                component: () => import('../views/DevCodes.vue')
            }
        ]
    }
]

const router = createRouter({
    history: createWebHistory(),
    routes
})

router.beforeEach((to, from, next) => {
    const token = localStorage.getItem('token')
    const adminToken = localStorage.getItem('adminToken')

    // Admin Guard
    if (to.matched.some(record => record.meta.requiresAdmin)) {
        if (!adminToken) {
            next('/admin/login')
        } else {
            next()
        }
        return
    }

    // User Guard
    if (to.matched.some(record => record.meta.requiresAuth)) {
        if (!token) {
            next('/login')
        } else {
            next()
        }
    } else {
        next()
    }
})

export default router
