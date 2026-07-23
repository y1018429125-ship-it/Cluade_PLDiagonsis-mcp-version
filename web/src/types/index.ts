export interface DiagnosisSummary {
  fault_type: string
  confidence: number
  primary_tool?: string
  line_name?: string
  voltage_level?: string
  fault_time?: string
  action_log?: Array<{
    action_type: string
    tool_name: string
    description: string
    weight?: number
  }>
}

export interface UserAction {
  action_type: string
  tool_name: string
  description: string
  weight?: number
  timestamp: string
}

export interface DiagnosisSession {
  session_id: string
  line_name: string
  status: 'pending' | 'diagnosing' | 'modifying' | 'completed' | 'excluded' | 'rechecking'
  voltage_level?: string
  fault_time?: string
  created_at: string
  updated_at: string
  latest_summary?: {
    fault_type: string
    confidence: number
    report: string | null
    line_name?: string
    voltage_level?: string
    fault_time?: string
  }
  chat_history?: ChatMessage[]
  action_log?: UserAction[]
}

export interface SSEEvent {
  event_type: 'start' | 'thinking' | 'result' | 'content' | 'complete' | 'error' | 'status'
  session_id: string
  payload: any
  timestamp: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  eventType?: SSEEvent['event_type']
  timestamp: string
  thinking?: string
  thinkingCollapsed?: boolean
  summary?: DiagnosisSummary
  report?: string
}
