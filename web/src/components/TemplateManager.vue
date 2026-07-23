<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useSessionStore } from '@/stores/sessionStore'
import { getTemplateParsed } from '@/api/http'
import type { TemplateInfo } from '@/api/http'

const store = useSessionStore()

const fileInput = ref<HTMLInputElement | null>(null)
const isUploading = ref(false)
const previewName = ref<string | null>(null)
const previewContent = ref<string>('')
const isLoadingPreview = ref(false)

function triggerFileUpload() {
  fileInput.value?.click()
}

async function handleFileChange(event: Event) {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return

  const validExtensions = ['.md', '.docx', '.pdf']
  const ext = file.name.slice(file.name.lastIndexOf('.')).toLowerCase()
  if (!validExtensions.includes(ext)) {
    alert('仅支持 .md, .docx, .pdf 格式的文件')
    if (fileInput.value) fileInput.value.value = ''
    return
  }

  isUploading.value = true
  try {
    await store.addTemplate(file)
  } catch (err) {
    alert(`上传失败: ${(err as Error).message}`)
  } finally {
    isUploading.value = false
    if (fileInput.value) fileInput.value.value = ''
  }
}

async function handleActivate(name: string) {
  try {
    await store.setActiveTemplate(name)
  } catch (err) {
    alert(`激活失败: ${(err as Error).message}`)
  }
}

async function handleDelete(name: string) {
  if (!confirm(`确定要删除模板 "${name}" 吗？此操作不可恢复。`)) return
  try {
    await store.removeTemplate(name)
  } catch (err) {
    alert(`删除失败: ${(err as Error).message}`)
  }
}

async function handleView(template: TemplateInfo) {
  if (!template.parsed) {
    alert('该模板尚未解析，暂无内容可查看')
    return
  }
  previewName.value = template.name
  isLoadingPreview.value = true
  previewContent.value = ''
  try {
    const data = await getTemplateParsed(template.name)
    previewContent.value = data.content
  } catch (err) {
    previewContent.value = `加载失败: ${(err as Error).message}`
  } finally {
    isLoadingPreview.value = false
  }
}

function closePreview() {
  previewName.value = null
  previewContent.value = ''
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '-'
  const d = new Date(dateStr)
  if (isNaN(d.getTime())) return dateStr
  return d.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function getFormatLabel(format: string): string {
  const map: Record<string, string> = {
    md: 'Markdown',
    docx: 'Word',
    pdf: 'PDF',
  }
  return map[format.toLowerCase()] || format.toUpperCase()
}

function getFormatClass(format: string): string {
  const map: Record<string, string> = {
    md: 'format-md',
    docx: 'format-docx',
    pdf: 'format-pdf',
  }
  return map[format.toLowerCase()] || 'format-default'
}

onMounted(() => {
  store.loadTemplates()
})
</script>

<template>
  <div class="template-manager">
    <header class="tm-header">
      <h1 class="tm-title">报告模板管理</h1>
      <button
        type="button"
        class="tm-upload-btn"
        :disabled="isUploading"
        @click="triggerFileUpload"
      >
        <span v-if="isUploading">上传中...</span>
        <span v-else>+ 上传模板</span>
      </button>
      <input
        ref="fileInput"
        type="file"
        accept=".md,.docx,.pdf"
        class="tm-file-input"
        @change="handleFileChange"
      />
    </header>

    <div v-if="store.error" class="tm-error">
      {{ store.error }}
    </div>

    <div v-if="store.templates.length === 0 && !store.error" class="tm-empty">
      暂无模板，请上传模板文件
    </div>

    <ul v-else class="tm-list">
      <li
        v-for="template in store.templates"
        :key="template.name"
        class="tm-item"
        :class="{ 'tm-item--active': template.is_active }"
      >
        <div class="tm-item-main">
          <div class="tm-item-info">
            <span class="tm-item-name">{{ template.name }}</span>
            <span class="tm-format-badge" :class="getFormatClass(template.source_format)">
              {{ getFormatLabel(template.source_format) }}
            </span>
            <span
              class="tm-status-badge"
              :class="template.parsed ? 'tm-status--parsed' : 'tm-status--pending'"
            >
              {{ template.parsed ? '已解析' : '待解析' }}
            </span>
            <span v-if="template.is_active" class="tm-active-badge">当前激活</span>
          </div>
          <div class="tm-item-meta">
            <span class="tm-parsed-at">
              解析时间: {{ formatDate(template.parsed_at) }}
            </span>
          </div>
        </div>
        <div class="tm-item-actions">
          <button
            v-if="!template.is_active"
            type="button"
            class="tm-action-btn tm-action--activate"
            @click="handleActivate(template.name)"
          >
            激活
          </button>
          <button
            type="button"
            class="tm-action-btn tm-action--view"
            @click="handleView(template)"
          >
            查看
          </button>
          <button
            type="button"
            class="tm-action-btn tm-action--delete"
            @click="handleDelete(template.name)"
          >
            删除
          </button>
        </div>
      </li>
    </ul>

    <div
      v-if="previewName"
      class="tm-preview-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="preview-title"
      @click.self="closePreview"
    >
      <div class="tm-preview-panel">
        <div class="tm-preview-header">
          <h3 id="preview-title" class="tm-preview-title">{{ previewName }}</h3>
          <button
            type="button"
            class="tm-preview-close"
            aria-label="关闭预览"
            @click="closePreview"
          >&times;</button>
        </div>
        <div class="tm-preview-body">
          <div v-if="isLoadingPreview" class="tm-preview-loading">加载中...</div>
          <pre v-else class="tm-preview-content">{{ previewContent }}</pre>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.template-manager {
  padding: 1.5rem;
  max-width: 900px;
  margin: 0 auto;
  color: var(--text-primary);
  font-family: var(--font-body);
  font-size: var(--text-base);
}

.tm-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1.5rem;
}

.tm-title {
  font-family: var(--font-display);
  font-size: var(--text-lg);
  font-weight: 600;
  margin: 0;
  color: var(--text-primary);
}

.tm-upload-btn {
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: var(--radius-md);
  padding: 0.5rem 1.25rem;
  font-size: var(--text-sm);
  font-family: var(--font-body);
  cursor: pointer;
  transition: opacity var(--duration-fast) ease;
}

.tm-upload-btn:hover:not(:disabled) {
  opacity: 0.9;
}

.tm-upload-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.tm-file-input {
  display: none;
}

.tm-error {
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: var(--color-danger);
  padding: 0.75rem 1rem;
  border-radius: var(--radius-md);
  margin-bottom: 1rem;
  font-size: var(--text-sm);
}

.tm-empty {
  text-align: center;
  padding: 3rem 1rem;
  color: var(--text-muted);
  font-size: var(--text-md);
  border: 1px dashed var(--border-medium);
  border-radius: var(--radius-lg);
}

.tm-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.tm-item {
  background: var(--bg-panel);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  padding: 1rem 1.25rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  transition: border-color var(--duration-fast) ease;
}

.tm-item:hover {
  border-color: var(--border-medium);
}

.tm-item--active {
  border-color: var(--color-success);
  box-shadow: 0 0 0 1px rgba(16, 185, 129, 0.15);
}

.tm-item-main {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  flex: 1;
  min-width: 0;
}

.tm-item-info {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.tm-item-name {
  font-weight: 500;
  font-size: var(--text-md);
  color: var(--text-primary);
  word-break: break-all;
}

.tm-format-badge {
  font-size: var(--text-xs);
  padding: 0.125rem 0.5rem;
  border-radius: var(--radius-sm);
  font-family: var(--font-mono);
  font-weight: 500;
}

.format-md {
  background: rgba(59, 130, 246, 0.15);
  color: var(--color-primary);
}

.format-docx {
  background: rgba(6, 182, 212, 0.15);
  color: var(--color-accent);
}

.format-pdf {
  background: rgba(239, 68, 68, 0.15);
  color: var(--color-danger);
}

.format-default {
  background: var(--bg-elevated);
  color: var(--text-secondary);
}

.tm-status-badge {
  font-size: var(--text-xs);
  padding: 0.125rem 0.5rem;
  border-radius: var(--radius-sm);
  font-weight: 500;
}

.tm-status--parsed {
  background: rgba(16, 185, 129, 0.15);
  color: var(--color-success);
}

.tm-status--pending {
  background: rgba(245, 158, 11, 0.15);
  color: var(--color-warning);
}

.tm-active-badge {
  font-size: var(--text-xs);
  padding: 0.125rem 0.5rem;
  border-radius: var(--radius-sm);
  background: rgba(16, 185, 129, 0.15);
  color: var(--color-success);
  font-weight: 500;
}

.tm-item-meta {
  font-size: var(--text-xs);
  color: var(--text-muted);
  font-family: var(--font-mono);
}

.tm-item-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-shrink: 0;
}

.tm-action-btn {
  padding: 0.375rem 0.75rem;
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  font-family: var(--font-body);
  cursor: pointer;
  border: 1px solid transparent;
  transition: all var(--duration-fast) ease;
  background: transparent;
}

.tm-action--activate {
  color: var(--color-success);
  border-color: rgba(16, 185, 129, 0.3);
}

.tm-action--activate:hover {
  background: rgba(16, 185, 129, 0.1);
}

.tm-action--view {
  color: var(--color-primary);
  border-color: rgba(59, 130, 246, 0.3);
}

.tm-action--view:hover {
  background: rgba(59, 130, 246, 0.1);
}

.tm-action--delete {
  color: var(--color-danger);
  border-color: rgba(239, 68, 68, 0.3);
}

.tm-action--delete:hover {
  background: rgba(239, 68, 68, 0.1);
}

.tm-preview-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 2rem;
}

.tm-preview-panel {
  background: var(--bg-panel);
  border: 1px solid var(--border-medium);
  border-radius: var(--radius-lg);
  width: 100%;
  max-width: 700px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.tm-preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--border-subtle);
}

.tm-preview-title {
  margin: 0;
  font-family: var(--font-display);
  font-size: var(--text-md);
  font-weight: 600;
  color: var(--text-primary);
}

.tm-preview-close {
  background: none;
  border: none;
  color: var(--text-secondary);
  font-size: 1.5rem;
  line-height: 1;
  cursor: pointer;
  padding: 0;
  width: 2rem;
  height: 2rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  transition: all var(--duration-fast) ease;
}

.tm-preview-close:hover {
  background: var(--bg-elevated);
  color: var(--text-primary);
}

.tm-preview-body {
  flex: 1;
  overflow: auto;
  padding: 1.25rem;
}

.tm-preview-loading {
  text-align: center;
  color: var(--text-muted);
  padding: 2rem;
}

.tm-preview-content {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  line-height: 1.6;
  color: var(--text-secondary);
}
</style>
