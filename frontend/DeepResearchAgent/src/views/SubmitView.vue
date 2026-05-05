<template>
  <div class="submit-view">
    <div class="submit-content">
      <h1 class="hero-title font-display animate-fade-in-up delay-0">
        智能深度研究助手
      </h1>
      <p class="hero-subtitle font-body animate-fade-in-up delay-100">
        输入一个研究主题，让 AI 自动完成深度调研与报告生成
      </p>

      <div class="input-wrapper animate-fade-in-up delay-200">
        <input
          v-model="topic"
          type="text"
          class="topic-input font-body"
          placeholder="输入研究主题，例如：2026年AI Agent开发框架对比调研"
          maxlength="500"
          @keyup.enter="handleSubmit"
          @focus="isFocused = true"
          @blur="isFocused = false"
          :disabled="isLoading"
        />
        <div class="input-underline" :class="{ focused: isFocused }"></div>
      </div>

      <button
        class="submit-btn btn-primary font-body animate-fade-in-up delay-300"
        :disabled="!canSubmit || isLoading"
        @click="handleSubmit"
      >
        <span v-if="!isLoading">开始研究</span>
        <span v-else class="btn-loading">
          <span class="spinner animate-spin"></span>
          提交中...
        </span>
      </button>

      <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>

      <div class="tech-stack font-body animate-fade-in-up delay-400">
        Vue · LangGraph · MCP · Redis
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { submitResearch } from '@/api/research.js'
import { useTaskStore } from '@/stores/task.js'

const router = useRouter()
const taskStore = useTaskStore()

const topic = ref('')
const isLoading = ref(false)
const errorMsg = ref('')
const isFocused = ref(false)

const canSubmit = computed(() => topic.value.trim().length > 0)

async function handleSubmit() {
  if (!canSubmit.value || isLoading.value) return

  isLoading.value = true
  errorMsg.value = ''

  try {
    const result = await submitResearch(topic.value.trim())
    taskStore.setTask(result.task_id, topic.value.trim())
    router.push(`/task/${result.task_id}`)
  } catch (err) {
    errorMsg.value = err.response?.data?.message || '提交失败，请检查后端服务是否启动'
    isLoading.value = false
  }
}
</script>

<style scoped>
.submit-view {
  min-height: 100vh;
  background: var(--bg-black);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 24px;
  padding-top: 48px; /* 为 glass nav 留空间 */
}

.submit-content {
  text-align: center;
  max-width: 680px;
  width: 100%;
}

.hero-title {
  font-size: 56px;
  font-weight: 600;
  line-height: 1.07;
  letter-spacing: -0.28px;
  color: var(--text-inverse);
  margin-bottom: 16px;
}

.hero-subtitle {
  font-size: 21px;
  font-weight: 400;
  line-height: 1.38;
  color: rgba(255, 255, 255, 0.60);
  margin-bottom: 48px;
}

.input-wrapper {
  position: relative;
  margin-bottom: 32px;
}

.topic-input {
  width: 100%;
  background: transparent;
  border: none;
  border-bottom: 1px solid var(--text-inverse);
  padding: 12px 0;
  font-size: 17px;
  color: var(--text-inverse);
  outline: none;
  text-align: center;
  transition: border-color 0.2s ease;
}

.topic-input::placeholder {
  color: rgba(255, 255, 255, 0.35);
}

.topic-input:focus {
  border-bottom-color: var(--accent);
}

.input-underline {
  position: absolute;
  bottom: 0;
  left: 50%;
  width: 0;
  height: 2px;
  background: var(--accent);
  transition: width 0.3s ease, left 0.3s ease;
}

.topic-input:focus ~ .input-underline {
  width: 100%;
  left: 0;
}

.submit-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background: var(--accent);
  color: var(--text-inverse);
  font-size: 17px;
  font-weight: 400;
  padding: 10px 24px;
  border-radius: 8px;
  min-width: 140px;
  min-height: 44px;
}

.submit-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-loading {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #ffffff;
  border-radius: 50%;
}

.error-msg {
  margin-top: 16px;
  font-size: 14px;
  color: #ff453a;
}

.tech-stack {
  margin-top: 64px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.48);
  letter-spacing: -0.12px;
}
</style>
