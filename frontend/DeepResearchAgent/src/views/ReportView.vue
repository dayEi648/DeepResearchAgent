<template>
  <div class="report-view">
    <!-- 顶部工具栏 -->
    <div class="report-toolbar">
      <div class="toolbar-inner container">
        <router-link to="/" class="toolbar-back">
          <span class="back-arrow">←</span>
          返回首页
        </router-link>
        <span class="toolbar-topic font-body">{{ taskStore.topic || '研究报告' }}</span>
        <button class="toolbar-download font-body" @click="downloadReport">
          下载 Markdown
        </button>
      </div>
    </div>

    <!-- 主体内容 -->
    <div class="report-body container">
      <article class="report-article markdown-body" v-html="renderedHtml"></article>
    </div>

    <!-- 目录导航 -->
    <TocNavigator :toc="tocItems" :active-id="activeTocId" />
  </div>
</template>

<script setup>
import { ref, onMounted, computed, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { getResearchStatus } from '@/api/research.js'
import { useTaskStore } from '@/stores/task.js'
import { renderMarkdown, extractToc } from '@/utils/markdown.js'
import TocNavigator from '@/components/TocNavigator.vue'

const route = useRoute()
const taskStore = useTaskStore()

const taskId = route.params.task_id
const renderedHtml = ref('')
const tocItems = ref([])
const activeTocId = ref('')

let scrollHandler = null

const reportContent = computed(() => taskStore.report || '')

async function loadReport() {
  // 如果 store 中没有报告内容，从 API 获取
  if (!taskStore.report) {
    try {
      const data = await getResearchStatus(taskId)
      taskStore.setTask(taskId, data.topic)
      taskStore.setReport(data.report, data.report_path)
    } catch {
      renderedHtml.value = '<p>加载报告失败，请返回首页重试。</p>'
      return
    }
  }

  const md = reportContent.value || ''
  renderedHtml.value = renderMarkdown(md)
  tocItems.value = extractToc(md)

  // 给标题添加 id，用于目录锚点
  setTimeout(() => {
    const headings = document.querySelectorAll('.report-article h1, .report-article h2, .report-article h3')
    headings.forEach((el, i) => {
      const item = tocItems.value[i]
      if (item) {
        el.id = item.id
      }
    })
    setupScrollSpy()
  }, 100)
}

function setupScrollSpy() {
  const headings = document.querySelectorAll('.report-article h1, .report-article h2, .report-article h3')
  if (!headings.length) return

  scrollHandler = () => {
    const scrollPos = window.scrollY + 160
    let current = ''
    headings.forEach((el) => {
      if (el.offsetTop <= scrollPos) {
        current = el.id
      }
    })
    if (current) activeTocId.value = current
  }

  window.addEventListener('scroll', scrollHandler)
  scrollHandler()
}

function downloadReport() {
  // 优先使用 OSS 外链（线上部署时）
  if (taskStore.reportUrl) {
    window.open(taskStore.reportUrl, '_blank')
    return
  }

  // 兜底：本地 Blob 下载（开发环境或 OSS 未配置时）
  const content = reportContent.value || ''
  if (!content.trim()) {
    alert('报告内容为空，可能尚未生成完成，请稍后重试。')
    return
  }

  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${taskStore.topic || '研究报告'}.md`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

onMounted(() => {
  loadReport()
})

onUnmounted(() => {
  if (scrollHandler) {
    window.removeEventListener('scroll', scrollHandler)
  }
})
</script>

<style scoped>
.report-view {
  min-height: 100vh;
  background: var(--bg-white);
  padding-top: 48px; /* glass nav 高度 */
}

.report-toolbar {
  position: sticky;
  top: 48px;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: saturate(180%) blur(20px);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  z-index: 50;
}

.toolbar-inner {
  height: 52px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.toolbar-back {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 14px;
  color: var(--accent);
  font-weight: 500;
  border: 1px solid rgba(0, 113, 227, 0.25);
  padding: 4px 12px;
  border-radius: 980px;
  transition: all 0.2s ease;
}

.toolbar-back:hover {
  background: rgba(0, 113, 227, 0.06);
  text-decoration: none;
}

.back-arrow {
  font-size: 13px;
}

.toolbar-topic {
  font-size: 15px;
  color: var(--text-primary);
  font-weight: 500;
  max-width: 400px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-align: center;
}

.toolbar-download {
  font-size: 14px;
  color: var(--text-secondary);
  background: var(--bg-white);
  border: 1px solid #d2d2d7;
  padding: 6px 14px;
  border-radius: 8px;
  transition: all 0.2s ease;
}

.toolbar-download:hover {
  border-color: var(--text-tertiary);
  color: var(--text-primary);
}

.report-body {
  max-width: 780px;
  padding-top: 48px;
  padding-bottom: 120px;
}

.report-article {
  animation: fadeIn 600ms ease-out forwards;
}
</style>
