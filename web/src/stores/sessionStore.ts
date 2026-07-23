import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { DiagnosisSession, ChatMessage, DiagnosisSummary } from '@/types'
import {
  getSessions,
  getSession,
  switchSession,
  completeSession,
  getSkillSummary,
  clearSessions,
  sendFrontendLog,
} from '@/api/http'
import {
  getTemplates,
  activateTemplate,
  deleteTemplate,
  uploadTemplate,
} from '@/api/http'
import { sendMessage } from '@/api/sse'

export const useSessionStore = defineStore('session', () => {
  const sessions = ref<DiagnosisSession[]>([])
  const activeSessionId = ref<string | null>(null)
  const messages = ref<ChatMessage[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const templates = ref<import('@/api/http').TemplateInfo[]>([])
  const activeTemplate = ref<string | null>(null)

  const activeSession = computed(() =>
    sessions.value.find((s) => s.session_id === activeSessionId.value) ?? null
  )

  async function loadSessions() {
    try {
      error.value = null
      const data = await getSessions()
      sessions.value = data.sessions
    } catch (err) {
      error.value = (err as Error).message
    }
  }

  async function selectSession(sessionId: string) {
    try {
      error.value = null
      const data = await switchSession(sessionId)
      if (data.success) {
        activeSessionId.value = sessionId

        const sessionData = await getSession(sessionId)

        // 恢复聊天记录
        if (sessionData.chat_history && sessionData.chat_history.length > 0) {
          messages.value = sessionData.chat_history.map((msg: any) => ({
            id: crypto.randomUUID(),
            role: msg.role,
            content: msg.content,
            eventType: msg.event_type || 'complete',
            timestamp: msg.timestamp || new Date().toISOString(),
            report: msg.report ?? undefined,
            summary: msg.summary ?? undefined,
          }))
        } else {
          messages.value = []
        }

        // 同步操作记录到会话列表
        const sessionIdx = sessions.value.findIndex((s) => s.session_id === sessionId)
        if (sessionIdx !== -1 && sessionData.action_log) {
          sessions.value[sessionIdx] = {
            ...sessions.value[sessionIdx],
            action_log: sessionData.action_log,
          }
        }

        // 如果会话有诊断报告但聊天记录中没有，补充诊断结果消息
        const hasReportInHistory = messages.value.some(
          (m) => m.role === 'assistant' && m.report
        )
        if (!hasReportInHistory && sessionData.latest_summary?.report) {
          const summary = sessionData.latest_summary
          const syntheticMsg: ChatMessage = {
            id: crypto.randomUUID(),
            role: 'assistant',
            content: `诊断完成：${summary.fault_type}（置信度 ${Math.round(summary.confidence * 100)}%）`,
            eventType: 'complete',
            timestamp: new Date().toISOString(),
            summary: {
              fault_type: summary.fault_type,
              confidence: summary.confidence,
              line_name: sessionData.line_name,
              voltage_level: summary.voltage_level,
            },
            report: summary.report ?? undefined,
          }
          messages.value.push(syntheticMsg)
        }
      }
    } catch (err) {
      error.value = (err as Error).message
    }
  }

  async function postMessage(text: string) {
    if (!text.trim() || isLoading.value) return

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: text.trim(),
      timestamp: new Date().toISOString(),
    }
    messages.value.push(userMsg)
    isLoading.value = true
    error.value = null

    const assistantMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: '',
      eventType: 'start',
      timestamp: new Date().toISOString(),
    }
    messages.value.push(assistantMsg)

    // 前端时间线：记录发送、开始接收、各事件到达时间
    const timeline: Array<{ event_type: string; timestamp: string; client_timestamp?: string }> = []
    timeline.push({ event_type: 'client_send', timestamp: new Date().toISOString() })

    let currentSessionId: string | null = null

    try {
      for await (const event of sendMessage(text.trim())) {
        timeline.push({
          event_type: event.event_type,
          timestamp: event.timestamp,
          client_timestamp: new Date().toISOString(),
        })

        if (event.session_id) {
          currentSessionId = event.session_id
        }

        assistantMsg.eventType = event.event_type

        if (event.event_type === 'thinking') {
          const msg = event.payload?.message ?? '思考中...'
          assistantMsg.thinking = msg
        } else if (event.event_type === 'result' || event.event_type === 'content') {
          assistantMsg.content += event.payload?.content ?? ''
        } else if (event.event_type === 'status') {
          const payloadStatus = event.payload?.status
          const validStatuses: DiagnosisSession['status'][] = ['pending', 'diagnosing', 'modifying', 'completed', 'excluded', 'rechecking']
          const newStatus = validStatuses.includes(payloadStatus) ? payloadStatus : undefined
          if (newStatus && activeSessionId.value) {
            const idx = sessions.value.findIndex(
              (s) => s.session_id === activeSessionId.value
            )
            if (idx !== -1) {
              sessions.value[idx] = { ...sessions.value[idx], status: newStatus }
            }
          }
        } else if (event.event_type === 'complete') {
          assistantMsg.content = event.payload?.message ?? '诊断完成'
          if (event.payload?.thinking) {
            assistantMsg.thinking = event.payload.thinking
          }
          if (event.payload?.summary) {
            assistantMsg.summary = event.payload.summary as DiagnosisSummary
          }
          if (event.payload?.report) {
            assistantMsg.report = event.payload.report as string
          }
          // 同步操作记录到会话列表
          const actions = event.payload?.summary?.action_log ?? event.payload?.action_log
          if (actions && event.session_id) {
            const idx = sessions.value.findIndex(
              (s) => s.session_id === event.session_id
            )
            if (idx !== -1) {
              sessions.value[idx] = {
                ...sessions.value[idx],
                action_log: actions.map((a: any) => ({
                  action_type: a.action_type,
                  tool_name: a.tool_name,
                  description: a.description,
                  weight: a.weight,
                  timestamp: a.timestamp || new Date().toISOString(),
                })),
              }
            }
          }
          // 确保诊断完成后会话状态为 modifying（兼容首次诊断场景）
          const completedStatus = event.payload?.status
          if (completedStatus && event.session_id) {
            const idx = sessions.value.findIndex(
              (s) => s.session_id === event.session_id
            )
            if (idx !== -1) {
              sessions.value[idx] = { ...sessions.value[idx], status: completedStatus }
            }
          }
        } else if (event.event_type === 'error') {
          assistantMsg.content = `错误: ${event.payload?.message ?? '未知错误'}`
          error.value = assistantMsg.content
        }

        if (event.session_id) {
          if (activeSessionId.value !== event.session_id) {
            activeSessionId.value = event.session_id
          }
          // Add new session to list if not present
          const existingIdx = sessions.value.findIndex(
            (s) => s.session_id === event.session_id
          )
          if (existingIdx === -1) {
            const lineName = event.payload?.line_name ?? '新会话'
            sessions.value.push({
              session_id: event.session_id,
              line_name: lineName,
              status: event.payload?.status ?? 'pending',
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
              action_log: [],
              fault_time: event.payload?.fault_time,
              voltage_level: event.payload?.voltage_level,
            })
          }
        }
      }
    } catch (err) {
      const msg = `错误: ${(err as Error).message}`
      assistantMsg.content = msg
      assistantMsg.eventType = 'error'
      error.value = msg
    } finally {
      isLoading.value = false
      assistantMsg.timestamp = new Date().toISOString()
      timeline.push({ event_type: 'client_stream_end', timestamp: new Date().toISOString() })

      // 将前端完整输出传回后端合并
      if (currentSessionId) {
        try {
          await sendFrontendLog({
            session_id: currentSessionId,
            frontend_log: {
              messages: messages.value.map((m) => ({
                id: m.id,
                role: m.role,
                content: m.content,
                eventType: m.eventType,
                timestamp: m.timestamp,
                summary: m.summary,
                report: m.report,
                thinking: m.thinking,
              })),
              timeline,
            },
          })
        } catch (e) {
          console.warn('发送前端日志失败:', e)
        }
      }
    }
  }

  function clearMessages() {
    messages.value = []
  }

  async function clearAllSessions() {
    if (!confirm('确定要清空所有诊断会话吗？此操作不可恢复。')) return
    try {
      error.value = null
      const data = await clearSessions()
      if (data.success) {
        sessions.value = []
        activeSessionId.value = null
        messages.value = []
      }
    } catch (err) {
      error.value = (err as Error).message
    }
  }

  async function markSessionComplete() {
    const sessionId = activeSessionId.value
    if (!sessionId) return null
    try {
      error.value = null
      const data = await completeSession(sessionId)
      if (data.success) {
        const idx = sessions.value.findIndex((s) => s.session_id === sessionId)
        if (idx !== -1) {
          sessions.value[idx] = { ...sessions.value[idx], status: 'completed' }
        }
      }
      return data
    } catch (err) {
      error.value = (err as Error).message
      return null
    }
  }

  async function fetchSkillSummary(sessionId: string) {
    try {
      error.value = null
      return await getSkillSummary(sessionId)
    } catch (err) {
      error.value = (err as Error).message
      throw err
    }
  }

  async function loadTemplates() {
    try {
      error.value = null
      const data = await getTemplates()
      templates.value = data.templates
      const active = data.templates.find((t) => t.is_active)
      if (active) {
        activeTemplate.value = active.name
      }
    } catch (err) {
      error.value = (err as Error).message
    }
  }

  async function setActiveTemplate(name: string) {
    try {
      error.value = null
      const data = await activateTemplate(name)
      if (data.success) {
        activeTemplate.value = name
        await loadTemplates()
      }
    } catch (err) {
      error.value = (err as Error).message
    }
  }

  async function removeTemplate(name: string) {
    try {
      error.value = null
      const data = await deleteTemplate(name)
      if (data.success) {
        templates.value = templates.value.filter((t) => t.name !== name)
        if (activeTemplate.value === name) {
          activeTemplate.value = null
        }
      }
    } catch (err) {
      error.value = (err as Error).message
    }
  }

  async function addTemplate(file: File) {
    try {
      error.value = null
      const data = await uploadTemplate(file)
      if (data.success) {
        await loadTemplates()
      }
      return data
    } catch (err) {
      error.value = (err as Error).message
      throw err
    }
  }

  return {
    sessions,
    activeSessionId,
    activeSession,
    messages,
    isLoading,
    error,
    templates,
    activeTemplate,
    loadSessions,
    selectSession,
    postMessage,
    clearMessages,
    clearAllSessions,
    markSessionComplete,
    fetchSkillSummary,
    loadTemplates,
    setActiveTemplate,
    removeTemplate,
    addTemplate,
  }
})
