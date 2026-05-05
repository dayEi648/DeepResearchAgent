/**
 * API 封装模块
 *
 * 作用：封装 Axios HTTP 请求和原生 EventSource SSE 连接。
 * Base URL：http://localhost:8000
 */

import axios from 'axios'

// API Base URL：
// - 开发环境（Vite）：指向本地后端 localhost:8000
// - 生产环境（前后端同域名部署）：使用相对路径，请求自动发到当前域名
const API_BASE = import.meta.env.DEV ? 'http://localhost:8000' : ''

// Axios 实例
const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
})

/**
 * 健康检查
 */
export async function checkHealth() {
  const { data } = await api.get('/health')
  return data
}

/**
 * 提交研究任务
 * @param {string} topic 研究主题
 */
export async function submitResearch(topic) {
  const { data } = await api.post('/research', { topic })
  // 兼容后端两种返回格式：{code, data} 包装 或 直接返回
  return data.data || data
}

/**
 * 查询任务状态与结果
 * @param {string} taskId 任务 ID
 */
export async function getResearchStatus(taskId) {
  const { data } = await api.get(`/research/${taskId}`)
  return data.data
}

/**
 * 建立 SSE 连接，实时监听任务进度
 * @param {string} taskId 任务 ID
 * @param {object} handlers 事件处理回调
 *   - onMessage: (event) => void
 *   - onError: (error) => void
 *   - onOpen: () => void
 * @returns {EventSource} SSE 实例（用于手动关闭）
 */
export function connectSSE(taskId, handlers = {}) {
  const { onMessage, onError, onOpen } = handlers
  const url = `${API_BASE}/research/${taskId}/stream`

  const es = new EventSource(url)

  es.onopen = () => {
    if (onOpen) onOpen()
  }

  es.onmessage = (event) => {
    if (onMessage) {
      try {
        const payload = JSON.parse(event.data)
        onMessage(payload)
      } catch {
        onMessage({ raw: event.data })
      }
    }
  }

  es.onerror = (err) => {
    if (onError) onError(err)
  }

  return es
}
