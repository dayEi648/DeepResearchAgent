/**
 * Pinia 全局状态管理
 *
 * 作用：管理任务相关的全局状态，跨页面共享 task_id、日志、进度等。
 */

import { ref, computed } from 'vue'
import { defineStore } from 'pinia'

export const useTaskStore = defineStore('task', () => {
  // -------------------- State --------------------

  /** 当前任务 ID */
  const taskId = ref('')

  /** 研究主题 */
  const topic = ref('')

  /** 任务状态 */
  const status = ref('')

  /** 当前节点 */
  const currentNode = ref('')

  /** 进度百分比 0~100 */
  const progress = ref(0)

  /** 日志列表 */
  const logs = ref([])

  /** 最终报告 Markdown */
  const report = ref('')

  /** 报告文件路径（本地路径或 OSS URL） */
  const reportPath = ref('')

  /** 报告下载 URL（OSS 外链，优先使用） */
  const reportUrl = ref('')

  /** SSE 连接实例 */
  const sseConnection = ref(null)

  // -------------------- Getters --------------------

  const isCompleted = computed(() => status.value === 'completed')
  const isFailed = computed(() => status.value === 'failed')

  // -------------------- Actions --------------------

  function setTask(id, taskTopic) {
    taskId.value = id
    topic.value = taskTopic
    status.value = 'pending'
    currentNode.value = 'pending'
    progress.value = 0
    logs.value = []
    report.value = ''
    reportPath.value = ''
  }

  function addLog(node, message, timestamp = new Date().toISOString()) {
    logs.value.push({ node, message, timestamp })
    // 最多保留 15 条
    if (logs.value.length > 15) {
      logs.value.shift()
    }
  }

  function updateProgress(node, pct) {
    currentNode.value = node
    progress.value = pct
  }

  function setStatus(newStatus) {
    status.value = newStatus
  }

  function setReport(content, path) {
    report.value = content
    reportPath.value = path
    // 如果 path 是 http 开头的 URL（OSS 外链），同时设为 reportUrl
    if (path && typeof path === 'string' && path.startsWith('http')) {
      reportUrl.value = path
    }
  }

  function setSSEConnection(conn) {
    sseConnection.value = conn
  }

  function closeSSE() {
    if (sseConnection.value) {
      sseConnection.value.close()
      sseConnection.value = null
    }
  }

  function reset() {
    taskId.value = ''
    topic.value = ''
    status.value = ''
    currentNode.value = ''
    progress.value = 0
    logs.value = []
    report.value = ''
    reportPath.value = ''
    reportUrl.value = ''
    closeSSE()
  }

  return {
    taskId,
    topic,
    status,
    currentNode,
    progress,
    logs,
    report,
    reportPath,
    reportUrl,
    sseConnection,
    isCompleted,
    isFailed,
    setTask,
    addLog,
    updateProgress,
    setStatus,
    setReport,
    setSSEConnection,
    closeSSE,
    reset,
  }
})
