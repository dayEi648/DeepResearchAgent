<template>
  <nav class="toc-nav">
    <ul class="toc-list">
      <li
        v-for="item in toc"
        :key="item.id"
        class="toc-item"
        :class="{ 'toc-active': activeId === item.id }"
        :style="{ paddingLeft: `${(item.level - 1) * 12 + 12}px` }"
        @click="scrollTo(item.id)"
      >
        {{ item.text }}
      </li>
    </ul>
  </nav>
</template>

<script setup>
const props = defineProps({
  toc: { type: Array, default: () => [] },
  activeId: { type: String, default: '' },
})

function scrollTo(id) {
  const el = document.getElementById(id)
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
}
</script>

<style scoped>
.toc-nav {
  position: fixed;
  right: 24px;
  top: 140px;
  width: 180px;
  z-index: 100;
}

.toc-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.toc-item {
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-tertiary);
  padding: 4px 0 4px 12px;
  cursor: pointer;
  border-left: 2px solid transparent;
  transition: all 200ms ease;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.toc-item:hover {
  color: var(--text-secondary);
}

.toc-active {
  color: var(--text-primary);
  font-weight: 600;
  border-left-color: var(--accent);
}

@media (max-width: 1200px) {
  .toc-nav {
    display: none;
  }
}
</style>
