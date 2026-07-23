<script setup lang="ts">
import { computed } from 'vue'
import { useSessionStore } from '@/stores/sessionStore'

const store = useSessionStore()

const statusColor = computed(() => {
  const map: Record<string, string> = {
    diagnosing: 'var(--status-diagnosing)',
    modifying: 'var(--status-modifying)',
    completed: 'var(--status-completed)',
  }
  return map[store.activeSession?.status || ''] || 'var(--status-pending)'
})

const isBreathing = computed(() => {
  const status = store.activeSession?.status
  return status === 'diagnosing' || status === 'modifying'
})

const statusLabel = computed(() => {
  const map: Record<string, string> = {
    pending: '就绪',
    diagnosing: '诊断中',
    modifying: '修改中',
    completed: '已完成',
    excluded: '已排除',
    rechecking: '复查中',
  }
  return map[store.activeSession?.status || ''] || '就绪'
})
</script>

<template>
  <header class="app-header">
    <div class="header-title">输电线路故障诊断智能体</div>
    <div class="status-indicator">
      <span
        class="status-dot"
        :class="{ breathing: isBreathing }"
        :style="{ background: statusColor, color: statusColor }"
      />
      <span>{{ statusLabel }}</span>
    </div>
  </header>
</template>

<style scoped>
.app-header {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 1.5rem;
  background: var(--bg-panel);
  border-bottom: 1px solid var(--border-subtle);
  position: sticky;
  top: 0;
  z-index: 100;
}

.header-title {
  font-family: var(--font-display);
  font-size: var(--text-md);
  font-weight: 700;
  letter-spacing: 0.05em;
  color: var(--text-primary);
  text-align: center;
}

.status-indicator {
  position: absolute;
  right: 1.5rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: var(--text-xs);
  color: var(--text-secondary);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  box-shadow: 0 0 4px currentColor;
}

.status-dot.breathing {
  animation: breathing 2s ease-in-out infinite;
}
</style>
