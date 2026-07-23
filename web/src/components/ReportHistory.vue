<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getReports } from '@/api/http'
import { renderMarkdown } from '@/utils/markdown'
import { formatTime } from '@/utils/time'
import type { ReportItem } from '@/api/http'

const reports = ref<ReportItem[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const viewingReport = ref<ReportItem | null>(null)

async function loadReports() {
  loading.value = true
  error.value = null
  try {
    const data = await getReports()
    reports.value = data.reports
  } catch (err) {
    error.value = (err as Error).message
  } finally {
    loading.value = false
  }
}

function handleView(report: ReportItem) {
  viewingReport.value = report
}

function handleClose() {
  viewingReport.value = null
}

function formatDate(iso: string): string {
  return formatTime(iso) || '-'
}

function confidenceClass(c: number): string {
  if (c >= 0.7) return 'confidence-high'
  if (c >= 0.4) return 'confidence-medium'
  return 'confidence-low'
}

onMounted(() => {
  loadReports()
})
</script>

<template>
  <section class="report-history">
    <header class="history-header">
      <h2>诊断报告历史</h2>
      <button class="refresh-btn" @click="loadReports" title="刷新">
        &#x21bb;
      </button>
    </header>

    <div v-if="loading" class="history-empty">加载中...</div>
    <div v-else-if="error" class="history-error">{{ error }}</div>
    <div v-else-if="reports.length === 0" class="history-empty">
      暂无诊断报告
    </div>

    <table v-else class="history-table">
      <thead>
        <tr>
          <th>线路名称</th>
          <th>故障类型</th>
          <th>置信度</th>
          <th>故障时间</th>
          <th>诊断时间</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in reports" :key="r.session_id">
          <td>{{ r.line_name }}</td>
          <td>{{ r.fault_type }}</td>
          <td>
            <span class="confidence-badge" :class="confidenceClass(r.confidence)">
              {{ Math.round(r.confidence * 100) }}%
            </span>
          </td>
          <td>{{ formatDate(r.fault_time) }}</td>
          <td>{{ formatDate(r.created_at) }}</td>
          <td>
            <button class="view-btn" @click="handleView(r)">查看报告</button>
          </td>
        </tr>
      </tbody>
    </table>

    <!-- Report detail modal -->
    <div v-if="viewingReport" class="report-overlay" @click.self="handleClose">
      <div class="report-detail">
        <header class="detail-header">
          <h3>{{ viewingReport.line_name }} - 诊断报告</h3>
          <button class="close-btn" @click="handleClose">&times;</button>
        </header>
        <div class="detail-body markdown-body" v-html="renderMarkdown(viewingReport.report)"></div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.report-history {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--bg-base);
  padding: 1.5rem 2rem;
  overflow-y: auto;
  color: var(--text-primary);
}

.history-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1.5rem;
}

.history-header h2 {
  margin: 0;
  font-size: var(--text-lg);
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
}

.refresh-btn:hover {
  color: var(--text-primary);
}

.history-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--text-sm);
  background: var(--bg-panel);
  border-radius: var(--radius-lg);
  overflow: hidden;
  border: 1px solid var(--border-subtle);
}

.history-table th {
  text-align: left;
  padding: 0.75rem 1rem;
  font-weight: 600;
  color: var(--text-secondary);
  border-bottom: 1px solid var(--border-medium);
  text-transform: uppercase;
  font-size: var(--text-xs);
  letter-spacing: 0.05em;
  background: var(--bg-panel);
}

.history-table td {
  padding: 0.875rem 1rem;
  border-bottom: 1px solid var(--border-subtle);
  color: var(--text-primary);
}

.history-table tr:hover td {
  background: rgba(148, 163, 184, 0.04);
}

.confidence-badge {
  display: inline-block;
  padding: 0.125rem 0.5rem;
  border-radius: var(--radius-sm);
  font-size: var(--text-xs);
  font-weight: 500;
}

.confidence-high {
  background: rgba(16, 185, 129, 0.15);
  color: var(--color-success);
}

.confidence-medium {
  background: rgba(245, 158, 11, 0.15);
  color: var(--color-warning);
}

.confidence-low {
  background: rgba(239, 68, 68, 0.15);
  color: var(--color-danger);
}

.view-btn {
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: var(--radius-md);
  padding: 0.375rem 0.75rem;
  font-size: var(--text-xs);
  cursor: pointer;
  transition: opacity var(--duration-fast);
}

.view-btn:hover {
  opacity: 0.9;
}

.history-empty,
.history-error {
  text-align: center;
  padding: 3rem;
  color: var(--text-muted);
}

.history-error {
  color: var(--color-danger);
}

.report-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  padding: 2rem;
}

.report-detail {
  background: var(--bg-panel);
  border-radius: var(--radius-lg);
  width: 100%;
  max-width: 900px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--border-subtle);
}

.detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid var(--border-subtle);
}

.detail-header h3 {
  margin: 0;
  font-size: var(--text-md);
  font-weight: 600;
  color: var(--text-primary);
}

.close-btn {
  background: transparent;
  border: none;
  font-size: 1.5rem;
  color: var(--text-secondary);
  cursor: pointer;
}

.close-btn:hover {
  color: var(--text-primary);
}

.detail-body {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem;
  font-size: var(--text-sm);
  line-height: 1.7;
  color: var(--text-primary);
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
