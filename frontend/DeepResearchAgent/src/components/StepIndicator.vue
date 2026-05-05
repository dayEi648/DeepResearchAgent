<template>
  <div class="step-indicator">
    <div
      v-for="(step, index) in steps"
      :key="step.key"
      class="step-item"
      :class="getStepClass(step.key)"
    >
      <div class="step-marker-wrapper">
        <div class="step-marker">
          <span v-if="isCompleted(step.key)" class="step-check">&#10003;</span>
          <span v-else-if="isCurrent(step.key)" class="step-dot"></span>
        </div>
        <!-- 连接线（最后一个不画） -->
        <div
          v-if="index < steps.length - 1"
          class="step-line"
          :class="{ 'line-active': isLineActive(index) }"
        ></div>
      </div>
      <span class="step-name font-body">{{ step.name }}</span>
      <!-- 当前步骤蓝色下划线 -->
      <div v-if="isCurrent(step.key)" class="step-underline indicator-slide-in"></div>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  currentNode: { type: String, default: '' },
})

const steps = [
  { key: 'planner',    name: 'Planner' },
  { key: 'researcher', name: 'Researcher' },
  { key: 'analyzer',   name: 'Analyzer' },
  { key: 'writer',     name: 'Writer' },
  { key: 'reviewer',   name: 'Reviewer' },
]

const nodeOrder = ['planner', 'researcher', 'analyzer', 'writer', 'reviewer', 'save_report', 'END']

function getNodeIndex(node) {
  const idx = nodeOrder.indexOf(node)
  return idx === -1 ? -1 : idx
}

function isCompleted(stepKey) {
  const currentIdx = getNodeIndex(props.currentNode)
  const stepIdx = getNodeIndex(stepKey)
  return currentIdx > stepIdx
}

function isCurrent(stepKey) {
  return props.currentNode === stepKey
}

function isLineActive(index) {
  const currentIdx = getNodeIndex(props.currentNode)
  const nextStepIdx = getNodeIndex(steps[index + 1].key)
  return currentIdx >= nextStepIdx
}

function getStepClass(stepKey) {
  if (isCurrent(stepKey)) return 'step-current'
  if (isCompleted(stepKey)) return 'step-completed'
  return 'step-pending'
}
</script>

<style scoped>
.step-indicator {
  display: flex;
  align-items: flex-start;
  justify-content: center;
  gap: 0;
  padding: 24px 0;
}

.step-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  position: relative;
  min-width: 100px;
}

.step-marker-wrapper {
  display: flex;
  align-items: center;
  position: relative;
}

.step-marker {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all 400ms ease;
  z-index: 2;
}

.step-check {
  font-size: 12px;
  color: #ffffff;
  font-weight: 700;
}

.step-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #ffffff;
}

.step-line {
  position: absolute;
  left: 24px;
  top: 50%;
  transform: translateY(-50%);
  width: calc(100px - 24px + 24px);
  height: 2px;
  background: var(--step-inactive-border);
  z-index: 1;
  transition: background 400ms ease;
}

.line-active {
  background: var(--step-completed-bg);
}

.step-name {
  margin-top: 8px;
  font-size: 14px;
  line-height: 1.2;
  transition: all 400ms ease;
}

.step-underline {
  margin-top: 6px;
  width: 24px;
  height: 3px;
  background: var(--accent);
  border-radius: 2px;
}

/* 状态样式 */
.step-pending .step-marker {
  border: 2px solid var(--step-inactive-border);
  background: transparent;
}
.step-pending .step-name {
  color: var(--text-tertiary);
}

.step-current .step-marker {
  background: var(--accent);
  border: 2px solid var(--accent);
}
.step-current .step-name {
  color: var(--text-primary);
  font-weight: 600;
}

.step-completed .step-marker {
  background: var(--step-completed-bg);
  border: 2px solid var(--step-completed-bg);
}
.step-completed .step-name {
  color: var(--text-primary);
}
</style>
