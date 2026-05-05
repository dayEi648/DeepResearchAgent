<template>
  <div class="app-root">
    <GlassNav />
    <router-view v-slot="{ Component }">
      <transition name="page" mode="out-in">
        <component :is="Component" />
      </transition>
    </router-view>
  </div>
</template>

<script setup>
import GlassNav from '@/components/GlassNav.vue'
</script>

<style>
/* 页面切换动画 */
.page-enter-active,
.page-leave-active {
  transition: opacity 200ms ease, transform 300ms ease;
}

.page-enter-from {
  opacity: 0;
  transform: translateY(12px);
}

.page-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
