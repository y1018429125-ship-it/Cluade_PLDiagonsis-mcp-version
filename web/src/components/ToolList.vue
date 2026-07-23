<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getTools, type ToolInfo } from '@/api/http'

const tools = ref<ToolInfo[]>([])
const loading = ref(false)
const error = ref<string | null>(null)

function categoryLabel(cat: string): string {
  const map: Record<string, string> = {
    electrical: '电气',
    environmental: '环境',
    biological: '生物',
    test: '测试',
  }
  return map[cat] ?? cat
}

async function loadTools() {
  loading.value = true
  error.value = null
  try {
    const data = await getTools()
    tools.value = data.tools
  } catch (err) {
    error.value = (err as Error).message
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadTools()
})
</script>

<template>
  <section class="tool-panel">
    <header class="tool-header">
      <h3>诊断工具</h3>
      <button type="button" class="refresh-btn" @click="loadTools" title="刷新">&#x21bb;</button>
    </header>

    <ul v-if="tools.length > 0" class="tool-list">
      <li v-for="t in tools" :key="t.name" class="tool-item">
        <div class="tool-row">
          <span class="tool-name">{{ t.display_name }}</span>
          <span class="tool-category">{{ categoryLabel(t.category) }}</span>
        </div>
        <div class="tool-desc">{{ t.description }}</div>
      </li>
    </ul>

    <div v-else-if="loading" class="tool-empty">加载中...</div>
    <div v-else-if="error" class="tool-error">{{ error }}</div>
    <div v-else class="tool-empty">暂无工具</div>
  </section>
</template>

<style scoped>
.tool-panel {
  width: 260px;
  min-width: 260px;
  background: var(--bg-panel);
  border-left: 1px solid var(--border-subtle);
  display: flex;
  flex-direction: column;
}

.tool-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--border-subtle);
}

.tool-header h3 {
  margin: 0;
  font-size: var(--text-md);
  font-weight: 600;
  color: var(--text-primary);
}

.refresh-btn {
  background: transparent;
  border: none;
  color: var(--text-secondary);
  font-size: 1.1rem;
  cursor: pointer;
  padding: 0.25rem;
  line-height: 1;
}

.refresh-btn:hover {
  color: var(--text-primary);
}

.tool-list {
  list-style: none;
  margin: 0;
  padding: 0.75rem;
  overflow-y: auto;
  flex: 1;
}

.tool-item {
  padding: 0.75rem;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  margin-bottom: 0.5rem;
}

.tool-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.tool-name {
  font-weight: 500;
  font-size: var(--text-sm);
  color: var(--text-primary);
}

.tool-category {
  font-size: var(--text-xs);
  font-weight: 600;
  padding: 0.15rem 0.4rem;
  border-radius: 9999px;
  background: var(--bg-elevated);
  color: var(--text-muted);
  white-space: nowrap;
}

.tool-desc {
  font-size: var(--text-sm);
  color: var(--text-muted);
  margin-top: 0.25rem;
  line-height: 1.4;
}

.tool-empty,
.tool-error {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2rem;
  font-size: var(--text-sm);
  color: var(--text-secondary);
}

.tool-error {
  color: var(--color-danger);
}
</style>
