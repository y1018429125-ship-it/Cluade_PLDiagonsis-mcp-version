<script setup lang="ts">
import { useSessionStore } from '@/stores/sessionStore'
import { onMounted } from 'vue'
import { formatTime } from '@/utils/time'

const store = useSessionStore()

const props = defineProps<{
  currentView: 'chat' | 'reports' | 'templates'
}>()

const emit = defineEmits<{
  (e: 'switchView', view: 'chat' | 'reports' | 'templates'): void
}>()

onMounted(() => {
  store.loadSessions()
})

function statusClass(status: string): string {
  switch (status) {
    case 'pending':
      return 'status-pending'
    case 'diagnosing':
      return 'status-diagnosing'
    case 'modifying':
      return 'status-modifying'
    case 'completed':
      return 'status-completed'
    case 'excluded':
      return 'status-excluded'
    case 'rechecking':
      return 'status-rechecking'
    default:
      return ''
  }
}

function statusLabel(status: string): string {
  const map: Record<string, string> = {
    pending: '待处理',
    diagnosing: '诊断中',
    modifying: '修改中',
    completed: '已完成',
    excluded: '已排除',
    rechecking: '复查中',
  }
  return map[status] ?? status
}

function handleSelect(session: import('@/types').DiagnosisSession) {
  if (session.status === 'completed') return
  emit('switchView', 'chat')
  store.selectSession(session.session_id)
}
</script>

<template>
  <aside class="sidebar">
    <header class="sidebar-header">
      <h2>诊断列表</h2>
      <button class="refresh-btn" @click="store.loadSessions" title="刷新">
        &#x21bb;
      </button>
    </header>

    <ul class="session-list">
      <li
        v-for="session in store.sessions"
        :key="session.session_id"
        class="session-item"
        :class="{ active: store.activeSessionId === session.session_id, disabled: session.status === 'completed' }"
        @click="handleSelect(session)"
      >
        <div class="session-row">
          <span class="line-name">{{ session.line_name }}</span>
          <span class="status-badge" :class="statusClass(session.status)">
            {{ statusLabel(session.status) }}
          </span>
        </div>
        <div class="session-meta">
          <span v-if="session.voltage_level" class="meta-tag">{{ session.voltage_level }}</span>
          <span v-if="session.fault_time" class="meta-tag fault-time">{{ formatTime(session.fault_time) }}</span>
          <span v-else class="meta-tag">{{ formatTime(session.created_at) }}</span>
        </div>
      </li>
    </ul>

    <div v-if="store.sessions.length === 0" class="empty">
      暂无会话
    </div>

    <div class="nav-links">
      <button
        class="nav-link"
        :class="{ active: props.currentView === 'chat' }"
        @click="emit('switchView', 'chat')"
      >
        诊断会话
      </button>
      <button
        class="nav-link"
        :class="{ active: props.currentView === 'reports' }"
        @click="emit('switchView', 'reports')"
      >
        报告历史
      </button>
      <button
        class="nav-link"
        :class="{ active: props.currentView === 'templates' }"
        @click="emit('switchView', 'templates')"
      >
        模板管理
      </button>
    </div>

    <div v-if="store.sessions.length > 0" class="sidebar-footer">
      <button class="clear-all-btn" @click="store.clearAllSessions">
        清空所有会话
      </button>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: 260px;
  min-width: 260px;
  background: var(--bg-panel);
  color: var(--text-primary);
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border-subtle);
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem;
  border-bottom: 1px solid var(--border-subtle);
  font-weight: 600;
  font-size: var(--text-sm);
}

.sidebar-header h2 {
  font-size: var(--text-sm);
  font-weight: 600;
  margin: 0;
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

.session-list {
  list-style: none;
  margin: 0;
  padding: 0;
  overflow-y: auto;
  flex: 1;
}

.session-item {
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--border-subtle);
  cursor: pointer;
  transition: background var(--duration-fast);
}

.session-item:hover {
  background: var(--bg-elevated);
}

.session-item.active {
  background: rgba(59, 130, 246, 0.08);
  border-left: 3px solid var(--color-primary);
}

.session-item.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.session-item.disabled:hover {
  background: transparent;
}

.session-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.line-name {
  font-weight: 500;
  font-size: var(--text-md);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-primary);
}

.status-badge {
  font-size: var(--text-xs);
  font-weight: 600;
  text-transform: uppercase;
  padding: 0.15rem 0.4rem;
  border-radius: 9999px;
  white-space: nowrap;
  flex-shrink: 0;
}

.status-pending {
  background: var(--bg-elevated);
  color: var(--text-secondary);
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.status-diagnosing {
  background: var(--color-warning);
  color: #fff;
  animation: pulse 1.5s ease-in-out infinite;
}

.status-modifying {
  background: var(--color-primary);
  color: #fff;
}

.status-completed {
  background: var(--color-success);
  color: #fff;
}

.status-excluded {
  background: var(--color-danger);
  color: #fff;
}

.status-rechecking {
  background: #8b5cf6;
  color: #fff;
}

.session-meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: 0.25rem;
  font-size: var(--text-xs);
  flex-wrap: wrap;
}

.meta-tag {
  padding: 0.125rem 0.375rem;
  border-radius: var(--radius-sm);
  font-size: var(--text-xs);
  background: var(--bg-elevated);
  color: var(--text-secondary);
}

.meta-tag.voltage {
  background: rgba(59, 130, 246, 0.12);
  color: var(--color-primary);
  font-family: var(--font-mono);
}

.meta-tag.fault-time {
  font-family: var(--font-mono);
  color: var(--text-secondary);
  background: transparent;
  padding: 0;
  letter-spacing: 0.02em;
}

.empty {
  padding: 2rem;
  text-align: center;
  color: var(--text-muted);
  font-size: var(--text-sm);
}

.sidebar-footer {
  padding: 0.75rem 1rem;
  border-top: 1px solid var(--border-subtle);
}

.clear-all-btn {
  width: 100%;
  background: transparent;
  color: var(--color-danger);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: var(--radius-md);
  padding: 0.5rem;
  font-size: var(--text-sm);
  cursor: pointer;
  transition: all var(--duration-fast);
}

.clear-all-btn:hover {
  background: rgba(239, 68, 68, 0.15);
  color: #fff;
}

.nav-links {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding: 0.75rem 1rem;
  border-top: 1px solid var(--border-subtle);
}

.nav-link {
  background: transparent;
  color: var(--text-secondary);
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  padding: 0.5rem 0.75rem;
  font-size: var(--text-sm);
  text-align: left;
  cursor: pointer;
  transition: all var(--duration-fast);
}

.nav-link:hover {
  background: var(--bg-elevated);
  color: var(--text-primary);
}

.nav-link.active {
  background: var(--bg-elevated);
  color: var(--text-primary);
  border-color: var(--border-medium);
}
</style>
