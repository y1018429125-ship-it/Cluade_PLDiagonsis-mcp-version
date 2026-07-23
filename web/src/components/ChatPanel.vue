<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import { useSessionStore } from '@/stores/sessionStore'
import { renderMarkdown } from '@/utils/markdown'
import { createSkill } from '@/api/http'
import { formatTime } from '@/utils/time'
import 'katex/dist/katex.min.css'

const store = useSessionStore()
const input = ref('')
const listRef = ref<HTMLDivElement | null>(null)
const reportExpanded = ref<Record<string, boolean>>({})
const showCompletionReview = ref(false)
const reviewSessionId = ref<string | null>(null)
const showModifyInput = ref(false)
const modifyInstruction = ref('')

async function scrollToBottom() {
  await nextTick()
  if (listRef.value) {
    listRef.value.scrollTop = listRef.value.scrollHeight
  }
}

function toggleReport(msgId: string) {
  reportExpanded.value[msgId] = !reportExpanded.value[msgId]
}

function getActionLogForReview(): Array<{ action_type: string; tool_name: string; description: string; weight?: number }> {
  const sid = reviewSessionId.value
  if (!sid) return []
  const session = store.sessions.find((s) => s.session_id === sid)
  if (!session) return []
  return session.action_log ?? []
}

watch(() => store.messages.length, scrollToBottom)
watch(() => store.messages.map((m) => m.content), scrollToBottom, { deep: true })
watch(() => store.activeSessionId, () => {
  showCompletionReview.value = false
  reviewSessionId.value = null
  reportExpanded.value = {}
})

// 自动展开修改报告后的诊断卡片
watch(() => store.messages, (newMessages, oldMessages) => {
  const oldLen = oldMessages?.length ?? 0
  if (newMessages.length > oldLen) {
    const lastMsg = newMessages[newMessages.length - 1]
    if (
      lastMsg.role === 'assistant'
      && lastMsg.summary
      && lastMsg.report
      && lastMsg.eventType === 'complete'
      && lastMsg.content?.includes('修改')
    ) {
      reportExpanded.value[lastMsg.id] = true
      scrollToBottom()
    }
  }
}, { deep: true })

// 完成诊断后自动滚动到底部，确保用户看到 completion review 面板
watch(showCompletionReview, async (visible) => {
  if (visible) {
    await nextTick()
    if (listRef.value) {
      listRef.value.scrollTo({
        top: listRef.value.scrollHeight,
        behavior: 'smooth',
      })
    }
  }
})

function handleSend() {
  if (!input.value.trim() || store.isLoading) return
  store.postMessage(input.value)
  input.value = ''
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

function bubbleClass(role: string, eventType?: string): string {
  if (role === 'user') return 'bubble-user'
  if (eventType === 'error') return 'bubble-error'
  if (eventType === 'thinking') return 'bubble-thinking'
  return 'bubble-assistant'
}

async function handleCompleteDiagnosis() {
  const sessionId = store.activeSessionId
  if (!sessionId) return
  reviewSessionId.value = sessionId

  const data = await store.markSessionComplete()
  if (data?.suggest_save_skill) {
    showCompletionReview.value = true
  }
  // 如果无调整操作，markSessionComplete 已将会话标记为 completed，无需显示面板
}

async function handleSaveSkillFromReview() {
  const sessionId = reviewSessionId.value
  if (!sessionId) return
  try {
    const data = await store.fetchSkillSummary(sessionId)
    const name = prompt('技能名称:', data.suggested_name)
    if (name) {
      await createSkill(name, data.content)
      window.dispatchEvent(new CustomEvent('skill-saved'))
      showCompletionReview.value = false
      await store.markSessionComplete()
    }
  } catch (err) {
    alert(`保存技能失败: ${(err as Error).message}`)
  }
}

async function handleSkipSave() {
  showCompletionReview.value = false
  await store.markSessionComplete()
}

function handleClearMessages() {
  if (confirm('确定要清除当前对话的所有消息吗？')) {
    store.clearMessages()
    reportExpanded.value = {}
  }
}

function formatActionLabel(action: { action_type: string; tool_name: string; description: string; weight?: number }): string {
  switch (action.action_type) {
    case 'exclude':
      return `排除${action.tool_name}`
    case 'include':
      return `恢复${action.tool_name}`
    case 'recheck':
      return `复查${action.tool_name}`
    case 'adjust_weight':
      return `调整权重：${action.tool_name} ${action.weight ?? ''}`
    case 'modify_report':
      return `修改报告：${action.description || action.tool_name}`
    case 'complete':
      return '完成诊断'
    default:
      return `${action.action_type}${action.tool_name ? ': ' + action.tool_name : ''}`
  }
}

// @ts-expect-error Reserved for future action panel buttons
function handleExcludeTool(toolName: string) {
  store.postMessage(`排除${toolName}`)
}
// @ts-expect-error Reserved for future action panel buttons
function handleRecheckTool(toolName: string) {
  store.postMessage(`重新检查${toolName}`)
}
// @ts-expect-error Reserved for future action panel buttons
function handleAdjustWeight(toolName: string) {
  const w = prompt(`调整 ${toolName} 权重 (0.1-2.0):`)
  if (w) store.postMessage(`把${toolName}权重调到${w}`)
}
function handleModifyReport() {
  showModifyInput.value = true
}
function submitModifyReport() {
  if (!modifyInstruction.value.trim()) return
  store.postMessage(modifyInstruction.value)
  modifyInstruction.value = ''
  showModifyInput.value = false
}
</script>

<template>
  <section class="chat-panel">
    <div ref="listRef" class="message-list">
      <div
        v-for="msg in store.messages"
        :key="msg.id"
        class="message-row"
        :class="msg.role"
      >
        <div class="bubble" :class="bubbleClass(msg.role, msg.eventType)">
          <!-- Start / Loading state -->
          <div
            v-if="msg.role === 'assistant' && msg.eventType === 'start'"
            class="thinking"
          >
            <span class="spinner"></span>
            <span>诊断中...</span>
          </div>

          <!-- Thinking state -->
          <div
            v-else-if="msg.role === 'assistant' && msg.eventType === 'thinking'"
            class="thinking"
          >
            <span class="spinner"></span>
            <span>诊断中...</span>
          </div>

          <!-- Complete state with summary card -->
          <div v-else-if="msg.role === 'assistant' && msg.summary" class="summary-card">
            <div class="summary-header">诊断完成</div>
            <div class="summary-body">
              <div v-if="msg.summary.voltage_level" class="summary-row">
                <span class="summary-label">电压等级</span>
                <span class="summary-value">{{ msg.summary.voltage_level }}</span>
              </div>
              <div v-if="msg.summary.line_name" class="summary-row">
                <span class="summary-label">线路名称</span>
                <span class="summary-value">{{ msg.summary.line_name }}</span>
              </div>
              <div v-if="msg.summary.fault_time" class="summary-row">
                <span class="summary-label">故障时间</span>
                <span class="summary-value time">{{ formatTime(msg.summary.fault_time) }}</span>
              </div>
              <div class="summary-row">
                <span class="summary-label">故障类型</span>
                <span class="summary-value">{{ msg.summary.fault_type }}</span>
              </div>
              <div class="summary-row">
                <span class="summary-label">置信度</span>
                <div class="confidence-bar">
                  <div
                    class="confidence-bar-fill"
                    :class="{ high: msg.summary.confidence >= 0.7, medium: msg.summary.confidence >= 0.4 && msg.summary.confidence < 0.7, low: msg.summary.confidence < 0.4 }"
                    :style="{ width: (msg.summary.confidence * 100) + '%' }"
                  />
                </div>
                <span class="summary-value">{{ Math.round(msg.summary.confidence * 100) }}%</span>
              </div>
            </div>
            <div v-if="msg.summary?.action_log?.length || store.activeSession?.action_log?.length" class="action-log">
              <div class="action-log-label">操作记录</div>
              <div class="action-log-items">
                <span
                  v-for="(action, idx) in (msg.summary?.action_log ?? store.activeSession?.action_log ?? [])"
                  :key="idx"
                  class="action-tag"
                >
                  {{ formatActionLabel(action) }}
                </span>
              </div>
            </div>
            <div v-if="msg.report" class="report-section">
              <button class="view-report-btn" @click="toggleReport(msg.id)">
                {{ reportExpanded[msg.id] ? '收起报告' : '查看报告' }}
              </button>
              <div v-if="reportExpanded[msg.id]" class="report-content markdown-body" v-html="renderMarkdown(msg.report)"></div>
            </div>
            <div class="summary-actions">
              <button
                v-if="store.activeSession?.status === 'modifying' || store.activeSession?.status === 'excluded'"
                class="complete-btn"
                @click="handleCompleteDiagnosis"
                :disabled="store.isLoading"
              >
                完成诊断
              </button>
            </div>
            <!-- Action Panel -->
            <div v-if="store.activeSession?.status === 'modifying'" class="action-panel">
              <div class="action-panel-title">快捷操作</div>
              <div class="action-buttons">
                <button class="action-btn" @click="handleModifyReport">修改报告</button>
              </div>
              <div v-if="showModifyInput" class="modify-input-panel">
                <textarea
                  v-model="modifyInstruction"
                  rows="2"
                  placeholder="描述您想要的修改..."
                  @keydown="(e: KeyboardEvent) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submitModifyReport() } }"
                ></textarea>
                <div class="modify-actions">
                  <button class="action-btn primary" @click="submitModifyReport">确认</button>
                  <button class="action-btn" @click="showModifyInput = false">取消</button>
                </div>
              </div>
            </div>
          </div>

          <!-- Regular assistant message -->
          <div v-else-if="msg.role === 'assistant'">
            <div v-if="!msg.content && store.isLoading" class="thinking">
              <span class="spinner"></span>
              <span>诊断中...</span>
            </div>
            <div
              v-if="msg.content"
              class="markdown-body"
              v-html="renderMarkdown(msg.content)"
            ></div>
          </div>

          <!-- User message -->
          <div v-else>{{ msg.content }}</div>
        </div>
        <div class="msg-time">
          {{ new Date(msg.timestamp).toLocaleTimeString() }}
        </div>
      </div>

      <div v-if="store.messages.length === 0" class="welcome">
        <h1>输电线路故障综合诊断智能体</h1>
        <p>请输入线路信息开始诊断</p>
      </div>

      <!-- Completion review panel -->
      <div v-if="showCompletionReview" class="completion-review">
        <div class="review-header">诊断完成 — 操作回顾</div>
        <div class="review-body">
          <div v-if="getActionLogForReview().length > 0" class="review-actions-list">
            <div class="review-label">本次诊断中您执行了以下操作：</div>
            <div class="review-tags">
              <span
                v-for="(action, idx) in getActionLogForReview()"
                :key="idx"
                class="review-tag"
              >
                {{ formatActionLabel(action) }}
              </span>
            </div>
          </div>
          <div v-else class="review-no-actions">
            本次诊断未进行修改操作。
          </div>
          <div class="review-prompt">是否将该诊断策略保存为新技能？</div>
          <div class="review-buttons">
            <button class="save-skill-btn" @click="handleSaveSkillFromReview">保存技能</button>
            <button class="skip-save-btn" @click="handleSkipSave">不保存</button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="store.messages.length > 0" class="chat-toolbar">
      <span class="msg-count">
        {{ store.messages.filter(m => m.role === 'user').length }} 轮对话
      </span>
      <button class="clear-btn" @click="handleClearMessages">
        清除对话
      </button>
    </div>

    <div class="input-area">
      <textarea
        v-model="input"
        rows="2"
        placeholder="输入消息..."
        @keydown="handleKeydown"
        :disabled="store.isLoading"
      ></textarea>
      <button
        class="send-btn"
        :disabled="!input.trim() || store.isLoading"
        @click="handleSend"
      >
        发送
      </button>
    </div>

    <div v-if="store.error" class="error-bar">
      {{ store.error }}
    </div>
  </section>
</template>

<style scoped>
.chat-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--bg-base);
  min-width: 0;
  color: var(--text-primary);
}

.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem 2rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.message-row {
  display: flex;
  flex-direction: column;
  max-width: 80%;
}

.message-row.user {
  align-self: flex-end;
  align-items: flex-end;
}

.message-row.assistant {
  align-self: flex-start;
  align-items: flex-start;
}

.bubble {
  padding: 0.75rem 1rem;
  border-radius: var(--radius-lg);
  font-size: var(--text-md);
  line-height: 1.6;
  word-break: break-word;
}

.bubble-user {
  background: var(--color-primary);
  color: #fff;
  border-bottom-right-radius: var(--radius-sm);
}

.bubble-assistant {
  background: var(--bg-panel);
  color: var(--text-primary);
  border: 1px solid var(--border-subtle);
  border-bottom-left-radius: var(--radius-sm);
}

.bubble-thinking {
  background: rgba(245, 158, 11, 0.08);
  color: var(--color-warning);
  border: 1px solid rgba(245, 158, 11, 0.2);
  border-bottom-left-radius: var(--radius-sm);
}

.bubble-error {
  background: rgba(239, 68, 68, 0.08);
  color: var(--color-danger);
  border: 1px solid rgba(239, 68, 68, 0.2);
  border-bottom-left-radius: var(--radius-sm);
}

.thinking {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-style: italic;
}

.spinner {
  display: inline-block;
  width: 0.875rem;
  height: 0.875rem;
  border: 2px solid var(--color-warning);
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.msg-time {
  font-size: var(--text-xs);
  color: var(--text-muted);
  margin-top: 0.25rem;
}

.welcome {
  margin: auto;
  text-align: center;
  color: var(--text-muted);
}

.welcome h1 {
  font-size: var(--text-xl);
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 0.5rem;
}

.chat-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.5rem 2rem;
  border-top: 1px solid var(--border-subtle);
  background: var(--bg-panel);
  font-size: var(--text-sm);
}

.msg-count {
  color: var(--text-muted);
}

.clear-btn {
  background: transparent;
  color: var(--color-danger);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: var(--radius-md);
  padding: 0.25rem 0.625rem;
  font-size: var(--text-xs);
  cursor: pointer;
  transition: all var(--duration-fast);
}

.clear-btn:hover {
  background: rgba(239, 68, 68, 0.15);
  color: #fff;
}

.input-area {
  display: flex;
  gap: 0.75rem;
  padding: 1rem 2rem;
  border-top: 1px solid var(--border-subtle);
  background: var(--bg-panel);
}

.input-area textarea {
  flex: 1;
  resize: none;
  border: 1px solid var(--border-medium);
  border-radius: var(--radius-md);
  padding: 0.625rem 0.875rem;
  font-size: var(--text-md);
  font-family: inherit;
  line-height: 1.5;
  outline: none;
  transition: border-color var(--duration-fast);
  background: var(--bg-input);
  color: var(--text-primary);
}

.input-area textarea:focus {
  border-color: var(--color-primary);
}

.input-area textarea:disabled {
  background: var(--bg-elevated);
  cursor: not-allowed;
}

.send-btn {
  align-self: flex-end;
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: var(--radius-md);
  padding: 0.625rem 1.25rem;
  font-size: var(--text-sm);
  font-weight: 500;
  cursor: pointer;
  transition: opacity var(--duration-fast);
}

.send-btn:hover:not(:disabled) {
  opacity: 0.9;
}

.send-btn:disabled {
  background: var(--text-muted);
  cursor: not-allowed;
}

.error-bar {
  padding: 0.75rem 2rem;
  background: rgba(239, 68, 68, 0.08);
  color: var(--color-danger);
  font-size: var(--text-sm);
  border-top: 1px solid rgba(239, 68, 68, 0.2);
}

/* Summary card */
.summary-card {
  background: var(--bg-panel-glass);
  border: 1px solid var(--border-medium);
  border-radius: var(--radius-lg);
  overflow: hidden;
  backdrop-filter: blur(8px);
  min-width: 280px;
}

.summary-header {
  padding: 0.75rem 1rem;
  background: rgba(16, 185, 129, 0.08);
  border-bottom: 1px solid var(--border-subtle);
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 600;
  color: var(--color-success);
}

.summary-body {
  padding: 0.75rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.summary-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.375rem 0;
  border-bottom: 1px solid var(--border-subtle);
}

.summary-row:last-child {
  border-bottom: none;
}

.summary-label {
  color: var(--text-secondary);
  font-size: var(--text-sm);
}

.summary-value {
  font-weight: 600;
  color: var(--text-primary);
  font-size: var(--text-sm);
}

.summary-value.time {
  font-family: var(--font-mono);
  color: var(--color-accent);
}

.confidence-bar {
  width: 120px;
  height: 6px;
  background: var(--bg-elevated);
  border-radius: 3px;
  overflow: hidden;
}

.confidence-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width var(--duration-slow) var(--ease-out-expo);
}

.confidence-bar-fill.high { background: var(--color-success); }
.confidence-bar-fill.medium { background: var(--color-warning); }
.confidence-bar-fill.low { background: var(--color-danger); }

.action-log {
  padding: 0.75rem 1rem;
  border-top: 1px solid var(--border-subtle);
}

.action-log-label {
  font-size: var(--text-xs);
  color: var(--text-muted);
  margin-bottom: 0.375rem;
}

.action-log-items {
  display: flex;
  flex-wrap: wrap;
  gap: 0.375rem;
}

.action-tag {
  display: inline-block;
  background: var(--bg-elevated);
  color: var(--text-secondary);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  padding: 0.125rem 0.5rem;
  font-size: var(--text-xs);
}

.view-report-btn {
  background: var(--bg-elevated);
  color: var(--text-secondary);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  padding: 0.375rem 0.75rem;
  font-size: var(--text-sm);
  font-weight: 500;
  cursor: pointer;
  transition: all var(--duration-fast);
}

.view-report-btn:hover {
  background: var(--border-subtle);
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.complete-btn {
  background: var(--color-success);
  color: #fff;
  border: none;
  border-radius: var(--radius-md);
  padding: 0.375rem 0.75rem;
  font-size: var(--text-sm);
  font-weight: 500;
  cursor: pointer;
  transition: opacity var(--duration-fast);
}

.complete-btn:hover:not(:disabled) {
  opacity: 0.9;
}

.complete-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.summary-actions {
  padding: 0.75rem 1rem;
  border-top: 1px solid var(--border-subtle);
}

/* Action Panel */
.action-panel {
  padding: 0.75rem 1rem;
  border-top: 1px solid var(--border-subtle);
  background: rgba(0, 0, 0, 0.35);
}

.action-panel-title {
  font-size: var(--text-xs);
  color: var(--text-muted);
  margin-bottom: 0.625rem;
  text-transform: uppercase;
  letter-spacing: 0.1em;
}

.action-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.action-btn {
  background: transparent;
  color: var(--text-secondary);
  border: 1px solid var(--border-medium);
  border-radius: var(--radius-sm);
  padding: 0.375rem 0.75rem;
  font-size: var(--text-sm);
  cursor: pointer;
  transition: all var(--duration-fast);
}

.action-btn:hover {
  background: rgba(59, 130, 246, 0.1);
  border-color: var(--color-primary);
  color: var(--color-primary);
  transform: translateY(-1px);
}

.action-btn.primary {
  background: var(--color-primary);
  color: #fff;
  border-color: var(--color-primary);
}

.action-btn.primary:hover {
  opacity: 0.9;
  transform: none;
}

.modify-input-panel {
  margin-top: 0.75rem;
  padding: 0.75rem;
  background: var(--bg-input);
  border: 1px solid var(--border-medium);
  border-radius: var(--radius-md);
}

.modify-input-panel textarea {
  width: 100%;
  resize: none;
  background: var(--bg-base);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  padding: 0.625rem;
  font-size: var(--text-base);
  color: var(--text-primary);
  line-height: 1.6;
  font-family: inherit;
}

.modify-input-panel textarea:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}

.modify-actions {
  display: flex;
  gap: 0.5rem;
  margin-top: 0.5rem;
}

/* Report section */
.report-section {
  padding: 0.75rem 1rem;
  border-top: 1px solid var(--border-subtle);
}

.report-content {
  margin-top: 0.75rem;
  padding: 0.75rem;
  background: var(--bg-base);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  max-height: 400px;
  overflow-y: auto;
}

/* Completion review panel */
.completion-review {
  background: var(--bg-panel);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  padding: 1.25rem;
  margin-top: 1rem;
  max-width: 480px;
  align-self: flex-start;
}

.review-header {
  font-weight: 600;
  font-size: var(--text-md);
  color: var(--text-primary);
  margin-bottom: 1rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--border-subtle);
}

.review-body {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.review-label {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  margin-bottom: 0.375rem;
}

.review-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.375rem;
  margin-bottom: 0.5rem;
}

.review-tag {
  display: inline-block;
  background: var(--bg-elevated);
  color: var(--text-secondary);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  padding: 0.25rem 0.5rem;
  font-size: var(--text-xs);
}

.review-no-actions {
  font-size: var(--text-sm);
  color: var(--text-muted);
  font-style: italic;
}

.review-prompt {
  font-size: var(--text-md);
  font-weight: 500;
  color: var(--text-primary);
  margin-top: 0.5rem;
}

.review-buttons {
  display: flex;
  gap: 0.75rem;
  margin-top: 0.5rem;
}

.save-skill-btn {
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: var(--radius-md);
  padding: 0.5rem 1rem;
  font-size: var(--text-sm);
  font-weight: 500;
  cursor: pointer;
  transition: opacity var(--duration-fast);
}

.save-skill-btn:hover {
  opacity: 0.9;
}

.skip-save-btn {
  background: transparent;
  color: var(--text-secondary);
  border: 1px solid var(--border-medium);
  border-radius: var(--radius-md);
  padding: 0.5rem 1rem;
  font-size: var(--text-sm);
  font-weight: 500;
  cursor: pointer;
  transition: all var(--duration-fast);
}

.skip-save-btn:hover {
  background: var(--bg-elevated);
  border-color: var(--text-secondary);
}
</style>

<style>
.markdown-body p {
  margin: 0 0 0.5rem;
}

.markdown-body p:last-child {
  margin-bottom: 0;
}

.markdown-body pre {
  background: var(--bg-elevated);
  padding: 0.75rem;
  border-radius: var(--radius-md);
  overflow-x: auto;
  font-size: var(--text-sm);
}

.markdown-body code {
  background: var(--bg-elevated);
  padding: 0.125rem 0.25rem;
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
}

.markdown-body pre code {
  background: transparent;
  padding: 0;
}

.markdown-body ul,
.markdown-body ol {
  margin: 0.5rem 0;
  padding-left: 1.25rem;
}

.markdown-body h1,
.markdown-body h2,
.markdown-body h3,
.markdown-body h4 {
  margin: 0.75rem 0 0.5rem;
  font-weight: 600;
  color: var(--text-primary);
}

.markdown-body table {
  border-collapse: collapse;
  width: 100%;
  font-size: var(--text-sm);
  margin: 0.5rem 0;
}

.markdown-body th,
.markdown-body td {
  border: 1px solid var(--border-subtle);
  padding: 0.375rem 0.5rem;
  text-align: left;
}

.markdown-body th {
  background: var(--bg-elevated);
  font-weight: 600;
}
</style>
