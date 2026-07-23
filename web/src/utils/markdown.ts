import { marked } from 'marked'
import markedKatex from 'marked-katex-extension'

marked.use(
  markedKatex({
    throwOnError: false,
    output: 'html',
  })
)

marked.setOptions({
  breaks: true,
  gfm: true,
})

export function renderMarkdown(raw: string): string {
  return marked.parse(raw) as string
}
