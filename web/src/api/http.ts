const BASE = ''

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}: ${res.statusText}`)
  }
  return res.json() as Promise<T>
}

export function getSessions() {
  return request<{ sessions: import('@/types').DiagnosisSession[] }>('/api/sessions')
}

export function getSession(sessionId: string) {
  return request<import('@/types').DiagnosisSession>(`/api/sessions/${sessionId}`)
}

export function switchSession(sessionId: string) {
  return request<{ success: boolean; session: import('@/types').DiagnosisSession }>(
    `/api/sessions/${sessionId}/switch`,
    { method: 'POST' }
  )
}

export function healthCheck() {
  return request<{ status: string }>('/api/health')
}

export interface ToolInfo {
  name: string
  display_name: string
  description: string
  category: string
}

export function getTools() {
  return request<{ tools: ToolInfo[] }>('/api/tools')
}

export interface SkillInfo {
  name: string
  description: string
  is_default: boolean
  source: string
}

export function getSkills() {
  return request<{ skills: SkillInfo[] }>('/api/skills')
}

export interface ReportItem {
  session_id: string
  line_name: string
  fault_type: string
  confidence: number
  fault_time: string
  created_at: string
  report: string
}

export function getReports() {
  return request<{ reports: ReportItem[] }>('/api/reports')
}

export function getDefaultSkill() {
  return request<{ default_skill: string; available_skills: string[] }>('/api/skills/default')
}

export function setDefaultSkill(name: string) {
  return request<{ success: boolean; default_skill: string; message: string }>(
    '/api/skills/default',
    {
      method: 'POST',
      body: JSON.stringify({ name }),
    }
  )
}

export function getSkillSummary(sessionId: string) {
  return request<{ content: string; suggested_name: string }>(
    `/api/sessions/${sessionId}/skill-summary`
  )
}

export function activateSkill(name: string) {
  return request<{ success: boolean; skill_name: string; message: string }>(
    `/api/skills/${encodeURIComponent(name)}/activate`,
    { method: 'POST' }
  )
}

export function deleteSkill(name: string) {
  return request<{ success: boolean; message: string }>(
    `/api/skills/${encodeURIComponent(name)}`,
    { method: 'DELETE' }
  )
}

export function resetSkills() {
  return request<{ success: boolean; message: string; default_weights: Record<string, number> }>(
    '/api/skills/reset',
    { method: 'POST' }
  )
}

export function clearSessions() {
  return request<{ success: boolean; message: string }>(
    '/api/sessions/clear',
    { method: 'POST' }
  )
}

export function completeSession(sessionId: string) {
  return request<{ success: boolean; session_id: string; line_name: string; status: string; suggest_save_skill?: boolean }>(
    `/api/sessions/${sessionId}/complete`,
    { method: 'POST' }
  )
}

export interface HistoryRelationSection {
  title: string
  answer: string
}

export function getHistoryRelation(sessionId: string) {
  return request<{ success: boolean; sections: HistoryRelationSection[] }>(
    '/api/history-relation',
    { method: 'POST', body: JSON.stringify({ session_id: sessionId }) }
  )
}

export interface FrontendLogPayload {
  session_id: string
  frontend_log: {
    messages: Array<{
      id?: string
      role: string
      content?: string
      eventType?: string
      timestamp?: string
      summary?: any
      report?: string
      thinking?: string
    }>
    timeline: Array<{
      event_type: string
      timestamp: string
      client_timestamp?: string
    }>
  }
}

export function sendFrontendLog(payload: FrontendLogPayload) {
  return request<{ success: boolean }>('/api/log/frontend', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function createSkill(name: string, content: string) {
  return request<{ success: boolean; message: string; name: string }>(
    '/api/skills',
    {
      method: 'POST',
      body: JSON.stringify({ name, content }),
    }
  )
}

export interface SettingsInfo {
  default_weights: Record<string, number>
  weight_range: { min: number; max: number }
  llm: { provider: string; model: string }
}

export function getSettings() {
  return request<SettingsInfo>('/api/settings')
}

export function updateWeights(weights: Record<string, number>) {
  return request<{ success: boolean; message: string; weights: Record<string, number> }>(
    '/api/settings/weights',
    {
      method: 'POST',
      body: JSON.stringify({ weights }),
    }
  )
}

// ------------------------------------------------------------------
// Template APIs
// ------------------------------------------------------------------

export interface TemplateInfo {
  name: string
  source_format: string
  parsed: boolean
  parsed_at: string | null
  is_active: boolean
}

export function getTemplates() {
  return request<{ templates: TemplateInfo[] }>('/api/templates')
}

export function uploadTemplate(file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return fetch('/api/templates/upload', {
    method: 'POST',
    body: formData,
  }).then(async (res) => {
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.error || `HTTP ${res.status}`)
    }
    return res.json() as Promise<{ success: boolean; template: { name: string; source_format: string; parsed: boolean } }>
  })
}

export function activateTemplate(name: string) {
  return request<{ success: boolean; active_template: string }>('/api/templates/activate', {
    method: 'POST',
    body: JSON.stringify({ template_name: name }),
  })
}

export function deleteTemplate(name: string) {
  return request<{ success: boolean; message: string }>(`/api/templates/${encodeURIComponent(name)}`, {
    method: 'DELETE',
  })
}

export function getTemplateParsed(name: string) {
  return request<{ name: string; content: string }>(`/api/templates/${encodeURIComponent(name)}/parsed`)
}
