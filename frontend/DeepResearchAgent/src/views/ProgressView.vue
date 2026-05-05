<template>
  <div class="progress-view">
    <div class="progress-content container">
      <!-- 任务主题 -->
      <h2 class="task-topic font-display">
        {{ taskStore.topic || '研究任务' }}
      </h2>

      <!-- 步骤条 -->
      <StepIndicator :current-node="taskStore.currentNode" />

      <!-- 进度条 -->
      <div class="progress-section">
        <ProgressBar :progress="taskStore.progress" />
      </div>

      <!-- 日志面板 -->
      <ActivityPanel :logs="taskStore.logs" />

      <!-- 完成提示 -->
      <div v-if="showCompleteCard" class="complete-card animate-fade-in">
        <p class="complete-text">报告已生成</p>
        <router-link
          :to="`/report/${taskStore.taskId}`"
          class="complete-link"
        >
          查看报告 →
        </router-link>
      </div>

      <!-- 失败提示 -->
      <div v-if="taskStore.isFailed" class="error-card animate-fade-in">
        <p class="error-text">任务执行失败</p>
        <p class="error-detail">{{ lastError }}</p>
        <router-link to="/" class="error-link">返回首页重试</router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { connectSSE, getResearchStatus } from '@/api/research.js'
import { useTaskStore } from '@/stores/task.js'
import StepIndicator from '@/components/StepIndicator.vue'
import ActivityPanel from '@/components/ActivityPanel.vue'
import ProgressBar from '@/components/ProgressBar.vue'

const route = useRoute()
const router = useRouter()
const taskStore = useTaskStore()

const taskId = route.params.task_id
const lastError = ref('')
const reconnectTimer = ref(null)
const shouldReconnect = ref(true)

const showCompleteCard = computed(() => {
  return taskStore.isCompleted && taskStore.currentNode === 'END'
})

// 节点到进度的映射
const progressMap = {
  pending: 0,
  planner: 20,
  researcher: 40,
  analyzer: 60,
  writer: 80,
  reviewer: 90,
  save_report: 100,
  END: 100,
}

function updateFromEvent(payload) {
  const { event_type, node, output, message, error_code } = payload

  if (event_type === 'node_start') {
    taskStore.updateProgress(node, progressMap[node] || 0)
    taskStore.addLog(node, '开始执行', new Date().toISOString())
  }

  if (event_type === 'node_complete') {
    taskStore.updateProgress(node, progressMap[node] || 0)
    let msg = '执行完成'
    if (output) {
      if (output.plan) msg = `生成 ${output.plan.length} 个子任务`
      if (output.search_results) msg = `搜索完成`
      if (output.analysis) msg = `分析完成`
      if (output.report_length) msg = `报告撰写完成 (${output.report_length} 字符)`
      if (output.result) msg = `审核结果: ${output.result}`
      if (output.report_path) msg = `报告已保存`
    }
    taskStore.addLog(node, msg, new Date().toISOString())

    if (node === 'END') {
      taskStore.setStatus('completed')
      if (output?.report_path) {
        taskStore.setReport(null, output.report_path)
      }
      // 2 秒后自动跳转到报告页
      setTimeout(() => {
        router.push(`/report/${taskId}`)
      }, 2500)
    }
  }

  if (event_type === 'error') {
    lastError.value = message || '未知错误'
    taskStore.setStatus('failed')
    taskStore.addLog(node || 'system', `错误: ${message}`, new Date().toISOString())
  }
}

async function fetchCurrentStatus() {
  try {
    const data = await getResearchStatus(taskId)
    if (data.status === 'completed') {
      taskStore.setStatus('completed')
      taskStore.updateProgress(data.current_node, progressMap[data.current_node] || 100)
      taskStore.setReport(data.report, data.report_path)
    } else if (data.status === 'failed') {
      taskStore.setStatus('failed')
    } else {
      taskStore.updateProgress(data.current_node, progressMap[data.current_node] || 0)
    }
  } catch {
    // 忽略查询失败
  }
}

function startSSE() {
  if (!shouldReconnect.value) return

  const es = connectSSE(taskId, {
    onMessage: (payload) => {
      updateFromEvent(payload)
    },
    onError: () => {
      // SSE 断开，延迟 3 秒重连
      if (shouldReconnect.value && !taskStore.isCompleted && !taskStore.isFailed) {
        reconnectTimer.value = setTimeout(() => {
          startSSE()
        }, 3000)
      }
    },
  })

  taskStore.setSSEConnection(es)
}

onMounted(async () => {
  // 如果 store 中没有当前任务信息，先查询一次
  if (taskStore.taskId !== taskId) {
    taskStore.reset()
    taskStore.setTask(taskId, '')
    await fetchCurrentStatus()
  }

  // 如果任务已完成或失败，不再建立 SSE
  if (!taskStore.isCompleted && !taskStore.isFailed) {
    startSSE()
  }
})

onUnmounted(() => {
  shouldReconnect.value = false
  if (reconnectTimer.value) {
    clearTimeout(reconnectTimer.value)
  }
  taskStore.closeSSE()
})

// 监听任务完成，自动跳转
watch(showCompleteCard, (val) => {
  if (val) {
    setTimeout(() => {
      router.push(`/report/${taskId}`)
    }, 2500)
  }
})
</script>

<style scoped>
.progress-view {
  min-height: 100vh;
  background: var(--bg-light);
  padding-top: 80px; /* glass nav + 间距 */
  padding-bottom: 64px;
}

.progress-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 32px;
}

.task-topic {
  font-size: 28px;
  font-weight: 400;
  line-height: 1.25;
  color: var(--text-primary);
  text-align: center;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  max-width: 800px;
}

.progress-section {
  width: 100%;
  max-width: 800px;
}

.complete-card {
  background: var(--bg-white);
  border-radius: 12px;
  padding: 24px 32px;
  text-align: center;
  box-shadow: var(--shadow-soft);
  max-width: 400px;
  width: 100%;
}

.complete-text {
  font-size: 17px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 8px;
}

.complete-link {
  font-size: 15px;
  color: var(--accent);
  font-weight: 500;
}

.error-card {
  background: #fff2f2;
  border-radius: 12px;
  padding: 24px 32px;
  text-align: center;
  max-width: 400px;
  width: 100%;
}

.error-text {
  font-size: 17px;
  font-weight: 600;
  color: #ff453a;
  margin-bottom: 4px;
}

.error-detail {
  font-size: 14px;
  color: var(--text-secondary);
  margin-bottom: 12px;
}

.error-link {
  font-size: 14px;
  color: var(--accent);
}
</style>
