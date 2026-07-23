<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { getSkills, deleteSkill, resetSkills, getDefaultSkill, setDefaultSkill } from '@/api/http'
import type { SkillInfo } from '@/api/http'

const skills = ref<SkillInfo[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const defaultSkill = ref<string>('comprehensive_diagnosis')

async function loadSkills() {
  loading.value = true
  error.value = null
  try {
    const [skillsData, defaultData] = await Promise.all([
      getSkills(),
      getDefaultSkill(),
    ])
    skills.value = skillsData.skills
    defaultSkill.value = defaultData.default_skill
  } catch (err) {
    error.value = (err as Error).message
  } finally {
    loading.value = false
  }
}

function onSkillSaved() {
  loadSkills()
}

async function handleActivate(name: string) {
  try {
    error.value = null
    await setDefaultSkill(name)
    defaultSkill.value = name
  } catch (err) {
    error.value = (err as Error).message
  }
}

async function handleDelete(skill: SkillInfo) {
  if (skill.is_default) {
    alert('默认技能不可删除')
    return
  }
  if (!confirm(`确定删除技能 "${skill.name}" 吗？`)) return
  try {
    error.value = null
    await deleteSkill(skill.name)
    if (defaultSkill.value === skill.name) defaultSkill.value = 'comprehensive_diagnosis'
    await loadSkills()
  } catch (err) {
    error.value = (err as Error).message
  }
}

async function handleReset() {
  try {
    error.value = null
    await resetSkills()
    defaultSkill.value = 'comprehensive_diagnosis'
  } catch (err) {
    error.value = (err as Error).message
  }
}

onMounted(() => {
  loadSkills()
  window.addEventListener('skill-saved', onSkillSaved)
})

onUnmounted(() => {
  window.removeEventListener('skill-saved', onSkillSaved)
})
</script>

<template>
  <section class="skill-panel">
    <header class="skill-header">
      <h3>技能管理</h3>
      <div class="skill-actions">
        <button type="button" class="icon-btn" @click="loadSkills" title="刷新">&#x21bb;</button>
        <button type="button" class="icon-btn" @click="handleReset" title="重置为默认">&#x21ba;</button>
      </div>
    </header>

    <ul v-if="skills.length > 0" class="skill-list">
      <li
        v-for="s in skills"
        :key="s.name"
        class="skill-item"
        :class="{ active: defaultSkill === s.name }"
      >
        <div class="skill-info">
          <div class="skill-name">
            {{ s.name }}
            <span class="source-tag" :class="{ 'source-default': s.is_default }">{{ s.source }}</span>
          </div>
          <div class="skill-desc">{{ s.description || '无描述' }}</div>
        </div>
        <div class="skill-actions">
          <button
            type="button"
            class="activate-btn"
            :class="{ activated: defaultSkill === s.name }"
            @click="handleActivate(s.name)"
          >
            {{ defaultSkill === s.name ? '已激活' : '激活' }}
          </button>
          <button
            v-if="!s.is_default"
            type="button"
            class="delete-btn"
            @click="handleDelete(s)"
            title="删除"
          >&times;</button>
        </div>
      </li>
    </ul>

    <div v-else-if="loading" class="skill-empty">加载中...</div>
    <div v-else-if="error" class="skill-error">{{ error }}</div>
    <div v-else class="skill-empty">
      暂无技能
      <p class="hint">完成诊断后可保存为新技能</p>
    </div>
  </section>
</template>

<style scoped>
.skill-panel {
  width: 280px;
  min-width: 280px;
  background: var(--bg-panel);
  border-left: 1px solid var(--border-subtle);
  display: flex;
  flex-direction: column;
}

.skill-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--border-subtle);
}

.skill-header h3 {
  margin: 0;
  font-size: var(--text-md);
  font-weight: 600;
  color: var(--text-primary);
}

.skill-actions {
  display: flex;
  gap: 0.25rem;
}

.icon-btn {
  background: transparent;
  border: none;
  color: var(--text-secondary);
  font-size: 1.1rem;
  cursor: pointer;
  padding: 0.25rem;
  line-height: 1;
}

.icon-btn:hover {
  color: var(--text-primary);
}

.skill-list {
  list-style: none;
  margin: 0;
  padding: 0.75rem;
  overflow-y: auto;
  flex: 1;
}

.skill-item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.75rem;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  margin-bottom: 0.5rem;
  transition: border-color 0.15s;
}

.skill-item.active {
  border-color: var(--color-success);
  background: rgba(16, 185, 129, 0.03);
}

.skill-name {
  font-weight: 500;
  font-size: var(--text-sm);
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.source-tag {
  font-size: var(--text-xs);
  font-weight: 600;
  padding: 0.1rem 0.375rem;
  border-radius: var(--radius-sm);
  background: rgba(59, 130, 246, 0.12);
  color: var(--color-primary);
}

.source-tag.source-default {
  background: rgba(100, 116, 139, 0.12);
  color: var(--text-muted);
}

.skill-desc {
  font-size: var(--text-sm);
  color: var(--text-muted);
  margin-top: 0.25rem;
  line-height: 1.4;
}

.activate-btn {
  flex-shrink: 0;
  background: var(--bg-elevated);
  color: var(--text-secondary);
  border: none;
  border-radius: var(--radius-sm);
  padding: 0.375rem 0.625rem;
  font-size: var(--text-sm);
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
}

.activate-btn:hover {
  background: var(--bg-input);
}

.activate-btn.activated {
  background: rgba(16, 185, 129, 0.12);
  color: var(--color-success);
}

.delete-btn {
  flex-shrink: 0;
  background: transparent;
  border: none;
  color: var(--text-secondary);
  font-size: 1rem;
  cursor: pointer;
  padding: 0.25rem;
  line-height: 1;
}

.delete-btn:hover {
  color: var(--color-danger);
}

.skill-empty,
.skill-error {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 2rem;
  font-size: var(--text-sm);
  color: var(--text-secondary);
  text-align: center;
}

.skill-error {
  color: var(--color-danger);
}

.hint {
  font-size: var(--text-sm);
  color: var(--text-muted);
  margin-top: 0.5rem;
}
</style>
