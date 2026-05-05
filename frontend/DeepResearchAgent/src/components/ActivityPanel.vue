<template>
  <div class="activity-panel">
    <h3 class="panel-title font-display">Activity</h3>
    <div class="log-list">
      <div
        v-for="(log, index) in logs"
        :key="index"
        class="log-entry"
        :class="{ 'log-latest': index === logs.length - 1 }"
      >
        <span class="log-time font-mono">{{ formatTime(log.timestamp) }}</span>
        <span class="log-node font-body">{{ log.node }}</span>
        <span class="log-message font-body">{{ log.message }}</span>
      </div>
      <div v-if="logs.length === 0" class="log-empty">
        等待任务开始...
      </div>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  logs: { type: Array, default: () => [] },
})

function formatTime(iso) {
  if (!iso) return '--:--:--'
  const d = new Date(iso)
  return d.toLocaleTimeString('zh-CN', { hour12: false })
}
</script>

<style scoped>
.activity-panel {
  background: var(--bg-white);
  border-radius: 12px;
  padding: 24px;
  box-shadow: var(--shadow-soft);
}

.panel-title {
  font-size: 21px;
  font-weight: 700;
  line-height: 1.19;
  color: var(--text-primary);
  margin-bottom: 20px;
  letter-spacing: 0.231px;
}

.log-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 400px;
  overflow-y: auto;
}

.log-entry {
  display: flex;
  align-items: baseline;
  gap: 12px;
  font-size: 14px;
  line-height: 1.5;
  padding: 4px 0;
  border-bottom: 1px solid transparent;
}

.log-latest {
  border-bottom-color: rgba(0, 113, 227, 0.15);
}

.log-time {
  font-size: 12px;
  color: var(--text-tertiary);
  flex-shrink: 0;
  min-width: 64px;
}

.log-node {
  font-weight: 600;
  color: var(--text-primary);
  flex-shrink: 0;
  min-width: 80px;
  text-transform: capitalize;
}

.log-message {
  color: var(--text-secondary);
  word-break: break-all;
}

.log-empty {
  font-size: 14px;
  color: var(--text-tertiary);
  text-align: center;
  padding: 24px 0;
}
</style>
