import { createRouter, createWebHistory } from 'vue-router'
import SubmitView from '../views/SubmitView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', name: 'submit', component: SubmitView },
    { path: '/task/:task_id', name: 'progress', component: () => import('../views/ProgressView.vue') },
    { path: '/report/:task_id', name: 'report', component: () => import('../views/ReportView.vue') },
  ],
})

export default router
