<template>
  <nav class="glass-nav">
    <div class="glass-nav-inner container">
      <router-link to="/" class="nav-brand">
        智能深度研究助手
      </router-link>

      <div v-if="taskStore.taskId" class="nav-task-id font-mono">
        {{ truncatedTaskId }}
      </div>

      <router-link v-if="showBackLink" to="/" class="nav-back">
        返回首页
      </router-link>
    </div>
  </nav>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useTaskStore } from '@/stores/task.js'

const route = useRoute()
const taskStore = useTaskStore()

const showBackLink = computed(() => route.path !== '/')

const truncatedTaskId = computed(() => {
  const id = taskStore.taskId
  if (!id) return ''
  return id.length > 12 ? id.slice(0, 8) + '...' + id.slice(-4) : id
})
</script>

<style scoped>
.glass-nav {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 48px;
  z-index: 1000;
  backdrop-filter: saturate(180%) blur(20px);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  background: rgba(0, 0, 0, 0.80);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.glass-nav-inner {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.nav-brand {
  font-family: 'Plus Jakarta Sans', 'Noto Sans SC', sans-serif;
  font-size: 15px;
  font-weight: 600;
  color: #ffffff;
  letter-spacing: -0.12px;
  text-decoration: none;
}

.nav-brand:hover {
  text-decoration: none;
  opacity: 0.9;
}

.nav-task-id {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.48);
  letter-spacing: normal;
}

.nav-back {
  font-family: 'DM Sans', 'Noto Sans SC', sans-serif;
  font-size: 14px;
  color: var(--accent-bright);
  text-decoration: none;
  transition: opacity 0.2s ease;
}

.nav-back:hover {
  text-decoration: underline;
  opacity: 0.9;
}
</style>
