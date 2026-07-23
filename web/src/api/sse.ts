import type { SSEEvent } from '@/types'

const CHAT_URL = '/chat'
const MAX_RETRIES = 3
const RETRY_DELAY_MS = 2000

export async function* sendMessage(message: string): AsyncGenerator<SSEEvent> {
  let attempt = 0

  while (attempt < MAX_RETRIES) {
    try {
      const res = await fetch(CHAT_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message }),
      })

      if (!res.ok || !res.body) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`)
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n\n')
        buffer = lines.pop() ?? ''

        for (const block of lines) {
          const event = parseSSEBlock(block)
          if (event) yield event
        }
      }

      if (buffer.trim()) {
        const event = parseSSEBlock(buffer)
        if (event) yield event
      }

      return
    } catch (err) {
      attempt++
      if (attempt >= MAX_RETRIES) {
        yield {
          event_type: 'error',
          session_id: '',
          payload: { message: (err as Error).message },
          timestamp: new Date().toISOString(),
        }
        return
      }
      await delay(RETRY_DELAY_MS)
    }
  }
}

function parseSSEBlock(block: string): SSEEvent | null {
  const lines = block.split('\n')
  let data = ''

  for (const line of lines) {
    if (line.startsWith('data:')) {
      data = line.slice(5).trim()
    }
  }

  if (!data) return null

  try {
    return JSON.parse(data) as SSEEvent
  } catch {
    return null
  }
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}
