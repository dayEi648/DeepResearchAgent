<template>
  <div class="progress-wrapper">
    <div class="progress-track">
      <div
        class="progress-fill"
        :style="{ width: `${clampedProgress}%` }"
      ></div>
    </div>
    <span class="progress-text font-display">{{ clampedProgress }}%</span>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  progress: { type: Number, default: 0 },
})

const clampedProgress = computed(() => {
  const p = Math.round(props.progress)
  return Math.max(0, Math.min(100, p))
})
</script>

<style scoped>
.progress-wrapper {
  display: flex;
  align-items: center;
  gap: 16px;
  width: 100%;
}

.progress-track {
  flex: 1;
  height: 4px;
  background: #d2d2d7;
  border-radius: 2px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--accent);
  border-radius: 2px;
  transition: width 600ms cubic-bezier(0.25, 0.1, 0.25, 1);
}

.progress-text {
  font-size: 40px;
  font-weight: 600;
  line-height: 1.10;
  color: var(--text-primary);
  letter-spacing: -0.28px;
  min-width: 80px;
  text-align: right;
}
</style>
